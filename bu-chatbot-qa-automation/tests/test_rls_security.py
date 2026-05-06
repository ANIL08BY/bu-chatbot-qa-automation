import pytest
import logging
from backend import db

# ====================================================================
# SAHTE (FAKE) VERİTABANI SINIFLARI
# Python'ın Mock kütüphanesiyle savaşmak yerine, async with kurallarına
# %100 uyan kendi sahte veritabanı mimarimizi (Fake Object Pattern) yazıyoruz.
# ====================================================================

class FakeTransaction:
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

class FakeConnection:
    def __init__(self):
        self.fetchval_called = False

    def transaction(self):
        # "async with conn.transaction():" bloğunu sorunsuz geçer
        return FakeTransaction()

    async def fetchval(self, *args, **kwargs):
        # Veritabanına INSERT atıldığında bombayı burada patlatıyoruz!
        self.fetchval_called = True
        raise Exception("insufficient_privilege: RLS engeli - Anonim işlem reddedildi!")

    async def execute(self, *args, **kwargs):
        pass

class FakeAcquire:
    def __init__(self, conn):
        self.conn = conn
    async def __aenter__(self):
        # "async with pool.acquire() as conn:" bloğunu sorunsuz geçer
        return self.conn
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

class FakePool:
    def __init__(self):
        self.conn = FakeConnection()
    def acquire(self):
        return FakeAcquire(self.conn)

# ====================================================================
# ASIL TEST SENARYOSU
# ====================================================================

@pytest.mark.asyncio
async def test_rls_anonymous_user_silent_fail(caplog):
    """
    RLS (Row-Level Security) Simülasyon Testi:
    Kimlik doğrulaması olmayan (anonim) bir işlem veritabanına yazılmaya çalışıldığında,
    RLS kuralının işlemi reddettiğini ve backend'in bu hatayı 500 fırlatmak yerine 
    sessizce yuttuğunu (Silent Fail) doğrular.
    """
    
    # 1. ARRANGE (Hazırlık): Sahte veritabanı havuzumuzu oluştur
    fake_pool = FakePool()
    
    # Log yakalayıcıyı aktifleştir
    caplog.set_level(logging.WARNING)

    # 2. ACT (Eylem): Arka yüz fonksiyonunu tetikle
    await db.log_interaction(
        pool=fake_pool,
        user_ip="127.0.0.1", 
        question="Veritabanı RLS testi",
        answer="Bu bir testtir",
        sources=[],
        latency_ms=42,
        error_status=None
    )

    # 3. ASSERT (Doğrulama)
    # A) Veritabanına gerçekten kayıt atılmaya çalışıldı mı?
    assert fake_pool.conn.fetchval_called, "HATA: Veritabanına INSERT isteği hiç gitmedi!"
    
    # B) Yutulan RLS hatası sistem loglarına doğru şekilde yazıldı mı?
    assert "DB log_interaction hatası" in caplog.text, "Sistem hatayı yuttu ama loglamayı unuttu!"
    assert "insufficient_privilege: RLS engeli" in caplog.text, "RLS uyarısı loglarda bulunamadı!"