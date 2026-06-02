"""
document_hashes Asset — SHA-256 incremental ingestion kapısı.

raw_web_pages + raw_pdf_documents + raw_local_documents
    → hash karşılaştırması → is_changed + is_new etiketleri.

Değişmeyen belgeler downstream asset'lerde atlanır.

Config:
    clear_registry (bool, default=False):
        True → hash kaydını silerek başlar; tüm belgeler is_new=True olur.
        full_pipeline_job tarafından otomatik True yapılır.
"""

import logging
import os
from typing import Any

from dagster import AssetExecutionContext, Config, asset

from ..config_v2 import BELEK_CONFIG_V2
from ..hash_store import compute_stats, filter_changed, load_registry, save_registry

logger = logging.getLogger(__name__)


class HashConfig(Config):
    clear_registry: bool = False


@asset(
    name="document_hashes",
    group_name="dedup",
    description=(
        "SHA-256 hash kaydını günceller; değişen belgeler is_changed=True, "
        "yeni belgeler is_new=True ile işaretlenir. "
        "clear_registry=True ile hash kaydı sıfırlanır (full run)."
    ),
    compute_kind="python",
)
def document_hashes(
    context: AssetExecutionContext,
    config: HashConfig,
    raw_web_pages: list[dict],
    raw_pdf_documents: list[dict],
    raw_local_documents: list[dict],
) -> dict[str, Any]:
    """
    Çıktı:
    {
        "changed":          list[dict],  # Yeni veya içeriği değişmiş belgeler
        "all_docs":         list[dict],  # Tüm belgeler (is_changed + is_new dolu)
        "unchanged_count":  int,
        "changed_count":    int,
    }
    """
    cfg = BELEK_CONFIG_V2
    all_docs = raw_web_pages + raw_pdf_documents + raw_local_documents
    context.log.info(
        "Toplam belge: %d (HTML: %d, PDF: %d, Local: %d)",
        len(all_docs), len(raw_web_pages), len(raw_pdf_documents), len(raw_local_documents),
    )

    # Full run: hash kaydını sıfırla
    if config.clear_registry:
        if os.path.exists(cfg.hash_registry_path):
            os.remove(cfg.hash_registry_path)
            context.log.info("Hash kaydı temizlendi (full run) — tüm belgeler yeni sayılacak.")
        else:
            context.log.info("Hash kaydı zaten yok, temizlemeye gerek yok.")

    registry = load_registry(cfg.hash_registry_path)
    context.log.info("Mevcut hash kaydı: %d giriş", len(registry))

    annotated, updated_registry = filter_changed(all_docs, registry)

    try:
        save_registry(updated_registry, cfg.hash_registry_path)
        context.log.info("Hash kaydı güncellendi: %s", cfg.hash_registry_path)
    except Exception as exc:
        context.log.error("Hash kaydı kaydedilemedi: %s", exc)

    stats = compute_stats(annotated)
    context.log.info(
        "Değişen: %d, Değişmeyen: %d, Toplam: %d",
        stats["changed"], stats["unchanged"], stats["total"],
    )

    context.add_output_metadata({
        "total_docs":      stats["total"],
        "changed_docs":    stats["changed"],
        "unchanged_docs":  stats["unchanged"],
        "registry_cleared": config.clear_registry,
    })

    changed_docs = [d for d in annotated if d.get("is_changed", True)]

    return {
        "changed":         changed_docs,
        "all_docs":        annotated,
        "unchanged_count": stats["unchanged"],
        "changed_count":   stats["changed"],
    }
