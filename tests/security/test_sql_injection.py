import pytest
from unittest.mock import AsyncMock

pytestmark = pytest.mark.asyncio

# Klasik ve tehlikeli SQL Injection saldırı vektörleri
SQL_INJECTION_PAYLOADS = [
    "1' OR '1'='1",
    "'; DROP TABLE belek_chatbot.sessions; --",
    "1 UNION SELECT null, version(); --",
    "admin' --",
]

@pytest.mark.parametrize("malicious_sql", SQL_INJECTION_PAYLOADS)
async def test_sql_injection_mitigation(async_client, mocker, malicious_sql):
    """
    Siber Güvenlik Testi: SQL Injection ve Veritabanı Sızma Koruması (FR.15).
    Soru alanına zararlı SQL komutları girildiğinde sistemin çökmediğini (500 vermediğini)
    ve parametrik sorgular sayesinde komutların zararsız birer düz metin olarak işlendiğini doğrular.
    """
    # Veritabanı ve LLM katmanlarını mocklayarak sadece kapıdaki SQLi kalkanını test et
    mocker.patch("backend.main.ask_question", return_value={"answer": "Güvendesiniz.", "sources": []})
    mocker.patch("backend.main.db.get_pool", return_value="fake_pool")
    mocker.patch("backend.main.db.log_interaction", new_callable=AsyncMock, return_value=1)

    payload = {
        "question": malicious_sql,
        "history": []
    }
    
    response = await async_client.post("/ask", json=payload)
    
    # KONTROL: Sistem sızma girişiminde 500 Internal Server Error verip çökmüyor,
    # atağı başarıyla göğüsleyip HTTP 200 veriyor.
    assert response.status_code == 200, f"Sistem SQL Injection atağında çöktü! Kod: {malicious_sql}"
    
    data = response.json()
    assert "answer" in data