"""
DocumentCleanerV2 — Metin normalleştirme ve boilerplate filtreleme.

Mevcut backend/pipeline/clean.py'den ilham alır; Markdown-aware versiyonu.
"""
from __future__ import annotations

import re
import unicodedata


# ---------------------------------------------------------------------------
# Boilerplate kalıpları (Markdown'da da geçerli)
# ---------------------------------------------------------------------------

_BOILERPLATE_PATTERNS: list[re.Pattern] = [
    re.compile(r"(?i)çerez\s*(politika|onay|kabul)", re.MULTILINE),
    re.compile(r"(?i)cookie\s*(policy|consent|accept)", re.MULTILINE),
    re.compile(r"(?i)tüm\s+haklar\s+saklıdır", re.MULTILINE),
    re.compile(r"(?i)all\s+rights\s+reserved", re.MULTILINE),
    re.compile(r"(?i)gizlilik\s+politikası", re.MULTILINE),
    re.compile(r"(?i)privacy\s+policy", re.MULTILINE),
    re.compile(r"(?i)sosyal\s+medya", re.MULTILINE),
    re.compile(r"(?i)bizi\s+takip\s+edin", re.MULTILINE),
    re.compile(r"(?i)follow\s+us", re.MULTILINE),
    re.compile(r"^!\[.*?\]\(.*?\)\s*$", re.MULTILINE),  # Orphan Markdown image
]

_MIN_WORD_COUNT = 8   # Bu kadar kelimeden az içerikli satırları çıkar


# ---------------------------------------------------------------------------
# Ana temizleyici
# ---------------------------------------------------------------------------

class DocumentCleanerV2:
    """
    Markdown belgeleri için temizleyici.

    Adımlar:
    1. Unicode NFC normalleştirme
    2. Whitespace normalleştirme (Unicode boşluklar → standart)
    3. Markdown'a özgü gürültü temizleme
    4. Boilerplate cümle tespiti
    5. Minimum içerik uzunluğu kontrolü
    """

    def __init__(self, min_content_chars: int = 150):
        self.min_content_chars = min_content_chars

    def clean(self, text: str) -> str:
        """Tek metin bloğunu temizle."""
        if not text:
            return ""
        text = self._normalize_unicode(text)
        text = self._normalize_whitespace(text)
        text = self._remove_markdown_noise(text)
        text = self._remove_boilerplate_lines(text)
        return text.strip()

    def is_valid(self, text: str) -> bool:
        """Minimum kalite eşiğini geçiyor mu?"""
        cleaned = self.clean(text)
        return len(cleaned) >= self.min_content_chars

    # ── Adımlar ──────────────────────────────────────────────────────────────

    @staticmethod
    def _normalize_unicode(text: str) -> str:
        """NFC normalleştirme + Unicode boşluk karakterleri → ASCII boşluk."""
        text = unicodedata.normalize("NFC", text)
        result = []
        for ch in text:
            cat = unicodedata.category(ch)
            if cat in ("Zs", "Cc") and ch not in ("\n", "\t", "\r"):
                result.append(" ")
            else:
                result.append(ch)
        return "".join(result)

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        """
        - Sekme → boşluk
        - 3+ ardışık boş satır → 2 boş satır
        - Satır sonu boşlukları temizle
        """
        text = text.replace("\t", "    ")
        text = re.sub(r"[ ]+", " ", text)          # Çoklu boşluk → tek
        text = re.sub(r" +\n", "\n", text)          # Satır sonu boşluk
        text = re.sub(r"\n{4,}", "\n\n\n", text)    # 4+ boş satır → 3
        return text

    @staticmethod
    def _remove_markdown_noise(text: str) -> str:
        """
        - HTML yorumları <!-- ... -->
        - Aşırı uzun yatay çizgiler (--- dışı)
        - Boş Markdown link etiketleri []()
        """
        text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
        text = re.sub(r"_{5,}", "", text)
        text = re.sub(r"\[]\(\)", "", text)
        return text

    @staticmethod
    def _remove_boilerplate_lines(text: str) -> str:
        """Boilerplate kalıbı içeren satırları çıkar."""
        lines = text.splitlines()
        filtered = []
        for line in lines:
            skip = any(pat.search(line) for pat in _BOILERPLATE_PATTERNS)
            if not skip:
                filtered.append(line)
        return "\n".join(filtered)
