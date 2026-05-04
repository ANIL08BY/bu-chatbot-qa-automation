# BU Chatbot — Belek Üniversitesi RAG tabanlı Sanal Asistanı

Belek Üniversitesinin yönetmelik ve akademik dokümanlarına dayalı RAG mimarili soru-cevap chatbotu.

**Stack:** FastAPI · Groq (Llama 3.3 70B) · Qdrant (hybrid search) · Dagster · React 19 · TypeScript · Vite · Tailwind CSS · PostgreSQL

---

## Mimari

```
ingestion_list.json → Dagster Pipeline V2 → Qdrant (dense + BM42)
                                                    ↓
React Frontend → FastAPI /ask → Query V2 (hybrid + cross-encoder reranker)
                    │             ↓ (Qdrant erişilemezse)
                    │           Query V1 (ChromaDB + BM25 + RRF)
                    │             ↓ (LLM rate limit)
                    │           Model fallback (70b → llama-4-scout → 8b)
                    │
                    └→ PostgreSQL log_interaction()
```

- **V2 (birincil):** Qdrant hybrid (dense 768d + BM42 sparse) + `BAAI/bge-reranker-base` cross-encoder
- **V1 (fallback):** ChromaDB MMR + BM25 pickle + Reciprocal Rank Fusion
- **LLM fallback:** `llama-3.3-70b-versatile` → `meta-llama/llama-4-scout-17b-16e-instruct` → `llama-3.1-8b-instant`
- **54 metadata kategorisi** otomatik olarak `ingestion_list.json`'dan türetilir (her kaynak kendi kategorisinde)

Detaylı mimari: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

---

## Gereksinimler

- Python 3.11+
- Node.js 18+
- (Opsiyonel) PostgreSQL 13+ — interaksiyon loglaması için
- Groq API anahtarı → https://console.groq.com
- Firecrawl API anahtarı → https://firecrawl.dev (yalnızca pipeline çalıştırılırken)

---

## Kurulum

### 1. Python bağımlılıklarını kur

```bash
# Sanal ortam oluştur
python -m venv venv
```

```powershell
# Aktif et — Windows (PowerShell)
.\venv\Scripts\Activate.ps1
```

```bash
# Aktif et — Windows (CMD / Git Bash)
venv\Scripts\activate

# Aktif et — Linux / macOS
source venv/bin/activate
```

```bash
# Bağımlılıkları kur
pip install -r requirements.txt
```

### 2. `.env` dosyasını oluştur

```bash
# Linux / macOS / Git Bash
cp .env.example .env
```

```powershell
# Windows (PowerShell)
Copy-Item .env.example .env
```

```cmd
:: Windows (CMD)
copy .env.example .env
```

`.env` dosyasını düzenleyerek API anahtarlarını gir.

| Değişken | Açıklama | Zorunlu |
|----------|----------|:-------:|
| `GROQ_API_KEY` | Groq LLM API anahtarı | ✅ |
| `FIRECRAWL_API_KEY` | Firecrawl web scraping API | Pipeline için |
| `QDRANT_PATH` | Qdrant local disk dizini (varsayılan: `./qdrant_local`) | — |
| `QDRANT_HOST`, `QDRANT_PORT` | `QDRANT_PATH` boşsa kullanılır (Docker / uzak) | — |
| `CORS_ORIGINS` | İzin verilen origin'ler (virgülle ayrılmış) | — |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | PostgreSQL bağlantı bilgileri (eksikse logging devre dışı kalır) | — |

### 3. (Opsiyonel) PostgreSQL şemasını kur

Interaksiyon loglaması istiyorsanız aşağıdaki tabloları `belek_chatbot` şeması altında oluşturun:

```sql
CREATE SCHEMA IF NOT EXISTS belek_chatbot;
SET search_path TO belek_chatbot;

CREATE TABLE sessions (
    id           SERIAL PRIMARY KEY,
    user_ip      VARCHAR(45) NOT NULL,
    start_time   TIMESTAMP   NOT NULL DEFAULT NOW()
);

CREATE TABLE messages (
    id           SERIAL PRIMARY KEY,
    session_id   INTEGER     NOT NULL REFERENCES sessions(id),
    role         VARCHAR(50) NOT NULL,
    content      TEXT        NOT NULL,
    timestamp    TIMESTAMP   NOT NULL DEFAULT NOW()
);

CREATE TABLE citations (
    id           SERIAL PRIMARY KEY,
    message_id   INTEGER      NOT NULL REFERENCES messages(id),
    doc_name     VARCHAR(255) NOT NULL,
    page_num     INTEGER
);

CREATE TABLE feedback (
    id           SERIAL PRIMARY KEY,
    message_id   INTEGER NOT NULL UNIQUE REFERENCES messages(id),
    is_positive  BOOLEAN NOT NULL,
    comment      TEXT
);

CREATE TABLE system_logs (
    id           SERIAL PRIMARY KEY,
    message_id   INTEGER      NOT NULL UNIQUE REFERENCES messages(id),
    latency_ms   INTEGER,
    error_status VARCHAR(255)
);
```

> **Not:** `backend/db.py` `belek_chatbot` şema prefix'iyle yazıyor. Tabloları başka bir şemaya kuracaksanız `db.py`'deki `INSERT INTO belek_chatbot.*` ifadelerini güncellemeniz gerekir.

### 4. Veri pipeline'ını çalıştır

```bash
# Dagster web arayüzü ile (önerilen)
dagster dev -w workspace.yaml

# Komut satırından tek seferlik
dagster job execute -m backend.pipeline_v2.definitions -j full_pipeline_job
```

Bu adım `ingestion_list.json`'daki kaynakları çekip Qdrant'a indeksler. Bitince `qdrant_local/` klasörü oluşur.

### 5. Frontend bağımlılıklarını kur

```bash
cd frontend
npm install
```

`frontend/.env` dosyası `VITE_API_URL=/api` olarak ayarlıdır — Vite proxy üzerinden backend'e yönlendirir.

---

## Çalıştırma

### Terminal 1 — Backend

```bash
# Uvicorn ile (önerilen)
uvicorn backend.main:app --reload

# Veya Python script ile
python run_backend.py
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
# Unit testler (hızlı, dış servis gerektirmez)
pytest tests/ -v

# Evaluation testleri (Qdrant + GROQ_API_KEY gerekli)
pytest -m slow tests/ -v
```

`pytest.ini`'de tanımlı `slow` marker'ı, RAG kalite metriklerini ölçen testleri ayırır. Bu testler hem Qdrant koleksiyonunun dolu olmasını hem de geçerli bir `GROQ_API_KEY` değerini gerektirir.

---

## Yardımcı Script'ler

| Script | Amaç |
|--------|------|
| `run_backend.py` | `.env` yükleyip uvicorn'u başlatan kısayol |
| `map_url.py` | Firecrawl ile URL keşfi → `ingestion_list.json` güncelleme |
| `apply_preview.py` | `ingestion_preview/`'daki manuel düzenlenmiş `.md` dosyalarını Qdrant'a aktarma |

Detaylı kullanım her script'in dosyasındaki docstring'de.

---

## API Endpoints

| Method | Endpoint | Rate Limit | Açıklama |
|--------|----------|:----------:|----------|
| POST | `/ask` | 50/dk | Soru sor — cevap + kaynak + kategori + motor |
| GET | `/health` | 200/dk | Bağımlılık durumu (Qdrant, Groq key, ChromaDB, PostgreSQL) |
| GET | `/docs` | — | Swagger UI |

Limit aşılırsa `429 Too Many Requests` döner.

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

### `/health` Response

```json
{
  "api": "ok",
  "groq_key": "ok",
  "qdrant": "ok",
  "chromadb": "ok",
  "postgres": "ok"
}
```

Bütün bileşenler `ok` ise HTTP 200; herhangi biri `unavailable`/`missing` ise HTTP 503.

---

## Proje Yapısı

```
bu-chatbot/
├── .env.example              # Environment variable şablonu
├── requirements.txt          # Python bağımlılıkları (pinlenmiş)
├── workspace.yaml            # Dagster workspace config
├── ingestion_list.json       # Veri kaynakları manifestosu (54 kaynak)
├── pytest.ini                # Test marker tanımları
├── run_backend.py            # Backend başlatıcı script
├── map_url.py                # Firecrawl URL keşif aracı
├── apply_preview.py          # Manuel düzenlenmiş .md → Qdrant
├── backend/
│   ├── main.py               # FastAPI uygulaması (rate limit, lifespan)
│   ├── db.py                 # PostgreSQL logging (asyncpg)
│   ├── query.py              # V1 RAG motoru (ChromaDB + BM25)
│   ├── query_v2.py           # V2 RAG motoru (Qdrant + Reranker)
│   ├── rag_common.py         # Paylaşılan: chain, prompt, kategori, fallback
│   ├── rag_config.py         # Merkezi RAG konfigürasyonu (k, weights, vb.)
│   ├── prompts/              # Externalized prompt template'leri
│   └── pipeline_v2/          # Dagster data pipeline
│       ├── assets/           # Asset'ler (web, pdf, clean, chunk, qdrant)
│       ├── resources/        # Resource'lar (Firecrawl, Embedding, Qdrant)
│       ├── schemas/          # Veri doğrulama şemaları
│       └── evaluation/       # RAG kalite metrikleri (Hit Rate, MRR)
├── frontend/                 # React 19 + TypeScript + Vite + Tailwind
│   └── src/
│       ├── App.tsx
│       └── components/
├── ingestion_preview/        # apply_preview.py için stage alanı
├── tests/                    # pytest test altyapısı
└── docs/
    └── ARCHITECTURE.md       # Detaylı mimari dokümantasyon
```

---

## Daha Fazla Bilgi

- **Mimari diyagramı:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- **Pipeline asset DAG'ı:** `dagster dev -w workspace.yaml` ile Dagster UI üzerinden
- **Evaluation rubric:** `backend/pipeline_v2/evaluation/eval.py` (Hit Rate, MRR)
- **Tailwind tema özelleştirmesi:** `frontend/tailwind.config.js`
