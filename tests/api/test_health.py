import pytest
from unittest.mock import AsyncMock

pytestmark = pytest.mark.asyncio

async def test_health_check_returns_200_if_all_ok(async_client, mocker):
    """
    Tüm bağımlılıklar (PostgreSQL dahil) sağlandığında /health 
    endpoint'inin HTTP 200 döndüğünü ve JSON formatının doğruluğunu test eder.
    """
    # 1. Ortam değişkenlerini ve klasörleri mockla
    mocker.patch("backend.main.os.getenv", return_value="fake_api_key")
    mocker.patch("backend.main.os.path.isdir", return_value=True)
    
    # 2. Qdrant bağlantısını mockla
    # DİKKAT: QdrantClient main.py'de fonksiyon içinde import edildiği için
    # doğrudan kendi kütüphanesinden (qdrant_client) mockluyoruz.
    mock_qdrant = mocker.patch("qdrant_client.QdrantClient")
    mock_qdrant.return_value.get_collection.return_value = True
    
    # 3. PostgreSQL bağlantı havuzunu ve DB sağlık kontrolünü mockla
    mocker.patch("backend.main.db.get_pool", return_value="fake_pool")
    mocker.patch("backend.main.db.check_health", new_callable=AsyncMock, return_value="ok")
    
    response = await async_client.get("/health")
    
    # Eğer her şey yolundaysa sistem 200 dönmeli
    assert response.status_code == 200
    data = response.json()
    
    # Yeni mimarideki tüm anahtarların "ok" olduğunu doğrula
    assert data.get("api") == "ok"
    assert data.get("groq_key") == "ok"
    assert data.get("qdrant") == "ok"
    assert data.get("postgres") == "ok"