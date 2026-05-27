"""
Qdrant Resource — QdrantClient wrapper.

Dagster ConfigurableResource olarak pipeline boyunca tek bağlantı kullanılır.

Dört mod (otomatik seçim — öncelik sırası):
  url="https://..."  → Cloud (Qdrant Cloud / özel URL); api_key ile birlikte kullanın.
  host=":memory:"    → In-memory (test, veri kalıcı değil)
  path="./qdrant"    → Yerel disk (Docker/binary gerekmez, kalıcı)
  host="localhost"   → Uzak sunucu (Docker / Qdrant binary)
"""

from __future__ import annotations

import logging
import os
from typing import Any

from dagster import ConfigurableResource

logger = logging.getLogger(__name__)


class QdrantResource(ConfigurableResource):
    """
    Qdrant bağlantı resource'u.

    Config:
        url:     Cloud/özel URL (örn: "https://xxx.qdrant.io"). Dolu ise diğer alanlar yok sayılır.
        api_key: Cloud API anahtarı (url ile birlikte kullanılır).
        host:    Qdrant sunucu adresi. ":memory:" → in-memory mod (test).
        port:    HTTP port (varsayılan: 6333).
        path:    Yerel disk modu için dizin yolu (örn: "./qdrant_local").
                 Dolu ise Docker/binary gerekmez; veri kalıcıdır.
        timeout: Bağlantı timeout (saniye).

    Mod önceliği: url (cloud) > ":memory:" > path (dolu) > host:port
    """

    url: str = ""  # Cloud URL — dolu ise cloud modu
    api_key: str = ""  # Cloud API key
    host: str = "localhost"
    port: int = 6333
    path: str = ""  # Dolu ise yerel disk modu
    timeout: float = 30.0

    _client: Any = None

    def get_client(self):
        """Lazy-load QdrantClient — mod otomatik tespit edilir."""
        if self._client is None:
            from qdrant_client import QdrantClient

            if self.url:
                logger.info("Qdrant Cloud modunda: %s", self.url)
                self._client = QdrantClient(
                    url=self.url,
                    api_key=self.api_key or None,
                )

            elif self.host == ":memory:":
                logger.info("Qdrant in-memory modunda başlatılıyor (test).")
                self._client = QdrantClient(":memory:")

            elif self.path:
                logger.info("Qdrant yerel disk modunda: %s", self.path)
                os.makedirs(self.path, exist_ok=True)
                self._client = QdrantClient(path=self.path)

            else:
                logger.info("Qdrant sunucuya bağlanılıyor: %s:%d", self.host, self.port)
                self._client = QdrantClient(
                    host=self.host,
                    port=self.port,
                    timeout=self.timeout,
                )

            logger.info("Qdrant hazır.")
        return self._client

    def health_check(self) -> bool:
        """Bağlantıyı test et."""
        try:
            self.get_client().get_collections()
            return True
        except Exception as exc:
            logger.error("Qdrant bağlantı hatası: %s", exc)
            return False
