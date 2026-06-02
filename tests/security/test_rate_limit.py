import pytest
import asyncio
from unittest.mock import AsyncMock

pytestmark = pytest.mark.asyncio

async def test_ddos_protection_rate_limit(async_client, mocker):
    """
    Siber Güvenlik Testi: DDoS Koruması ve Rate Limiting.
    Bir IP adresinden arka arkaya çok fazla (50+) istek geldiğinde
    sistemin kendini korumaya alıp HTTP 429 (Too Many Requests) döndüğünü test eder.
    """
    # 50 isteğin gerçekten Groq API'ye gidip kotasını (API limitini) bitirmemesi için
    # LLM fonksiyonunu ve veritabanını geçici olarak mockla. (Sadece kapıdaki güvenliği test ediyoruz)
    mocker.patch("backend.main.ask_question", return_value={"answer": "ok", "sources": []})
    mocker.patch("backend.main.db.get_pool", return_value="fake_pool")
    mocker.patch("backend.main.db.log_interaction", new_callable=AsyncMock, return_value=1)

    payload = {"question": "DDoS Test Saldırısı", "history": []}
    
    status_codes = []
    
    # Sisteme saniyeler içinde tam 52 adet istek yolla (Sınır 50)
    for _ in range(52):
        response = await async_client.post("/ask", json=payload)
        status_codes.append(response.status_code)
        
    # KONTROL: İlk 50 istek 200 dönse bile, 51. veya 52. istek kesinlikle engellenmeli (429)
    assert 429 in status_codes, (
        f"🚨 KRİTİK GÜVENLİK AÇIĞI! 🚨\n"
        f"Sistem 50'den fazla anlık isteği engellemedi (Rate Limiter çalışmıyor)!\n"
        f"Alınan Yanıtlar: {status_codes}"
    )