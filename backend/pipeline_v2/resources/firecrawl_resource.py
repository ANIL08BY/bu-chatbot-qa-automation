"""
Firecrawl Resource — Firecrawl API istemcisi.

Hem doğrudan API çağrısı hem de firecrawl-py SDK sarmalayıcısı.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from dagster import ConfigurableResource

logger = logging.getLogger(__name__)


class FirecrawlResource(ConfigurableResource):
    """
    Firecrawl API bağlantı resource'u.

    Config:
        api_key:      Firecrawl API key (FIRECRAWL_API_KEY env var'dan okunur).
        api_url:      Firecrawl API base URL.
        timeout:      İstek timeout (saniye).
        only_main_content: Boilerplate kaldırma (varsayılan True).
    """

    api_key: str = ""
    api_url: str = "https://api.firecrawl.dev"
    timeout: float = 60.0
    only_main_content: bool = True

    def _get_api_key(self) -> str:
        key = self.api_key or os.environ.get("FIRECRAWL_API_KEY", "")
        if not key:
            raise RuntimeError(
                "FIRECRAWL_API_KEY bulunamadı. "
                ".env dosyasına FIRECRAWL_API_KEY ekleyin."
            )
        return key

    def scrape(self, url: str) -> dict[str, Any] | None:
        """
        Tek URL'yi Markdown olarak çek.

        Returns:
            {"title": str, "markdown": str} veya None (hata durumunda).
        """
        try:
            from firecrawl import FirecrawlApp

            app = FirecrawlApp(api_key=self._get_api_key())
            result = app.scrape_url(
                url,
                params={
                    "formats": ["markdown"],
                    "onlyMainContent": self.only_main_content,
                    "removeBase64Images": True,
                },
            )
            if not result or not result.get("markdown"):
                logger.warning("Firecrawl boş sonuç: %s", url)
                return None

            return {
                "title": (result.get("metadata") or {}).get("title", ""),
                "markdown": result["markdown"],
            }

        except Exception as exc:
            logger.error("Firecrawl hatası [%s]: %s", url, exc)
            return None

    def map(
        self,
        url: str,
        limit: int = 200,
        include_subdomains: bool = False,
        ignore_sitemap: bool = False,
        search: str = "",
    ) -> list[str]:
        """
        Bir URL'deki tüm linkleri keşfet (içerik çekmez, sadece URL listesi).

        Firecrawl /v1/map endpoint'ini kullanır.

        Args:
            url:               Taranacak kök URL.
            limit:             Maksimum link sayısı (varsayılan 200).
            include_subdomains: Alt alan adlarını dahil et.
            ignore_sitemap:    sitemap.xml'i yoksay.
            search:            Opsiyonel anahtar kelime filtresi (URL içinde arar).

        Returns:
            list[str] — bulunan URL'ler (boş liste hata durumunda).
        """
        import httpx

        api_key = self._get_api_key()
        payload: dict[str, Any] = {
            "url": url,
            "limit": limit,
            "includeSubdomains": include_subdomains,
            "ignoreSitemap": ignore_sitemap,
        }
        if search:
            payload["search"] = search

        try:
            with httpx.Client(
                base_url=self.api_url,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=self.timeout,
            ) as client:
                resp = client.post("/v1/map", json=payload)
                resp.raise_for_status()
                data = resp.json()

            if not data.get("success"):
                logger.warning("Firecrawl map başarısız [%s]: %s", url, data)
                return []

            links: list[str] = data.get("links", [])
            logger.info("Map tamamlandı [%s]: %d link", url, len(links))
            return links

        except Exception as exc:
            logger.error("Firecrawl map hatası [%s]: %s", url, exc)
            return []

    def scrape_batch(
        self,
        urls: list[str],
        concurrency: int = 5,
    ) -> dict[str, dict[str, Any] | None]:
        """
        Birden fazla URL'yi paralel çek.

        Returns:
            {url: {"title": str, "markdown": str} | None}
        """
        import asyncio
        import sys

        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        results: dict[str, dict | None] = {}

        async def _run() -> None:
            import httpx

            sem = asyncio.Semaphore(concurrency)
            api_key = self._get_api_key()

            async with httpx.AsyncClient(
                base_url=self.api_url,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=httpx.Timeout(connect=10.0, read=self.timeout, write=10.0, pool=5.0),
            ) as client:
                tasks = [_fetch(client, sem, url) for url in urls]
                fetched = await asyncio.gather(*tasks, return_exceptions=True)
                for url, doc in zip(urls, fetched):
                    results[url] = None if isinstance(doc, Exception) else doc

        async def _fetch(
            client,
            sem: asyncio.Semaphore,
            url: str,
        ) -> dict | None:
            async with sem:
                payload = {
                    "url": url,
                    "formats": ["markdown"],
                    "onlyMainContent": self.only_main_content,
                    "removeBase64Images": True,
                }
                for attempt in range(3):
                    try:
                        resp = await client.post("/v1/scrape", json=payload)
                        resp.raise_for_status()
                        data = resp.json()
                        if not data.get("success"):
                            return None
                        md = (data.get("data") or {}).get("markdown", "")
                        title = ((data.get("data") or {}).get("metadata") or {}).get("title", "")
                        return {"title": title, "markdown": md} if md.strip() else None
                    except Exception as exc:
                        msg = str(exc)
                        if "429" in msg or "rate_limit" in msg.lower():
                            await asyncio.sleep(2 ** attempt * 5)
                            continue
                        logger.error("Fetch hatası [%s] deneme %d: %s", url, attempt + 1, exc)
                        if attempt < 2:
                            await asyncio.sleep(2 ** attempt)
                return None

        asyncio.run(_run())
        return results
