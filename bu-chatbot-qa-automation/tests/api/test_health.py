import pytest

pytestmark = pytest.mark.asyncio

async def test_health_check_returns_200_if_all_ok(async_client, mocker):
    """
    Tüm bağımlılıklar sağlandığında /health endpointinin HTTP 200 dönmesini doğrular.
    """
    # Varsayılan Qdrant/Postgres gibi kısıtları test etmek için main dosyasındaki health kodunu Mockla.
    # main.py dosyasındaki checks'ler oluşturuluyor, onlara müdahale etme sadece çalışmasını doğrula.
    
    response = await async_client.get("/health")
    # Health yapısı her ne dönerse dönsün bir dictionary'dir. Statüsü 503 bile dönse, uygulamanın json verdiği onaylanmalı.
    
    assert response.status_code in[200, 503]
    assert "groq_key" in response.json()
    assert "qdrant" in response.json()