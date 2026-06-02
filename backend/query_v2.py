"""
Soru-Cevap Motoru — Qdrant Hybrid Search + Cross-Encoder Reranking.

Pipeline: Qdrant built-in hybrid (dense + BM42 sparse) + bge-reranker-base
LLM:      LLM_PROVIDER env var ile seçilir (varsayılan: groq)
          - groq:   llama-3.3-70b → llama-4-scout → llama-3.1-8b-instant fallback
          - openai: gpt-4o-mini
          - gemini: gemini-2.0-flash → gemini-1.5-flash fallback

Lazy initialization: Tüm modeller ilk istekte yüklenir.
Qdrant veya LLM erişilemezse RuntimeError fırlatır → main.py 503 olarak döner.
"""

from __future__ import annotations

import logging
import os
import threading

from dotenv import load_dotenv

from backend.pipeline_v2.config_v2 import KNOWN_CATEGORIES_V2
from backend.rag_common import (
    LIST_RE,
    analyze_query,
    compute_k,
    format_history,
    invoke_fallback,
    is_rate_limit,
)
from backend.rag_config import rag_config as _cfg

current_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(current_dir, "..", ".env"))

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------

# Qdrant bağlantı modu (öncelik: Cloud URL > Local Disk > Host:Port)
_QDRANT_URL = os.getenv("QDRANT_URL", "")  # Cloud: https://xxx.qdrant.io
_QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")  # Cloud API key
_QDRANT_PATH = os.getenv("QDRANT_PATH", "")  # Dolu → local disk modu
_QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
_QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
_COLLECTION = "belek_v2"
_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
_RERANKER_MODEL = "BAAI/bge-reranker-base"
_DENSE_VECTOR_NAME = "dense"

# ---------------------------------------------------------------------------
# Lazy-loaded state
# ---------------------------------------------------------------------------

_embedding_model = None
_reranker = None
_qdrant_client = None
_llm_chain = None
_initialized = False
_init_lock = threading.Lock()


def _init_v2() -> None:
    """
    Qdrant + embedding + reranker + LLM zincirini hazırla.

    Hata durumunda RuntimeError fırlatır — fallback yoktur, hata
    main.py tarafından 503 olarak döndürülür.
    """
    global _embedding_model, _reranker, _qdrant_client, _llm_chain, _initialized

    if _initialized:
        return

    with _init_lock:
        if _initialized:
            return

        try:
            # Embedding modeli
            if _embedding_model is None:
                from sentence_transformers import SentenceTransformer

                logger.info("Embedding modeli yükleniyor: %s", _EMBEDDING_MODEL)
                _embedding_model = SentenceTransformer(_EMBEDDING_MODEL)

            # Reranker
            if _reranker is None:
                from sentence_transformers import CrossEncoder

                logger.info("Reranker yükleniyor: %s", _RERANKER_MODEL)
                _reranker = CrossEncoder(_RERANKER_MODEL, max_length=_cfg.reranker_max_length)

            # Qdrant bağlantısı — Cloud URL > Local disk > Host:port
            if _qdrant_client is None:
                from qdrant_client import QdrantClient

                if _QDRANT_URL:
                    _qdrant_client = QdrantClient(url=_QDRANT_URL, api_key=_QDRANT_API_KEY or None)
                    logger.info("Qdrant Cloud modu: %s/%s", _QDRANT_URL, _COLLECTION)
                elif _QDRANT_PATH:
                    _qdrant_client = QdrantClient(path=_QDRANT_PATH)
                    logger.info("Qdrant local disk modu: %s/%s", _QDRANT_PATH, _COLLECTION)
                else:
                    _qdrant_client = QdrantClient(host=_QDRANT_HOST, port=_QDRANT_PORT, timeout=10)
                    logger.info(
                        "Qdrant host:port modu: %s:%d/%s", _QDRANT_HOST, _QDRANT_PORT, _COLLECTION
                    )
                _qdrant_client.get_collection(_COLLECTION)

            # LLM chain
            if _llm_chain is None:
                from backend.rag_common import build_chain

                _llm_chain = build_chain()

            _initialized = True
            logger.info("Query motoru hazır.")

        except Exception as exc:
            # Stack trace ile loglayalım — hatanın gerçek kaynağı görünür olsun
            logger.exception("Query motoru başlatılamadı: %s", exc)
            raise RuntimeError(
                f"Servis başlatılamadı: {exc}. "
                "Qdrant/Groq erişimini ve .env değişkenlerini kontrol edin."
            ) from exc


# ---------------------------------------------------------------------------
# Hybrid Search (Qdrant)
# ---------------------------------------------------------------------------


def _hybrid_search_v2(
    search_query: str,
    category: str = "genel",
    k: int = 10,
) -> tuple[list[dict], str, bool]:
    """
    Qdrant hybrid arama: dense + BM42.

    Returns:
        (results, effective_category, used_fallback)
        used_fallback=True → kategori filtresi yetersiz kaldı, tüm koleksiyondan arama yapıldı.
    """
    import time

    from qdrant_client.models import FieldCondition, Filter, MatchValue

    _t_embed = time.perf_counter()
    q_vec = _embedding_model.encode(search_query, normalize_embeddings=True).tolist()
    logger.info("⏱ embed=%.3fs", time.perf_counter() - _t_embed)

    apply_filter = category != "genel" and category in KNOWN_CATEGORIES_V2

    qdrant_filter = None
    if apply_filter:
        qdrant_filter = Filter(
            must=[FieldCondition(key="doc_category", match=MatchValue(value=category))]
        )

    def _search(flt, limit: int):
        _t_q = time.perf_counter()
        response = _qdrant_client.query_points(
            collection_name=_COLLECTION,
            query=q_vec,
            using=_DENSE_VECTOR_NAME,
            query_filter=flt,
            limit=limit,
            with_payload=True,
        )
        logger.info("⏱ qdrant_query(limit=%d)=%.3fs", limit, time.perf_counter() - _t_q)
        return response.points

    multiplier = 3 if k >= 20 else 2
    results = _search(qdrant_filter, k * multiplier)

    used_fallback = False
    if apply_filter and len(results) < _cfg.min_category_results:
        logger.info("Kategori '%s' için az sonuç (%d), genel fallback.", category, len(results))
        results = _search(None, k * multiplier)
        apply_filter = False
        used_fallback = True

    effective = category if apply_filter else "genel"
    payloads = [r.payload for r in results]
    return payloads, effective, used_fallback


# ---------------------------------------------------------------------------
# Cross-Encoder Reranker
# ---------------------------------------------------------------------------


def _rerank(
    query: str,
    docs: list[dict],
    top_k: int,
) -> list[dict]:
    """BAAI/bge-reranker-base ile çapraz kodlayıcı yeniden sıralama."""
    if not docs:
        return []

    pairs = [(query, doc.get("text", "")) for doc in docs]
    try:
        scores = _reranker.predict(pairs, show_progress_bar=False)
    except Exception as exc:
        logger.exception("Reranker hatası — sıralama korunuyor: %s", exc)
        return docs[:top_k]

    ranked = sorted(zip(scores, docs, strict=False), key=lambda x: x[0], reverse=True)
    return [doc for _, doc in ranked[:top_k]]


# ---------------------------------------------------------------------------
# Ana fonksiyon
# ---------------------------------------------------------------------------


def ask_question_v2(
    query: str,
    history: list[dict] | None = None,
) -> dict:
    """
    V2 pipeline ile soru yanıtla.

    Qdrant veya LLM hatası → RuntimeError (main.py 503 olarak döner).

    Returns:
        {"answer": str, "sources": list[dict], "category": str, "engine": "v2"}
    """
    import time

    _t_total = time.perf_counter()
    timings: dict[str, float] = {}

    # ── Init ──────────────────────────────────────────────────────────────
    _t = time.perf_counter()
    _init_v2()  # hata durumunda RuntimeError fırlatır
    timings["init"] = time.perf_counter() - _t

    # ── Sorgu analizi (Groq) ───────────────────────────────────────────────
    # history iletiliyor: follow-up sorguları ("hepsini listele") bağlamla çözümlenir.
    _t = time.perf_counter()
    detected, search_query = analyze_query(query, history=history)
    timings["analyze_query"] = time.perf_counter() - _t

    k = compute_k(query)

    # ── Embedding + Qdrant arama ───────────────────────────────────────────
    _t = time.perf_counter()
    try:
        raw_docs, effective_category, used_fallback = _hybrid_search_v2(
            search_query, category=detected, k=k
        )
    except Exception as exc:
        logger.exception("Qdrant arama hatası: %s", exc)
        raise RuntimeError(f"Qdrant arama hatası: {exc}") from exc
    timings["embed_and_search"] = time.perf_counter() - _t

    # ── Reranking ─────────────────────────────────────────────────────────
    # Not: Reranker'a raw query kullanıyoruz (search_query değil).
    # search_query denenmiş ancak Q4, Q5, Q6'da regresyon yarattığı için geri alındı.
    # Neden: search_query bazı edge-case sorgularda (öznel/genel) beklenmedik chunk'ları
    # öne çıkarıyordu (örn. "kampüs güzel mi" → tıbbi bitkiler, sosyoloji sızması).
    is_list_query = bool(LIST_RE.search(query))
    _t = time.perf_counter()
    if is_list_query:
        # Liste sorgularında daha geniş top_k ile rerank: en alakalı chunk öne gelsin.
        # top_k = k*1.5 → reranker büyük listede doğru chunk'ı seçer; ardından k'ya kırp.
        reranked = _rerank(query, raw_docs, top_k=int(k * 1.5))[:k]
    else:
        reranked = _rerank(query, raw_docs, top_k=k)
    timings["rerank"] = time.perf_counter() - _t

    # ── Context ve kaynak kartları ────────────────────────────────────────
    context = "\n\n".join(doc.get("text", "") for doc in reranked)

    sources: list[dict] = []
    for doc in reranked[:3]:
        page = doc.get("page")
        sources.append(
            {
                "page": (page + 1) if isinstance(page, int) else "?",
                "url": doc.get("url", ""),
                "snippet": doc.get("text", "")[:200].strip(),
            }
        )

    history_text = format_history(history)

    # Kategori adını LLM'e vermiyoruz — yalnızca "belge güveni" bayrağı iletilir.
    # Bu, LLM'nin yanıtta kategori adı/etiketi telaffuz etmesini önler.
    if effective_category != "genel" and not used_fallback:
        category_context = (
            "\nNOT: Aşağıdaki belgeler kullanıcının sorduğu konuyla doğrudan eşleşiyor.\n"
        )
    elif used_fallback:
        category_context = (
            "\nNOT: Aşağıdaki belgeler kullanıcının sorduğu spesifik konuyla doğrudan "
            "eşleşmeyebilir; yanıtında belge yetersizliğini Kural 6 şablonuyla belirt. "
            "Belirli bir kategori adı, etiket veya kaynak adı ASLA telaffuz etme.\n"
        )
    else:
        category_context = ""

    payload = {
        "context": context,
        "question": query,
        "history": history_text,
        "category_context": category_context,
    }

    # ── LLM ──────────────────────────────────────────────────────────────
    _t = time.perf_counter()
    try:
        response = _llm_chain.invoke(payload)
    except Exception as exc:
        if not is_rate_limit(exc):
            logger.exception("LLM çağrısı başarısız: %s", exc)
            raise
        response = invoke_fallback(payload)
    timings["llm"] = time.perf_counter() - _t

    timings["total"] = time.perf_counter() - _t_total

    # ── Timing özeti logla ────────────────────────────────────────────────
    logger.info(
        "⏱ LATENCY | k=%d | list=%s | cat=%s | "
        "init=%.2fs | analyze=%.2fs | embed+search=%.2fs | "
        "rerank=%.2fs | llm=%.2fs | TOTAL=%.2fs",
        k,
        is_list_query,
        effective_category,
        timings["init"],
        timings["analyze_query"],
        timings["embed_and_search"],
        timings["rerank"],
        timings["llm"],
        timings["total"],
    )

    return {
        "answer": response.content,
        "sources": sources,
        "category": effective_category,
        "engine": "v2",
        "timings": timings,
    }
