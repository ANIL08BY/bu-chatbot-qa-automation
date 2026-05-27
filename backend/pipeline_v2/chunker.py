"""
SemanticChunker — Başlık hiyerarşisi bazlı semantik bölme.

Strateji:
1. Markdown metni ## ve ### başlıklarına göre section'lara böl.
2. Her section kendi içinde RecursiveCharacterTextSplitter ile bölünür.
3. Her chunk "[Konu: {heading}]\n" ön ekini taşır (mevcut v1 formatıyla uyumlu).
4. Tüm metin NFC normalize edilir; Türkçe karakterler korunur.

Mevcut backend/pipeline/chunk.py ile aynı chunk boyutlarını kullanır
(800 karakter, 150 overlap) — vektör alanı karşılaştırılabilir kalır.
"""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlparse

from langchain_text_splitters import RecursiveCharacterTextSplitter

from .models import ChunkV2

_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)


def _extract_sections(markdown: str) -> list[tuple[str, str]]:
    """
    Markdown'ı (heading, content) çiftlerine böl.

    Başlık öncesi içerik varsa ("" heading ile) korunur.
    Döner: [(heading_text, section_content), ...]
    """
    sections: list[tuple[str, str]] = []
    matches = list(_HEADING_RE.finditer(markdown))

    if not matches:
        return [("", markdown)]

    # Başlık öncesi içerik
    pre = markdown[: matches[0].start()].strip()
    if pre:
        sections.append(("", pre))

    for i, match in enumerate(matches):
        heading = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        content = markdown[start:end].strip()
        if content:
            sections.append((heading, content))

    return sections


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc or "belek.edu.tr"
    except Exception:
        return "belek.edu.tr"


class SemanticChunker:
    """
    Başlık hiyerarşisi bazlı semantik chunker.

    Args:
        chunk_size:    Maksimum karakter sayısı (varsayılan 800).
        chunk_overlap: Chunk'lar arası örtüşme (varsayılan 150).
        min_chars:     Bu uzunluktan kısa chunk'lar atlanır (varsayılan 80).
    """

    def __init__(
        self,
        chunk_size: int = 800,
        chunk_overlap: int = 150,
        min_chars: int = 80,
    ) -> None:
        self.min_chars = min_chars
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            keep_separator=False,
        )

    def chunk(self, doc: dict) -> list[ChunkV2]:
        """
        Ham belge dict'ini ChunkV2 listesine dönüştür.

        doc anahtarları: url, title, markdown_body, fmt, category,
                         doc_category, crawled_at, last_updated,
                         content_hash, access_level, is_active
        """
        raw_md = unicodedata.normalize("NFC", doc.get("markdown_body", ""))
        sections = _extract_sections(raw_md)

        chunks: list[ChunkV2] = []
        chunk_idx = 0
        page_counter: dict[str, int] = {}   # Section → sayfa tahmini (PDF)

        for heading, content in sections:
            splits = self._splitter.split_text(content)
            for split in splits:
                text = split.strip()
                if len(text) < self.min_chars:
                    continue

                # "[Konu: heading]\n" ön eki — v1 ile uyumlu
                prefix = f"[Konu: {heading}]\n" if heading else ""
                full_text = prefix + text

                chunks.append(ChunkV2(
                    text=full_text,
                    chunk_idx=chunk_idx,
                    doc_chunks=0,             # Sonradan doldurulur
                    url=doc.get("url", ""),
                    source_url=doc.get("source_url", doc.get("url", "")),
                    title=doc.get("title", ""),
                    fmt=doc.get("fmt", "html"),
                    section=heading,
                    page=None,                # PDF sayfaları Docling metadata'sından alınabilir
                    category=doc.get("category", "genel"),
                    doc_category=doc.get("doc_category", "genel"),
                    source=_domain(doc.get("url", "")),
                    crawled_at=doc.get("crawled_at", ""),
                    last_updated=doc.get("last_updated", ""),
                    content_hash=doc.get("content_hash", ""),
                    is_active=doc.get("is_active", True),
                    access_level=doc.get("access_level", "public"),
                ))
                chunk_idx += 1

        # doc_chunks alanını geriye dönük doldur
        total = len(chunks)
        for ch in chunks:
            ch.doc_chunks = total

        return chunks
