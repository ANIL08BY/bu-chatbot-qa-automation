import pytest
import asyncio
# asyncpg hatalarını yakalamak için
try:
    from asyncpg.exceptions import ForeignKeyViolationError
except ImportError:
    ForeignKeyViolationError = Exception 

@pytest.mark.asyncio
async def test_session_delete_restrict_rule(db_pool):
    """
    Yusuf'un bahsettiği RESTRICT kuralını test eder:
    İçinde mesaj (message) olan bir oturum (session) silinmeye çalışıldığında 
    veritabanı buna izin vermemeli ve hata fırlatmalıdır.
    """
    
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            # 1. ARRANGE: Bir oturum oluştur ve ona bağlı bir mesaj ekle
            session_id = await conn.fetchval(
                "INSERT INTO belek_chatbot.sessions (user_ip) VALUES ($1) RETURNING id",
                "127.0.0.1"
            )
            
            await conn.execute(
                "INSERT INTO belek_chatbot.messages (session_id, role, content) VALUES ($1, $2, $3)",
                session_id, "user", "Burs olanakları nelerdir?"
            )

            # 2. ACT & ASSERT: İçinde mesaj olan oturumu silmeye çalış
            # RESTRICT kuralı gereği bu işlemin ForeignKeyViolationError fırlatması gerekir.
            with pytest.raises(ForeignKeyViolationError):
                await conn.execute("DELETE FROM belek_chatbot.sessions WHERE id = $1", session_id)
            
            # 3. CLEANUP: İşlemi geri al (Rollback otomatik gerçekleşir ama temizlik iyidir)
            await conn.execute("ROLLBACK")