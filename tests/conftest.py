"""
Pytest fixture'ları — test altyapısı.

External servisleri (Groq, Qdrant, embedding model) mock'lar.
"""
from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _set_test_env(monkeypatch):
    """Testlerde gerçek API çağrısı yapılmasını engelle."""
    monkeypatch.setenv("GROQ_API_KEY", "test-key-not-real")
    monkeypatch.setenv("QDRANT_HOST", "localhost")
    monkeypatch.setenv("QDRANT_PORT", "6333")
