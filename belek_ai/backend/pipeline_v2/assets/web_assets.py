"""
raw_web_pages Asset — Firecrawl API ile HTML sayfaları.

- ingestion_list.json'daki HTML (PDF/DOCX olmayan) URL'leri çeker.
- depth=2 olan kaynaklar için Firecrawl map ile alt linkleri keşfeder ve scrape eder.
- onlyMainContent=True: navigasyon/footer otomatik temizlenir.
- Her URL için 3 deneme; 429 rate-limit'te exponential backoff.
- Hata → log + continue (pipeline durmaz).
- Çıktı: list[dict] — RawDocumentV2.to_dict() formatı.
"""

import hashlib
import logging
from datetime import datetime, timezone

from dagster import AssetExecutionContext, Backoff, RetryPolicy, asset

from ..config_v2 import BELEK_CONFIG_V2, load_ingestion_list_v2
from ..resources.firecrawl_resource import FirecrawlResource

logger = logging.getLogger(__name__)


def _build_doc(url: str, data: dict, src, now_iso: str) -> dict:
    """Firecrawl sonucundan RawDocumentV2 dict oluştur."""
    md = data.get("markdown", "").strip()
    content_hash = hashlib.sha256(md.encode("utf-8")).hexdigest()
    return {
        "url": url,
        "title": data.get("title", ""),
        "markdown_body": md,
        "fmt": "html",
        "category": src.category,
        "source_url": src.url,           # ana kaynak URL
        "doc_category": src.category_slug,
        "last_updated": now_iso,
        "is_active": True,
        "access_level": "public",
        "content_hash": content_hash,
        "crawled_at": now_iso,
        "is_changed": True,              # hash_assets güncelleyecek
    }


@asset(
    name="raw_web_pages",
    group_name="ingestion",
    description=(
        "Firecrawl API üzerinden HTML sayfalarını Markdown olarak çeker. "
        "depth=2 olan kaynaklar için alt linkleri otomatik keşfeder ve scrape eder."
    ),
    retry_policy=RetryPolicy(max_retries=2, delay=30, backoff=Backoff.EXPONENTIAL),
    compute_kind="firecrawl",
)
def raw_web_pages(
    context: AssetExecutionContext,
    firecrawl: FirecrawlResource,
) -> list[dict]:
    """
    Çıktı: list[dict] — RawDocumentV2 JSON repr.
    """
    cfg = BELEK_CONFIG_V2
    sources = load_ingestion_list_v2(cfg.ingestion_list_path)
    html_sources = [s for s in sources if s.is_html]

    context.log.info("HTML kaynak sayısı: %d", len(html_sources))

    if not html_sources:
        context.log.warning("İşlenecek HTML kaynak bulunamadı.")
        return []

    # ── depth=1 ve depth>=2 ayır ──────────────────────────────────────────
    depth1_sources = [s for s in html_sources if s.depth < 2]
    depth2_sources = [s for s in html_sources if s.depth >= 2]

    context.log.info(
        "depth=1: %d kaynak, depth≥2: %d kaynak",
        len(depth1_sources), len(depth2_sources),
    )

    # Tüm scrape edilecek URL'leri topla: (url, kaynak_ref)
    scrape_plan: dict[str, any] = {}   # url → TargetSourceV2

    for s in depth1_sources:
        scrape_plan[s.url] = s

    # ── depth>=2: map ile alt linkleri keşfet ─────────────────────────────
    for s in depth2_sources:
        # Ana URL'yi her zaman ekle
        scrape_plan[s.url] = s

        context.log.info("Map keşfi başlatılıyor (depth=%d): %s", s.depth, s.url)
        sub_links = firecrawl.map(s.url, limit=200, include_subdomains=False)

        if sub_links:
            new_count = 0
            for link in sub_links:
                if link not in scrape_plan:
                    scrape_plan[link] = s      # alt-link ana kaynağın kategorisini devralır
                    new_count += 1
            context.log.info(
                "  → %d link keşfedildi, %d yeni eklendi (toplam plan: %d)",
                len(sub_links), new_count, len(scrape_plan),
            )
        else:
            context.log.warning("  → Map sonucu boş: %s", s.url)

    context.log.info("Toplam scrape planı: %d URL", len(scrape_plan))

    # ── Batch scrape ──────────────────────────────────────────────────────
    all_urls = list(scrape_plan.keys())
    fetched = firecrawl.scrape_batch(all_urls, concurrency=cfg.firecrawl_concurrency)

    now_iso = datetime.now(timezone.utc).isoformat()
    results: list[dict] = []

    for url, data in fetched.items():
        if data is None:
            context.log.warning("Atlandı (Firecrawl başarısız): %s", url)
            continue

        md = data.get("markdown", "").strip()
        if not md:
            context.log.warning("Boş içerik: %s", url)
            continue

        src = scrape_plan[url]
        results.append(_build_doc(url, data, src, now_iso))

    context.log.info("Çekilen HTML belge: %d / %d", len(results), len(all_urls))
    context.add_output_metadata({
        "html_fetched":   len(results),
        "html_total":     len(all_urls),
        "depth1_sources": len(depth1_sources),
        "depth2_sources": len(depth2_sources),
        "depth2_sublinks": len(all_urls) - len(html_sources),
    })
    return results
