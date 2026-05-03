"""
Pipeline CLI giriş noktası.

Kullanım:
    python -m backend.pipeline.run                # Tam pipeline (auto-detect mod)
    python -m backend.pipeline.run --resume       # Checkpoint'ten devam
    python -m backend.pipeline.run --fresh        # Cache + VectorDB sil, baştan başla
    python -m backend.pipeline.run --ingest-only  # Crawl atla, cache'den ingest et
    python -m backend.pipeline.run --local-only   # Sadece backend/data/ dosyaları
    python -m backend.pipeline.run --targeted     # Zorla targeted mod
    python -m backend.pipeline.run --bfs          # Zorla BFS mod

Crawler modu seçimi:
    ingestion_list.json varsa → TargetedCrawler (önerilen)
    Yoksa veya --bfs verilirse → WebCrawler (BFS)
"""
from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import sys

# Encoding fix (Windows)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from .chunk import DocumentChunker
from .clean import DataCleaner
from .config import BELEK_CONFIG, PipelineConfig, load_ingestion_list
from .crawler import WebCrawler, TargetedCrawler, clear_cache, load_documents
from .extract import DOCXExtractor, PDFExtractor, RawDocument, HTMLExtractor
from .store import VectorStore


# ---------------------------------------------------------------------------
# Yerel dosyaları yükle (backend/data/)
# ---------------------------------------------------------------------------

def load_local_files(data_dir: str) -> list[RawDocument]:
    """
    backend/data/ içindeki PDF, DOCX ve MD dosyalarını yükler.
    """
    if not os.path.isdir(data_dir):
        return []

    pdf_ext  = PDFExtractor()
    docx_ext = DOCXExtractor()
    docs: list[RawDocument] = []

    for fname in os.listdir(data_dir):
        fpath = os.path.join(data_dir, fname)
        if not os.path.isfile(fpath):
            continue

        low = fname.lower()
        try:
            with open(fpath, "rb") as f:
                raw = f.read()

            if low.endswith(".pdf"):
                doc = pdf_ext.extract(raw, f"local://{fname}")
            elif low.endswith(".docx"):
                doc = docx_ext.extract(raw, f"local://{fname}")
            elif low.endswith((".md", ".txt")):
                text = raw.decode("utf-8", errors="replace")
                doc  = RawDocument(
                    url=f"local://{fname}",
                    title=fname,
                    body=text,
                    fmt="md",
                    metadata={"source": "local"},
                )
            else:
                continue

            if doc and not doc.is_empty():
                docs.append(doc)
                print(f"  ✓ Yerel | {fname} | {len(doc.body):,} kar.")

        except Exception as exc:
            print(f"  ✗ Yerel dosya okunamadı: {fname} → {exc}")

    return docs


# ---------------------------------------------------------------------------
# Ana Pipeline
# ---------------------------------------------------------------------------

async def run_pipeline(cfg: PipelineConfig, args: argparse.Namespace) -> None:

    skip_crawl  = args.ingest_only or args.local_only
    local_only  = args.local_only
    resume      = getattr(args, "resume",   False)
    fresh       = getattr(args, "fresh",    False)
    force_tgt   = getattr(args, "targeted", False)
    force_bfs   = getattr(args, "bfs",      False)

    # ── Sıfırlama (--fresh) ───────────────────────────────────────────────
    if fresh:
        clear_cache(cfg.cache_dir)
        print("  🗑  Pipeline cache temizlendi.")
        if os.path.exists(cfg.vector_db_path):
            shutil.rmtree(cfg.vector_db_path, ignore_errors=True)
            print("  🗑  Vector DB temizlendi.")
        # _tmp kalıntısı da sil
        tmp_path = cfg.vector_db_path + "_tmp"
        if os.path.exists(tmp_path):
            shutil.rmtree(tmp_path, ignore_errors=True)

    # ── Crawler modu tespiti ──────────────────────────────────────────────
    sources = []
    if not force_bfs and cfg.ingestion_list_path:
        sources = load_ingestion_list(cfg.ingestion_list_path)

    use_targeted = (
        force_tgt
        or (not force_bfs and bool(sources))
        or cfg.crawl_mode == "targeted"
    )

    # ── Faz 1: Crawl ──────────────────────────────────────────────────────
    if not skip_crawl:
        has_state = os.path.exists(os.path.join(cfg.cache_dir, "state.json"))
        if resume and not has_state:
            print("  ⚠  Checkpoint bulunamadı, baştan crawl yapılıyor.")

        if use_targeted and sources:
            mode_label = "Targeted"
            print(f"\n[1/4] Crawl başlıyor → Targeted mod "
                  f"({len(sources)} kaynak, ingestion_list.json)")
            print("       Ctrl+C → checkpoint kaydedilir, --resume ile devam\n")
            crawler = TargetedCrawler(cfg, sources)
        else:
            mode_label = "BFS"
            mode = "devam ediliyor" if (resume and has_state) else "başlıyor"
            print(f"\n[1/4] Crawl {mode} → BFS mod ({cfg.seed_urls[0]})")
            print("       Ctrl+C → checkpoint kaydedilir, --resume ile devam\n")
            crawler = WebCrawler(cfg)

        await crawler.crawl(resume=resume or has_state)

    # ── Faz 2: Belge yükleme ──────────────────────────────────────────────
    print("\n[2/4] Belgeler yükleniyor...")
    docs: list[RawDocument] = []

    if not local_only:
        web_docs = load_documents(cfg.cache_dir)
        print(f"  Web crawl: {len(web_docs)} belge")
        docs.extend(web_docs)

    local_docs = load_local_files(cfg.local_data_dir)
    print(f"  Yerel    : {len(local_docs)} belge")
    docs.extend(local_docs)

    if not docs:
        print("\n  ⚠  Hiç belge bulunamadı. Crawl tamamlandı mı?")
        print("     Eğer crawl Ctrl+C ile duruyorsa: --resume ile devam et.")
        return

    print(f"  Toplam   : {len(docs)} belge")

    # ── Faz 3: Temizleme ──────────────────────────────────────────────────
    print("\n[3/4] Temizleme ve tekilleştirme...")
    cleaner = DataCleaner(cfg)
    clean_docs = cleaner.clean(docs)

    if not clean_docs:
        print("  ⚠  Temizleme sonrası belge kalmadı.")
        return

    # ── Faz 4: Chunk + Embed + Store ──────────────────────────────────────
    print("\n[4/4] Chunking + Embedding + VectorDB...")
    chunker = DocumentChunker(cfg)
    chunks  = chunker.chunk(clean_docs)

    if not chunks:
        print("  ⚠  Hiç chunk üretilemedi.")
        return

    store = VectorStore(cfg)
    store.build(chunks)

    print("\n" + "=" * 55)
    print("Pipeline tamamlandi.")
    print(f"  Belge   : {len(docs)} (ham) → {len(clean_docs)} (temiz)")
    print(f"  Chunk   : {len(chunks)}")
    print(f"  VectorDB: {cfg.vector_db_path}")
    print("=" * 55)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="BU Chatbot — Data Preparation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ornekler:
  python -m backend.pipeline.run                # Tam pipeline
  python -m backend.pipeline.run --resume       # Checkpoint'ten devam
  python -m backend.pipeline.run --fresh        # Sifirdan basla
  python -m backend.pipeline.run --ingest-only  # Sadece ingest (crawl atla)
  python -m backend.pipeline.run --local-only   # Sadece backend/data/
        """,
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--resume",      action="store_true", help="Checkpoint'ten devam et")
    mode.add_argument("--fresh",       action="store_true", help="Cache + VectorDB sil, sifirdan basla")
    mode.add_argument("--ingest-only", action="store_true", help="Crawl atla, cache'den ingest")
    mode.add_argument("--local-only",  action="store_true", help="Sadece backend/data/ dosyalari")

    crawler_mode = p.add_mutually_exclusive_group()
    crawler_mode.add_argument("--targeted", action="store_true", help="Zorla targeted mod (ingestion_list.json)")
    crawler_mode.add_argument("--bfs",      action="store_true", help="Zorla BFS mod (seed_urls)")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(run_pipeline(BELEK_CONFIG, args))
