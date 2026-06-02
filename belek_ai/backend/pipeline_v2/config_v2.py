"""
Pipeline V2 Yapılandırması.

Mevcut PipelineConfig'den bağımsız; Dagster resource'ları bu config'i kullanır.
"""
from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Kategori normalize yardımcısı
# ---------------------------------------------------------------------------

_TR_MAP = str.maketrans(
    "şğüöıçŞĞÜÖİÇ",
    "sguoicSGUOIC",
)


def slugify(text: str) -> str:
    """Turkish text → kebab-case ASCII slug."""
    s = text.strip().lower().translate(_TR_MAP)
    s = unicodedata.normalize("NFKD", s)
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"[\s,/]+", "-", s.strip())
    s = re.sub(r"-{2,}", "-", s)
    return s.strip("-")


# ---------------------------------------------------------------------------
# Tüm kategoriler — ingestion_list.json'dan OTOMATİK türetilir.
# Yeni kaynak eklendiğinde burayı güncellemeye gerek yok.
# ---------------------------------------------------------------------------

def _build_categories_from_ingestion_list() -> tuple[frozenset[str], dict[str, str]]:
    """
    ingestion_list.json'daki category alanlarından slug ve label oluşturur.
    Dosya okunamazsa boş set döner.
    """
    path = os.path.join(_ROOT, "ingestion_list.json")
    slugs: set[str] = {"genel"}
    labels: dict[str, str] = {"genel": "Genel"}

    try:
        with open(path, encoding="utf-8") as f:
            items = json.load(f)
        for item in items:
            raw_cat = item.get("category", "").strip()
            if not raw_cat:
                continue
            slug = slugify(raw_cat)
            if slug and slug != "genel":
                slugs.add(slug)
                labels[slug] = raw_cat
    except Exception as exc:
        logger.warning("Kategori listesi oluşturulamadı: %s", exc)

    return frozenset(slugs), labels


KNOWN_CATEGORIES_V2, CATEGORY_LABELS_V2 = _build_categories_from_ingestion_list()


# ---------------------------------------------------------------------------
# TargetSourceV2 — ingestion_list.json satırı
# ---------------------------------------------------------------------------

@dataclass
class TargetSourceV2:
    url: str
    category: str = "genel"
    priority: int = 1
    depth: int = 1                     # 1 = sadece bu URL, 2 = bu URL + alt linkleri

    @property
    def category_slug(self) -> str:
        return slugify(self.category)

    @property
    def is_pdf(self) -> bool:
        return self.url.lower().endswith(".pdf")

    @property
    def is_docx(self) -> bool:
        return self.url.lower().endswith(".docx")

    @property
    def is_html(self) -> bool:
        return not (self.is_pdf or self.is_docx)


# ---------------------------------------------------------------------------
# PipelineConfigV2
# ---------------------------------------------------------------------------

@dataclass
class PipelineConfigV2:
    ingestion_list_path: str = os.path.join(_ROOT, "ingestion_list.json")

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "belek_v2"
    qdrant_vector_size: int = 768          # paraphrase-multilingual-mpnet-base-v2

    # Embedding & Reranker
    embedding_model: str = (
        "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    )
    embed_batch_size: int = 64
    reranker_model: str = "BAAI/bge-reranker-v2-m3"

    # Firecrawl
    firecrawl_concurrency: int = 5        # paralel istek sayısı

    # PDF
    max_pdf_size_mb: int = 50
    pdf_timeout_s: float = 90.0           # Docling TableFormer için uzun

    # Chunking
    chunk_size: int = 800
    chunk_overlap: int = 150
    min_content_chars: int = 100

    # Paths
    hash_registry_path: str = os.path.join(
        _ROOT, "backend", "pipeline_v2_cache", "doc_hashes.json"
    )
    user_agent: str = "BUChatbot/2.0 (+https://belek.edu.tr)"


# ---------------------------------------------------------------------------
# Kaynak yükleme
# ---------------------------------------------------------------------------

def load_ingestion_list_v2(path: str) -> list[TargetSourceV2]:
    """ingestion_list.json → list[TargetSourceV2], priority sırasına göre."""
    try:
        with open(path, encoding="utf-8") as f:
            items = json.load(f)
        sources = [
            TargetSourceV2(
                url=item["url"],
                category=item.get("category", "genel"),
                priority=item.get("priority", 1),
                depth=item.get("depth", 1),
            )
            for item in items
            if item.get("url")
        ]
        sources.sort(key=lambda s: s.priority)
        return sources
    except Exception as exc:
        logger.warning("ingestion_list.json okunamadı: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Varsayılan config örneği
# ---------------------------------------------------------------------------

BELEK_CONFIG_V2 = PipelineConfigV2()
