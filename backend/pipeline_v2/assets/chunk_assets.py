"""
semantic_chunks Asset — Başlık hiyerarşisi bazlı semantik chunking.

Temizlenmiş Markdown belgelerini ChunkV2 listesine dönüştürür.
"""
import logging

from dagster import AssetExecutionContext, asset

from ..chunker import SemanticChunker
from ..config_v2 import BELEK_CONFIG_V2
from ..models import ChunkV2

logger = logging.getLogger(__name__)


@asset(
    name="semantic_chunks",
    group_name="transform",
    description="Başlık hiyerarşisine dayalı semantik chunking uygular",
    compute_kind="python",
)
def semantic_chunks(
    context: AssetExecutionContext,
    cleaned_documents: list[dict],
) -> list[dict]:
    """
    Çıktı: list[dict] — ChunkV2.to_payload() formatı (Qdrant'a yazılmaya hazır).
    """
    cfg = BELEK_CONFIG_V2
    chunker = SemanticChunker(
        chunk_size=cfg.chunk_size,
        chunk_overlap=cfg.chunk_overlap,
    )

    context.log.info("Chunk'lanacak belge: %d", len(cleaned_documents))

    all_chunks: list[dict] = []
    total_docs = 0
    short_docs = 0

    for doc in cleaned_documents:
        chunks: list[ChunkV2] = chunker.chunk(doc)
        if not chunks:
            short_docs += 1
            context.log.debug("Chunk üretilemedi: %s", doc.get("url", "?"))
            continue

        total_docs += 1
        for ch in chunks:
            all_chunks.append(ch.to_payload())

    context.log.info(
        "Toplam chunk: %d (%d belgeden, %d belge atlandı)",
        len(all_chunks), total_docs, short_docs,
    )
    context.add_output_metadata({
        "total_chunks":   len(all_chunks),
        "total_docs":     total_docs,
        "skipped_docs":   short_docs,
        "avg_chunks_per_doc": round(len(all_chunks) / max(total_docs, 1), 1),
    })
    return all_chunks
