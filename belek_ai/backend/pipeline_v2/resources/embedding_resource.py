"""
Embedding Resource — Singleton HuggingFace model wrapper.

Dagster ConfigurableResource olarak tanımlandığında pipeline boyunca
tek bir model örneği paylaşılır (bellek tasarrufu).
"""
from __future__ import annotations

import logging
from typing import Any

from dagster import ConfigurableResource

logger = logging.getLogger(__name__)


class EmbeddingResource(ConfigurableResource):
    """
    sentence-transformers modeli için Dagster resource.

    Config:
        model_name: HuggingFace model adı.
        batch_size:  Embedding batch boyutu.
        device:      "cpu" | "cuda" | "mps" (auto-detect için "auto").
    """

    model_name: str = (
        "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    )
    batch_size: int = 64
    device: str = "cpu"

    # _model iç state — Dagster resource lifecycle'da yönetilir
    _model: Any = None

    def _get_model(self):
        """Lazy-load: ilk çağrıda modeli yükle, sonrasında cache'ten döner."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            dev = self.device
            if dev == "auto":
                import torch
                dev = "cuda" if torch.cuda.is_available() else "cpu"

            logger.info("Embedding modeli yükleniyor: %s (%s)", self.model_name, dev)
            self._model = SentenceTransformer(self.model_name, device=dev)
            logger.info("Embedding modeli hazır.")
        return self._model

    def encode(self, texts: list[str]) -> list[list[float]]:
        """
        Metinleri yoğun vektöre dönüştür.

        Returns:
            list[list[float]] — her metin için 768-boyutlu vektör.
        """
        model = self._get_model()
        vectors = model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,  # Cosine için L2 normalize
        )
        return [v.tolist() for v in vectors]

    def encode_one(self, text: str) -> list[float]:
        """Tek metin için kısayol."""
        return self.encode([text])[0]
