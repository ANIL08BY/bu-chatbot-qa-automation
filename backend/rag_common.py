"""
Ortak RAG yardımcıları — query_v2.py tarafından kullanılır.

Bu modül vector store YÜKLEMEz; yalnızca saf fonksiyonlar, prompt template,
LLM chain factory ve sorgu analizi sağlar.
"""
from __future__ import annotations

import logging
import os
import re

from backend.pipeline_v2.config_v2 import (
    CATEGORY_LABELS_V2 as CATEGORY_LABELS,
)
from backend.pipeline_v2.config_v2 import (
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
# LLM provider seçimi — LLM_PROVIDER env var ile kontrol edilir
# Desteklenen değerler: "groq" (varsayılan) | "openai" | "gemini"
# ---------------------------------------------------------------------------

_LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "groq").lower()

# Groq fallback zinciri (varsayılan)
FALLBACK_MODELS: list[str] = [
    "llama-3.3-70b-versatile",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "llama-3.1-8b-instant",
]

# OpenAI model tercih sırası (LLM_PROVIDER=openai)
_OPENAI_MODELS: list[str] = [
    "gpt-4o-mini",
]

# Gemini model tercih sırası (LLM_PROVIDER=gemini)
# NOT: gemini-2.0-flash ve gemini-1.5-flash free tier'dan kaldırıldı (limit: 0 hatası).
# Free tier'da hâlâ kotası olanlar: 2.5-flash (10 RPM, 250 RPD) ve 2.5-flash-lite (15 RPM, 1000 RPD).
_GEMINI_MODELS: list[str] = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]


def _get_active_models() -> list[str]:
    """Aktif provider için model listesi döndürür."""
    if _LLM_PROVIDER == "openai":
        return _OPENAI_MODELS
    if _LLM_PROVIDER == "gemini":
        return _GEMINI_MODELS
    return FALLBACK_MODELS


def _build_llm(model_name: str):
    """Provider'a göre LangChain LLM nesnesi oluşturur."""
    if _LLM_PROVIDER == "openai":
        from langchain_openai import ChatOpenAI

        api_key = os.getenv("OPENAI_API_KEY", "")
        return ChatOpenAI(temperature=0, model=model_name, api_key=api_key)
    if _LLM_PROVIDER == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        api_key = os.getenv("GOOGLE_API_KEY", "")
        # max_retries=0 — iç retry'ı kapat; bizim invoke_fallback kendisi model değiştiriyor.
        # Aksi halde 429'da 7-8 kez retry edip kullanıcıyı bekletiyor.
        return ChatGoogleGenerativeAI(
            temperature=0,
            model=model_name,
            google_api_key=api_key,
            max_retries=0,
        )
    # groq (varsayılan)
    from langchain_groq import ChatGroq

    api_key = os.getenv("GROQ_API_KEY", "")
    return ChatGroq(temperature=0, model_name=model_name, api_key=api_key)


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


def analyze_query(query: str, history: list[dict] | None = None) -> tuple[str, str]:
    """
    Tek LLM çağrısıyla hem kategori hem optimize edilmiş arama sorgusunu döndürür.

    history verilirse son 3 mesajı bağlam olarak ekler; bu sayede
    "hepsini listele" gibi belirsiz follow-up sorguları doğru kategoriye çözümlenir.

    Returns:
        (category, search_query) — hata durumunda ("genel", orijinal_sorgu).
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return "genel", query

    # Follow-up sorguları için geçmiş bağlamı oluştur
    effective_question = query
    if history:
        prev_lines = []
        for msg in history[-3:]:
            role = "Kullanıcı" if msg["role"] == "user" else "Asistan"
            content = msg["content"][:150].strip()
            prev_lines.append(f"{role}: {content}")
        if prev_lines:
            effective_question = (
                "Önceki konuşma:\n" + "\n".join(prev_lines) + f"\n\nYeni soru: {query}"
            )

    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "user", "content": _ANALYZE_PROMPT.format(question=effective_question)}
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
# Sorgu boyutu — k değeri sorgu tipine göre dinamik
# ---------------------------------------------------------------------------

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
    Aktif provider'ın model listesini sırasıyla dener; ilk başarılı yanıtı döner.
    Tüm modeller tükenirse kullanıcı dostu RuntimeError fırlatır.
    """
    from langchain_core.prompts import ChatPromptTemplate

    prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    models = _get_active_models()
    errors: list[str] = []

    for model in models:
        try:
            llm = _build_llm(model)
            chain = prompt | llm
            return chain.invoke(payload)
        except Exception as exc:
            errors.append(f"{model}: {exc}")
            if is_rate_limit(exc):
                continue
            raise

    raise RuntimeError(
        f"Tüm {_LLM_PROVIDER.upper()} modelleri başarısız oldu.\n"
        "Lütfen birkaç dakika sonra tekrar deneyin.\n"
        "Detaylar:\n" + "\n".join(errors)
    )


# ---------------------------------------------------------------------------
# LLM zinciri oluşturma
# ---------------------------------------------------------------------------


def build_chain():
    """
    Aktif provider (LLM_PROVIDER env) + prompt template zinciri döndürür.

    Desteklenen provider'lar: groq (varsayılan), openai, gemini.
    İlgili API key env değişkeni eksikse RuntimeError fırlatır.
    """
    from langchain_core.prompts import ChatPromptTemplate

    _provider_keys = {
        "groq": ("GROQ_API_KEY", "GROQ_API_KEY bulunamadı."),
        "openai": ("OPENAI_API_KEY", "OPENAI_API_KEY bulunamadı."),
        "gemini": ("GOOGLE_API_KEY", "GOOGLE_API_KEY bulunamadı."),
    }
    env_var, err_msg = _provider_keys.get(
        _LLM_PROVIDER, ("GROQ_API_KEY", "GROQ_API_KEY bulunamadı.")
    )
    if not os.getenv(env_var):
        raise RuntimeError(f"{err_msg} .env dosyasını kontrol edin ve uygulamayı yeniden başlatın.")

    models = _get_active_models()
    llm = _build_llm(models[0])
    logger.info("LLM provider: %s | model: %s", _LLM_PROVIDER, models[0])
    return ChatPromptTemplate.from_template(PROMPT_TEMPLATE) | llm


# ---------------------------------------------------------------------------
# Konuşma geçmişi formatlama
# ---------------------------------------------------------------------------

def format_history(history: list[dict] | None) -> str:
    """Konuşma geçmişini prompt'a eklenecek metin formatına dönüştürür."""
    if not history:
        return ""
    lines = []
    for msg in history[-_cfg.max_history_messages :]:
        role = "Kullanıcı" if msg["role"] == "user" else "Asistan"
        lines.append(f"{role}: {msg['content']}")
    return "KONUŞMA GEÇMİŞİ:\n" + "\n".join(lines) + "\n"
