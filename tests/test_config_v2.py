"""
config_v2.py unit testleri — kategori sistemi ve slugify.
"""
from __future__ import annotations

from backend.pipeline_v2.config_v2 import (
    CATEGORY_LABELS_V2,
    KNOWN_CATEGORIES_V2,
    slugify,
)


class TestSlugify:
    def test_turkish_chars(self):
        assert slugify("burs olanakları") == "burs-olanaklari"

    def test_multiple_spaces(self):
        assert slugify("çok  boşluklu  metin") == "cok-bosluklu-metin"

    def test_uppercase(self):
        assert slugify("Büyük Harf") == "buyuk-harf"

    def test_special_chars(self):
        assert slugify("test (deneme)") == "test-deneme"


class TestCategorySystem:
    def test_categories_loaded(self):
        assert len(KNOWN_CATEGORIES_V2) > 0

    def test_labels_match_categories(self):
        for slug in KNOWN_CATEGORIES_V2:
            assert slug in CATEGORY_LABELS_V2

    def test_slug_format(self):
        for slug in KNOWN_CATEGORIES_V2:
            assert slug == slug.lower(), f"Slug lowercase olmalı: {slug}"
            assert " " not in slug, f"Slug boşluk içermemeli: {slug}"
