"""
cleaned_documents Asset — Metin normalleştirme ve kalite filtresi.

Öncelik kuralı:
  1. URL için ingestion_preview/'de status:approved veya status:processed bir
     dosya varsa → o dosyanın içeriği kullanılır (taze crawl görmezden gelinir).
  2. Approved preview yoksa → taze crawl içeriği temizlenerek işlenir.

Bu sayede elle düzenlenmiş onaylı içerik, full pipeline yeniden çalışsa bile
üzerine yazılmaz.
"""

import logging
from typing import Any

from dagster import AssetExecutionContext, asset

from ..cleaner import DocumentCleanerV2
from ..config_v2 import BELEK_CONFIG_V2

logger = logging.getLogger(__name__)


@asset(
    name="cleaned_documents",
    group_name="transform",
    description=(
        "Unicode normalleştirme, boilerplate temizleme ve kalite filtresi uygular. "
        "approved_preview_index'teki onaylı içerikler taze crawl yerine tercih edilir."
    ),
    compute_kind="python",
)
def cleaned_documents(
    context: AssetExecutionContext,
    document_hashes: dict[str, Any],
    approved_preview_index: dict[str, dict],
) -> list[dict]:
    """
    Döndürür: list[dict] — temizlenmiş, arama için hazır belgeler.
    Her dict'te "_source" anahtarı vardır: "approved_preview" veya "crawled".
    """
    cfg = BELEK_CONFIG_V2
    cleaner = DocumentCleanerV2(min_content_chars=cfg.min_content_chars)

    changed_docs: list[dict] = document_hashes.get("changed", [])
    context.log.info(
        "Temizlenecek belge: %d | Approved preview index: %d kayıt",
        len(changed_docs), len(approved_preview_index),
    )

    results: list[dict] = []
    skipped = 0
    from_preview = 0
    from_crawl = 0

    for doc in changed_docs:
        url = doc.get("url", "")
        approved = approved_preview_index.get(url)

        if approved:
            # Onaylı içerik — taze crawl görmezden geliniyor
            body = approved["markdown_body"]
            if not cleaner.is_valid(body):
                context.log.debug(
                    "Approved preview minimum eşik altında, atlandı: %s (%d karakter)",
                    url, len(body),
                )
                skipped += 1
                continue

            merged = {
                **doc,
                "markdown_body": body,
                # Frontmatter'dan gelen alanlarla güncelle (elle değiştirmiş olabilir)
                "title":        approved.get("title") or doc.get("title", ""),
                "fmt":          approved.get("fmt") or doc.get("fmt", "html"),
                "category":     approved.get("category") or doc.get("category", ""),
                "doc_category": approved.get("doc_category") or doc.get("doc_category", ""),
                "_source":      "approved_preview",
            }
            results.append(merged)
            from_preview += 1
            context.log.debug("Approved preview kullanıldı: %s", url)

        else:
            # Approved preview yok — taze crawl içeriğini temizle
            raw_body = doc.get("markdown_body", "")
            cleaned_body = cleaner.clean(raw_body)

            if not cleaner.is_valid(cleaned_body):
                context.log.debug(
                    "Minimum içerik eşiği geçilemedi, atlandı: %s (%d karakter)",
                    url, len(cleaned_body),
                )
                skipped += 1
                continue

            results.append({**doc, "markdown_body": cleaned_body, "_source": "crawled"})
            from_crawl += 1

    context.log.info(
        "Temizlendi: %d belge (approved_preview: %d, crawled: %d, atlandı: %d)",
        len(results), from_preview, from_crawl, skipped,
    )
    context.add_output_metadata({
        "cleaned":          len(results),
        "from_approved_preview": from_preview,
        "from_crawl":       from_crawl,
        "skipped":          skipped,
        "input":            len(changed_docs),
    })
    return results
