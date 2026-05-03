"""
Belge bölümleme (chunking).

Strateji:
  1. Metnini ## / ### başlıklarına göre bölümlere ayır
  2. Her bölümü RecursiveCharacterTextSplitter ile boyutuna göre böl
  3. Her chunk'a üst bölüm başlığını bağlam olarak ekle
  4. Zengin metadata: url, title, fmt, section, page, chunk_idx, doc_chunks
"""
from __future__ import annotations

import re
from datetime import datetime

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .config import PipelineConfig
from .extract import RawDocument


# ---------------------------------------------------------------------------
# Başlık tabanlı bölüm ayırıcı
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^(#{1,3}) (.+)$", re.MULTILINE)


def _split_by_headings(text: str) -> list[tuple[str, str]]:
    """
    Metni ## / ### başlıklarına göre (başlık, içerik) çiftlerine böl.

    Başlıksız ön metin varsa ("", içerik) olarak eklenir.
    """
    sections: list[tuple[str, str]] = []
    current_heading = ""
    current_lines:  list[str] = []

    for line in text.split("\n"):
        m = _HEADING_RE.match(line)
        if m:
            if current_lines:
                body = "\n".join(current_lines).strip()
                if body:
                    sections.append((current_heading, body))
            current_heading = m.group(2).strip()
            current_lines   = []
        else:
            current_lines.append(line)

    if current_lines:
        body = "\n".join(current_lines).strip()
        if body:
            sections.append((current_heading, body))

    # Hiç başlık bulunamadıysa tüm metin tek bölüm
    if not sections:
        sections = [("", text)]

    return sections


# ---------------------------------------------------------------------------
# DocumentChunker
# ---------------------------------------------------------------------------

class DocumentChunker:
    def __init__(self, cfg: PipelineConfig) -> None:
        self.cfg = cfg
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=cfg.chunk_size,
            chunk_overlap=cfg.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            add_start_index=False,
        )

    def chunk(self, docs: list[RawDocument]) -> list[Document]:
        today      = datetime.now().strftime("%Y-%m-%d")
        all_chunks: list[Document] = []

        for doc in docs:
            chunks = self._chunk_one(doc, today)
            all_chunks.extend(chunks)

        print(f"  Chunking: {len(docs)} belge → {len(all_chunks)} chunk")
        return all_chunks

    def _chunk_one(self, doc: RawDocument, date: str) -> list[Document]:
        sections = _split_by_headings(doc.body)
        chunks:  list[Document] = []

        for section_heading, section_body in sections:
            if not section_body.strip():
                continue

            sub_texts = self.splitter.split_text(section_body)

            for sub in sub_texts:
                sub = sub.strip()
                if not sub:
                    continue

                # Bölüm başlığını chunk başına bağlam olarak ekle
                if section_heading:
                    content = f"[Konu: {section_heading}]\n{sub}"
                else:
                    content = sub

                metadata: dict = {
                    "url":        doc.url,
                    "title":      doc.title,
                    "fmt":        doc.fmt,
                    "section":    section_heading,
                    "page":       doc.metadata.get("page"),
                    "chunk_idx":  len(chunks),
                    "source":     doc.metadata.get("source", "belek.edu.tr"),
                    "category":   doc.metadata.get("category", "genel"),
                    "crawled_at": date,
                }
                chunks.append(Document(page_content=content, metadata=metadata))

        # doc_chunks: bu belgeden kaç chunk üretildi
        for ch in chunks:
            ch.metadata["doc_chunks"] = len(chunks)

        return chunks
