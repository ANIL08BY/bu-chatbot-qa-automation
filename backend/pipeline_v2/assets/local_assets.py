"""
raw_local_documents Asset — local_sources/ dizinindeki dosyaları okur.

Desteklenen formatlar: .txt, .md, .pdf

Her dosyanın adı veya ilk satırı title olarak kullanılır.
Kategori, dosya adından veya metadata.json'dan belirlenir.

Kullanım:
    local_sources/
        akademik-takvim-ek.txt       → Düz metin
        burs-bilgileri.md            → Markdown
        ogrenci-el-kitabi.pdf        → PDF (pdfplumber ile parse)
        metadata.json                → Opsiyonel kategori eşleştirmesi
"""

import json
import logging
import os

from dagster import AssetExecutionContext, asset

from ..config_v2 import slugify

logger = logging.getLogger(__name__)

_LOCAL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "local_sources",
)

_SUPPORTED_EXT = {".txt", ".md", ".pdf"}


def _load_metadata(directory: str) -> dict[str, dict]:
    """
    metadata.json opsiyonel dosyası:
    {
        "akademik-takvim-ek.txt": {"category": "lisans akademik takvim"},
        "burs-bilgileri.md": {"category": "burs olanakları"}
    }
    """
    meta_path = os.path.join(directory, "metadata.json")
    if not os.path.exists(meta_path):
        return {}
    try:
        with open(meta_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("metadata.json okunamadı: %s", exc)
        return {}


def _read_text_file(path: str) -> str:
    """txt/md dosyasını oku."""
    with open(path, encoding="utf-8") as f:
        return f.read()


def _read_pdf_file(path: str) -> str:
    """PDF dosyasını pdfplumber ile oku."""
    try:
        import pdfplumber
        texts = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    texts.append(text)
        return "\n\n".join(texts)
    except Exception as exc:
        logger.warning("PDF okunamadı (%s): %s", path, exc)
        return ""


def _extract_title(filename: str, body: str) -> str:
    """Dosya adından veya ilk satırdan title çıkar."""
    name = os.path.splitext(filename)[0].replace("-", " ").replace("_", " ")
    # Markdown başlık varsa onu kullan
    for line in body.splitlines()[:5]:
        line = line.strip()
        if line.startswith("# "):
            return line.lstrip("# ").strip()
    return name.title()


@asset(
    name="raw_local_documents",
    group_name="ingestion",
    description="local_sources/ dizinindeki txt/md/pdf dosyalarını okur",
    compute_kind="python",
)
def raw_local_documents(
    context: AssetExecutionContext,
) -> list[dict]:
    """
    local_sources/ dizinindeki dosyaları tarar.
    Çıktı: list[dict] — raw_web_pages / raw_pdf_documents ile aynı format.
    """
    if not os.path.isdir(_LOCAL_DIR):
        context.log.info("local_sources/ dizini bulunamadı, atlanıyor.")
        return []

    metadata = _load_metadata(_LOCAL_DIR)
    docs: list[dict] = []

    for filename in sorted(os.listdir(_LOCAL_DIR)):
        ext = os.path.splitext(filename)[1].lower()
        if ext not in _SUPPORTED_EXT:
            continue

        filepath = os.path.join(_LOCAL_DIR, filename)
        context.log.info("Okunuyor: %s", filename)

        # İçerik oku
        if ext == ".pdf":
            body = _read_pdf_file(filepath)
        else:
            body = _read_text_file(filepath)

        if not body.strip():
            context.log.warning("Boş dosya atlandı: %s", filename)
            continue

        # Metadata
        file_meta = metadata.get(filename, {})
        raw_category = file_meta.get("category", "genel")
        category_slug = slugify(raw_category)
        title = _extract_title(filename, body)

        import hashlib
        content_hash = hashlib.sha256(body.encode()).hexdigest()

        docs.append({
            "url": f"local://{filename}",
            "source_url": f"local://{filename}",
            "title": title,
            "markdown_body": body,
            "content_hash": content_hash,
            "fmt": ext.lstrip("."),
            "category": raw_category,
            "doc_category": category_slug,
        })

    context.log.info("local_sources: %d dosya okundu", len(docs))
    context.add_output_metadata({"file_count": len(docs)})
    return docs
