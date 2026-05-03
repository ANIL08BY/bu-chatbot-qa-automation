# BU Chatbot — Belek Üniversitesi RAG Asistanı

Belek Üniversitesi yönetmelik ve akademik dokümanlarına dayalı soru-cevap chatbotu.

**Stack:** FastAPI · LangChain · Groq (Llama 3.3 70B) · Chroma · React 19 · TypeScript · Vite · Tailwind CSS

---

## Kurulum

### Gereksinimler
- Python 3.11+
- Node.js 18+
- Groq API anahtarı → https://console.groq.com

### 1. Python bağımlılıklarını kur

```bash
cd C:\Users\yusuf\Desktop\bu-chatbot
pip install -r requirements.txt
```

### 2. `.env` dosyasını oluştur

Proje kökünde bir `.env` dosyası oluştur (zaten varsa atla):

```
GROQ_API_KEY=gsk_...buraya_kendi_anahtarını_yaz...
```

### 3. Vektör veritabanını oluştur (ilk kurulumda bir kez)

```bash
cd C:\Users\yusuf\Desktop\bu-chatbot
python -m backend.ingest
```

> `backend/vector_db/` klasörü oluşturulur. Yeni PDF eklenirse bu adımı tekrar çalıştır.

### 4. Frontend bağımlılıklarını kur

```bash
cd C:\Users\yusuf\Desktop\bu-chatbot\frontend
npm install
```

---

## Çalıştırma

### Terminal 1 — Backend

```bash
cd C:\Users\yusuf\Desktop\bu-chatbot
uvicorn backend.main:app --reload
```

API `http://127.0.0.1:8000` adresinde çalışır.
Swagger dokümantasyonu: `http://127.0.0.1:8000/docs`

### Terminal 2 — Frontend

```bash
cd C:\Users\yusuf\Desktop\bu-chatbot\frontend
npm run dev
```

Uygulama `http://localhost:5173` adresinde açılır.

---

## Proje Yapısı

```
bu-chatbot/
├── .env                      # API anahtarları (git'e ekleme!)
├── requirements.txt          # Python bağımlılıkları
├── backend/
│   ├── __init__.py
│   ├── main.py               # FastAPI uygulaması
│   ├── ingest.py             # PDF → Vektör DB pipeline
│   ├── query.py              # RAG sorgu motoru
│   └── data/
│       └── yonetmelik.pdf    # Kaynak doküman
└── frontend/
    ├── .env                  # VITE_API_URL
    └── src/
        ├── App.tsx
        └── components/
```

---

## API Endpoints

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| POST | `/ask` | Soru sor, cevap + kaynak döner |
| GET | `/health` | Servis durumu |
| GET | `/docs` | Swagger UI |

### `/ask` Request

```json
{
  "question": "Yatay geçiş şartları nelerdir?",
  "history": [
    { "role": "user", "content": "Merhaba" },
    { "role": "assistant", "content": "Merhaba! Nasıl yardımcı olabilirim?" }
  ]
}
```

### `/ask` Response

```json
{
  "answer": "Yatay geçiş için...",
  "sources": [
    { "page": 12, "snippet": "Madde 15 - Yatay geçiş başvuruları..." }
  ]
}
```
