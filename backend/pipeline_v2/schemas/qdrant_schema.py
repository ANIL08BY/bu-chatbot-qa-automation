"""
Qdrant Collection Şeması — belek_v2.

Named vectors:
  - "dense"  : 768-boyutlu yoğun vektör (HuggingFace multilingual-mpnet)
  - "sparse" : BM42 seyrek vektör (Qdrant built-in keyword arama)

Payload index'ler hızlı filtreleme için tanımlanır.

Kullanım:
    from backend.pipeline_v2.schemas.qdrant_schema import create_collection_if_not_exists
    create_collection_if_not_exists(client, "belek_v2")
"""
from __future__ import annotations

import logging

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    HnswConfigDiff,
    OptimizersConfigDiff,
    PayloadSchemaType,
    SparseIndexParams,
    SparseVectorParams,
    VectorParams,
)

logger = logging.getLogger(__name__)

COLLECTION_NAME = "belek_v2"
DENSE_VECTOR_SIZE = 768
DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"

# Filtrelenecek payload alanları ve index türleri
_PAYLOAD_INDEXES: dict[str, PayloadSchemaType] = {
    "doc_category":  PayloadSchemaType.KEYWORD,
    "fmt":           PayloadSchemaType.KEYWORD,
    "is_active":     PayloadSchemaType.BOOL,
    "access_level":  PayloadSchemaType.KEYWORD,
    "source":        PayloadSchemaType.KEYWORD,
    "crawled_at":    PayloadSchemaType.DATETIME,
    "last_updated":  PayloadSchemaType.DATETIME,
}


def create_collection_if_not_exists(
    client: QdrantClient,
    collection_name: str = COLLECTION_NAME,
) -> bool:
    """
    Collection yoksa oluşturur; varsa dokunmaz (idempotent).

    Returns:
        True  → yeni oluşturuldu
        False → zaten vardı
    """
    existing = {c.name for c in client.get_collections().collections}
    if collection_name in existing:
        logger.info("Collection zaten mevcut: %s", collection_name)
        return False

    logger.info("Collection oluşturuluyor: %s", collection_name)

    client.create_collection(
        collection_name=collection_name,
        vectors_config={
            DENSE_VECTOR_NAME: VectorParams(
                size=DENSE_VECTOR_SIZE,
                distance=Distance.COSINE,
                on_disk=False,
            ),
        },
        sparse_vectors_config={
            SPARSE_VECTOR_NAME: SparseVectorParams(
                index=SparseIndexParams(
                    on_disk=False,
                ),
                modifier="idf",   # BM42 IDF ağırlıklandırması
            ),
        },
        hnsw_config=HnswConfigDiff(
            m=16,
            ef_construct=100,
            full_scan_threshold=10_000,
        ),
        optimizers_config=OptimizersConfigDiff(
            default_segment_number=2,
            max_optimization_threads=1,
        ),
    )

    # Payload index'leri oluştur
    _create_payload_indexes(client, collection_name)

    logger.info("Collection hazır: %s", collection_name)
    return True


def _create_payload_indexes(
    client: QdrantClient,
    collection_name: str,
) -> None:
    """Payload alanları için index tanımla."""
    for field_name, schema_type in _PAYLOAD_INDEXES.items():
        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=schema_type,
            )
            logger.debug("Payload index oluşturuldu: %s", field_name)
        except Exception as exc:
            # Index zaten varsa sessizce geç
            logger.debug("Payload index atlandı (%s): %s", field_name, exc)


def get_collection_info(
    client: QdrantClient,
    collection_name: str = COLLECTION_NAME,
) -> dict:
    """Collection istatistiklerini döndür."""
    try:
        info = client.get_collection(collection_name)
        return {
            "name": collection_name,
            "points_count": info.points_count,
            "vectors_count": info.vectors_count,
            "status": str(info.status),
        }
    except Exception as exc:
        return {"error": str(exc)}
