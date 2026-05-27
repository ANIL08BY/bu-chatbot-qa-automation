"""
RAG Değerlendirme Modülü — Hit Rate & MRR.

Kullanım:
    python -m backend.pipeline_v2.evaluation.eval

Çıktı:
    {
      "hit_rate@5":  0.80,
      "mrr":         0.72,
      "per_query":   [...]
    }

Gereksinim: Qdrant çalışıyor ve belek_v2 collection dolu olmalı.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Örnek sorgu seti (Türkçe üniversite soruları)
# ---------------------------------------------------------------------------

SAMPLE_QUERIES: list[dict[str, str]] = [
    {
        "query": "Lisans final sınavları ne zaman başlıyor?",
        "expected_category": "lisans-akademik-takvim",
        "expected_keyword": "final",
    },
    {
        "query": "Yüksek lisans kayıt tarihleri ne zaman?",
        "expected_category": "lisansustu-akademik-takvim",
        "expected_keyword": "kayıt",
    },
    {
        "query": "Kütüphaneden kitap ödünç almak için ne yapmalıyım?",
        "expected_category": "kutuphane-hakkinda",
        "expected_keyword": "ödünç",
    },
    {
        "query": "Kütüphane iletişim bilgileri ve adres nedir?",
        "expected_category": "kutuphane-iletisim",
        "expected_keyword": "iletişim",
    },
    {
        "query": "Burs başvurusu için son tarih nedir?",
        "expected_category": "burs-olanaklari",
        "expected_keyword": "burs",
    },
    {
        "query": "Engelli öğrencilere sağlanan destek hizmetleri nelerdir?",
        "expected_category": "engelli-ogrenci",
        "expected_keyword": "engelli",
    },
    {
        "query": "Kurum içi yatay geçiş koşulları nelerdir?",
        "expected_category": "kurum-ici-yatay-gecis",
        "expected_keyword": "yatay",
    },
    {
        "query": "Öğrenci toplulukları nasıl kurulur?",
        "expected_category": "ogrenci-topluluklari",
        "expected_keyword": "topluluk",
    },
    {
        "query": "Eğitim öğretim ücreti ne kadar?",
        "expected_category": "egitim-ogretim-ucretleri",
        "expected_keyword": "ücret",
    },
    {
        "query": "Belek Üniversitesi misyonu nedir?",
        "expected_category": "vizyon-misyon",
        "expected_keyword": "misyon",
    },
]


# ---------------------------------------------------------------------------
# Metrikler
# ---------------------------------------------------------------------------


def compute_hit_rate(
    retriever_fn: Callable[[str, str, int], list[dict]],
    queries: list[dict[str, str]] | None = None,
    k: int = 5,
) -> float:
    """
    Hit Rate@k: Doğru kategoriden en az 1 chunk top-k içinde mi?

    Args:
        retriever_fn: (query, category, k) → list[dict] (her dict "doc_category" içerir)
        queries:      Test sorgularını, None ise SAMPLE_QUERIES kullanılır.
        k:            Top-k eşiği.

    Returns:
        0.0 ile 1.0 arasında float.
    """
    queries = queries or SAMPLE_QUERIES
    hits = 0

    for item in queries:
        try:
            results = retriever_fn(item["query"], item["expected_category"], k)
            categories = [r.get("doc_category", "") for r in results]
            if item["expected_category"] in categories:
                hits += 1
        except Exception as exc:
            logger.warning("Hit rate hesaplama hatası [%s]: %s", item["query"], exc)

    return hits / len(queries) if queries else 0.0


def compute_mrr(
    retriever_fn: Callable[[str, str, int], list[dict]],
    queries: list[dict[str, str]] | None = None,
    k: int = 10,
) -> float:
    """
    Mean Reciprocal Rank: İlk doğru sonucun sıralama tersi ortalaması.

    Returns:
        0.0 ile 1.0 arasında float.
    """
    queries = queries or SAMPLE_QUERIES
    rr_sum = 0.0

    for item in queries:
        try:
            results = retriever_fn(item["query"], item["expected_category"], k)
            for rank, result in enumerate(results, 1):
                if result.get("doc_category") == item["expected_category"]:
                    rr_sum += 1.0 / rank
                    break
        except Exception as exc:
            logger.warning("MRR hesaplama hatası [%s]: %s", item["query"], exc)

    return rr_sum / len(queries) if queries else 0.0


def compute_keyword_coverage(
    retriever_fn: Callable[[str, str, int], list[dict]],
    queries: list[dict[str, str]] | None = None,
    k: int = 5,
) -> float:
    """
    Anahtar kelime kapsama oranı: Beklenen anahtar kelime top-k sonuçlarında var mı?
    """
    queries = queries or SAMPLE_QUERIES
    covered = 0

    for item in queries:
        keyword = item.get("expected_keyword", "").lower()
        if not keyword:
            continue
        try:
            results = retriever_fn(item["query"], item["expected_category"], k)
            texts = " ".join(r.get("text", "").lower() for r in results)
            if keyword in texts:
                covered += 1
        except Exception as exc:
            logger.warning("Keyword coverage hatası [%s]: %s", item["query"], exc)

    valid = [q for q in queries if q.get("expected_keyword")]
    return covered / len(valid) if valid else 0.0


# ---------------------------------------------------------------------------
# Qdrant retriever yardımcısı
# ---------------------------------------------------------------------------


def _build_qdrant_retriever(
    url: str = "",
    api_key: str = "",
    host: str = "localhost",
    port: int = 6333,
    collection: str = "belek_v2",
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
):
    """
    Qdrant hybrid arama fonksiyonu döndürür.
    Eval modülü içinde standalone çalışabilir.

    Bağlantı modu (öncelik): url (cloud) > host:port (local)
    """
    from qdrant_client import QdrantClient
    from qdrant_client.models import FieldCondition, Filter, MatchValue
    from sentence_transformers import SentenceTransformer

    if url:
        client = QdrantClient(url=url, api_key=api_key or None)
    else:
        client = QdrantClient(host=host, port=port)
    model = SentenceTransformer(embedding_model)

    def retriever(query: str, category: str, k: int) -> list[dict]:
        query_vector = model.encode(query, normalize_embeddings=True).tolist()
        filter_condition = None
        if category and category != "genel":
            filter_condition = Filter(
                must=[FieldCondition(key="doc_category", match=MatchValue(value=category))]
            )
        response = client.query_points(
            collection_name=collection,
            query=query_vector,
            using="dense",
            query_filter=filter_condition,
            limit=k,
            with_payload=True,
        )
        return [r.payload for r in response.points]

    return retriever


# ---------------------------------------------------------------------------
# Ana değerlendirme
# ---------------------------------------------------------------------------


def run_evaluation(retriever_fn=None) -> dict[str, Any]:
    """
    Tüm metrikleri hesapla ve raporla.

    Args:
        retriever_fn: None → Qdrant'a otomatik bağlan.

    Returns:
        {"hit_rate@5": float, "mrr": float, "keyword_coverage": float, "per_query": list}
    """
    if retriever_fn is None:
        qdrant_url = os.environ.get("QDRANT_URL", "")
        retriever_fn = _build_qdrant_retriever(
            url=qdrant_url,
            api_key=os.environ.get("QDRANT_API_KEY", ""),
            host=os.environ.get("QDRANT_HOST", "localhost"),
            port=int(os.environ.get("QDRANT_PORT", "6333")),
        )

    logger.info("Değerlendirme başlıyor (%d sorgu)...", len(SAMPLE_QUERIES))

    hit_rate = compute_hit_rate(retriever_fn, k=5)
    mrr = compute_mrr(retriever_fn, k=10)
    kw_cov = compute_keyword_coverage(retriever_fn, k=5)

    # Per-query detay
    per_query: list[dict] = []
    for item in SAMPLE_QUERIES:
        try:
            results = retriever_fn(item["query"], item["expected_category"], 5)
            top_cats = [r.get("doc_category", "?") for r in results[:3]]
            per_query.append(
                {
                    "query": item["query"],
                    "expected": item["expected_category"],
                    "top3_categories": top_cats,
                    "hit": item["expected_category"] in [r.get("doc_category") for r in results],
                }
            )
        except Exception as exc:
            per_query.append({"query": item["query"], "error": str(exc)})

    report = {
        "hit_rate@5": round(hit_rate, 4),
        "mrr": round(mrr, 4),
        "keyword_coverage": round(kw_cov, 4),
        "total_queries": len(SAMPLE_QUERIES),
        "per_query": per_query,
    }
    return report


# ---------------------------------------------------------------------------
# CLI girişi
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    report = run_evaluation()
    print("\n── Değerlendirme Sonuçları ─────────────────────────")
    print(f"  Hit Rate@5       : {report['hit_rate@5']:.2%}")
    print(f"  MRR              : {report['mrr']:.4f}")
    print(f"  Keyword Coverage : {report['keyword_coverage']:.2%}")
    print(f"  Toplam sorgu     : {report['total_queries']}")
    print("\n── Per-Query ────────────────────────────────────────")
    for q in report["per_query"]:
        status = "✓" if q.get("hit") else "✗"
        print(f"  {status} {q['query'][:55]:<55} → {q.get('top3_categories', q.get('error'))}")
    print()
    print(json.dumps(report, ensure_ascii=False, indent=2))
