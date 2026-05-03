"""
raw_preview_dump Asset — Yeni kaynaklar için preview dosyası üretir.

- document_hashes çıktısından is_new=True olan belgeler yazılır.
- Mevcut preview dosyaları ezilmez (dosya varsa atlanır).

Config:
    clear_on_full_run (bool, default=False):
        True → status: approved OLMAYAN tüm .md dosyalarını siler, sonra yeniden yazar.
        full_pipeline_job tarafından otomatik True yapılır.
"""
import json
import logging
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dagster import AssetExecutionContext, Config, asset

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).parent.parent.parent.parent
_PREVIEW_DIR = _ROOT / "ingestion_preview"


# ---------------------------------------------------------------------------
# slugify
# ---------------------------------------------------------------------------

_TR_MAP = str.maketrans(
    "şğüöıçŞĞÜÖİÇ",
    "sguoicSGUOIC",
)


def _slugify(text: str) -> str:
    s = text.strip().lower().translate(_TR_MAP)
    s = unicodedata.normalize("NFKD", s)
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"[\s,/]+", "-", s.strip())
    s = re.sub(r"-{2,}", "-", s)
    return s.strip("-")


def _url_slug(url: str) -> str:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    raw = parsed.netloc + parsed.path
    return _slugify(raw)[:60]


# ---------------------------------------------------------------------------
# Full run: approved olmayanları temizle
# ---------------------------------------------------------------------------

def _read_status(md_path: Path) -> str:
    """Dosyanın frontmatter'ındaki status değerini döndür. Okunamazsa 'pending'."""
    try:
        first_bytes = md_path.read_text(encoding="utf-8", errors="ignore")[:500]
        m = re.search(r"^status:\s*(\S+)", first_bytes, re.MULTILINE)
        if m:
            return m.group(1).strip()
    except Exception:
        pass
    return "pending"


def _clear_non_approved_previews(context: AssetExecutionContext) -> tuple[int, int]:
    """
    ingestion_preview/ altındaki .md dosyalarını tara.
    status: approved olmayanları sil.

    Returns:
        (deleted_count, kept_count)
    """
    if not _PREVIEW_DIR.exists():
        return 0, 0

    deleted = 0
    kept = 0

    for md_file in _PREVIEW_DIR.rglob("*.md"):
        status = _read_status(md_file)
        if status == "approved":
            kept += 1
            context.log.debug("Korundu (approved): %s", md_file.name)
        else:
            try:
                md_file.unlink()
                deleted += 1
                context.log.debug("Silindi (%s): %s", status, md_file.name)
            except Exception as exc:
                context.log.warning("Silinemedi [%s]: %s", md_file.name, exc)

    # Boş kalan alt dizinleri temizle
    for d in sorted(_PREVIEW_DIR.rglob("*"), reverse=True):
        if d.is_dir() and d != _PREVIEW_DIR:
            try:
                d.rmdir()  # sadece boşsa silinir
            except OSError:
                pass

    context.log.info(
        "Preview temizlendi: %d silindi, %d approved dosya korundu.",
        deleted, kept,
    )
    return deleted, kept


# ---------------------------------------------------------------------------
# Dosya yazma yardımcıları
# ---------------------------------------------------------------------------

def _write_preview_file(
    path: Path,
    url: str,
    title: str,
    category: str,
    doc_category: str,
    fmt: str,
    markdown: str,
    crawled_at: str,
) -> None:
    """YAML frontmatter + markdown body. Atomik yazma (.tmp → rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    char_count = len(markdown)

    frontmatter = (
        "---\n"
        f'url: "{url}"\n'
        f'title: "{title}"\n'
        f'category: "{category}"\n'
        f'doc_category: "{doc_category}"\n'
        f'fmt: "{fmt}"\n'
        f'crawled_at: "{crawled_at}"\n'
        f"char_count: {char_count}\n"
        "status: pending\n"
        "---\n\n"
    )

    tmp = path.with_suffix(".tmp")
    tmp.write_text(frontmatter + markdown, encoding="utf-8")
    os.replace(tmp, path)


def _merge_manifest(new_entries: list[dict]) -> None:
    """manifest.json'u mevcut girdilerle birleştirerek güncelle."""
    manifest_path = _PREVIEW_DIR / "manifest.json"
    _PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

    existing: dict[str, dict] = {}
    if manifest_path.exists():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            for e in data.get("entries", []):
                existing[e.get("url", "")] = e
        except Exception:
            pass

    for e in new_entries:
        url = e.get("url", "")
        if url not in existing:
            existing[url] = e

    all_entries = list(existing.values())
    ok = sum(1 for e in all_entries if e.get("fetch_status") == "ok")

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pipeline": "dagster",
        "summary": {
            "total":        len(all_entries),
            "fetched_ok":   ok,
            "fetch_errors": len(all_entries) - ok,
            "pending":      sum(1 for e in all_entries if e.get("approval_status") == "pending"),
            "approved":     sum(1 for e in all_entries if e.get("approval_status") == "approved"),
        },
        "entries": all_entries,
    }

    tmp = manifest_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, manifest_path)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class PreviewConfig(Config):
    clear_on_full_run: bool = False


# ---------------------------------------------------------------------------
# Asset
# ---------------------------------------------------------------------------

@asset(
    name="raw_preview_dump",
    group_name="dedup",
    description=(
        "Yeni (is_new=True) belgeleri ingestion_preview/ dizinine yazar. "
        "clear_on_full_run=True ise önce approved olmayan dosyaları temizler (full run)."
    ),
    compute_kind="python",
)
def raw_preview_dump(
    context: AssetExecutionContext,
    config: PreviewConfig,
    document_hashes: dict[str, Any],
) -> dict:
    """
    Döndürür: {"written": int, "skipped_existing": int, "preview_dir": str}
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    all_docs: list[dict] = document_hashes.get("all_docs", [])

    # Full run: approved olmayan mevcut preview'ları temizle
    deleted_count = 0
    kept_approved = 0
    if config.clear_on_full_run:
        context.log.info("Full run: preview temizleme başlatılıyor...")
        deleted_count, kept_approved = _clear_non_approved_previews(context)

    # Sadece is_new=True belgeler için preview yaz
    new_docs = [d for d in all_docs if d.get("is_new", False)]

    context.log.info(
        "Preview: toplam %d belge, %d yeni (is_new=True), %d mevcut (atlanacak)",
        len(all_docs), len(new_docs), len(all_docs) - len(new_docs),
    )

    if not new_docs:
        context.log.info("Yeni belge yok — preview üretilmeyecek.")
        context.add_output_metadata({
            "written": 0,
            "skipped_existing": len(all_docs),
            "deleted_on_full_run": deleted_count,
            "kept_approved": kept_approved,
        })
        return {
            "written": 0,
            "skipped_existing": len(all_docs),
            "preview_dir": str(_PREVIEW_DIR),
        }

    written = 0
    errors = 0
    skipped_file_exists = 0
    entries: list[dict] = []

    for doc in new_docs:
        url: str = doc.get("url", "")
        title: str = doc.get("title", "")
        markdown: str = doc.get("markdown_body", "")
        category: str = doc.get("category", "genel")
        doc_category: str = doc.get("doc_category", _slugify(category))
        fmt: str = doc.get("fmt", "html")
        crawled_at: str = doc.get("crawled_at", now_iso)

        category_slug = _slugify(doc_category or category)
        url_slug = _url_slug(url) if url else "unknown"
        file_path = _PREVIEW_DIR / category_slug / (url_slug + ".md")

        # Dosya hâlâ varsa (approved olduğu için korundu) ezme
        if file_path.exists():
            skipped_file_exists += 1
            context.log.debug("Dosya mevcut (korunuyor): %s", file_path.name)
            continue

        fetch_status = "ok" if markdown.strip() else "empty"

        try:
            _write_preview_file(
                path=file_path,
                url=url,
                title=title,
                category=category,
                doc_category=doc_category,
                fmt=fmt,
                markdown=markdown,
                crawled_at=crawled_at,
            )
            written += 1
            context.log.info("Yeni preview: %s", file_path.name)
        except Exception as exc:
            errors += 1
            fetch_status = "error"
            context.log.warning("Dosya yazma hatası [%s]: %s", url, exc)

        try:
            rel = file_path.relative_to(Path.cwd())
        except ValueError:
            rel = file_path

        entries.append({
            "url": url,
            "title": title,
            "category": category,
            "doc_category": doc_category,
            "fmt": fmt,
            "file_path": str(rel).replace("\\", "/"),
            "char_count": len(markdown),
            "fetch_status": fetch_status,
            "approval_status": "pending",
            "crawled_at": crawled_at,
        })

    if entries:
        try:
            _merge_manifest(entries)
        except Exception as exc:
            context.log.warning("Manifest yazılamadı: %s", exc)

    context.log.info(
        "Preview tamamlandı: %d yeni yazıldı, %d dosya korundu (approved/mevcut), %d hata",
        written, skipped_file_exists, errors,
    )
    context.add_output_metadata({
        "new_previews_written":  written,
        "skipped_existing":      skipped_file_exists,
        "deleted_on_full_run":   deleted_count,
        "kept_approved":         kept_approved,
        "errors":                errors,
        "preview_dir":           str(_PREVIEW_DIR),
    })

    return {
        "written":          written,
        "skipped_existing": skipped_file_exists,
        "preview_dir":      str(_PREVIEW_DIR),
    }
