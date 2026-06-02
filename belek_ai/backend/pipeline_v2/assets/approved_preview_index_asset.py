"""
approved_preview_index Asset — ingestion_preview/ klasöründeki approved .md dosyalarını
URL → içerik haritasına dönüştürür.

cleaned_documents bu haritayı kullanarak hangi belgenin taze crawl yerine
onaylı (elle düzenlenmiş) içeriğini kullanacağına karar verir.
"""
import logging
import re
from pathlib import Path
from typing import Any

from dagster import AssetExecutionContext, asset

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).parent.parent.parent.parent
_PREVIEW_DIR = _ROOT / "ingestion_preview"

# approved + processed → her ikisi de "onaylı içerik" sayılır
_APPROVED_STATUSES = {"approved", "processed"}


def _parse_md_file(path: Path) -> dict[str, Any] | None:
    """
    YAML frontmatter + markdown body içeren .md dosyasını parse eder.
    Döndürür: {"url", "markdown_body", "title", "fmt", "category",
               "doc_category", "status", "crawled_at"} veya None.
    """
    try:
        raw = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None

    # Frontmatter: ilk --- ile ikinci --- arasındaki blok
    if not raw.startswith("---"):
        return None

    end_idx = raw.find("---", 3)
    if end_idx == -1:
        return None

    fm_block = raw[3:end_idx]
    body = raw[end_idx + 3:].lstrip("\n")

    def _get(key: str) -> str:
        m = re.search(rf'^{key}:\s*"?([^"\n]+)"?', fm_block, re.MULTILINE)
        return m.group(1).strip() if m else ""

    status = _get("status")
    if status not in _APPROVED_STATUSES:
        return None

    url = _get("url")
    if not url:
        return None

    return {
        "url":          url,
        "markdown_body": body,
        "title":        _get("title"),
        "fmt":          _get("fmt") or "html",
        "category":     _get("category"),
        "doc_category": _get("doc_category"),
        "status":       status,
        "crawled_at":   _get("crawled_at"),
    }


@asset(
    name="approved_preview_index",
    group_name="dedup",
    description=(
        "ingestion_preview/ altındaki status:approved/processed .md dosyalarını "
        "URL → içerik haritasına dönüştürür. "
        "cleaned_documents bu haritayı kullanarak onaylı içeriği korur."
    ),
    compute_kind="python",
)
def approved_preview_index(context: AssetExecutionContext) -> dict[str, dict]:
    """
    Döndürür: {url: {markdown_body, title, fmt, category, doc_category, status}}
    """
    if not _PREVIEW_DIR.exists():
        context.log.info("ingestion_preview/ dizini bulunamadı — boş index döndürülüyor.")
        context.add_output_metadata({"approved_count": 0})
        return {}

    index: dict[str, dict] = {}

    for md_file in _PREVIEW_DIR.rglob("*.md"):
        parsed = _parse_md_file(md_file)
        if parsed is None:
            continue
        url = parsed["url"]
        index[url] = parsed
        context.log.debug("Approved preview yüklendi: %s → %s", url, md_file.name)

    context.log.info(
        "approved_preview_index hazır: %d onaylı dosya bulundu.", len(index)
    )
    context.add_output_metadata({"approved_count": len(index)})
    return index
