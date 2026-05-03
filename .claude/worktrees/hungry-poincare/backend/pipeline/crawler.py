"""
Asenkron BFS Web Crawler — pipeline v2

Özellikler:
  - HTML, PDF, DOCX indirme + inline extraction
  - Checkpoint: her N sayfada state.json + documents.jsonl güncellenir
  - Ctrl+C → checkpoint kaydeder, --resume ile devam edilir
  - Atomic checkpoint yazma (.tmp → rename)
  - PDF streaming + HEAD boyut kontrolü
  - pypdf/pdfplumber için thread-pool + hard timeout
  - robots.txt uyumu
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import signal
import sys
from collections import deque
from datetime import datetime
from urllib.parse import urljoin, urldefrag, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from .config import PipelineConfig, TargetSource
from .extract import (
    RawDocument,
    HTMLExtractor,
    PDFExtractor,
    DOCXExtractor,
    _url_ext,
)

# Checkpoint dosya adları (cache_dir içinde)
_STATE_FILE = "state.json"
_DOCS_FILE  = "documents.jsonl"

_PDF_EXTS  = frozenset({".pdf"})
_DOCX_EXTS = frozenset({".docx"})


# ---------------------------------------------------------------------------
# Checkpoint I/O (modül seviyesi — bağımsız fonksiyonlar)
# ---------------------------------------------------------------------------

def _save_state(
    cache_dir: str,
    visited:   set[str],
    queue:     deque[tuple[str, int]],
) -> None:
    os.makedirs(cache_dir, exist_ok=True)
    data = {
        "saved_at":    datetime.now().isoformat(timespec="seconds"),
        "pages":       len(visited),
        "queue_len":   len(queue),
        "visited":     list(visited),
        "queue":       [[u, d] for u, d in queue],
    }
    _atomic_write(os.path.join(cache_dir, _STATE_FILE), data)


def _load_state(
    cache_dir: str,
) -> tuple[set[str], deque[tuple[str, int]]] | None:
    path = os.path.join(cache_dir, _STATE_FILE)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        visited = set(data["visited"])
        queue   = deque((item[0], item[1]) for item in data["queue"])
        print(
            f"  Checkpoint yüklendi ({data['saved_at']}): "
            f"{len(visited)} ziyaret, {data['queue_len']} URL kuyrukta"
        )
        return visited, queue
    except Exception as exc:
        print(f"  ⚠  Checkpoint okunamadı, baştan başlanıyor: {exc}")
        return None


def _append_doc(cache_dir: str, doc: RawDocument) -> None:
    """documents.jsonl'ye yeni satır ekle."""
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, _DOCS_FILE)
    line = json.dumps(
        {
            "url":      doc.url,
            "title":    doc.title,
            "body":     doc.body,
            "fmt":      doc.fmt,
            "metadata": doc.metadata,
        },
        ensure_ascii=False,
    )
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_documents(cache_dir: str) -> list[RawDocument]:
    """documents.jsonl'yi okuyup RawDocument listesi döndür."""
    path = os.path.join(cache_dir, _DOCS_FILE)
    if not os.path.exists(path):
        return []
    docs: list[RawDocument] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                docs.append(
                    RawDocument(
                        url=d["url"],
                        title=d["title"],
                        body=d["body"],
                        fmt=d["fmt"],
                        metadata=d.get("metadata", {}),
                    )
                )
            except Exception:
                continue
    return docs


def _atomic_write(path: str, data: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


def clear_cache(cache_dir: str) -> None:
    """Checkpoint ve doküman dosyalarını sil."""
    for fname in (_STATE_FILE, _DOCS_FILE, _STATE_FILE + ".tmp"):
        p = os.path.join(cache_dir, fname)
        if os.path.exists(p):
            os.remove(p)


# ---------------------------------------------------------------------------
# WebCrawler
# ---------------------------------------------------------------------------

class WebCrawler:
    def __init__(self, cfg: PipelineConfig) -> None:
        self.cfg  = cfg
        self._skip_re    = [re.compile(p, re.I) for p in cfg.skip_patterns]
        self._prio_re    = [re.compile(p, re.I) for p in cfg.priority_patterns]
        self._robots_cache: dict[str, RobotFileParser] = {}
        self._stop = False

        self._html_ext = HTMLExtractor()
        self._pdf_ext  = PDFExtractor()
        self._docx_ext = DOCXExtractor()

    # ── URL yardımcıları ──────────────────────────────────────────────────

    def _norm(self, url: str) -> str:
        url, _ = urldefrag(url)
        return url.rstrip("/")

    def _in_domain(self, url: str) -> bool:
        netloc = urlparse(url).netloc.lower()
        return any(
            netloc == d or netloc.endswith("." + d)
            for d in self.cfg.allowed_domains
        )

    def _skip(self, url: str) -> bool:
        return any(rx.search(url) for rx in self._skip_re)

    def _priority(self, url: str) -> bool:
        return any(rx.search(url) for rx in self._prio_re)

    # ── robots.txt ───────────────────────────────────────────────────────

    async def _robots(self, url: str, client: httpx.AsyncClient) -> RobotFileParser:
        p = urlparse(url)
        robots_url = f"{p.scheme}://{p.netloc}/robots.txt"
        if robots_url in self._robots_cache:
            return self._robots_cache[robots_url]
        rp = RobotFileParser()
        rp.set_url(robots_url)
        try:
            r = await client.get(robots_url, timeout=8)
            rp.parse(r.text.splitlines())
        except Exception:
            pass
        self._robots_cache[robots_url] = rp
        return rp

    def _allowed(self, rp: RobotFileParser, url: str) -> bool:
        try:
            return rp.can_fetch(self.cfg.user_agent, url)
        except Exception:
            return True

    # ── Link çıkarma ─────────────────────────────────────────────────────

    def _links(self, html: str, base: str) -> list[str]:
        soup = BeautifulSoup(html, "lxml")
        links: list[str] = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith(("mailto:", "tel:", "javascript:", "#")):
                continue
            full = self._norm(urljoin(base, href))
            if full.startswith("http"):
                links.append(full)
        return links

    # ── Streaming PDF indirme ─────────────────────────────────────────────

    async def _stream_bytes(
        self,
        client: httpx.AsyncClient,
        url:    str,
        label:  str = "dosya",
    ) -> bytes | None:
        max_bytes = self.cfg.max_pdf_size_mb * 1024 * 1024

        # HEAD ön kontrolü
        try:
            head = await client.head(url, timeout=8)
            cl   = head.headers.get("content-length")
            if cl and int(cl) > max_bytes:
                size_mb = int(cl) / 1024 / 1024
                print(f"  ⊘ {label} çok büyük (HEAD: {size_mb:.1f} MB), atlandı: {url}")
                return None
        except Exception:
            pass

        chunks: list[bytes] = []
        total  = 0
        try:
            t = httpx.Timeout(connect=10.0, read=45.0, write=10.0, pool=5.0)
            async with client.stream("GET", url, timeout=t) as resp:
                resp.raise_for_status()
                async for chunk in resp.aiter_bytes(65_536):
                    total += len(chunk)
                    if total > max_bytes:
                        print(f"  ⊘ {label} akışta boyut aşıldı ({total/1024/1024:.1f} MB): {url}")
                        return None
                    chunks.append(chunk)
        except httpx.TimeoutException:
            print(f"  ✗ Timeout ({label}): {url}")
            return None
        except Exception as exc:
            print(f"  ✗ İndirme hatası ({label}): {url} → {exc}")
            return None

        return b"".join(chunks)

    # ── Thread-pool'da extraction (blocking kod için) ─────────────────────

    async def _safe_extract_binary(
        self,
        extractor,
        raw: bytes,
        url: str,
        timeout: float,
    ) -> RawDocument | None:
        loop = asyncio.get_event_loop()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(None, extractor.extract, raw, url),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            print(f"  ⊘ Extraction timeout ({timeout}s): {url}")
            return None
        except Exception as exc:
            print(f"  ✗ Extraction hatası: {url} → {exc}")
            return None

    # ── HTTP fetch (retry) ────────────────────────────────────────────────

    async def _fetch(
        self,
        client: httpx.AsyncClient,
        url: str,
    ) -> httpx.Response | None:
        t = httpx.Timeout(
            connect=8.0,
            read=float(self.cfg.timeout_seconds),
            write=8.0,
            pool=5.0,
        )
        for attempt in range(self.cfg.max_retries + 1):
            try:
                r = await client.get(url, timeout=t)
                r.raise_for_status()
                return r
            except httpx.HTTPStatusError as exc:
                code = exc.response.status_code
                if code in (404, 410, 403, 401):
                    print(f"  ✗ HTTP {code}: {url}")
                    return None
                print(f"  ✗ HTTP {code} (deneme {attempt + 1}): {url}")
            except httpx.TimeoutException:
                print(f"  ✗ Timeout (deneme {attempt + 1}): {url}")
            except Exception as exc:
                print(f"  ✗ Hata (deneme {attempt + 1}): {url} → {exc}")
            if attempt < self.cfg.max_retries:
                await asyncio.sleep(2 ** attempt)
        return None

    # ── Ana crawl döngüsü ─────────────────────────────────────────────────

    async def crawl(self, resume: bool = False) -> list[RawDocument]:
        """
        BFS crawl.

        resume=True  → state.json varsa kaldığı yerden devam et.
        resume=False → state.json yoksa baştan başla.

        Her cfg.checkpoint_interval sayfada state.json güncellenir.
        Yeni belgeler documents.jsonl'ye anlık eklenir.
        Ctrl+C → state.json kaydedilir, sonraki çalıştırmada --resume ile devam.
        """
        cache_dir = self.cfg.cache_dir
        os.makedirs(cache_dir, exist_ok=True)

        # State yükle veya sıfırla
        loaded = _load_state(cache_dir) if resume else None
        if loaded:
            visited, queue = loaded
        else:
            visited: set[str]              = set()
            queue:   deque[tuple[str, int]] = deque()
            for seed in self.cfg.seed_urls:
                queue.append((self._norm(seed), 0))

        # Daha önce kaydedilmiş belgeleri yükle
        results: list[RawDocument] = load_documents(cache_dir) if resume else []

        limit_str = str(self.cfg.max_pages) if self.cfg.max_pages else "∞"

        # ── Ctrl+C handler ────────────────────────────────────────────────
        def _on_sigint(sig, frame):
            if not self._stop:
                print(
                    "\n\n  ⚠  Ctrl+C — mevcut işlem bitince duruluyor...\n"
                    "     (Tekrar Ctrl+C → anında çıkış)\n"
                )
                self._stop = True
            else:
                _save_state(cache_dir, visited, queue)
                print("\n  Zorla çıkılıyor.")
                sys.exit(1)

        original = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, _on_sigint)

        def _checkpoint(label: str = "") -> None:
            _save_state(cache_dir, visited, queue)
            if label:
                print(
                    f"  💾 Checkpoint{label}: "
                    f"{len(visited)} ziyaret, {len(results)} belge"
                )

        def _under_limit() -> bool:
            return self.cfg.max_pages == 0 or len(visited) < self.cfg.max_pages

        try:
            async with httpx.AsyncClient(
                headers={
                    "User-Agent":      self.cfg.user_agent,
                    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
                },
                follow_redirects=True,
            ) as client:

                # robots.txt ön-yükleme
                for seed in self.cfg.seed_urls:
                    await self._robots(seed, client)

                while queue and _under_limit() and not self._stop:
                    url, depth = queue.popleft()

                    if url in visited:
                        continue
                    if depth > self.cfg.max_depth:
                        continue
                    if not self._in_domain(url):
                        continue
                    if self._skip(url):
                        continue

                    rp = await self._robots(url, client)
                    if not self._allowed(rp, url):
                        print(f"  ⊘ robots.txt: {url}")
                        continue

                    visited.add(url)
                    print(f"[{len(visited):>4}/{limit_str}] {url}")

                    # Periyodik checkpoint
                    if len(visited) % self.cfg.checkpoint_interval == 0:
                        _checkpoint(f" (her {self.cfg.checkpoint_interval})")

                    await asyncio.sleep(self.cfg.delay_seconds)
                    ext = _url_ext(url)

                    # ── PDF ───────────────────────────────────────────────
                    if ext in _PDF_EXTS and self.cfg.follow_pdfs:
                        raw = await self._stream_bytes(client, url, "PDF")
                        if raw is None:
                            continue
                        doc = await self._safe_extract_binary(
                            self._pdf_ext, raw, url, self.cfg.pdf_parse_timeout
                        )
                        if doc and not doc.is_empty():
                            results.append(doc)
                            _append_doc(cache_dir, doc)
                            print(f"  ✓ PDF  | {doc.title[:60]} | {len(doc.body):,} kar.")
                        continue

                    # ── DOCX ──────────────────────────────────────────────
                    if ext in _DOCX_EXTS and self.cfg.follow_docx:
                        raw = await self._stream_bytes(client, url, "DOCX")
                        if raw is None:
                            continue
                        doc = await self._safe_extract_binary(
                            self._docx_ext, raw, url, 15.0
                        )
                        if doc and not doc.is_empty():
                            results.append(doc)
                            _append_doc(cache_dir, doc)
                            print(f"  ✓ DOCX | {doc.title[:60]} | {len(doc.body):,} kar.")
                        continue

                    # ── HTML ──────────────────────────────────────────────
                    response = await self._fetch(client, url)
                    if response is None:
                        continue

                    ct = response.headers.get("content-type", "").lower()

                    # Content-Type PDF / DOCX
                    if "pdf" in ct and self.cfg.follow_pdfs:
                        doc = await self._safe_extract_binary(
                            self._pdf_ext,
                            response.content,
                            url,
                            self.cfg.pdf_parse_timeout,
                        )
                        if doc and not doc.is_empty():
                            results.append(doc)
                            _append_doc(cache_dir, doc)
                            print(f"  ✓ PDF  | {doc.title[:60]} | {len(doc.body):,} kar.")
                        continue

                    if ("word" in ct or "docx" in ct) and self.cfg.follow_docx:
                        doc = await self._safe_extract_binary(
                            self._docx_ext, response.content, url, 15.0
                        )
                        if doc and not doc.is_empty():
                            results.append(doc)
                            _append_doc(cache_dir, doc)
                            print(f"  ✓ DOCX | {doc.title[:60]} | {len(doc.body):,} kar.")
                        continue

                    if "text/html" not in ct:
                        continue

                    # HTML extraction (sync ama hızlı → executor gerekmez)
                    doc = self._html_ext.extract(response.text, url)
                    if doc and not doc.is_empty():
                        results.append(doc)
                        _append_doc(cache_dir, doc)
                        print(f"  ✓ HTML | {doc.title[:60]} | {len(doc.body):,} kar.")

                    # Yeni linkleri kuyruğa ekle
                    if depth < self.cfg.max_depth:
                        added = 0
                        for link in self._links(response.text, url):
                            if link not in visited and self._in_domain(link):
                                if self._priority(link):
                                    queue.appendleft((link, depth + 1))
                                else:
                                    queue.append((link, depth + 1))
                                added += 1
                        if added:
                            print(f"       + {added} link eklendi")

        except Exception as exc:
            import traceback
            traceback.print_exc()
            print(f"\n  ✗ Beklenmeyen hata: {exc}")
            _checkpoint(" (hata)")

        finally:
            signal.signal(signal.SIGINT, original)

        if self._stop:
            _checkpoint(" (Ctrl+C)")
            print(
                f"\n{'=' * 55}\n"
                f"Crawl durduruldu (Ctrl+C).\n"
                f"  Ziyaret : {len(visited)}\n"
                f"  Belge   : {len(results)}\n"
                f"  Devam   : python -m backend.pipeline.run --resume\n"
                f"{'=' * 55}"
            )
        else:
            # Normal bitiş → state'i sil (bir sonraki çalıştırma baştan başlar)
            state_path = os.path.join(cache_dir, _STATE_FILE)
            if os.path.exists(state_path):
                os.remove(state_path)
            print(
                f"\n{'=' * 55}\n"
                f"Crawl tamamlandı.\n"
                f"  Ziyaret : {len(visited)}\n"
                f"  Belge   : {len(results)}\n"
                f"{'=' * 55}"
            )

        return results


# ---------------------------------------------------------------------------
# TargetedCrawler — Whitelist tabanlı hedefli crawler
# ---------------------------------------------------------------------------

class TargetedCrawler:
    """
    BFS yerine yalnızca ingestion_list.json'daki URL'leri işler.

    Davranış:
    - Her TargetSource URL'si doğrudan çekilir (derinlik yok)
    - HTML sayfalarında crawl_linked_docs=True ise sayfadaki
      PDF ve DOCX linkleri de otomatik olarak indirilir (1 hop)
    - HTML linkleri TAKİP EDİLMEZ → link discovery yok
    - Her belgeye kaynak URL'nin category'si metadata olarak yazılır
    - Checkpoint sistemi WebCrawler ile aynı (state.json + documents.jsonl)
    """

    def __init__(self, cfg: PipelineConfig, sources: list[TargetSource]) -> None:
        self.cfg     = cfg
        self.sources = sorted(sources, key=lambda s: s.priority)
        self._stop   = False
        self._robots_cache: dict[str, RobotFileParser] = {}

        self._html_ext = HTMLExtractor()
        self._pdf_ext  = PDFExtractor()
        self._docx_ext = DOCXExtractor()

        self._skip_re = [re.compile(p, re.I) for p in cfg.skip_patterns]

    # ── URL yardımcıları ─────────────────────────────────────────────────

    def _norm(self, url: str) -> str:
        url, _ = urldefrag(url)
        return url.rstrip("/")

    def _in_domain(self, url: str) -> bool:
        netloc = urlparse(url).netloc.lower()
        return any(
            netloc == d or netloc.endswith("." + d)
            for d in self.cfg.allowed_domains
        )

    def _skip(self, url: str) -> bool:
        return any(rx.search(url) for rx in self._skip_re)

    # ── robots.txt ───────────────────────────────────────────────────────

    async def _robots(self, url: str, client: httpx.AsyncClient) -> RobotFileParser:
        p = urlparse(url)
        robots_url = f"{p.scheme}://{p.netloc}/robots.txt"
        if robots_url in self._robots_cache:
            return self._robots_cache[robots_url]
        rp = RobotFileParser()
        rp.set_url(robots_url)
        try:
            r = await client.get(robots_url, timeout=8)
            rp.parse(r.text.splitlines())
        except Exception:
            pass
        self._robots_cache[robots_url] = rp
        return rp

    def _allowed(self, rp: RobotFileParser, url: str) -> bool:
        try:
            return rp.can_fetch(self.cfg.user_agent, url)
        except Exception:
            return True

    # ── HTTP yardımcıları (WebCrawler ile aynı) ──────────────────────────

    async def _stream_bytes(
        self, client: httpx.AsyncClient, url: str, label: str = "dosya"
    ) -> bytes | None:
        max_bytes = self.cfg.max_pdf_size_mb * 1024 * 1024
        try:
            head = await client.head(url, timeout=8)
            cl   = head.headers.get("content-length")
            if cl and int(cl) > max_bytes:
                print(f"  ⊘ {label} çok büyük (HEAD: {int(cl)/1024/1024:.1f} MB): {url}")
                return None
        except Exception:
            pass
        chunks: list[bytes] = []
        total  = 0
        try:
            t = httpx.Timeout(connect=10.0, read=45.0, write=10.0, pool=5.0)
            async with client.stream("GET", url, timeout=t) as resp:
                resp.raise_for_status()
                async for chunk in resp.aiter_bytes(65_536):
                    total += len(chunk)
                    if total > max_bytes:
                        print(f"  ⊘ {label} boyut aşıldı ({total/1024/1024:.1f} MB): {url}")
                        return None
                    chunks.append(chunk)
        except httpx.TimeoutException:
            print(f"  ✗ Timeout ({label}): {url}")
            return None
        except Exception as exc:
            print(f"  ✗ İndirme hatası ({label}): {url} → {exc}")
            return None
        return b"".join(chunks)

    async def _safe_extract_binary(
        self, extractor, raw: bytes, url: str, timeout: float
    ) -> RawDocument | None:
        loop = asyncio.get_event_loop()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(None, extractor.extract, raw, url),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            print(f"  ⊘ Extraction timeout ({timeout}s): {url}")
            return None
        except Exception as exc:
            print(f"  ✗ Extraction hatası: {url} → {exc}")
            return None

    async def _fetch(self, client: httpx.AsyncClient, url: str) -> httpx.Response | None:
        t = httpx.Timeout(
            connect=8.0, read=float(self.cfg.timeout_seconds), write=8.0, pool=5.0
        )
        for attempt in range(self.cfg.max_retries + 1):
            try:
                r = await client.get(url, timeout=t)
                r.raise_for_status()
                return r
            except httpx.HTTPStatusError as exc:
                code = exc.response.status_code
                if code in (404, 410, 403, 401):
                    print(f"  ✗ HTTP {code}: {url}")
                    return None
                print(f"  ✗ HTTP {code} (deneme {attempt + 1}): {url}")
            except httpx.TimeoutException:
                print(f"  ✗ Timeout (deneme {attempt + 1}): {url}")
            except Exception as exc:
                print(f"  ✗ Hata (deneme {attempt + 1}): {url} → {exc}")
            if attempt < self.cfg.max_retries:
                await asyncio.sleep(2 ** attempt)
        return None

    # ── Bağlı belge keşfi (1 hop, sadece PDF/DOCX) ───────────────────────

    async def _fetch_linked_docs(
        self,
        client:    httpx.AsyncClient,
        html:      str,
        base_url:  str,
        category:  str,
        visited:   set[str],
        results:   list[RawDocument],
        cache_dir: str,
    ) -> None:
        """
        Bir HTML sayfasındaki tüm PDF/DOCX linklerini indir ve işle.
        HTML linkleri kesinlikle takip edilmez.
        """
        soup = BeautifulSoup(html, "lxml")
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith(("mailto:", "tel:", "javascript:", "#")):
                continue
            full_url = self._norm(urljoin(base_url, href))
            if full_url in visited:
                continue
            if not self._in_domain(full_url):
                continue
            if self._skip(full_url):
                continue

            ext = _url_ext(full_url)

            if ext in _PDF_EXTS and self.cfg.follow_pdfs:
                visited.add(full_url)
                raw = await self._stream_bytes(client, full_url, "PDF")
                if raw is None:
                    continue
                doc = await self._safe_extract_binary(
                    self._pdf_ext, raw, full_url, self.cfg.pdf_parse_timeout
                )
                if doc and not doc.is_empty():
                    doc.metadata["category"] = category
                    results.append(doc)
                    _append_doc(cache_dir, doc)
                    print(f"    ✓ PDF  [{category}] {doc.title[:55]} | {len(doc.body):,} kar.")

            elif ext in _DOCX_EXTS and self.cfg.follow_docx:
                visited.add(full_url)
                raw = await self._stream_bytes(client, full_url, "DOCX")
                if raw is None:
                    continue
                doc = await self._safe_extract_binary(
                    self._docx_ext, raw, full_url, 15.0
                )
                if doc and not doc.is_empty():
                    doc.metadata["category"] = category
                    results.append(doc)
                    _append_doc(cache_dir, doc)
                    print(f"    ✓ DOCX [{category}] {doc.title[:55]} | {len(doc.body):,} kar.")

    # ── Ana crawl döngüsü ─────────────────────────────────────────────────

    async def crawl(self, resume: bool = False) -> list[RawDocument]:
        """
        Whitelist'teki kaynakları sırayla işle.

        resume=True → state.json'daki visited seti yükle, işlenenleri atla.
        Her cfg.checkpoint_interval kaynakta state kaydet.
        Ctrl+C → checkpoint kaydedilir, --resume ile devam edilir.
        """
        cache_dir = self.cfg.cache_dir
        os.makedirs(cache_dir, exist_ok=True)

        # Checkpoint yükle
        loaded = _load_state(cache_dir) if resume else None
        visited: set[str] = loaded[0] if loaded else set()
        results: list[RawDocument] = load_documents(cache_dir) if resume else []

        total = len(self.sources)
        print(f"  Hedef kaynak sayısı : {total}")
        print(f"  Mod                 : targeted (BFS kapalı)")

        # Ctrl+C handler
        def _on_sigint(sig, frame):
            if not self._stop:
                print("\n\n  ⚠  Ctrl+C — mevcut işlem bitince duruluyor...\n"
                      "     (Tekrar Ctrl+C → anında çıkış)\n")
                self._stop = True
            else:
                _save_state(cache_dir, visited, deque())
                print("\n  Zorla çıkılıyor.")
                sys.exit(1)

        original = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, _on_sigint)

        def _checkpoint(label: str = "") -> None:
            _save_state(cache_dir, visited, deque())
            if label:
                print(f"  💾 Checkpoint{label}: {len(visited)} işlendi, {len(results)} belge")

        try:
            async with httpx.AsyncClient(
                headers={
                    "User-Agent":      self.cfg.user_agent,
                    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
                },
                follow_redirects=True,
            ) as client:

                # robots.txt ön yükle
                if self.sources:
                    await self._robots(self.sources[0].url, client)

                for idx, source in enumerate(self.sources, 1):
                    if self._stop:
                        break

                    url = self._norm(source.url)
                    if url in visited:
                        print(f"[{idx:>3}/{total}] ↷ Atlandı: {url}")
                        continue

                    rp = await self._robots(url, client)
                    if not self._allowed(rp, url):
                        print(f"[{idx:>3}/{total}] ⊘ robots.txt: {url}")
                        visited.add(url)
                        continue

                    print(f"[{idx:>3}/{total}] [{source.category}] {url}")
                    visited.add(url)
                    await asyncio.sleep(self.cfg.delay_seconds)

                    ext = _url_ext(url)

                    # ── PDF ──────────────────────────────────────────────
                    if ext in _PDF_EXTS and self.cfg.follow_pdfs:
                        raw = await self._stream_bytes(client, url, "PDF")
                        if raw is None:
                            continue
                        doc = await self._safe_extract_binary(
                            self._pdf_ext, raw, url, self.cfg.pdf_parse_timeout
                        )
                        if doc and not doc.is_empty():
                            doc.metadata["category"] = source.category
                            results.append(doc)
                            _append_doc(cache_dir, doc)
                            print(f"  ✓ PDF  [{source.category}] {doc.title[:55]}")
                        continue

                    # ── DOCX ─────────────────────────────────────────────
                    if ext in _DOCX_EXTS and self.cfg.follow_docx:
                        raw = await self._stream_bytes(client, url, "DOCX")
                        if raw is None:
                            continue
                        doc = await self._safe_extract_binary(
                            self._docx_ext, raw, url, 15.0
                        )
                        if doc and not doc.is_empty():
                            doc.metadata["category"] = source.category
                            results.append(doc)
                            _append_doc(cache_dir, doc)
                            print(f"  ✓ DOCX [{source.category}] {doc.title[:55]}")
                        continue

                    # ── HTML ─────────────────────────────────────────────
                    response = await self._fetch(client, url)
                    if response is None:
                        continue

                    ct = response.headers.get("content-type", "").lower()

                    if "pdf" in ct and self.cfg.follow_pdfs:
                        doc = await self._safe_extract_binary(
                            self._pdf_ext, response.content, url, self.cfg.pdf_parse_timeout
                        )
                        if doc and not doc.is_empty():
                            doc.metadata["category"] = source.category
                            results.append(doc)
                            _append_doc(cache_dir, doc)
                            print(f"  ✓ PDF  [{source.category}] {doc.title[:55]}")
                        continue

                    if ("word" in ct or "docx" in ct) and self.cfg.follow_docx:
                        doc = await self._safe_extract_binary(
                            self._docx_ext, response.content, url, 15.0
                        )
                        if doc and not doc.is_empty():
                            doc.metadata["category"] = source.category
                            results.append(doc)
                            _append_doc(cache_dir, doc)
                            print(f"  ✓ DOCX [{source.category}] {doc.title[:55]}")
                        continue

                    if "text/html" not in ct:
                        continue

                    doc = self._html_ext.extract(response.text, url)
                    if doc and not doc.is_empty():
                        doc.metadata["category"] = source.category
                        results.append(doc)
                        _append_doc(cache_dir, doc)
                        print(f"  ✓ HTML [{source.category}] {doc.title[:55]} | {len(doc.body):,} kar.")

                    # Bağlı PDF/DOCX'leri çek (HTML linklerini takip etme)
                    if source.crawl_linked_docs:
                        await self._fetch_linked_docs(
                            client, response.text, url,
                            source.category, visited, results, cache_dir,
                        )

                    # Periyodik checkpoint
                    if idx % self.cfg.checkpoint_interval == 0:
                        _checkpoint(f" ({idx}/{total})")

        except Exception as exc:
            import traceback
            traceback.print_exc()
            print(f"\n  ✗ Beklenmeyen hata: {exc}")
            _checkpoint(" (hata)")
        finally:
            signal.signal(signal.SIGINT, original)

        if self._stop:
            _checkpoint(" (Ctrl+C)")
            print(
                f"\n{'=' * 55}\n"
                f"Targeted crawl durduruldu (Ctrl+C).\n"
                f"  İşlenen : {len(visited)}/{total}\n"
                f"  Belge   : {len(results)}\n"
                f"  Devam   : python -m backend.pipeline.run --resume\n"
                f"{'=' * 55}"
            )
        else:
            state_path = os.path.join(cache_dir, _STATE_FILE)
            if os.path.exists(state_path):
                os.remove(state_path)
            print(
                f"\n{'=' * 55}\n"
                f"Targeted crawl tamamlandı.\n"
                f"  İşlenen : {len(visited)}/{total} kaynak\n"
                f"  Belge   : {len(results)}\n"
                f"{'=' * 55}"
            )

        return results
