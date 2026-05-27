"""
raw_pdf_documents Asset — Docling ile PDF belgelerini ayrıştırır.

- ingestion_list.json'daki PDF URL'leri httpx ile indirilir.
- Docling DocumentConverter (TableFormer ACCURATE modu) → Hiyerarşik Markdown.
- Docling import yoksa pdfplumber fallback.
- ThreadPoolExecutor (CPU-bound): max 2 paralel PDF parse.
- Timeout: 90s per PDF.
- Hata → log + continue (pipeline durmaz).
"""

import asyncio
import concurrent.futures
import hashlib
import logging
import os
import sys
import tempfile
from datetime import datetime, timezone

import httpx
from dagster import AssetExecutionContext, Backoff, RetryPolicy, asset

from ..config_v2 import BELEK_CONFIG_V2, load_ingestion_list_v2

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PDF parse — Docling + fallback
# ---------------------------------------------------------------------------

def _parse_with_docling(pdf_bytes: bytes) -> str | None:
    """Docling TableFormer ile PDF → Markdown. Başarısız olursa None."""
    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption

        opts = PdfPipelineOptions()
        opts.do_table_structure = True
        opts.table_structure_options.mode = "ACCURATE"  # TableFormer

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=opts)
            }
        )

        tmp_dir = os.environ.get("TEMP", tempfile.gettempdir())
        with tempfile.NamedTemporaryFile(
            suffix=".pdf", delete=False, dir=tmp_dir
        ) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        try:
            result = converter.convert(tmp_path)
            md = result.document.export_to_markdown(
                strict_text=False,
                image_mode="placeholder",
            )
            return md.strip() or None
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    except ImportError:
        return _parse_with_pdfplumber(pdf_bytes)
    except Exception as exc:
        logger.warning("Docling parse hatası: %s", exc)
        return _parse_with_pdfplumber(pdf_bytes)


def _parse_with_pdfplumber(pdf_bytes: bytes) -> str | None:
    """pdfplumber fallback — tablo desteği sınırlı."""
    try:
        import io
        import pdfplumber

        pages: list[str] = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for i, page in enumerate(pdf.pages, 1):
                text = (page.extract_text() or "").strip()
                if text:
                    pages.append(f"## Sayfa {i}\n{text}")
        return "\n\n".join(pages) or None
    except Exception as exc:
        logger.error("pdfplumber fallback hatası: %s", exc)
        return None


def _title_from_url(url: str) -> str:
    import re
    name = url.rstrip("/").split("/")[-1]
    name = re.sub(r"\.(pdf|docx|html?)$", "", name, flags=re.I)
    name = re.sub(r"[_\-]", " ", name)
    return name.strip().title()


def _process_pdf(
    url: str,
    category: str,
    category_slug: str,
    pdf_bytes: bytes,
) -> dict | None:
    """Tek PDF'yi parse et → dict veya None."""
    md = _parse_with_docling(pdf_bytes)
    if not md:
        return None

    now_iso = datetime.now(timezone.utc).isoformat()
    content_hash = hashlib.sha256(md.encode("utf-8")).hexdigest()

    return {
        "url": url,
        "title": _title_from_url(url),
        "markdown_body": md,
        "fmt": "pdf",
        "category": category,
        "source_url": url,
        "doc_category": category_slug,
        "last_updated": now_iso,
        "is_active": True,
        "access_level": "public",
        "content_hash": content_hash,
        "crawled_at": now_iso,
        "is_changed": True,
    }


# ---------------------------------------------------------------------------
# Asset
# ---------------------------------------------------------------------------

@asset(
    name="raw_pdf_documents",
    group_name="ingestion",
    description="Docling + TableFormer ile PDF belgelerini hiyerarşik Markdown'a dönüştürür",
    retry_policy=RetryPolicy(max_retries=2, delay=60, backoff=Backoff.EXPONENTIAL),
    compute_kind="docling",
)
def raw_pdf_documents(context: AssetExecutionContext) -> list[dict]:
    cfg = BELEK_CONFIG_V2
    sources = load_ingestion_list_v2(cfg.ingestion_list_path)
    pdf_sources = [s for s in sources if s.is_pdf]

    context.log.info("PDF kaynak sayısı: %d", len(pdf_sources))
    if not pdf_sources:
        return []

    # ── PDF indirme (async) ──────────────────────────────────────────────────
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    max_bytes = cfg.max_pdf_size_mb * 1024 * 1024

    async def _download_all() -> list[tuple[str, str, str, bytes]]:
        sem = asyncio.Semaphore(3)
        async with httpx.AsyncClient(
            headers={"User-Agent": cfg.user_agent},
            follow_redirects=True,
            timeout=httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=5.0),
        ) as client:
            tasks = [
                _download_one(client, sem, s.url, s.category, s.category_slug)
                for s in pdf_sources
            ]
            return [
                r for r in await asyncio.gather(*tasks, return_exceptions=True)
                if not isinstance(r, Exception) and r is not None
            ]

    async def _download_one(
        client, sem, url, category, category_slug
    ) -> tuple | None:
        async with sem:
            for attempt in range(3):
                try:
                    # HEAD kontrolü
                    try:
                        head = await client.head(url, timeout=8)
                        cl = head.headers.get("content-length")
                        if cl and int(cl) > max_bytes:
                            context.log.warning(
                                "PDF çok büyük (%.1f MB): %s",
                                int(cl) / 1024 / 1024, url,
                            )
                            return None
                    except Exception:
                        pass

                    resp = await client.get(url)
                    resp.raise_for_status()
                    if len(resp.content) > max_bytes:
                        context.log.warning("PDF akışta boyut aşıldı: %s", url)
                        return None
                    return url, category, category_slug, resp.content

                except Exception as exc:
                    context.log.warning(
                        "İndirme hatası (deneme %d): %s → %s", attempt + 1, url, exc
                    )
                    if attempt < 2:
                        await asyncio.sleep(2 ** attempt)
        return None

    downloads = asyncio.run(_download_all())
    context.log.info("İndirilen PDF: %d / %d", len(downloads), len(pdf_sources))

    # ── Docling parse (thread pool) ──────────────────────────────────────────
    results: list[dict] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        future_map = {
            pool.submit(
                _process_pdf, url, category, category_slug, pdf_bytes
            ): url
            for url, category, category_slug, pdf_bytes in downloads
        }
        for future, url in future_map.items():
            try:
                doc = future.result(timeout=cfg.pdf_timeout_s + 5)
                if doc:
                    results.append(doc)
            except concurrent.futures.TimeoutError:
                context.log.warning("Docling timeout (%.0fs): %s", cfg.pdf_timeout_s, url)
            except Exception as exc:
                context.log.error("PDF parse hatası [%s]: %s", url, exc)

    context.log.info("Ayrıştırılan PDF: %d / %d", len(results), len(downloads))
    context.add_output_metadata({"pdf_parsed": len(results), "pdf_total": len(pdf_sources)})
    return results
