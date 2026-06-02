import pytest
from unittest.mock import AsyncMock

pytestmark = pytest.mark.asyncio

async def test_ask_endpoint_happy_path(async_client, mocker):
    """
    Sistemin RAG yanıtını başarıyla döndüğünü ve PostgreSQL RLS 
    kurallarını aşarak log_interaction'dan bir message_id alabildiğini test eder.
    """
    # 1. Yapay zeka motorunu mockla
    mocker.patch(
        "backend.main.ask_question",
        return_value={
            "answer": "Bu test ortamından dönen sahte cevaptır.",
            "sources": [],
            "category": "Test Kategori",
            "engine": "Test v1"
        }
    )
    
    # 2. Veritabanı havuzunu (pool) ve başarılı RLS kaydını mockla
    mocker.patch("backend.main.db.get_pool", return_value="fake_pool")
    mocker.patch("backend.main.db.log_interaction", new_callable=AsyncMock, return_value=1453)

    payload = {
        "question": "Mezuniyet yönetmeliği nasıldır?",
        "history": []
    }
    
    response = await async_client.post("/ask", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert data["answer"] == "Bu test ortamından dönen sahte cevaptır."
    
    # YENİ KONTROL: RLS başarılıysa frontend'e message_id dönmeli
    assert data.get("message_id") == 1453


async def test_ask_endpoint_rls_silent_fail(async_client, mocker):
    """
    Veritabanında RLS engeline takılındığında veya DB çöktüğünde
    sistemin kullanıcıya 500 dönmek yerine, sessizce hatayı yutup
    (message_id=None olarak) cevap verebildiğini doğrular.
    """
    mocker.patch(
        "backend.main.ask_question",
        return_value={"answer": "DB çöksede bu cevap gelir.", "sources": []}
    )
    
    mocker.patch("backend.main.db.get_pool", return_value="fake_pool")
    # RLS yetkisiz kullanıcıyı engellediği için log_interaction None dönüyor
    mocker.patch("backend.main.db.log_interaction", new_callable=AsyncMock, return_value=None)
    
    payload = {"question": "Test", "history": []}
    response = await async_client.post("/ask", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "DB çöksede bu cevap gelir."
    # Sessiz hata durumu: Sistem çökmüyor ama message_id atanmıyor.
    assert data.get("message_id") is None


async def test_ask_endpoint_empty_input_rejected(async_client, mock_db_and_query):
    """
    Girdi Sanitizasyonu (FR.15): Boş istek atıldığında 
    sistemin isteği geri çevirdiğini doğrular.
    """
    bad_payload = {
        "question": "",
        "history": []
    }
    
    response = await async_client.post("/ask", json=bad_payload)
    assert response.status_code in [400, 422]