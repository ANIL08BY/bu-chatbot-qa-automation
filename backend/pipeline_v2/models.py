"""
Pipeline V2 Veri Modelleri.

RawDocumentV2  — Firecrawl/Docling çıktısı (ham belge)
ChunkV2        — Semantik bölünmüş, metadata zengin parça
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RawDocumentV2:
    """Ham belge — scraping/parsing sonrası, temizleme öncesi."""

    url: str                          # Kaynak URL
    title: str                        # Sayfa/dosya başlığı
    markdown_body: str                # Firecrawl/Docling Markdown çıktısı
    fmt: str                          # "html" | "pdf" | "docx"
    category: str                     # İnsan okunur kategori ("burs olanakları")
    content_hash: str                 # SHA-256 (markdown_body üzerinde)
    crawled_at: str                   # ISO 8601 UTC timestamp

    # Zorunlu metadata alanları (Qdrant payload)
    source_url: str                   # Canonical URL (url ile aynı, yedeklilik için)
    doc_category: str                 # Slug (örn: "burs-olanaklari")
    last_updated: str                 # ISO 8601 UTC timestamp
    is_active: bool = True
    access_level: str = "public"      # "public" | "internal"

    # Incremental işaretleyici — hash_assets tarafından atanır
    is_changed: bool = True

    def is_empty(self) -> bool:
        return len(self.markdown_body.strip()) < 50

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "markdown_body": self.markdown_body,
            "fmt": self.fmt,
            "category": self.category,
            "content_hash": self.content_hash,
            "crawled_at": self.crawled_at,
            "source_url": self.source_url,
            "doc_category": self.doc_category,
            "last_updated": self.last_updated,
            "is_active": self.is_active,
            "access_level": self.access_level,
            "is_changed": self.is_changed,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RawDocumentV2":
        return cls(
            url=d["url"],
            title=d.get("title", ""),
            markdown_body=d.get("markdown_body", ""),
            fmt=d.get("fmt", "html"),
            category=d.get("category", "genel"),
            content_hash=d.get("content_hash", ""),
            crawled_at=d.get("crawled_at", ""),
            source_url=d.get("source_url", d["url"]),
            doc_category=d.get("doc_category", "genel"),
            last_updated=d.get("last_updated", ""),
            is_active=d.get("is_active", True),
            access_level=d.get("access_level", "public"),
            is_changed=d.get("is_changed", True),
        )


@dataclass
class ChunkV2:
    """
    Semantik bölünmüş metin parçası — Qdrant'a yazılacak birim.
    Her alan Qdrant payload key'i ile birebir eşleşir.
    """
    # İçerik
    text: str                         # "[Konu: ...]\n..." prefix'li chunk metni
    chunk_idx: int                    # Belge içindeki sıra numarası
    doc_chunks: int                   # Bu belgeden toplam kaç chunk üretildi

    # Kaynak bilgisi
    url: str
    source_url: str
    title: str
    fmt: str                          # "html" | "pdf" | "docx"
    section: str                      # ## heading
    page: int | None                  # PDF sayfa numarası (None = HTML)

    # Kategori
    category: str                     # Ham (örn: "burs olanakları")
    doc_category: str                 # Slug (örn: "burs-olanaklari")

    # Metadata
    source: str                       # Domain (örn: "belek.edu.tr")
    crawled_at: str                   # ISO 8601
    last_updated: str                 # ISO 8601
    content_hash: str                 # Belge düzeyinde SHA-256
    is_active: bool = True
    access_level: str = "public"

    def to_payload(self) -> dict[str, Any]:
        """Qdrant point payload olarak kullanılacak dict."""
        return {
            "text": self.text,
            "chunk_idx": self.chunk_idx,
            "doc_chunks": self.doc_chunks,
            "url": self.url,
            "source_url": self.source_url,
            "title": self.title,
            "fmt": self.fmt,
            "section": self.section,
            "page": self.page,
            "category": self.category,
            "doc_category": self.doc_category,
            "source": self.source,
            "crawled_at": self.crawled_at,
            "last_updated": self.last_updated,
            "content_hash": self.content_hash,
            "is_active": self.is_active,
            "access_level": self.access_level,
        }
