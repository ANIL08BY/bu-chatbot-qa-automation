"""
Apply Preview — Manuel düzenlenmiş .md dosyalarını pipeline'a aktar.

Akış:
  ingestion_preview/**/*.md  (status: approved)
      → hash karşılaştırma (is_changed tespiti)
      → temizleme (DocumentCleanerV2)
      → chunking (SemanticChunker)
      → embedding + Qdrant upsert

Kullanım:
    python apply_preview.py [SEÇENEKLER]

Seçenekler:
    --preview DIR     ingestion_preview dizini  (varsayılan: ./ingestion_preview)
    --dry-run         Qdrant'a yazma; sadece kaç belge işleneceğini göster
    --force           Hash eşleşse bile yeniden işle (is_changed=True zorla)
    --env PATH        .env dosyası              (varsayılan: ./.env)

.md Dosya Formatı (YAML frontmatter):
    ---
    url: "https://..."
    title: "..."
    category: "..."
    doc_category: "..."
    fmt: "html"
    status: approved     ← sadece bu dosyalar işlenir
    ---

    (markdown içerik)
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Proje kökünü Python path'ine ekle (backend.* importları için)
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).parent
sys.path.insert(0, str(_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("apply_preview")

# ---------------------------------------------------------------------------
# Frontmatter ayrıştırıcı
# ---------------------------------------------------------------------------

def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """
    YAML frontmatter (--- ... ---) ile gövdeyi ayır.

    Returns:
        (meta_dict, body_str)
    """
    meta: dict = {}
    body = text

    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
    if not m:
        return meta, body

    fm_block = m.group(1)
    body = m.group(2)

    for line in fm_block.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, val = line.partition(":")
        val = val.strip().strip('"')
        # int dönüşümü
        try:
            meta[key.strip()] = int(val)
        except ValueError:
            meta[key.strip()] = val

    return meta, body


def load_approved_docs(preview_dir: Path) -> list[dict]:
    """
    ingestion_preview/**/*.md dosyalarını tara.
    Sadece status: approved olanları döndür.

    Returns:
        list[dict] — RawDocumentV2 formatında belgeler
    """
    docs: list[dict] = []
    skipped_pending = 0
    skipped_rejected = 0
    errors = 0

    md_files = sorted(preview_dir.rglob("*.md"))

    for fpath in md_files:
        try:
            raw = fpath.read_text(encoding="utf-8")
        except Exception as exc:
            logger.warning("Dosya okunamadı [%s]: %s", fpath, exc)
            errors += 1
            continue

        meta, body = _parse_frontmatter(raw)
        status = meta.get("status", "pending")

        if status == "rejected":
            skipped_rejected += 1
            continue
        if status != "approved":
            skipped_pending += 1
            continue

        url = meta.get("url", "")
        if not url:
            logger.warning("URL eksik, atlandı: %s", fpath)
            continue

        markdown = body.strip()
        content_hash = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
        now_iso = datetime.now(timezone.utc).isoformat()

        docs.append({
            "url": url,
            "title": meta.get("title", ""),
            "markdown_body": markdown,
            "fmt": meta.get("fmt", "html"),
            "category": meta.get("category", "genel"),
            "source_url": url,
            "doc_category": meta.get("doc_category", "genel"),
            "last_updated": now_iso,
            "is_active": True,
            "access_level": "public",
            "content_hash": content_hash,
            "crawled_at": meta.get("crawled_at", now_iso),
            "is_changed": True,      # hash adımı üzerine yazabilir
            "_preview_file": str(fpath),
        })

    logger.info(
        "Preview taraması: %d onaylı, %d beklemede, %d reddedildi, %d hata",
        len(docs), skipped_pending, skipped_rejected, errors,
    )
    return docs


# ---------------------------------------------------------------------------
# Pipeline adımları
# ---------------------------------------------------------------------------

def step_hash(docs: list[dict], force: bool) -> list[dict]:
    """Hash karşılaştırması — değişmeyen belgeler is_changed=False olur."""
    from backend.pipeline_v2.config_v2 import BELEK_CONFIG_V2
    from backend.pipeline_v2.hash_store import filter_changed, load_registry, save_registry

    cfg = BELEK_CONFIG_V2
    registry = load_registry(cfg.hash_registry_path)
    logger.info("Hash kaydı yüklendi: %d giriş", len(registry))

    annotated, updated_registry = filter_changed(docs, registry)

    if force:
        annotated = [{**d, "is_changed": True} for d in annotated]
        logger.info("--force: tüm belgeler is_changed=True olarak işaretlendi")

    changed = sum(1 for d in annotated if d.get("is_changed"))
    unchanged = len(annotated) - changed
    logger.info("Değişen: %d, Değişmeyen: %d (atlanacak)", changed, unchanged)

    save_registry(updated_registry, cfg.hash_registry_path)
    logger.info("Hash kaydı güncellendi.")

    return [d for d in annotated if d.get("is_changed")]


def step_clean(docs: list[dict]) -> list[dict]:
    """Boilerplate temizleme ve minimum içerik filtresi."""
    from backend.pipeline_v2.cleaner import DocumentCleanerV2
    from backend.pipeline_v2.config_v2 import BELEK_CONFIG_V2

    cfg = BELEK_CONFIG_V2
    cleaner = DocumentCleanerV2(min_content_chars=cfg.min_content_chars)

    cleaned = []
    skipped = 0
    for doc in docs:
        body = cleaner.clean(doc.get("markdown_body", ""))
        if not cleaner.is_valid(body):
            logger.debug("Minimum içerik eşiği geçilemedi, atlandı: %s", doc.get("url"))
            skipped += 1
            continue
        cleaned.append({**doc, "markdown_body": body})

    logger.info("Temizleme: %d belge (%d atlandı)", len(cleaned), skipped)
    return cleaned


def step_chunk(docs: list[dict]) -> list[dict]:
    """Semantik chunking."""
    from backend.pipeline_v2.chunker import SemanticChunker
    from backend.pipeline_v2.config_v2 import BELEK_CONFIG_V2

    cfg = BELEK_CONFIG_V2
    chunker = SemanticChunker(
        chunk_size=cfg.chunk_size,
        chunk_overlap=cfg.chunk_overlap,
    )

    all_chunks: list[dict] = []
    short_docs = 0
    for doc in docs:
        chunks = chunker.chunk(doc)
        if not chunks:
            short_docs += 1
            continue
        for ch in chunks:
            all_chunks.append(ch.to_payload())

    logger.info(
        "Chunking: %d chunk (%d belgeden, %d belge atlandı)",
        len(all_chunks), len(docs) - short_docs, short_docs,
    )
    return all_chunks


def step_upsert(chunks: list[dict]) -> dict:
    """Embedding ve Qdrant upsert."""
    from backend.pipeline_v2.config_v2 import BELEK_CONFIG_V2
    from backend.pipeline_v2.resources.embedding_resource import EmbeddingResource
    from backend.pipeline_v2.resources.qdrant_resource import QdrantResource
    from backend.pipeline_v2.schemas.qdrant_schema import (
        DENSE_VECTOR_NAME,
        create_collection_if_not_exists,
    )
    from qdrant_client.models import PointStruct

    cfg = BELEK_CONFIG_V2
    _UUID_NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

    # Qdrant bağlantısı
    qdrant = QdrantResource(
        host=os.environ.get("QDRANT_HOST", cfg.qdrant_host),
        port=int(os.environ.get("QDRANT_PORT", str(cfg.qdrant_port))),
        path=os.environ.get("QDRANT_PATH", ""),
    )
    client = qdrant.get_client()
    create_collection_if_not_exists(client, cfg.qdrant_collection)

    # Embedding modeli
    embedding = EmbeddingResource(
        model_name=cfg.embedding_model,
        batch_size=cfg.embed_batch_size,
        device="cpu",
    )
    logger.info("Embedding modeli yükleniyor...")

    upserted = 0
    failed_batches = 0
    _BATCH = 100

    for i in range(0, len(chunks), _BATCH):
        batch = chunks[i: i + _BATCH]
        texts = [ch["text"] for ch in batch]

        try:
            dense_vectors = embedding.encode(texts)
        except Exception as exc:
            logger.error("Embedding hatası (batch %d-%d): %s", i, i + len(batch), exc)
            failed_batches += 1
            continue

        points: list[PointStruct] = []
        for chunk_dict, dvec in zip(batch, dense_vectors):
            point_id = str(uuid.uuid5(_UUID_NS, f"{chunk_dict['url']}:{chunk_dict['chunk_idx']}"))
            points.append(PointStruct(
                id=point_id,
                vector={DENSE_VECTOR_NAME: dvec},
                payload=chunk_dict,
            ))

        try:
            client.upsert(
                collection_name=cfg.qdrant_collection,
                points=points,
                wait=True,
            )
            upserted += len(points)
            logger.info("Upsert: %d / %d chunk", upserted, len(chunks))
        except Exception as exc:
            logger.error("Upsert hatası (batch %d-%d): %s", i, i + len(batch), exc)
            failed_batches += 1

    return {"upserted": upserted, "failed_batches": failed_batches}


# ---------------------------------------------------------------------------
# .md Dosyasını güncelle — status: approved → processed
# ---------------------------------------------------------------------------

def mark_as_processed(docs: list[dict]) -> None:
    """
    Qdrant'a yazılan belgelerin .md dosyasındaki status'unu
    'processed' olarak güncelle (yeniden işlenmesini engeller).
    """
    for doc in docs:
        fpath_str = doc.get("_preview_file")
        if not fpath_str:
            continue
        fpath = Path(fpath_str)
        if not fpath.exists():
            continue
        try:
            raw = fpath.read_text(encoding="utf-8")
            updated = re.sub(
                r"^status:\s*approved\s*$",
                "status: processed",
                raw,
                flags=re.MULTILINE,
            )
            if updated != raw:
                fpath.write_text(updated, encoding="utf-8")
        except Exception as exc:
            logger.warning("Dosya güncellenemedi [%s]: %s", fpath, exc)


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Onaylı preview dosyalarını Qdrant'a aktar",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--preview", default="ingestion_preview", metavar="DIR",
                        help="ingestion_preview dizini (varsayılan: ./ingestion_preview)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Qdrant'a yazma; sadece işlenecek belge sayısını göster")
    parser.add_argument("--force", action="store_true",
                        help="Hash eşleşse bile yeniden işle")
    parser.add_argument("--env", default=".env", metavar="PATH",
                        help=".env dosyası (varsayılan: ./.env)")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    # .env yükle
    try:
        from dotenv import load_dotenv
        load_dotenv(args.env, override=False)
    except ImportError:
        pass

    preview_dir = Path(args.preview)
    if not preview_dir.exists():
        logger.error("ingestion_preview dizini bulunamadı: %s", preview_dir)
        sys.exit(1)

    # ── 1. Onaylı dosyaları yükle ──────────────────────────────────────────
    logger.info("=== ADIM 1: Preview dosyaları yükleniyor ===")
    docs = load_approved_docs(preview_dir)

    if not docs:
        logger.info("İşlenecek onaylı (status: approved) belge bulunamadı.")
        logger.info("Belgelerinizi gözden geçirip status: approved yapın.")
        sys.exit(0)

    logger.info("Toplam onaylı belge: %d", len(docs))

    if args.dry_run:
        logger.info("--dry-run: Qdrant'a yazılmadı. Çıkılıyor.")
        for d in docs:
            logger.info("  [%s] %s (%d karakter)", d["fmt"].upper(), d["url"], len(d["markdown_body"]))
        sys.exit(0)

    # ── 2. Hash karşılaştırma ──────────────────────────────────────────────
    logger.info("=== ADIM 2: Hash karşılaştırma ===")
    changed_docs = step_hash(docs, force=args.force)

    if not changed_docs:
        logger.info("Tüm onaylı belgeler zaten güncel. Qdrant'a yazılacak yeni içerik yok.")
        logger.info("Yeniden işlemek için --force kullanın.")
        sys.exit(0)

    # ── 3. Temizleme ───────────────────────────────────────────────────────
    logger.info("=== ADIM 3: İçerik temizleme ===")
    cleaned = step_clean(changed_docs)

    if not cleaned:
        logger.warning("Temizleme sonrası işlenecek belge kalmadı.")
        sys.exit(0)

    # ── 4. Chunking ────────────────────────────────────────────────────────
    logger.info("=== ADIM 4: Semantik chunking ===")
    chunks = step_chunk(cleaned)

    if not chunks:
        logger.warning("Chunk üretilemedi.")
        sys.exit(0)

    # ── 5. Embed + Upsert ──────────────────────────────────────────────────
    logger.info("=== ADIM 5: Embedding + Qdrant upsert ===")
    result = step_upsert(chunks)

    logger.info(
        "Tamamlandı: %d chunk upsert edildi (%d batch başarısız)",
        result["upserted"], result["failed_batches"],
    )

    # ── 6. İşlenen dosyaları işaretle ─────────────────────────────────────
    if result["upserted"] > 0:
        mark_as_processed(changed_docs)
        logger.info("İşlenen .md dosyaları 'status: processed' olarak güncellendi.")

    logger.info("=== TAMAMLANDI ===")


if __name__ == "__main__":
    main()
