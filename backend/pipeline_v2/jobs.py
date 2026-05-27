"""
Dagster Job Tanımları.

full_pipeline_job  — Tüm pipeline sıfırdan çalışır.
                     Hash kaydı + approved olmayan preview'lar otomatik temizlenir.
incremental_job    — Sadece yeni/değişen belgeler işlenir.
                     ingestion_list'e yeni URL eklendiğinde kullanılır.
"""
from dagster import AssetSelection, define_asset_job

# ── full_pipeline_job ──────────────────────────────────────────────────────
#
# clear_registry=True      → hash kaydı silinir → tüm belgeler is_new=True
# clear_on_full_run=True   → approved olmayan preview dosyaları silinir
#
full_pipeline_job = define_asset_job(
    name="full_pipeline_job",
    selection=AssetSelection.groups("ingestion", "dedup", "transform", "store"),
    config={
        "ops": {
            "document_hashes": {
                "config": {"clear_registry": True}
            },
            "raw_preview_dump": {
                "config": {"clear_on_full_run": True}
            },
        }
    },
    description=(
        "Tüm ingestion → dedup → transform → store pipeline'ını sıfırdan çalıştırır. "
        "Hash kaydı temizlenir, approved olmayan preview'lar yeniden oluşturulur."
    ),
)

# ── incremental_job ────────────────────────────────────────────────────────
#
# Hash dedup sayesinde sadece:
#   - ingestion_list'e yeni eklenen URL'ler (is_new=True)
#   - içeriği değişen URL'ler (is_changed=True)
# Qdrant'a yazılır ve preview'ları oluşturulur.
#
incremental_job = define_asset_job(
    name="incremental_job",
    selection=AssetSelection.groups("ingestion", "dedup", "transform", "store"),
    description=(
        "Sadece yeni veya değişen belgeler işlenir. "
        "ingestion_list'e yeni URL eklendiğinde çalıştırılır."
    ),
)
