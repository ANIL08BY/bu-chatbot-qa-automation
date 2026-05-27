"""
main.py endpoint testleri — FastAPI TestClient ile.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from backend.main import app
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_json(self, client):
        response = client.get("/health")
        data = response.json()
        assert "api" in data
        assert data["api"] == "ok"

    def test_health_checks_groq_key(self, client):
        response = client.get("/health")
        data = response.json()
        assert "groq_key" in data

    def test_health_checks_qdrant(self, client):
        response = client.get("/health")
        data = response.json()
        assert "qdrant" in data


class TestAskEndpoint:
    def test_empty_question_rejected(self, client):
        response = client.post("/ask", json={"question": "", "history": []})
        assert response.status_code == 422

    def test_too_long_question_rejected(self, client):
        response = client.post("/ask", json={"question": "x" * 501, "history": []})
        assert response.status_code == 422

    @patch("backend.main.ask_question")
    def test_successful_response(self, mock_ask, client):
        mock_ask.return_value = {
            "answer": "Test yanıtı",
            "sources": [],
            "category": "genel",
            "engine": "v2",
        }
        response = client.post("/ask", json={"question": "Test sorusu", "history": []})
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Test yanıtı"
        assert data["engine"] == "v2"

    @patch("backend.main.ask_question")
    def test_runtime_error_returns_503(self, mock_ask, client):
        mock_ask.side_effect = RuntimeError("GROQ_API_KEY bulunamadı")
        response = client.post("/ask", json={"question": "Test", "history": []})
        assert response.status_code == 503

    @patch("backend.main.ask_question")
    def test_unexpected_error_returns_500(self, mock_ask, client):
        mock_ask.side_effect = ValueError("Beklenmeyen hata")
        response = client.post("/ask", json={"question": "Test", "history": []})
        assert response.status_code == 500
