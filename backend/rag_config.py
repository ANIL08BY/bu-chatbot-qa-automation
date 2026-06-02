"""
RAG retrieval konfigürasyonu — tüm sihirli sayıların tek kaynağı.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RAGConfig:
    """V2 RAG arama parametreleri."""

    # Retrieval — sorgu tipine göre döndürülecek chunk sayısı
    k_general: int = 15
    k_list: int = 40
    k_aggregation: int = 18
    k_specific: int = 5

    # Reranker
    reranker_max_length: int = 512

    # Konuşma geçmişi
    max_history_messages: int = 6

    # Kategori fallback eşiği — sonuç < bu sayı ise "genel" kategorisine geç.
    # 1: kategoride tek chunk bile varsa fallback olmaz; sızıntıyı önler.
    min_category_results: int = 1


# Tek global instance — import edip kullanın
rag_config = RAGConfig()
