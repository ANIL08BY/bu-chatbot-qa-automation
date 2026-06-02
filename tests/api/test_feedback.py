import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch

pytestmark = pytest.mark.asyncio

# Veritabanı bağlantısını ve kayıt işlemini "kandır" (Mocking)
@patch("backend.main.db.save_feedback", new_callable=AsyncMock)
@patch("backend.main.db.get_pool")
async def test_feedback_endpoint_success(mock_get_pool, mock_save_feedback, async_client: AsyncClient):
    """
    Kullanıcının yaptığı oylamanın (like/dislike) veritabanı ayakta olmasa bile
    API rotası tarafından doğru karşılanıp işlendiğini (HTTP 200) test eder.
    """
    # 1. Sisteme sahte bir veritabanı bağlantısı varmış gibi davranmasını söyle
    mock_get_pool.return_value = "fake_db_pool"
    # 2. Veritabanı kaydının her zaman başarılı (True) döndüğünü varsay
    mock_save_feedback.return_value = True

    # 3. Herhangi bir message_id ile doğrudan /feedback rotasına istek at
    feedback_payload = {
        "message_id": 9999,
        "is_positive": True,
        "comment": "Mock testi çok başarılı"
    }
    
    response = await async_client.post("/feedback", json=feedback_payload)
    
    # 4. KONTROLLER
    assert response.status_code == 200, f"Feedback API başarısız oldu: {response.text}"
    assert response.json().get("status") == "ok", "API 'ok' yanıtı dönmedi."
    
    # 5. Arka plandaki fonksiyonun doğru verilerle tetiklendiğini doğrula
    mock_save_feedback.assert_called_once_with(
        "fake_db_pool",
        message_id=9999,
        is_positive=True,
        comment="Mock testi çok başarılı"
    )

async def test_feedback_endpoint_validation_error(async_client: AsyncClient):
    """
    Eksik veri (message_id olmadan) gönderildiğinde Pydantic'in sistemi 
    koruyup HTTP 422 Hatası fırlattığını test eder.
    """
    bad_payload = {
        "is_positive": False,
        "comment": "Bu mesajın id'si yok!"
    }
    
    response = await async_client.post("/feedback", json=bad_payload)
    
    # 422 Unprocessable Entity bekle (Pydantic doğrulama hatası)
    assert response.status_code == 422, "API eksik message_id için hata fırlatmadı!"