"""
BU Chatbot API — FastAPI giriş noktası.

Endpoint'ler:
  POST /ask    — Soru-cevap (rate-limited)
  GET  /health — Bağımlılık durumu kontrolü
"""
import logging
import os
import re
import time
from contextlib import asynccontextmanager
from urllib.parse import quote_plus

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from . import db
from .query_v2 import ask_question_v2 as ask_question

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

# ---------------------------------------------------------------------------
# DB DSN
# ---------------------------------------------------------------------------


def _build_dsn() -> str:
    """DB_* env var'larından PostgreSQL DSN oluşturur. Herhangi biri eksikse boş döner."""
    host     = os.getenv("DB_HOST", "")
    port     = os.getenv("DB_PORT", "5432")
    name     = os.getenv("DB_NAME", "")
    user     = os.getenv("DB_USER", "")
    password = os.getenv("DB_PASSWORD", "")
    if not all([host, name, user, password]):
        return ""
    return f"postgresql://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{name}"


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_pool(_build_dsn())
    # Modelleri startup'ta yükle — ilk kullanıcı isteği soğuk başlatmaya kurban gitmesin
    import asyncio
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _preload_models)
    yield
    await db.close_pool()


def _preload_models() -> None:
    """Embedding ve reranker modellerini arka planda yükle."""
    try:
        from backend.query_v2 import _init_v2
        _init_v2()
        logger.info("Model preload tamamlandı — ilk istek hazır.")
    except Exception as exc:
        logger.warning("Model preload başarısız (ilk istek yükleyecek): %s", exc)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="BU Chatbot API", version="2.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_cors_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# ---------------------------------------------------------------------------
# Input sanitizasyonu
# ---------------------------------------------------------------------------

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _sanitize_input(text: str) -> str:
    """Kontrol karakterlerini temizle."""
    return _CONTROL_CHAR_RE.sub("", text).strip()


# ---------------------------------------------------------------------------
# Request / Response modelleri
# ---------------------------------------------------------------------------


class HistoryMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    history: list[HistoryMessage] = []


# ---------------------------------------------------------------------------
# Endpoint'ler
# ---------------------------------------------------------------------------


@app.post("/ask")
@limiter.limit("50/minute")
async def chat(request: Request, body: ChatRequest):
    start = time.monotonic()
    error_status: str | None = None
    result: dict = {}

    try:
        question = _sanitize_input(body.question)
        if not question:
            raise HTTPException(status_code=400, detail="Soru boş olamaz.")

        history = [{"role": m.role, "content": m.content} for m in body.history]
        result = ask_question(question, history)
        return {
            "answer":   result["answer"],
            "sources":  result["sources"],
            "category": result.get("category", "genel"),
            "engine":   result.get("engine", "v1"),
        }
    except HTTPException:
        raise
    except RuntimeError as e:
        error_status = str(e)[:255]
        logger.error("Servis hatası: %s", e)
        raise HTTPException(status_code=503, detail=str(e))
    except httpx.TimeoutException:
        error_status = "TimeoutException"
        raise HTTPException(status_code=504, detail="Arama servisi zaman aşımına uğradı.")
    except Exception as e:
        error_status = str(e)[:255]
        logger.error("Beklenmeyen hata: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Yanıt oluşturulurken bir hata oluştu.")
    finally:
        latency_ms = int((time.monotonic() - start) * 1000)
        pool = db.get_pool()
        if pool and result:
            try:
                await db.log_interaction(
                    pool,
                    user_ip=request.client.host if request.client else "unknown",
                    question=body.question,
                    answer=result.get("answer", ""),
                    sources=result.get("sources", []),
                    latency_ms=latency_ms,
                    error_status=error_status,
                )
            except Exception as exc:
                logger.warning("DB log hatası: %s", exc)


@app.get("/health")
@limiter.limit("200/minute")
async def health(request: Request):
    checks: dict[str, str] = {"api": "ok"}

    # Groq API key kontrolü
    checks["groq_key"] = "ok" if os.getenv("GROQ_API_KEY") else "missing"

    # Qdrant bağlantı kontrolü (local disk veya uzak sunucu)
    try:
        from qdrant_client import QdrantClient
        qdrant_path = os.getenv("QDRANT_PATH", "")
        if qdrant_path:
            client = QdrantClient(path=qdrant_path)
        else:
            host = os.getenv("QDRANT_HOST", "localhost")
            port = int(os.getenv("QDRANT_PORT", "6333"))
            client = QdrantClient(host=host, port=port, timeout=3)
        client.get_collection("belek_v2")
        checks["qdrant"] = "ok"
    except Exception:
        checks["qdrant"] = "unavailable"

    # ChromaDB varlık kontrolü (V1 fallback)
    vector_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vector_db")
    checks["chromadb"] = "ok" if os.path.isdir(vector_db_path) else "missing"

    # PostgreSQL bağlantı kontrolü
    pool = db.get_pool()
    if pool:
        checks["postgres"] = await db.check_health(pool)
    else:
        checks["postgres"] = "unavailable"

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(checks, status_code=200 if all_ok else 503)
