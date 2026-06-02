import pytest
import asyncpg

# Test veritabanı ortam değişkeni (İzole Neon Test DB)
TEST_DATABASE_URL = "postgresql://belek06:AnılBilgehan7012%402026@ep-morning-math-ag237as9-pooler.c-2.eu-central-1.aws.neon.tech:5432/belekuni_test?sslmode=require"

@pytest.mark.asyncio
async def test_database_transaction_rollback_on_error():
    """
    NFR.12 gereksinimi: Veritabanı işlemleri sırasında (sessions, messages) 
    hata oluşursa tüm transaction geri alınmalı (rollback) ve veri kirliliği önlenmelidir.
    """
    # 1. Gerçek test veritabanına asenkron bağlantı kur
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    
    # Kapsam dışından kontrol edebilmek için ID'leri başlat
    session_id = None
    message_id = None
    
    try:
        # 2. Transaction bloğunu başlat (Atomik İşlem)
        async with conn.transaction():
            # A. Oturum oluştur
            session_id = await conn.fetchval(
                "INSERT INTO belek_chatbot.sessions (user_ip) VALUES ('127.0.0.1') RETURNING id"
            )
            
            # B. Mesaj oluştur (Oturuma bağlı)
            message_id = await conn.fetchval(
                "INSERT INTO belek_chatbot.messages (session_id, role, content) VALUES ($1, 'user', 'Entegrasyon Test Mesajı') RETURNING id",
                session_id
            )
            
            # C. Suni bir sistem hatası fırlat (Örn: LLM servisi çöktü veya elektrik kesildi)
            raise RuntimeError("Yapay sistem hatası simülasyonu (Rollback tetikleyici)")
            
    except RuntimeError as e:
        # Fırlatılan hatanın beklenen test hatası olduğunu doğrula
        assert str(e) == "Yapay sistem hatası simülasyonu (Rollback tetikleyici)"
        
    # 3. Hata Sonrası Veri Bütünlüğü Kontrolü (ASSERTION)
    # Transaction iptal olduğu (Rollback) için bu ID'lerin veritabanında HİÇ OLMAMASI gerekir.
    
    if session_id:
        session_exists = await conn.fetchval("SELECT id FROM belek_chatbot.sessions WHERE id = $1", session_id)
        assert session_exists is None, "Kritik Hata: Oturum kaydı geri alınmadı (Rollback başarısız)!"
        
    if message_id:
        message_exists = await conn.fetchval("SELECT id FROM belek_chatbot.messages WHERE id = $1", message_id)
        assert message_exists is None, "Kritik Hata: Mesaj kaydı geri alınmadı (Rollback başarısız)!"
    
    # Bağlantıyı kapat
    await conn.close()