"""
Soru-Cevap motoru V1 — Hibrit RAG (BM25 + Semantik MMR + RRF).

Lazy initialization: vectorstore ve BM25 ilk istekte yüklenir.
Eksik vector_db veya chunks.pkl varsa açıklayıcı hata döner.

Metadata-Aware Search: Sorgunun kategorisi tespit edilerek ChromaDB ve
BM25 filtrelemesi yapılır. Sonuç < 3 ise otomatik fallback ile genel arama.
"""
from __future__ import annotations

import logging
import os
import pickle
import threading

from dotenv import load_dotenv

from backend.rag_common import (
    CATEGORY_LABELS,
    FALLBACK_MODELS,
    KNOWN_CATEGORIES,
    PROMPT_TEMPLATE,
    analyze_query,
    compute_k,
    format_history,
    invoke_fallback,
    is_rate_limit,
    rrf_weights,
)
from backend.rag_config import rag_config as _cfg

current_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(current_dir, "..", ".env"))

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------

_VECTOR_DB_PATH  = os.path.join(current_dir, "vector_db")
_CHUNKS_PKL      = os.path.join(_VECTOR_DB_PATH, "chunks.pkl")
_EMBEDDING_MODEL = (
    "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
)

# ---------------------------------------------------------------------------
# Lazy-loaded kaynaklar
# ---------------------------------------------------------------------------

_embeddings     = None
_vectorstore    = None
_bm25_retriever = None
_llm            = None
_chain          = None
_chunks_list: list = []
_init_lock = threading.Lock()


def _init() -> None:
    """Kaynakları ilk istekte yükle. Sonraki isteklerde atlanır."""
    global _embeddings, _vectorstore, _bm25_retriever
    global _chain, _chunks_list

    if _chain is not None:
        return

    with _init_lock:
        if _chain is not None:
            return

        # ── API Key ───────────────────────────────────────────────────────
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY bulunamadı. "
                ".env dosyasını kontrol edin ve uvicorn'u yeniden başlatın."
            )

        # ── Vector DB varlık kontrolü ─────────────────────────────────────
        if not os.path.isdir(_VECTOR_DB_PATH):
            raise RuntimeError(
                f"Vector DB bulunamadı: {_VECTOR_DB_PATH}\n"
                "Önce pipeline'ı çalıştırın:\n"
                "  dagster job execute -m backend.pipeline_v2.definitions"
            )
        if not os.path.exists(_CHUNKS_PKL):
            raise RuntimeError(
                f"BM25 indeksi bulunamadı: {_CHUNKS_PKL}\n"
                "Pipeline'ı yeniden çalıştırın:\n"
                "  dagster job execute -m backend.pipeline_v2.definitions"
            )

        # ── Embedding + Chroma ────────────────────────────────────────────
        from langchain_chroma import Chroma
        from langchain_huggingface import HuggingFaceEmbeddings

        _embeddings  = HuggingFaceEmbeddings(model_name=_EMBEDDING_MODEL)
        _vectorstore = Chroma(
            persist_directory=_VECTOR_DB_PATH,
            embedding_function=_embeddings,
        )

        # ── BM25 ─────────────────────────────────────────────────────────
        from langchain_community.retrievers import BM25Retriever

        with open(_CHUNKS_PKL, "rb") as f:
            _chunks_list = pickle.load(f)
        _bm25_retriever   = BM25Retriever.from_documents(_chunks_list)
        _bm25_retriever.k = _cfg.k_general

        # ── LLM + Chain ──────────────────────────────────────────────────
        from backend.rag_common import build_chain
        _chain = build_chain()


# ---------------------------------------------------------------------------
# Hibrit arama (Metadata-Aware)
# ---------------------------------------------------------------------------

def _hybrid_search(
    query:        str,
    search_query: str  = "",
    category:     str  = "genel",
    k:            int  = 10,
) -> tuple[list, str]:
    """
    Ağırlıklı Reciprocal Rank Fusion: BM25 + Semantik MMR.

    Returns:
        (docs, effective_category)
    """
    sq = search_query.strip() or query
    bm25_w, sem_w = rrf_weights(query)

    apply_filter = category != "genel" and category in KNOWN_CATEGORIES

    # ── Kategori filtreli BM25 chunk kontrolü ────────────────────────────
    filtered_chunks: list = []
    if apply_filter:
        filtered_chunks = [
            c for c in _chunks_list
            if c.metadata.get("category") == category
        ]
        if len(filtered_chunks) < _cfg.min_category_results:
            apply_filter = False

    # ── BM25 (optimize sorguyla) ──────────────────────────────────────────
    if apply_filter:
        from langchain_community.retrievers import BM25Retriever
        tmp_bm25   = BM25Retriever.from_documents(filtered_chunks)
        tmp_bm25.k = k + 4
        bm25_docs  = tmp_bm25.invoke(sq)
    else:
        _bm25_retriever.k = k + 4
        bm25_docs = _bm25_retriever.invoke(sq)

    # ── Semantik / ChromaDB MMR (optimize sorguyla) ───────────────────────
    fetch_k = max(k * 3, 30)
    if apply_filter:
        try:
            semantic_docs = _vectorstore.max_marginal_relevance_search(
                sq, k=k + 4, fetch_k=fetch_k,
                filter={"category": category},
            )
        except Exception:
            semantic_docs = []

        if len(semantic_docs) < _cfg.min_category_results:
            apply_filter  = False
            _bm25_retriever.k = k + 4
            bm25_docs     = _bm25_retriever.invoke(sq)
            semantic_docs = _vectorstore.max_marginal_relevance_search(
                sq, k=k + 4, fetch_k=fetch_k,
            )
    else:
        semantic_docs = _vectorstore.max_marginal_relevance_search(
            sq, k=k + 4, fetch_k=fetch_k,
        )

    effective_category = category if apply_filter else "genel"

    # ── RRF ──────────────────────────────────────────────────────────────
    scores:  dict[str, float]  = {}
    doc_map: dict[str, object] = {}

    for rank, doc in enumerate(bm25_docs):
        key = f"{len(doc.page_content)}:{doc.page_content[:150]}"
        scores[key]  = scores.get(key, 0.0) + bm25_w / (rank + _cfg.rrf_denominator)
        doc_map[key] = doc

    for rank, doc in enumerate(semantic_docs):
        key = f"{len(doc.page_content)}:{doc.page_content[:150]}"
        scores[key]  = scores.get(key, 0.0) + sem_w / (rank + _cfg.rrf_denominator)
        doc_map[key] = doc

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # ── Gürültü filtresi ────────────────────────────────────────────────
    if ranked:
        top_score = ranked[0][1]
        threshold = top_score * _cfg.noise_threshold
        filtered  = [(key, s) for key, s in ranked if s >= threshold]
        if len(filtered) >= 4:
            ranked = filtered

    return [doc_map[key] for key, _ in ranked[:k]], effective_category


# ---------------------------------------------------------------------------
# Ana fonksiyon
# ---------------------------------------------------------------------------

def ask_question(query: str, history: list[dict] | None = None) -> dict:
    """
    Soruyu hibrit RAG ile yanıtlar.

    Returns:
        {"answer": str, "sources": list[dict], "category": str}
    """
    _init()

    detected, search_query = analyze_query(query)
    k = compute_k(query)

    docs, effective_category = _hybrid_search(
        query, search_query=search_query, category=detected, k=k
    )
    context = "\n\n".join(doc.page_content for doc in docs)

    # ── Kaynak kartları ───────────────────────────────────────────────────
    sources: list[dict] = []
    for doc in docs[:3]:
        page = doc.metadata.get("page")
        sources.append({
            "page":    (page + 1) if isinstance(page, int) else "?",
            "url":     doc.metadata.get("url", ""),
            "snippet": doc.page_content[:200].strip(),
        })

    history_text = format_history(history)

    label = CATEGORY_LABELS.get(effective_category, effective_category)
    category_context = (
        f"\nŞu an '{label}' kategorisindeki belgelere dayanarak cevap veriyorsun.\n"
        if effective_category != "genel" else ""
    )

    payload = {
        "context":          context,
        "question":         query,
        "history":          history_text,
        "category_context": category_context,
    }

    try:
        response = _chain.invoke(payload)
    except Exception as exc:
        if not is_rate_limit(exc):
            raise
        response = invoke_fallback(payload)

    return {
        "answer":   response.content,
        "sources":  sources,
        "category": effective_category,
    }
