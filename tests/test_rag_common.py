"""
rag_common.py unit testleri — saf fonksiyonlar (LLM çağrısı gerektirmez).
"""

from __future__ import annotations

from backend.rag_common import (
    AGGREGATION_RE,
    CATEGORY_LABELS,
    KNOWN_CATEGORIES,
    LIST_RE,
    PROMPT_TEMPLATE,
    compute_k,
    format_history,
    is_rate_limit,
)
from backend.rag_config import rag_config

# ---------------------------------------------------------------------------
# RAGConfig
# ---------------------------------------------------------------------------


class TestRAGConfig:
    def test_defaults_exist(self):
        assert rag_config.k_general == 15
        assert rag_config.k_list == 40
        assert rag_config.k_aggregation == 18
        assert rag_config.k_specific == 5
        assert rag_config.reranker_max_length == 512
        assert rag_config.max_history_messages == 6
        assert rag_config.min_category_results == 3

    def test_frozen(self):
        import pytest

        with pytest.raises(AttributeError):
            rag_config.k_general = 999  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------


class TestPromptTemplate:
    def test_template_loaded(self):
        assert "{context}" in PROMPT_TEMPLATE
        assert "{question}" in PROMPT_TEMPLATE
        assert "{history}" in PROMPT_TEMPLATE
        assert "{category_context}" in PROMPT_TEMPLATE

    def test_turkish_content(self):
        assert "DÖKÜMAN" in PROMPT_TEMPLATE
        assert "KURALLAR" in PROMPT_TEMPLATE


# ---------------------------------------------------------------------------
# Kategori sistemi
# ---------------------------------------------------------------------------


class TestCategories:
    def test_known_categories_not_empty(self):
        assert len(KNOWN_CATEGORIES) > 0

    def test_labels_cover_categories(self):
        for cat in KNOWN_CATEGORIES:
            assert cat in CATEGORY_LABELS, f"Label eksik: {cat}"


# ---------------------------------------------------------------------------
# compute_k
# ---------------------------------------------------------------------------


class TestComputeK:
    def test_list_query(self):
        assert compute_k("Tüm bursları listele") == rag_config.k_list

    def test_aggregation_query(self):
        assert compute_k("Kaç madde var?") == rag_config.k_aggregation

    def test_specific_query(self):
        assert compute_k("Madde 5 ne diyor?") == rag_config.k_specific

    def test_general_query(self):
        assert compute_k("Kayıt nasıl yapılır?") == rag_config.k_general


# ---------------------------------------------------------------------------
# format_history
# ---------------------------------------------------------------------------


class TestFormatHistory:
    def test_empty_history(self):
        assert format_history(None) == ""
        assert format_history([]) == ""

    def test_basic_formatting(self):
        history = [
            {"role": "user", "content": "Merhaba"},
            {"role": "assistant", "content": "Nasıl yardımcı olabilirim?"},
        ]
        result = format_history(history)
        assert "Kullanıcı: Merhaba" in result
        assert "Asistan: Nasıl yardımcı olabilirim?" in result
        assert "KONUŞMA GEÇMİŞİ:" in result

    def test_max_messages_limit(self):
        history = [{"role": "user", "content": f"msg{i}"} for i in range(20)]
        result = format_history(history)
        # Son 6 mesaj olmalı
        assert "msg14" in result
        assert "msg19" in result
        assert "msg0" not in result


# ---------------------------------------------------------------------------
# is_rate_limit
# ---------------------------------------------------------------------------


class TestIsRateLimit:
    def test_detects_429(self):
        assert is_rate_limit(Exception("Error 429: rate limit"))

    def test_detects_rate_limit_text(self):
        assert is_rate_limit(Exception("rate_limit_exceeded"))

    def test_detects_token_limit(self):
        assert is_rate_limit(Exception("tokens per day limit reached"))

    def test_normal_error(self):
        assert not is_rate_limit(Exception("connection refused"))


# ---------------------------------------------------------------------------
# Regex pattern'ları
# ---------------------------------------------------------------------------


class TestRegexPatterns:
    def test_aggregation_patterns(self):
        assert AGGREGATION_RE.search("Kaç madde var?")
        assert AGGREGATION_RE.search("toplam sayısı")
        assert not AGGREGATION_RE.search("Kayıt nasıl yapılır?")

    def test_list_patterns(self):
        assert LIST_RE.search("Tüm bursları listele")
        assert LIST_RE.search("Hangileri var?")
        assert not LIST_RE.search("Ne zaman başlıyor?")
