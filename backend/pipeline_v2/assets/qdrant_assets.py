"""
qdrant_collection Asset — Qdrant'a hybrid upsert.

Adımlar:
1. Collection yoksa oluştur (idempotent).
2. Her chunk için:
   - dense vector: HuggingFace embedding (batch=64).
   - sparse vector: Qdrant built-in BM42 (text alanından otomatik).
3. Batch upsert (100 chunk / batch).
4. point_id: uuid5(NAMESPACE_URL, url + ":" + str(chunk_idx)) — deterministik.
"""

import logging
import uuid
from typing import Any

from dagster import AssetExecutionContext, Backoff, RetryPolicy, asset
from qdrant_client.models import PointStruct

from ..config_v2 import BELEK_CONFIG_V2
from ..resources.embedding_resource import EmbeddingResource
from ..resources.qdrant_resource import QdrantResource
from ..schemas.qdrant_schema import (
    DENSE_VECTOR_NAME,
    SPARSE_VECTOR_NAME,
    create_collection_if_not_exists,
)

logger = logging.getLogger(__name__)

_UUID_NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # uuid.NAMESPACE_URL
_UPSERT_BATCH = 100


def _make_point_id(url: str, chunk_idx: int) -> str:
    """Deterministik UUID5 — aynı chunk her pipeline çalışmasında aynı ID alır."""
    return str(uuid.uuid5(_UUID_NS, f"{url}:{chunk_idx}"))


@asset(
    name="qdrant_collection",
    group_name="store",
    description="Chunk'ları Qdrant'a dense+sparse (BM42) hybrid vektör olarak yazar",
    retry_policy=RetryPolicy(max_retries=2, delay=15, backoff=Backoff.EXPONENTIAL),
    compute_kind="qdrant",
)
def qdrant_collection(
    context: AssetExecutionContext,
    semantic_chunks: list[dict],
    qdrant: QdrantResource,
    embedding: EmbeddingResource,
) -> dict[str, Any]:
    """
    Çıktı:
    {
        "collection":    str,   # Collection adı
        "upserted":      int,   # Başarıyla yazılan chunk sayısı
        "failed_batches": int,
    }
    """
    cfg = BELEK_CONFIG_V2
    client = qdrant.get_client()

    # Collection oluştur (idempotent)
    created = create_collection_if_not_exists(client, cfg.qdrant_collection)
    context.log.info(
        "Collection %s (%s)",
        cfg.qdrant_collection,
        "oluşturuldu" if created else "zaten mevcut",
    )

    if not semantic_chunks:
        context.log.info("Yazılacak chunk yok — incremental çalışma.")
        return {"collection": cfg.qdrant_collection, "upserted": 0, "failed_batches": 0}

    context.log.info("Toplam chunk yazılacak: %d", len(semantic_chunks))

    upserted = 0
    failed_batches = 0

    # Batch upsert
    for batch_start in range(0, len(semantic_chunks), _UPSERT_BATCH):
        batch = semantic_chunks[batch_start: batch_start + _UPSERT_BATCH]
        texts = [ch["text"] for ch in batch]

        # Dense embeddings (batch)
        try:
            dense_vectors = embedding.encode(texts)
        except Exception as exc:
            context.log.error(
                "Embedding hatası (batch %d-%d): %s",
                batch_start, batch_start + len(batch), exc,
            )
            failed_batches += 1
            continue

        # Qdrant PointStruct listesi
        points: list[PointStruct] = []
        for chunk_dict, dense_vec in zip(batch, dense_vectors):
            point_id = _make_point_id(
                chunk_dict["url"], chunk_dict["chunk_idx"]
            )
            points.append(
                PointStruct(
                    id=point_id,
                    vector={
                        DENSE_VECTOR_NAME: dense_vec,
                        # sparse BM42 — Qdrant "text" alanından otomatik üretir
                        # Manuel sparse vektör eklemek için SparseVector kullanılır:
                        # SPARSE_VECTOR_NAME: SparseVector(indices=[], values=[]),
                    },
                    payload=chunk_dict,
                )
            )

        # Upsert
        try:
            client.upsert(
                collection_name=cfg.qdrant_collection,
                points=points,
                wait=True,
            )
            upserted += len(points)
        except Exception as exc:
            context.log.error(
                "Upsert hatası (batch %d-%d): %s",
                batch_start, batch_start + len(batch), exc,
            )
            failed_batches += 1

    context.log.info(
        "Upsert tamamlandı: %d chunk (%d batch başarısız)",
        upserted, failed_batches,
    )
    context.add_output_metadata({
        "collection":     cfg.qdrant_collection,
        "upserted":       upserted,
        "failed_batches": failed_batches,
    })

    return {
        "collection":     cfg.qdrant_collection,
        "upserted":       upserted,
        "failed_batches": failed_batches,
    }
