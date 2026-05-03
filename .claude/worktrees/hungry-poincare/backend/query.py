"""
Soru-Cevap motoru — Hibrit RAG (BM25 + Semantik MMR + RRF).

Lazy initialization: vectorstore ve BM25 ilk istekte yüklenir.
Eksik vector_db veya chunks.pkl varsa açıklayıcı hata döner.

Metadata-Aware Search: Sorgunun kategorisi tespit edilerek ChromaDB ve
BM25 filtrelemesi yapılır. Sonuç < 3 ise otomatik fallback ile genel arama.
"""
from __future__ import annotations

import os
import pickle
import re

from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(current_dir, "..", ".env"))

# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------

_VECTOR_DB_PATH  = os.path.join(current_dir, "vector_db")
_CHUNKS_PKL      = os.path.join(_VECTOR_DB_PATH, "chunks.pkl")
_EMBEDDING_MODEL = (
    "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
)

# ingestion_list.json'dan türetilen geçerli kategoriler.
# Yeni kategori eklendiğinde buraya da eklenmeli.
KNOWN_CATEGORIES: frozenset[str] = frozenset({
    "lisans-akademik-takvim",
    "lisansustu-akademik-takvim",
    "kutuphane-hakkinda",
    "kutuphane-iletisim",
    "ogrenci-topluluklari",
    "engelli-ogrenci",
    "aday-ogrenci",
    "burs-olanaklari",
    "genel",
})

_CATEGORY_LABELS: dict[str, str] = {
    "lisans-akademik-takvim":      "Lisans Akademik Takvim",
    "lisansustu-akademik-takvim":  "Lisansüstü Akademik Takvim",
    "kutuphane-hakkinda":          "Kütüphane (Hakkında)",
    "kutuphane-iletisim":          "Kütüphane (İletişim)",
    "ogrenci-topluluklari":        "Öğrenci Toplulukları",
    "engelli-ogrenci":             "Engelli Öğrenci Hizmetleri",
    "aday-ogrenci":                "Aday Öğrenci / Başvuru",
    "burs-olanaklari":             "Burs Olanakları",
    "genel":                       "Genel",
}

# Groq model tercih sırası — primer 429 verirse bir sonrakine geçilir.
# Günlük limitler birbirinden bağımsızdır.
_FALLBACK_MODELS: list[str] = [
    "llama-3.3-70b-versatile",   # primer  – en kaliteli
    "llama-3.1-8b-instant",      # fallback – hızlı, ayrı TPD limiti
    "gemma2-9b-it",              # son çare – Google/Groq, ayrı TPD limiti
]

_PROMPT_TEMPLATE = """\
Sen Belek Üniversitesi için geliştirilmiş profesyonel bir akademik asistansın.
Görevin aşağıdaki DÖKÜMAN içeriğini kullanarak soruları doğru ve eksiksiz yanıtlamak.
{category_context}
KURALLAR:
1. Yalnızca DÖKÜMAN'daki bilgileri kullan — asla tahmin etme veya bilgi uydurma.
2. Madde/bölüm alıntısı istendiğinde, ilgili metni DÖKÜMAN'dan olduğu gibi aktar; kırpma.
3. Sayım sorularında ("kaç madde", "toplam") DÖKÜMAN'daki tüm öğeleri say; tahminde bulunma.
4. Tarih, saat ve son başvuru tarihlerini kesin olarak belirt; "yaklaşık", "civarı" kullanma.
5. Liste veya tablo sorularında TÜM öğeleri sırala — "vb.", "..." veya benzeri kısaltmayla kesme.
6. Yanıt dökümanda yoksa: "Bu konu hakkında elimde yeterli bilgi bulunmuyor. Lütfen üniversitenin ilgili birimiyle iletişime geçin." de.
7. Yanıtlarını Türkçe ver; teknik terimleri ve özel isimleri koru.
8. Yanıt birden fazla konuyu kapsıyorsa, her konuyu ayrı paragraf veya madde ile sun.

DÖKÜMAN:
{context}

{history}SORU: {question}

YANIT:"""

# ---------------------------------------------------------------------------
# Lazy-loaded kaynaklar
# ---------------------------------------------------------------------------

_embeddings     = None
_vectorstore    = None
_bm25_retriever = None
_llm            = None
_chain          = None
_chunks_list: list = []   # Ham chunk listesi — kategori filtrelemesi için


def _init() -> None:
    """Kaynakları ilk istekte yükle. Sonraki isteklerde atlanır."""
    global _embeddings, _vectorstore, _bm25_retriever
    global _llm, _chain, _chunks_list

    if _chain is not None:
        return  # Zaten yüklü

    # ── API Key ───────────────────────────────────────────────────────────
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY bulunamadı. "
            ".env dosyasını kontrol edin ve uvicorn'u yeniden başlatın."
        )

    # ── Vector DB varlık kontrolü ─────────────────────────────────────────
    if not os.path.isdir(_VECTOR_DB_PATH):
        raise RuntimeError(
            f"Vector DB bulunamadı: {_VECTOR_DB_PATH}\n"
            "Önce pipeline'ı çalıştırın:\n"
            "  python -m backend.pipeline.run"
        )
    if not os.path.exists(_CHUNKS_PKL):
        raise RuntimeError(
            f"BM25 indeksi bulunamadı: {_CHUNKS_PKL}\n"
            "Pipeline'ı yeniden çalıştırın:\n"
            "  python -m backend.pipeline.run --ingest-only"
        )

    # ── Embedding + Chroma ────────────────────────────────────────────────
    from langchain_chroma import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings

    _embeddings  = HuggingFaceEmbeddings(model_name=_EMBEDDING_MODEL)
    _vectorstore = Chroma(
        persist_directory=_VECTOR_DB_PATH,
        embedding_function=_embeddings,
    )

    # ── BM25 ─────────────────────────────────────────────────────────────
    from langchain_community.retrievers import BM25Retriever

    with open(_CHUNKS_PKL, "rb") as f:
        _chunks_list = pickle.load(f)
    _bm25_retriever   = BM25Retriever.from_documents(_chunks_list)
    _bm25_retriever.k = 10

    # ── LLM + Chain ───────────────────────────────────────────────────────
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_groq import ChatGroq

    _llm = ChatGroq(
        temperature=0,
        model_name=_FALLBACK_MODELS[0],
        api_key=api_key,
    )

    _chain = ChatPromptTemplate.from_template(_PROMPT_TEMPLATE) | _llm


# ---------------------------------------------------------------------------
# Sorgu analizi: kategori tespiti + query rewriting (tek LLM çağrısı)
# ---------------------------------------------------------------------------

_ANALYZE_PROMPT = """\
Bir üniversite bilgi sisteminin ön işlemcisisin. Aşağıdaki soruyu analiz et.

KATEGORİLER:
- lisans-akademik-takvim: lisans ders/sınav tarihleri, kayıt dönemleri, lisans takvimi
- lisansustu-akademik-takvim: yüksek lisans, doktora, lisansüstü takvim/tarihler
- kutuphane-hakkinda: kütüphane hizmetleri, kitap ödünç, veritabanı erişimi
- kutuphane-iletisim: kütüphane adres, telefon, e-posta, iletişim bilgileri
- ogrenci-topluluklari: öğrenci kulüpleri, topluluklar, etkinlikler
- engelli-ogrenci: engelli öğrenci hizmetleri, erişilebilirlik, destek
- aday-ogrenci: başvuru, kayıt, kabul, yeni öğrenci, üniversiteye giriş
- burs-olanaklari: burslar, mali destek, ücret muafiyeti, burs başvurusu
- genel: hiçbiri uymuyorsa

SORU: {question}

Yanıtı YALNIZCA şu 2 satır formatta ver (açıklama ekleme):
kategori: <kategori_adı>
sorgu: <soruyu BM25+vektör arama için optimize et; eş anlamlılar, ilgili terimler ve Türkçe/İngilizce varyasyonlar ekle; max 20 kelime>"""


def _analyze_query(query: str) -> tuple[str, str]:
    """
    Tek LLM çağrısıyla hem kategori hem optimize edilmiş arama sorgusunu döndürür.
    Hız için llama-3.1-8b-instant, max_tokens=60.

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

        category    = "genel"
        search_query = query  # Fallback: orijinal sorgu

        for line in raw.splitlines():
            line = line.strip()
            if line.lower().startswith("kategori:"):
                cat = line.split(":", 1)[1].strip().lower().strip(".\n ")
                if cat in KNOWN_CATEGORIES:
                    category = cat
                else:
                    # Kısmi eşleşme: "burs" → "burs-olanaklari"
                    for known in KNOWN_CATEGORIES:
                        if cat in known or known in cat:
                            category = known
                            break
            elif line.lower().startswith("sorgu:"):
                sq = line.split(":", 1)[1].strip()
                if sq:
                    search_query = sq

        return category, search_query

    except Exception:
        return "genel", query


# ---------------------------------------------------------------------------
# Model fallback yardımcısı
# ---------------------------------------------------------------------------

def _is_rate_limit(exc: Exception) -> bool:
    """429 / rate_limit_exceeded hatası mı?"""
    msg = str(exc).lower()
    return "rate_limit" in msg or "429" in msg or "tokens per day" in msg


def _invoke_fallback(payload: dict):
    """
    _FALLBACK_MODELS sırasıyla dener; ilk başarılı yanıtı döner.
    Tüm modeller tükenirse kullanıcı dostu RuntimeError fırlatır.
    """
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_groq import ChatGroq

    api_key = os.getenv("GROQ_API_KEY", "")
    prompt  = ChatPromptTemplate.from_template(_PROMPT_TEMPLATE)
    errors: list[str] = []

    for model in _FALLBACK_MODELS:
        try:
            llm   = ChatGroq(temperature=0, model_name=model, api_key=api_key)
            chain = prompt | llm
            return chain.invoke(payload)
        except Exception as exc:
            errors.append(f"{model}: {exc}")
            if _is_rate_limit(exc):
                continue   # Sonraki modeli dene
            raise          # Rate-limit değilse direkt fırlat

    raise RuntimeError(
        "Tüm Groq modelleri günlük token limitine ulaştı.\n"
        "Lütfen birkaç dakika sonra tekrar deneyin.\n"
        "Detaylar:\n" + "\n".join(errors)
    )


# ---------------------------------------------------------------------------
# Sorgu ağırlıklandırma ve boyutu
# ---------------------------------------------------------------------------

_AGGREGATION_RE = re.compile(
    r"\b(kaç|toplam|kaçıncı|tane|adet|sayısı|yapısı|bölüm sayısı|madde sayısı)\b",
    re.IGNORECASE,
)
_LIST_RE = re.compile(
    r"\b(tümü|hepsi|hepsini|listele|tüm\s+\S+lar|tüm\s+\S+ler|sırala|yaz)\b",
    re.IGNORECASE,
)


def _rrf_weights(query: str) -> tuple[float, float]:
    """(bm25_w, semantic_w) döndür — sorgu tipine göre dinamik."""
    if _AGGREGATION_RE.search(query):
        return 0.70, 0.30   # "kaç madde var?" → BM25 baskın
    if re.search(r"madde\s+\d+", query, re.IGNORECASE):
        return 0.60, 0.40   # "Madde 42'yi yaz" → keyword baskın
    return 0.35, 0.65       # Genel soru → semantik baskın


def _compute_k(query: str) -> int:
    """
    Sorgu tipine göre kaç chunk getirileceğini belirle.

    Liste/tablo → 16  (tüm öğeler için daha fazla bağlam)
    Sayım       →  8  (birkaç chunk sayıyı verir)
    Madde no    →  5  (çok spesifik — az ama hedefli)
    Genel       → 10  (dengeli)
    """
    if _LIST_RE.search(query):
        return 16
    if _AGGREGATION_RE.search(query):
        return 8
    if re.search(r"madde\s+\d+", query, re.IGNORECASE):
        return 5
    return 10


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

    Args:
        query:        Kullanıcının orijinal sorusu (gösterim/prompt için).
        search_query: Optimize edilmiş arama sorgusu (retrieval için).
                      Boşsa orijinal query kullanılır.
        category:     Tespit edilen metadata kategorisi.
        k:            Döndürülecek chunk sayısı (_compute_k ile belirlenir).

    Returns:
        (docs, effective_category) — effective_category 'genel' ise fallback
        devreye girmiş demektir.
    """
    sq       = search_query.strip() or query   # Optimize sorgu yoksa orijinali kullan
    bm25_w, sem_w = _rrf_weights(query)        # Ağırlıklar orijinal sorguya göre

    apply_filter = category != "genel" and category in KNOWN_CATEGORIES

    # ── Kategori filtreli BM25 chunk kontrolü ────────────────────────────
    filtered_chunks: list = []
    if apply_filter:
        filtered_chunks = [
            c for c in _chunks_list
            if c.metadata.get("category") == category
        ]
        if len(filtered_chunks) < 3:
            apply_filter = False  # Yeterli chunk yok — fallback

    # ── BM25 (optimize sorguyla) ──────────────────────────────────────────
    if apply_filter:
        from langchain_community.retrievers import BM25Retriever
        tmp_bm25   = BM25Retriever.from_documents(filtered_chunks)
        tmp_bm25.k = k + 4   # RRF'de elenecekler için biraz fazla al
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

        if len(semantic_docs) < 3:
            # Chroma'da da yetersiz sonuç → tümüyle fallback
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
        scores[key]  = scores.get(key, 0.0) + bm25_w / (rank + 60)
        doc_map[key] = doc

    for rank, doc in enumerate(semantic_docs):
        key = f"{len(doc.page_content)}:{doc.page_content[:150]}"
        scores[key]  = scores.get(key, 0.0) + sem_w / (rank + 60)
        doc_map[key] = doc

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # ── Gürültü filtresi: top_score'un %35'inden düşük chunk'ları çıkar ──
    # En az 4 sonuç her zaman korunur.
    if ranked:
        top_score = ranked[0][1]
        threshold = top_score * 0.35
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

    Raises:
        RuntimeError: Vector DB veya API key eksikse açıklayıcı mesajla.
    """
    _init()  # İlk çağrıda kaynakları yükle

    # ── Sorgu analizi: kategori + optimize arama sorgusu (tek LLM çağrısı) ─
    detected, search_query = _analyze_query(query)
    k = _compute_k(query)

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

    # ── Konuşma geçmişi ───────────────────────────────────────────────────
    history_text = ""
    if history:
        for msg in history[-6:]:
            role = "Kullanıcı" if msg["role"] == "user" else "Asistan"
            history_text += f"{role}: {msg['content']}\n"
        history_text = f"KONUŞMA GEÇMİŞİ:\n{history_text}\n"

    # ── Kategori bağlamı ──────────────────────────────────────────────────
    label = _CATEGORY_LABELS.get(effective_category, effective_category)
    if effective_category != "genel":
        category_context = (
            f"\nŞu an '{label}' kategorisindeki belgelere dayanarak cevap veriyorsun.\n"
        )
    else:
        category_context = ""

    payload = {
        "context":          context,
        "question":         query,
        "history":          history_text,
        "category_context": category_context,
    }

    # Primer modeli dene; 429 gelirse fallback zinciri devreye girer.
    try:
        response = _chain.invoke(payload)
    except Exception as exc:
        if not _is_rate_limit(exc):
            raise
        response = _invoke_fallback(payload)

    return {
        "answer":   response.content,
        "sources":  sources,
        "category": effective_category,
    }
