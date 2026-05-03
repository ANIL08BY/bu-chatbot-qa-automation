"""
Ortak RAG yardımcıları — query.py ve query_v2.py tarafından paylaşılır.

Bu modül LLM, embedding veya vector store YÜKLEMEz; yalnızca saf fonksiyonlar
ve konfigürasyon sağlar.
"""
from __future__ import annotations

import logging
import os
import re

from backend.pipeline_v2.config_v2 import (
    CATEGORY_LABELS_V2 as CATEGORY_LABELS,
    KNOWN_CATEGORIES_V2 as KNOWN_CATEGORIES,
)
from backend.rag_config import rag_config as _cfg

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt template (external dosyadan)
# ---------------------------------------------------------------------------

_PROMPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")

with open(os.path.join(_PROMPT_DIR, "system_prompt.txt"), encoding="utf-8") as _f:
    PROMPT_TEMPLATE = _f.read()

# ---------------------------------------------------------------------------
# Groq model tercih sırası
# ---------------------------------------------------------------------------

FALLBACK_MODELS: list[str] = [
    "llama-3.3-70b-versatile",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "llama-3.1-8b-instant",
]

# ---------------------------------------------------------------------------
# Regex pattern'ları (sorgu tipi tespiti)
# ---------------------------------------------------------------------------

AGGREGATION_RE = re.compile(
    r"\b(kaç|toplam|kaçıncı|tane|adet|sayısı|yapısı|bölüm sayısı|madde sayısı)\b",
    re.IGNORECASE,
)
LIST_RE = re.compile(
    r"\b(tümü|hepsi|hepsini|listele|listeler|tüm\s+\S+lar|tüm\s+\S+ler|sırala|nelerdir|hangileri|sayar\s*mısın|söyler\s*misin)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Sorgu analizi: kategori tespiti + query rewriting
# ---------------------------------------------------------------------------

def _build_analyze_prompt() -> str:
    """KNOWN_CATEGORIES'den dinamik prompt oluştur."""
    lines = []
    for slug in sorted(KNOWN_CATEGORIES):
        label = CATEGORY_LABELS.get(slug, slug)
        lines.append(f"- {slug}: {label}")
    lines.append("- genel: hiçbiri uymuyorsa")
    cat_block = "\n".join(lines)

    return f"""\
Bir üniversite bilgi sisteminin ön işlemcisisin. Aşağıdaki soruyu analiz et.

KATEGORİLER:
{cat_block}

SORU: {{question}}

Yanıtı YALNIZCA şu 2 satır formatta ver (açıklama ekleme):
kategori: <kategori_adı>
sorgu: <soruyu BM25+vektör arama için optimize et; eş anlamlılar, ilgili terimler ve Türkçe/İngilizce varyasyonlar ekle; max 20 kelime>"""


_ANALYZE_PROMPT = _build_analyze_prompt()


def analyze_query(query: str) -> tuple[str, str]:
    """
    Tek LLM çağrısıyla hem kategori hem optimize edilmiş arama sorgusunu döndürür.

    Returns:
        (category, search_query) — hata durumunda ("genel", orijinal_sorgu).
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return "genel", query

    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "user", "content": _ANALYZE_PROMPT.format(question=query)}
            ],
            temperature=0,
            max_tokens=60,
        )
        raw = response.choices[0].message.content.strip()

        category = "genel"
        search_query = query

        for line in raw.splitlines():
            line = line.strip()
            if line.lower().startswith("kategori:"):
                cat = line.split(":", 1)[1].strip().lower().strip(".\n ")
                if cat in KNOWN_CATEGORIES:
                    category = cat
                else:
                    for known in KNOWN_CATEGORIES:
                        if cat in known or known in cat:
                            category = known
                            break
            elif line.lower().startswith("sorgu:"):
                sq = line.split(":", 1)[1].strip()
                if sq:
                    search_query = sq

        return category, search_query

    except Exception as exc:
        logger.warning("Sorgu analizi hatası: %s", exc)
        return "genel", query


# ---------------------------------------------------------------------------
# Sorgu ağırlıklandırma ve boyutu
# ---------------------------------------------------------------------------

def rrf_weights(query: str) -> tuple[float, float]:
    """(bm25_w, semantic_w) döndür — sorgu tipine göre dinamik."""
    if AGGREGATION_RE.search(query):
        return _cfg.bm25_weight_aggregation, 1.0 - _cfg.bm25_weight_aggregation
    if re.search(r"madde\s+\d+", query, re.IGNORECASE):
        return _cfg.bm25_weight_specific, 1.0 - _cfg.bm25_weight_specific
    return _cfg.bm25_weight_general, 1.0 - _cfg.bm25_weight_general


def compute_k(query: str) -> int:
    """Sorgu tipine göre kaç chunk getirileceğini belirle."""
    if LIST_RE.search(query):
        return _cfg.k_list
    if AGGREGATION_RE.search(query):
        return _cfg.k_aggregation
    if re.search(r"madde\s+\d+", query, re.IGNORECASE):
        return _cfg.k_specific
    return _cfg.k_general


# ---------------------------------------------------------------------------
# Model fallback yardımcısı
# ---------------------------------------------------------------------------

def is_rate_limit(exc: Exception) -> bool:
    """429 / rate_limit_exceeded hatası mı?"""
    msg = str(exc).lower()
    return "rate_limit" in msg or "429" in msg or "tokens per day" in msg


def invoke_fallback(payload: dict):
    """
    FALLBACK_MODELS sırasıyla dener; ilk başarılı yanıtı döner.
    Tüm modeller tükenirse kullanıcı dostu RuntimeError fırlatır.
    """
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_groq import ChatGroq

    api_key = os.getenv("GROQ_API_KEY", "")
    prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    errors: list[str] = []

    for model in FALLBACK_MODELS:
        try:
            llm = ChatGroq(temperature=0, model_name=model, api_key=api_key)
            chain = prompt | llm
            return chain.invoke(payload)
        except Exception as exc:
            errors.append(f"{model}: {exc}")
            if is_rate_limit(exc):
                continue
            raise

    raise RuntimeError(
        "Tüm Groq modelleri günlük token limitine ulaştı.\n"
        "Lütfen birkaç dakika sonra tekrar deneyin.\n"
        "Detaylar:\n" + "\n".join(errors)
    )


# ---------------------------------------------------------------------------
# LLM zinciri oluşturma — V1 ve V2 tarafından bağımsız olarak kullanılır
# ---------------------------------------------------------------------------

def build_chain():
    """
    ChatGroq + prompt template zinciri döndürür.

    GROQ_API_KEY env değişkeninden okunur; eksikse RuntimeError fırlatır.
    Hem query.py (V1) hem query_v2.py (V2) bu fonksiyonu çağırarak kendi
    zincirlerini bağımsız başlatır — iki motor arasında global state paylaşılmaz.
    """
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_groq import ChatGroq

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY bulunamadı. "
            ".env dosyasını kontrol edin ve uygulamayı yeniden başlatın."
        )
    llm = ChatGroq(temperature=0, model_name=FALLBACK_MODELS[0], api_key=api_key)
    return ChatPromptTemplate.from_template(PROMPT_TEMPLATE) | llm


# ---------------------------------------------------------------------------
# Konuşma geçmişi formatlama
# ---------------------------------------------------------------------------

def format_history(history: list[dict] | None) -> str:
    """Konuşma geçmişini prompt'a eklenecek metin formatına dönüştürür."""
    if not history:
        return ""
    lines = []
    for msg in history[-_cfg.max_history_messages:]:
        role = "Kullanıcı" if msg["role"] == "user" else "Asistan"
        lines.append(f"{role}: {msg['content']}")
    return "KONUŞMA GEÇMİŞİ:\n" + "\n".join(lines) + "\n"
