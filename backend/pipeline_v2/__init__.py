"""
Pipeline V2 — Enterprise-Grade Dagster RAG Pipeline.

Bileşenler:
  - Firecrawl   → HTML scraping
  - Docling     → PDF parsing (TableFormer)
  - SHA-256     → Incremental ingestion
  - Qdrant      → Hybrid vector search (dense + BM42)
  - bge-reranker-v2-m3 → Cross-encoder reranking (query_v2.py'de)

Başlatma:
  dagster dev -w workspace.yaml

Doğrudan çalıştırma:
  python -m backend.pipeline_v2.evaluation.eval
"""
try:
    from .definitions import defs
    __all__ = ["defs"]
except ImportError:
    # Dagster kurulu değilse (örn: sadece query_v2 veya config_v2 kullanılıyorsa)
    defs = None
    __all__ = []
