# BU Chatbot — Belek Üniversitesi RAG Asistanı

Belek Üniversitesi yönetmelik ve akademik dokümanlarına dayalı soru-cevap chatbotu.

**Stack:** FastAPI · Groq (Llama 3.3 70B) · Qdrant (hybrid search) · Dagster · React 19 · TypeScript · Vite · Tailwind CSS

---

## Mimari

```
ingestion_list.json → Dagster Pipeline V2 → Qdrant (dense + BM42)
                                                    ↓
React Frontend → FastAPI /ask → Query V2 (hybrid search + reranker)
                                    ↓ (fallback)
                               Query V1 (ChromaDB + BM25 + RRF)
```

- **V2 (birincil):** Qdrant hybrid arama + BAAI/bge-reranker-v2-m3 cross-encoder
- **V1 (fallback):** ChromaDB MMR + BM25 pickle + Reciprocal Rank Fusion
- **LLM fallback:** llama-3.3-70b → llama-3.1-8b-instant → gemma2-9b-it
- **16 metadata kategorisi** otomatik olarak `ingestion_list.json`'dan türetilir

Detaylı mimari: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

---

## Gereksinimler

- Python 3.11+
- Node.js 18+
- Python paketleri yeterli — Qdrant local disk modunda çalışır, Docker gerekmez
- Groq API anahtarı → https://console.groq.com
- Firecrawl API anahtarı → https://firecrawl.dev

---

## Kurulum

### 1. Python bağımlılıklarını kur

```bash
python -m venv venv
source venv/Scripts/activate   # Windows
pip install -r requirements.txt
```

### 2. `.env` dosyasını oluştur

```bash
cp .env.example .env
# .env dosyasını düzenleyerek API anahtarlarını gir
```

Değişkenler:
| Değişken | Açıklama | Zorunlu |
|----------|----------|---------|
| `GROQ_API_KEY` | Groq LLM API anahtarı | Evet |
| `FIRECRAWL_API_KEY` | Firecrawl web scraping API | Pipeline için evet |
| `QDRANT_PATH` | Qdrant local disk dizini (varsayılan: `./qdrant_local`) | Hayır |
| `QDRANT_HOST` | Docker/uzak sunucu adresi — `QDRANT_PATH` boşsa kullanılır | Hayır |
| `QDRANT_PORT` | Qdrant portu — `QDRANT_PATH` boşsa kullanılır | Hayır |
| `CORS_ORIGINS` | İzin verilen origin'ler (virgülle ayrılmış) | Hayır |

### 3. Data pipeline'ı çalıştır

```bash
# Dagster web arayüzü ile
dagster dev -w workspace.yaml

# Veya komut satırından
dagster job execute -m backend.pipeline_v2.definitions -j full_pipeline_job
```

### 5. Frontend bağımlılıklarını kur

```bash
cd frontend
npm install
```

---

## Çalıştırma

### Terminal 1 — Backend

```bash
uvicorn backend.main:app --reload
```

API: `http://127.0.0.1:8000` · Swagger: `http://127.0.0.1:8000/docs`

### Terminal 2 — Frontend

```bash
cd frontend && npm run dev
```

Uygulama: `http://localhost:5173`

---

## Test

```bash
# Unit testler
pytest tests/ -v

# Evaluation testleri (Qdrant gerekli)
pytest -m slow tests/ -v
```

---

## API Endpoints

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| POST | `/ask` | Soru sor — cevap + kaynak + kategori + motor bilgisi döner |
| GET | `/health` | Bağımlılık durumu (Qdrant, Groq key, ChromaDB) |
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
    { "page": 12, "url": "https://...", "snippet": "Madde 15 - Yatay geçiş..." }
  ],
  "category": "kurum-ici-yatay-gecis",
  "engine": "v2"
}
```

---

## Proje Yapısı

```
bu-chatbot/
├── .env.example              # Environment variable şablonu
├── requirements.txt          # Python bağımlılıkları (pinlenmiş)
├── workspace.yaml            # Dagster workspace config
├── ingestion_list.json       # Veri kaynakları manifestosu (16 kaynak)
├── backend/
│   ├── main.py               # FastAPI uygulaması
│   ├── query.py              # V1 RAG motoru (ChromaDB + BM25)
│   ├── query_v2.py           # V2 RAG motoru (Qdrant + Reranker)
│   ├── rag_common.py         # Paylaşılan RAG yardımcıları
│   ├── rag_config.py         # Merkezi RAG konfigürasyonu
│   ├── prompts/              # Externalized prompt template'leri
│   └── pipeline_v2/          # Dagster data pipeline
│       ├── assets/           # Dagster asset'leri (ingestion, clean, chunk, store)
│       ├── resources/        # Dagster resource'ları (Firecrawl, Embedding, Qdrant)
│       ├── schemas/          # Veri doğrulama şemaları
│       └── evaluation/       # RAG kalite metrikleri (Hit Rate, MRR)
├── frontend/                 # React 19 + TypeScript + Vite
│   └── src/
│       ├── App.tsx
│       └── components/
├── tests/                    # pytest test altyapısı
└── docs/                     # Mimari dokümantasyon
```
