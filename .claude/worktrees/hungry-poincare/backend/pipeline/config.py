"""
Pipeline yapılandırması — tüm ayarlar tek yerden yönetilir.

Crawl modları
─────────────
"auto"     → ingestion_list.json varsa Targeted, yoksa BFS
"targeted" → Sadece whitelist URL'leri + bağlı PDF/DOCX
"bfs"      → Geleneksel derinlik bazlı BFS (eski davranış)
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

_HERE    = os.path.dirname(os.path.abspath(__file__))   # backend/pipeline/
_BACKEND = os.path.dirname(_HERE)                        # backend/
_ROOT    = os.path.dirname(_BACKEND)                     # proje kökü


# ---------------------------------------------------------------------------
# Hedef kaynak tanımı
# ---------------------------------------------------------------------------

@dataclass
class TargetSource:
    """ingestion_list.json'daki tek bir URL kaydı."""
    url:               str
    category:          str  = "genel"
    priority:          int  = 1
    crawl_linked_docs: bool = True   # Sayfadaki PDF/DOCX linklerini de çek


def load_ingestion_list(path: str) -> list[TargetSource]:
    """
    ingestion_list.json → list[TargetSource].

    Dosya yoksa veya bozuksa sessizce boş liste döner.
    Kaynaklar priority değerine göre artan sırada sıralanır
    (priority=1 en önce, priority=3 en sonda).
    """
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            items = json.load(f)
        sources = [
            TargetSource(
                url               = item["url"],
                category          = item.get("category", "genel"),
                priority          = item.get("priority", 1),
                crawl_linked_docs = item.get("crawl_linked_docs", True),
            )
            for item in items
            if item.get("url")          # url anahtarı olmayan satırları atla
        ]
        sources.sort(key=lambda s: s.priority)
        return sources
    except Exception as exc:
        print(f"  ⚠  ingestion_list.json okunamadı: {exc}")
        return []


# ---------------------------------------------------------------------------
# Ana pipeline yapılandırması
# ---------------------------------------------------------------------------

@dataclass
class PipelineConfig:
    # ── Crawl ─────────────────────────────────────────────────────────────
    seed_urls: list[str]          = field(default_factory=list)
    allowed_domains: list[str]    = field(default_factory=list)
    max_pages: int                = 0        # 0 = limitsiz (BFS modu)
    max_depth: int                = 5        # BFS modu için derinlik
    delay_seconds: float          = 0.5      # İstekler arası bekleme
    timeout_seconds: float        = 20.0
    max_retries: int              = 2
    user_agent: str               = "BUChatbot/2.0 (+https://belek.edu.tr)"
    follow_pdfs: bool             = True
    follow_docx: bool             = True
    max_pdf_size_mb: int          = 50
    pdf_parse_timeout: float      = 25.0
    skip_patterns: list[str]      = field(default_factory=list)
    priority_patterns: list[str]  = field(default_factory=list)
    checkpoint_interval: int      = 25      # Her N URL'de checkpoint yaz

    # ── Crawl modu ────────────────────────────────────────────────────────
    crawl_mode: str               = "auto"  # "auto" | "targeted" | "bfs"
    ingestion_list_path: str      = ""      # ingestion_list.json yolu

    # ── Extraction ────────────────────────────────────────────────────────
    min_content_chars: int        = 150

    # ── Chunking ──────────────────────────────────────────────────────────
    chunk_size: int               = 800
    chunk_overlap: int            = 150

    # ── Embedding ─────────────────────────────────────────────────────────
    embedding_model: str = (
        "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    )
    embed_batch_size: int         = 64
    chroma_batch_size: int        = 500

    # ── Paths ─────────────────────────────────────────────────────────────
    vector_db_path: str           = ""
    cache_dir: str                = ""
    local_data_dir: str           = ""


# ---------------------------------------------------------------------------
# Belek Üniversitesi yapılandırması
# ---------------------------------------------------------------------------
BELEK_CONFIG = PipelineConfig(
    seed_urls=[
        "https://www.belek.edu.tr",
        "https://www.belek.edu.tr/TR/1/Anasayfa",
        "https://www.belek.edu.tr/Akademi",
    ],
    allowed_domains=["belek.edu.tr", "www.belek.edu.tr"],
    max_pages=0,
    max_depth=5,
    delay_seconds=0.5,
    timeout_seconds=20.0,
    max_retries=2,
    follow_pdfs=True,
    follow_docx=True,
    max_pdf_size_mb=50,
    pdf_parse_timeout=25.0,
    checkpoint_interval=25,
    crawl_mode="auto",
    ingestion_list_path=os.path.join(_ROOT, "ingestion_list.json"),
    min_content_chars=150,
    chunk_size=800,
    chunk_overlap=150,
    skip_patterns=[
        r"\.(jpg|jpeg|png|gif|svg|ico|webp|bmp|mp4|mp3|avi|mov)$",
        r"\.(zip|rar|exe|js|css|json|xml|map)$",
        r"[?&](page|sayfa|p)=\d+",
        r"/(wp-admin|wp-login|wp-content/uploads)",
        r"/(login|logout|register|kayit|giris)\b",
        r"^mailto:",
        r"^tel:",
    ],
    priority_patterns=[
        r"\.(pdf|docx)$",
        r"/(Akademi|akademi)",
        r"/(Mevzuat|mevzuat|yonetmelik|yönetmelik)",
        r"/(Haberler|Duyurular|haberler|duyurular)",
        r"/(AkademikTakvim|akademik-takvim|ders-programlari)",
    ],
    vector_db_path=os.path.join(_BACKEND, "vector_db"),
    cache_dir=os.path.join(_BACKEND, "pipeline_cache"),
    local_data_dir=os.path.join(_BACKEND, "data"),
)
