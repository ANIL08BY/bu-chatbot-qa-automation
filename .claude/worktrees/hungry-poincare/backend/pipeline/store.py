"""
Vektör depolama: ChromaDB + BM25 pickle.

Atomic yazma:
  1. vector_db_tmp/ dizinine yaz
  2. vector_db/ → vector_db_bak/ rename
  3. vector_db_tmp/ → vector_db/ rename
  4. vector_db_bak/ sil

Bu yaklaşım, yazma sırasında hata olursa mevcut DB'yi korur.
Windows'ta çalışan uvicorn varsa rename başarısız olabilir; hata mesajı verilir.
"""
from __future__ import annotations

import math
import os
import pickle
import shutil

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

from .config import PipelineConfig


class VectorStore:
    def __init__(self, cfg: PipelineConfig) -> None:
        self.cfg = cfg

    def build(self, chunks: list[Document]) -> None:
        """Chunk listesinden ChromaDB + BM25 inşa et (atomic)."""
        db_path  = self.cfg.vector_db_path
        tmp_path = db_path + "_tmp"
        bak_path = db_path + "_bak"

        # Önceki yarım kalmış tmp temizle
        if os.path.exists(tmp_path):
            shutil.rmtree(tmp_path)

        # ── Embedding modeli ──────────────────────────────────────────────
        print(f"  Embedding modeli yükleniyor: {self.cfg.embedding_model}")
        embeddings = HuggingFaceEmbeddings(
            model_name=self.cfg.embedding_model,
            encode_kwargs={"batch_size": self.cfg.embed_batch_size},
        )

        # ── ChromaDB batch insert ─────────────────────────────────────────
        n_batches = math.ceil(len(chunks) / self.cfg.chroma_batch_size)
        print(f"  {len(chunks)} chunk → {n_batches} batch halinde ChromaDB yazılıyor...")

        vectorstore = None
        for i in range(0, len(chunks), self.cfg.chroma_batch_size):
            batch = chunks[i : i + self.cfg.chroma_batch_size]
            b_num = i // self.cfg.chroma_batch_size + 1
            print(f"    [{b_num}/{n_batches}] {len(batch)} chunk")

            if vectorstore is None:
                vectorstore = Chroma.from_documents(
                    documents=batch,
                    embedding=embeddings,
                    persist_directory=tmp_path,
                )
            else:
                vectorstore.add_documents(batch)

        if vectorstore is None:
            raise RuntimeError("Hiç chunk yazılamadı — chunks listesi boş.")

        # ── BM25 pickle ───────────────────────────────────────────────────
        print("  BM25 indeksi pickle'a kaydediliyor...")
        chunk_count = len(chunks)
        with open(os.path.join(tmp_path, "chunks.pkl"), "wb") as f:
            pickle.dump(chunks, f)

        # ── ChromaDB bağlantısını kapat (Windows dosya kilidi) ────────────
        # os.rename() Windows'ta açık SQLite handle varken PermissionError verir.
        # Langchain-Chroma'nın altındaki chromadb sistemini durdurup GC'yi
        # çalıştırarak tüm dosya tanıtıcılarını serbest bırakıyoruz.
        try:
            client = getattr(vectorstore, "_client", None)
            system = getattr(client, "_system", None)
            if system and hasattr(system, "stop"):
                system.stop()
        except Exception:
            pass
        del vectorstore
        import gc, time
        gc.collect()
        time.sleep(0.3)   # Windows'un handle listesini güncellemesi için

        # ── Atomic swap ───────────────────────────────────────────────────
        if os.path.exists(bak_path):
            shutil.rmtree(bak_path, ignore_errors=True)

        try:
            if os.path.exists(db_path):
                os.rename(db_path, bak_path)
            os.rename(tmp_path, db_path)
        except PermissionError:
            # Son çare: rename yerine kopyala-sil
            print("  ⚠  rename başarısız, kopyalama yöntemi deneniyor...")
            shutil.copytree(tmp_path, db_path)
            shutil.rmtree(tmp_path, ignore_errors=True)

        if os.path.exists(bak_path):
            shutil.rmtree(bak_path, ignore_errors=True)

        print(
            f"\n  ✓ Vector DB hazır\n"
            f"    Dizin  : {db_path}\n"
            f"    Chunk  : {chunk_count}\n"
        )
