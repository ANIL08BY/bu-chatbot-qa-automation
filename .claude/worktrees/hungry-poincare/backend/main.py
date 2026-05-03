from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from .query import ask_question

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="BU Chatbot API", version="1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class HistoryMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    history: list[HistoryMessage] = []


@app.post("/ask")
@limiter.limit("50/minute")
async def chat(request: Request, body: ChatRequest):
    try:
        history = [{"role": m.role, "content": m.content} for m in body.history]
        result = ask_question(body.question, history)
        return {
            "answer":   result["answer"],
            "sources":  result["sources"],
            "category": result.get("category", "genel"),
        }
    except Exception as e:
        print(f"HATA: {str(e)}")
        raise HTTPException(status_code=500, detail="Yanıt oluşturulurken bir hata oluştu.")


@app.get("/health")
async def health():
    return {"status": "ok", "message": "BU Chatbot API çalışıyor."}
