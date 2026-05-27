"""
RAG evaluation entegrasyon testi.

@pytest.mark.slow ile işaretli — varsayılan pytest çalıştırmada atlanır.
Çalıştırma: pytest -m slow tests/test_eval_integration.py

Gereksinimler: Qdrant çalışıyor ve belek_v2 collection'ı dolu olmalı.
"""
from __future__ import annotations

import pytest


@pytest.mark.slow
def test_evaluation_hit_rate():
    """Hit rate minimum eşiğin üstünde olmalı."""
    from backend.pipeline_v2.evaluation.eval import run_evaluation

    results = run_evaluation()
    assert results["hit_rate"] >= 0.5, (
        f"Hit rate çok düşük: {results['hit_rate']:.2f} (min: 0.50)"
    )


@pytest.mark.slow
def test_evaluation_mrr():
    """MRR minimum eşiğin üstünde olmalı."""
    from backend.pipeline_v2.evaluation.eval import run_evaluation

    results = run_evaluation()
    assert results["mrr"] >= 0.3, (
        f"MRR çok düşük: {results['mrr']:.2f} (min: 0.30)"
    )
