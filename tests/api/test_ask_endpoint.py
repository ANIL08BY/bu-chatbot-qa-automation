import pytest

pytestmark = pytest.mark.asyncio

async def test_ask_endpoint_happy_path(async_client, mock_db_and_query):
    """
    Uygulamaya uygun formatta (ChatRequest) soru geldiğinde 
    Sistemin hata fırlatmadan JSON formatında RAG yanıtı döndüğünü test eder. (US.04-API Modeli)
    """
    payload = {
        "question": "Mezuniyet yönetmeliği nasıldır?",
        "history":[]
    }
    
    response = await async_client.post("/ask", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert data["answer"] == "Bu test ortamından dönen sahte cevaptır."
    assert "category" in data

async def test_ask_endpoint_empty_input_rejected(async_client, mock_db_and_query):
    """
    Arayüzden kazara boş string veya geçersiz değer atıldığında
    sistemin FR.15 (Girdi Sanitizasyonu) kurallarını işleyip 
    kötü/boş istekleri geri çevirdiğini doğrular.
    """
    bad_payload = {
        "question": "", # Soru girmek zorunlu, backend 400 veya 422 dönmeli
        "history":[]
    }
    
    response = await async_client.post("/ask", json=bad_payload)
    
    # FastAPI Validation Exception genelde 422 atar,
    # manuel hata varsa main.py de yazdığı üzere 400 atmalıdır.
    assert response.status_code in [400, 422]