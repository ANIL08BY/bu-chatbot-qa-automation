"""
RAG retrieval konfigürasyonu — tüm sihirli sayıların tek kaynağı.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RAGConfig:
    """Hibrit RAG arama parametreleri."""

    # Retrieval — sorgu tipine göre döndürülecek chunk sayısı
    k_general: int = 15
    k_list: int = 40
    k_aggregation: int = 18
    k_specific: int = 5

    # RRF (Reciprocal Rank Fusion)
    rrf_denominator: int = 45
    noise_threshold: float = 0.35

    # BM25 / Semantik ağırlıklar (sorgu tipine göre)
    bm25_weight_aggregation: float = 0.70
    bm25_weight_specific: float = 0.60
    bm25_weight_general: float = 0.50

    # Reranker
    reranker_max_length: int = 512

    # Konuşma geçmişi
    max_history_messages: int = 6

    # Kategori fallback eşiği
    min_category_results: int = 3


# Tek global instance — import edip kullanın
rag_config = RAGConfig()
