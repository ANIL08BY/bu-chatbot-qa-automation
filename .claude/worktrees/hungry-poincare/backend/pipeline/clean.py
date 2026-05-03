"""
Veri kalite kontrolü ve temizleme.

İşlemler (sırayla):
  1. Boşluk normalizasyonu
  2. Minimum uzunluk filtresi
  3. Navigasyon / boilerplate tespiti
  4. Hash tabanlı yinelenen içerik tespiti (SHA-256)

Not: Dil filtresi uygulanmaz — kaynak belek.edu.tr olduğundan
tüm içerik üniversiteyle alakalıdır.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import replace

from .config import PipelineConfig
from .extract import RawDocument


# ---------------------------------------------------------------------------
# Yardımcı: metin normalizasyonu
# ---------------------------------------------------------------------------

def _normalize_whitespace(text: str) -> str:
    """Satır sonlarını, boşlukları ve unicode boşluklarını normalize et."""
    # Unicode boşluk karakterlerini → normal boşluğa
    text = "".join(
        " " if unicodedata.category(c) in ("Zs", "Cc") and c not in ("\n", "\t") else c
        for c in text
    )
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)             # Yatay boşlukları birleştir
    text = re.sub(r"\n{3,}", "\n\n", text)           # 3+ boş satır → 2
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return text.strip()


def _content_hash(text: str) -> str:
    """Beyaz boşluktan bağımsız SHA-256 parmak izi."""
    normalized = re.sub(r"\s+", " ", text.lower().strip())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Yardımcı: navigasyon / boilerplate tespiti
# ---------------------------------------------------------------------------

# Navigasyon ayıraçları (bullet, ok, dash vb.)
_SEPARATOR_RE = re.compile(r"[•›»·|/\\]")

# Çerez / GDPR kalıpları
_COOKIE_TERMS = frozenset([
    "çerez", "cookie", "gdpr", "kişisel veri",
    "gizlilik politikası", "kabul ediyorum",
])


def _is_navigation(text: str) -> bool:
    """
    Kısa metinlerde yüksek separator yoğunluğu → navigasyon menüsü.
    """
    if len(text) > 400:
        return False
    sep_count = len(_SEPARATOR_RE.findall(text))
    if sep_count >= 4:
        return True

    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines:
        return True
    single_word_ratio = sum(1 for l in lines if len(l.split()) <= 2) / len(lines)
    if single_word_ratio >= 0.75 and len(lines) >= 5:
        return True

    return False


def _is_cookie_notice(text: str) -> bool:
    """Çerez / GDPR bildirimi."""
    lower = text.lower()
    hits  = sum(1 for t in _COOKIE_TERMS if t in lower)
    return hits >= 2 and len(text) < 600


def _is_boilerplate(text: str) -> bool:
    return _is_navigation(text) or _is_cookie_notice(text)


# ---------------------------------------------------------------------------
# DataCleaner
# ---------------------------------------------------------------------------

class DataCleaner:
    """
    RawDocument listesini temizler ve deduplicate eder.

    Aynı instance kullanılırsa hash seti korunur (crawl boyunca).
    """

    def __init__(self, cfg: PipelineConfig) -> None:
        self.cfg   = cfg
        self._seen: set[str] = set()

    def reset(self) -> None:
        """Hash setini sıfırla (yeni ingest için)."""
        self._seen.clear()

    def clean(self, docs: list[RawDocument]) -> list[RawDocument]:
        clean: list[RawDocument] = []
        stats = {"short": 0, "boilerplate": 0, "duplicate": 0, "ok": 0}

        for doc in docs:
            result, reason = self._process(doc)
            if result:
                clean.append(result)
                stats["ok"] += 1
            else:
                stats[reason] = stats.get(reason, 0) + 1

        total = len(docs)
        print(
            f"  Temizleme: {total} → {stats['ok']} belge  "
            f"(kısa:{stats['short']} boilerplate:{stats['boilerplate']} "
            f"duplikat:{stats['duplicate']})"
        )
        return clean

    def _process(self, doc: RawDocument) -> tuple[RawDocument | None, str]:
        body = _normalize_whitespace(doc.body)

        # 1. Minimum uzunluk
        if len(body) < self.cfg.min_content_chars:
            return None, "short"

        # 2. Boilerplate
        if _is_boilerplate(body):
            return None, "boilerplate"

        # 3. Yineleme
        h = _content_hash(body)
        if h in self._seen:
            return None, "duplicate"
        self._seen.add(h)

        cleaned = replace(doc, body=body)
        return cleaned, "ok"
