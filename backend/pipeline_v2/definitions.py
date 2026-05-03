"""
Dagster Definitions — Pipeline V2 ana giriş noktası.

workspace.yaml bu modülü yükler:
  load_from:
    - python_module:
        module_name: backend.pipeline_v2.definitions
        working_directory: .

Başlatma:
  dagster dev -w workspace.yaml
"""
import os

from dagster import Definitions

from .assets import (
    approved_preview_index,
    cleaned_documents,
    document_hashes,
    qdrant_collection,
    raw_local_documents,
    raw_pdf_documents,
    raw_preview_dump,
    raw_web_pages,
    semantic_chunks,
)
from .config_v2 import BELEK_CONFIG_V2
from .jobs import full_pipeline_job, incremental_job
from .resources import EmbeddingResource, FirecrawlResource, QdrantResource

_resources = {
    "firecrawl": FirecrawlResource(
        api_key=os.environ.get("FIRECRAWL_API_KEY", ""),
        only_main_content=True,
        timeout=60.0,
    ),
    "qdrant": QdrantResource(
        host=os.environ.get("QDRANT_HOST", BELEK_CONFIG_V2.qdrant_host),
        port=int(os.environ.get("QDRANT_PORT", str(BELEK_CONFIG_V2.qdrant_port))),
        path=os.environ.get("QDRANT_PATH", ""),
    ),
    "embedding": EmbeddingResource(
        model_name=BELEK_CONFIG_V2.embedding_model,
        batch_size=BELEK_CONFIG_V2.embed_batch_size,
        device="cpu",
    ),
}

defs = Definitions(
    assets=[
        raw_web_pages,
        raw_pdf_documents,
        raw_local_documents,
        raw_preview_dump,
        document_hashes,
        approved_preview_index,
        cleaned_documents,
        semantic_chunks,
        qdrant_collection,
    ],
    resources=_resources,
    jobs=[
        full_pipeline_job,
        incremental_job,
    ],
)
