"""
PostgreSQL bağlantı modülü — belek_chatbot şeması.

Tablolar:
  sessions    — Her /ask isteği için yeni oturum
  messages    — Kullanıcı sorusu + asistan yanıtı
  citations   — Yanıt kaynakları
  system_logs — Gecikme süresi ve hata durumu

Kullanım (main.py):
  await db.init_pool(dsn)          # startup
  pool = db.get_pool()
  await db.log_interaction(pool, ...)
  await db.close_pool()            # shutdown
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_pool = None  # asyncpg.Pool | None


async def init_pool(dsn: str) -> None:
    """Bağlantı havuzunu başlat. DSN boşsa sessizce atla."""
    global _pool
    if not dsn:
        logger.warning("DB_* env değişkenleri eksik — PostgreSQL kaydı devre dışı.")
        return
    try:
        import asyncpg
        _pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5, command_timeout=5, ssl="require")
        logger.info("PostgreSQL bağlantı havuzu başlatıldı.")
    except Exception as exc:
        logger.warning("PostgreSQL bağlanamadı, kayıt devre dışı: %s", exc)
        _pool = None


async def close_pool() -> None:
    """Bağlantı havuzunu kapat."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("PostgreSQL bağlantı havuzu kapatıldı.")


def get_pool():
    """Mevcut havuzu döndür. Başlatılmamışsa None."""
    return _pool


async def check_health(pool) -> str:
    """Basit ping. Başarılıysa 'ok', hata varsa 'unavailable'."""
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return "ok"
    except Exception:
        return "unavailable"


async def log_interaction(
    pool,
    *,
    user_ip: str,
    question: str,
    answer: str,
    sources: list[dict[str, Any]],
    latency_ms: int,
    error_status: str | None,
) -> int | None:
    """
    Tek transaction içinde sırasıyla:
      1. sessions  → yeni oturum aç
      2. messages  → kullanıcı mesajı
      3. messages  → asistan mesajı
      4. citations → her kaynak için bir satır
      5. system_logs → gecikme ve hata durumu

    Başarılı olursa asistan mesajının id'sini döndürür (feedback için kullanılır).
    Herhangi bir hata oluşursa transaction geri alınır, None döner ve uyarı loglanır.
    Bu fonksiyon HİÇBİR ZAMAN exception fırlatmaz.
    """
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():

                # 1. Oturum
                session_id: int = await conn.fetchval(
                    """
                    INSERT INTO belek_chatbot.sessions (user_ip)
                    VALUES ($1)
                    RETURNING id
                    """,
                    user_ip,
                )

                # 2. Kullanıcı mesajı
                await conn.fetchval(
                    """
                    INSERT INTO belek_chatbot.messages (session_id, role, content)
                    VALUES ($1, $2, $3)
                    RETURNING id
                    """,
                    session_id, "user", question,
                )

                # 3. Asistan mesajı
                asst_msg_id: int = await conn.fetchval(
                    """
                    INSERT INTO belek_chatbot.messages (session_id, role, content)
                    VALUES ($1, $2, $3)
                    RETURNING id
                    """,
                    session_id, "assistant", answer,
                )

                # 4. Kaynaklar (citations)
                for source in sources:
                    raw_page = source.get("page")
                    page_num: int | None = raw_page if isinstance(raw_page, int) else None
                    doc_name: str = (source.get("url") or "")[:255]

                    await conn.execute(
                        """
                        INSERT INTO belek_chatbot.citations (message_id, doc_name, page_num)
                        VALUES ($1, $2, $3)
                        """,
                        asst_msg_id, doc_name, page_num,
                    )

                # 5. Sistem logu
                await conn.execute(
                    """
                    INSERT INTO belek_chatbot.system_logs (message_id, latency_ms, error_status)
                    VALUES ($1, $2, $3)
                    """,
                    asst_msg_id, latency_ms, error_status,
                )

        return asst_msg_id

    except Exception as exc:
        # Stack trace ile logla — RLS bypass eksikliği gibi sessiz fail'lerin gerçek
        # kaynağı görünür olsun. Yanıt akışı etkilenmez (logging best-effort'tur).
        logger.exception("DB log_interaction hatası (yanıt etkilenmedi): %s", exc)
        return None


async def save_feedback(
    pool,
    *,
    message_id: int,
    is_positive: bool,
    comment: str | None = None,
) -> bool:
    """
    Kullanıcının bir asistan mesajına verdiği geri bildirimi (like/dislike) kaydet.

    feedback tablosunda message_id UNIQUE olduğundan ON CONFLICT ile günceller:
    kullanıcı fikrini değiştirirse (like → dislike) yeni değer geçerli olur.

    Başarılı olursa True, aksi halde False döner. Exception fırlatmaz.
    """
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO belek_chatbot.feedback (message_id, is_positive, comment)
                VALUES ($1, $2, $3)
                ON CONFLICT (message_id)
                DO UPDATE SET
                    is_positive = EXCLUDED.is_positive,
                    comment     = EXCLUDED.comment
                """,
                message_id, is_positive, comment,
            )
        return True
    except Exception as exc:
        logger.exception("DB save_feedback hatası: %s", exc)
        return False
