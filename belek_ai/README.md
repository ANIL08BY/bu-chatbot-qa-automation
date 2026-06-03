# Belek AI

> **Belek Üniversitesi için RAG mimarili Türkçe akademik sanal asistan.**
> Yusuf İlbey Aydın'ın bitirme tez projesi.

Belek AI; üniversitenin yönetmelikleri, akademik takvimleri, bölüm/program sayfaları, idari belgeleri ve duyurularına dayalı doğal dil soru-cevap sağlar. Kullanıcı sorduğu soruyu, Qdrant üzerinde **hibrit arama** (dense embedding + BM42 sparse) ile en alakalı belge parçalarına eşleştirir; cross-encoder ile yeniden sıralar; ardından Groq Llama 3.3 70B (veya OpenAI/Gemini) üzerinde, sıkı kurallarla yazılmış bir prompt ile yanıt üretir.
Belek AI; üniversitenin yönetmelikleri, akademik takvimleri, bölüm/program sayfaları, idari belgeleri ve duyurularına dayalı doğal dil soru-cevap sağlar. Kullanıcı sorduğu soruyu Qdrant üzerinde **dense anlamsal arama** (768d kosinüs, HNSW indeksi) ile en alakalı belge parçalarına eşleştirir; ardından **cross-encoder** (`BAAI/bge-reranker-base`) ile iki aşamalı (retrieve-then-rerank) olarak yeniden sıralar; son olarak Groq Llama 3.3 70B (veya OpenAI/Gemini) üzerinde sıkı kurallarla yazılmış bir prompt ile yanıt üretir. Qdrant koleksiyon şemasında BM42 sparse vektör config'i hazır bulundurulmakta; aktif kullanım yol haritasının ileri sürümüne (v2.1) bırakılmıştır.

---

@@ -43,15 +43,15 @@
───────────────────▶ │ raw\_\* → hash_dedup → clean → chunk │
│ ↓ │
│ Qdrant Cloud │
│ (dense 768d + BM42) │
│ (dense 768d cosine) │
╰───────────────────────────────────────────────╯
▲
│ retrieval
│
┌────────── Frontend ──────────┐ POST /ask ┌──────────── Backend (FastAPI) ────────┐
│ React 19 + Vite + Tailwind │ ───────────▶ │ analyze_query (Groq llama-3.1-8b) │
│ ChatHeader · ChatMessage │ │ ↓ │
│ ChatInput · SettingsModal │ │ Qdrant hybrid search (k = 5/15/18/40) │
│ ChatInput · SettingsModal │ │ Qdrant dense search (k = 5/15/18/40) │
│ localStorage persist │ │ ↓ │
│ Markdown render + feedback │ │ Cross-encoder rerank (bge-base) │
└──────────────────────────────┘ │ ↓ │
@@ -79,7 +79,7 @@
| **Backend** | FastAPI · Uvicorn · slowapi (rate limit) · python-dotenv |
| **LLM** | Groq (Llama 3.3 70B + fallback) · OpenAI (gpt-4o-mini) · Gemini (2.5-flash) — `LLM_PROVIDER` ile seçim |
| **LLM framework** | LangChain · langchain-groq · langchain-openai · langchain-google-genai |
| **Vector DB** | Qdrant ≥1.9 (Cloud aktif, dense 768d + BM42 sparse) |
| **Vector DB** | Qdrant ≥1.9 (Cloud aktif, dense 768d kosinüs, HNSW) |
| **Embedding** | `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` (Türkçe destekli) |
| **Reranker** | `BAAI/bge-reranker-base` (cross-encoder, query-time) |
| **Pipeline** | Dagster ≥1.7 (asset DAG, incremental dedup, web UI) |
@@ -170,300 +170,328 @@

### 5.3 (Opsiyonel) PostgreSQL Şeması

İnteraksiyon loglaması istiyorsan `belek_chatbot` şemasını kur:
İnteraksiyon loglaması istiyorsan `belek_chatbot` şemasını kur. Aşağıdaki DDL **canlı veritabanı (Neon) şemasıyla birebir** uyumludur; her tablo işlevsel sütunların yanında ortak denetim (audit) sütunları içerir.

```sql
CREATE SCHEMA IF NOT EXISTS belek_chatbot;
SET search_path TO belek_chatbot;

CREATE TABLE sessions (
  id SERIAL PRIMARY KEY,
  user_ip VARCHAR(45) NOT NULL,
  start_time TIMESTAMP NOT NULL DEFAULT NOW()
  id          SERIAL PRIMARY KEY,
  user_ip     VARCHAR(45) NOT NULL,
  start_time  TIMESTAMP   NOT NULL DEFAULT NOW(),
  -- audit
  is_active   BOOLEAN   DEFAULT TRUE,
  created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  created_by  INTEGER,
  updated_at  TIMESTAMP,
  updated_by  INTEGER
);
CREATE TABLE messages (
  id SERIAL PRIMARY KEY,
  session_id INTEGER NOT NULL REFERENCES sessions(id),
  role VARCHAR(50) NOT NULL,
  content TEXT NOT NULL,
  timestamp TIMESTAMP NOT NULL DEFAULT NOW()
  id          SERIAL PRIMARY KEY,
  session_id  INTEGER NOT NULL REFERENCES sessions(id),
  role        VARCHAR(50) NOT NULL,            -- 'user' | 'assistant' (CHECK yok)
  content     TEXT NOT NULL,
  timestamp   TIMESTAMP NOT NULL DEFAULT NOW(),
  is_active   BOOLEAN   DEFAULT TRUE,
  created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  created_by  INTEGER,
  updated_at  TIMESTAMP,
  updated_by  INTEGER
);
CREATE TABLE citations (
  id SERIAL PRIMARY KEY,
  message_id INTEGER NOT NULL REFERENCES messages(id),
  doc_name VARCHAR(255) NOT NULL,
  page_num INTEGER
  id          SERIAL PRIMARY KEY,
  message_id  INTEGER NOT NULL REFERENCES messages(id),
  doc_name    VARCHAR(255) NOT NULL,
  page_num    INTEGER,
  is_active   BOOLEAN   DEFAULT TRUE,
  created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  created_by  INTEGER,
  updated_at  TIMESTAMP,
  updated_by  INTEGER
);
CREATE TABLE feedback (
  id SERIAL PRIMARY KEY,
  message_id INTEGER NOT NULL UNIQUE REFERENCES messages(id),
  id          SERIAL PRIMARY KEY,
  message_id  INTEGER NOT NULL UNIQUE REFERENCES messages(id),
  is_positive BOOLEAN NOT NULL,
  comment TEXT
  comment     TEXT,
  is_active   BOOLEAN   DEFAULT TRUE,
  created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  created_by  INTEGER,
  updated_at  TIMESTAMP,
  updated_by  INTEGER
);
CREATE TABLE system_logs (
  id SERIAL PRIMARY KEY,
  message_id INTEGER NOT NULL UNIQUE REFERENCES messages(id),
  latency_ms INTEGER,
  error_status VARCHAR(255)
  id           SERIAL PRIMARY KEY,
  message_id   INTEGER NOT NULL UNIQUE REFERENCES messages(id),
  latency_ms   INTEGER,
  error_status VARCHAR(255),
  is_active    BOOLEAN   DEFAULT TRUE,
  created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  created_by   INTEGER,
  updated_at   TIMESTAMP,
  updated_by   INTEGER
);
```

> **Denetim (audit) sütunları:** `created_at` ve `is_active` veritabanı varsayılanlarıyla otomatik dolar. `created_by`/`updated_by`/`updated_at` alanları uygulama tarafından yazılmaz (kullanıcı kimlik doğrulaması v2.1'e ertelenmiştir) → NULL kalır. Canlı şemada `created_by`/`updated_by`, kullanıcı tablosuna `ON DELETE SET NULL` ile bağlı INTEGER yabancı anahtarlardır. `backend/db.py` yalnızca işlevsel sütunlara INSERT yapar; audit sütunları varsayılan/NULL üzerinden çalışır.

> **RLS Uyarısı** (Supabase vb.): `db.py` `INSERT INTO belek_chatbot.*` yazar. RLS aktifse bot kullanıcısına ya `ALTER USER bot_user BYPASSRLS;` ver, ya da açık INSERT policy yaz. Aksi halde `log_interaction()` sessizce fail eder (loglarda stack trace görünür).

### 5.4 Frontend

```bash
cd frontend
npm install
```

`frontend/.env` zaten `VITE_API_URL=/api` olarak ayarlı — Vite dev sunucusu `/api/*` isteklerini `http://127.0.0.1:8000`'e proxy eder ([`vite.config.ts`](frontend/vite.config.ts)).

---

## 6. Çalıştırma

### Terminal 1 — Backend

```bash
uvicorn backend.main:app --reload
# veya
python run_backend.py
```

- API: <http://127.0.0.1:8000>
- Swagger UI: <http://127.0.0.1:8000/docs>
- Sağlık kontrolü: `curl http://127.0.0.1:8000/health`

### Terminal 2 — Frontend

```bash
cd frontend && npm run dev
```

- Uygulama: <http://localhost:5173>

### Production build

```bash
cd frontend && npm run build   # dist/ klasörüne statik build
npm run preview                # build'i lokalde preview
```

---

## 7. Veri Pipeline'ı (Dagster)

`ingestion_list.json`'da tanımlı **84 kaynak** (web sayfaları, PDF'ler, lokal dosyalar) sırasıyla Firecrawl/Docling ile çekilir → temizlenir → 800/150 chunk'lara bölünür → Qdrant'a upsert edilir.

```bash
# Web UI ile (önerilen — http://localhost:3000)
dagster dev -w workspace.yaml

# CLI — sıfırdan tam pipeline
dagster job execute -m backend.pipeline_v2.definitions -j full_pipeline_job

# CLI — yalnızca yeni/değişen kaynaklar (SHA-256 dedup)
dagster job execute -m backend.pipeline_v2.definitions -j incremental_job
```

**Job farkları:**

| Job                 | clear_registry | clear_on_full_run | Kullanım                                      |
| ------------------- | :------------: | :---------------: | --------------------------------------------- |
| `full_pipeline_job` |       ✅       |        ✅         | Sıfırdan re-ingest                            |
| `incremental_job`   |       —        |         —         | `ingestion_list.json`'a yeni URL eklendiğinde |

Manuel düzenlenmiş `.md` dosyalarını Qdrant'a aktarmak için ([`apply_preview.py`](apply_preview.py)) kullanılabilir — ⚠ bilinen bug: `QDRANT_URL` okumadığı için cloud aktif iken local'e yazar.

---

## 8. API Sözleşmesi

| Method | Endpoint    | Rate Limit | Açıklama                                 |
| :----: | ----------- | :--------: | ---------------------------------------- |
| `POST` | `/ask`      |   50/dk    | Soru sor, yanıt + kaynak al              |
| `POST` | `/feedback` |   60/dk    | Asistan mesajına 👍/👎 + opsiyonel yorum |
| `GET`  | `/health`   |   200/dk   | Qdrant + Groq + PostgreSQL durum         |
| `GET`  | `/docs`     |     —      | Swagger UI                               |

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

- `question`: 1-500 karakter
- `history`: opsiyonel; son 6 mesaj prompt'a aktarılır, son 3 mesaj analyze_query bağlamına gider

### `/ask` Response

```json
{
  "answer": "Yatay geçiş için...",
  "sources": [
    { "page": 12, "url": "https://...", "snippet": "Madde 15 - Yatay geçiş..." }
  ],
  "category": "kurum-ici-yatay-gecis",
  "engine": "v2",
  "message_id": 1234
}
```

**Hata kodları:** 400 (boş soru) · 422 (validation) · 429 (rate limit) · 503 (Qdrant/LLM unavailable) · 504 (timeout) · 500 (diğer)

### `/feedback` Request

```json
{ "message_id": 1234, "is_positive": true, "comment": null }
```

PostgreSQL `feedback` tablosunda `ON CONFLICT (message_id) DO UPDATE` ile yazılır — kullanıcı fikrini değiştirebilir.

### `/health` Response

```json
{
  "api": "ok",
  "groq_key": "ok",
  "qdrant": "ok",
  "postgres": "ok"
}
```

Kritik bileşenler (`api`, `groq_key`, `qdrant`) için `ok` → HTTP 200; aksi → 503. PostgreSQL opsiyonel (`disabled`/`unavailable` durumu servis dışı bırakmaz).

---

## 9. Konfigürasyon (`.env`)

Tam env değişkenleri listesi: [`.env.example`](.env.example) · [`CLAUDE.md` §10](CLAUDE.md)

**Qdrant bağlantı önceliği** (her bileşen — query, health, pipeline, eval — aynı sırayı kullanır):

```
QDRANT_URL set?  ─yes→  Cloud modu (api_key opsiyonel)
       ↓no
QDRANT_PATH set? ─yes→  Local disk (embedded, Docker gerekmez)
       ↓no
                        Host:port modu (QDRANT_HOST:QDRANT_PORT, default localhost:6333)
```

**LLM provider değiştirme:**

```env
LLM_PROVIDER=gemini
GOOGLE_API_KEY=AIza...
```

Backend restart yeterli. `analyze_query()` her zaman Groq kullanır (hız + ücretsizlik için), yalnızca **chat LLM** değişir.

---

## 10. Test & Kalite

```bash
# Unit testler (hızlı, mock'lu, dış servis gerekmez)
pytest tests/ -v

# RAG eval (Qdrant dolu + GROQ_API_KEY gerekli; ~2-3 dk)
pytest -m slow tests/ -v
```

**Eval eşikleri** ([`tests/test_eval_integration.py`](tests/test_eval_integration.py)):

- Hit Rate ≥ 0.50
- MRR ≥ 0.30

Standart test seti: [`docs/RAG_BASELINE.md`](docs/RAG_BASELINE.md) (8 sorgu: kadro listesi, follow-up, gastronomi, DGS, öznel/off-topic, vb.)

**Lint:**

```bash
ruff check . && ruff format .
cd frontend && npm run lint
```

Pre-commit hook ([`.pre-commit-config.yaml`](.pre-commit-config.yaml)) ruff + ruff-format çalıştırır.

---

## 11. Proje Yapısı

```
bu-chatbot/
├── backend/
│   ├── main.py                    # FastAPI: /ask /feedback /health + lifespan
│   ├── db.py                      # asyncpg PostgreSQL logging
│   ├── query_v2.py                # RAG motoru (Qdrant + reranker + LLM)
│   ├── rag_common.py              # Prompt, fallback, analyze_query, regex
│   ├── rag_config.py              # Merkezi RAG konfigürasyonu (frozen dataclass)
│   ├── prompts/system_prompt.txt  # 13 kurallı Türkçe prompt
│   └── pipeline_v2/
│       ├── definitions.py         # Dagster Definitions
│       ├── jobs.py                # full + incremental job
│       ├── config_v2.py           # PipelineConfigV2 + slugify + kategori auto-build
│       ├── chunker.py · cleaner.py · hash_store.py · models.py
│       ├── assets/                # 9 asset (web/pdf/local/preview/hash/clean/chunk/qdrant)
│       ├── resources/             # Embedding · Qdrant · Firecrawl
│       ├── schemas/qdrant_schema.py  # Collection + payload index'ler
│       └── evaluation/eval.py     # Hit Rate, MRR
│
├── frontend/
│   ├── index.html · vite.config.ts · tailwind.config.js
│   ├── public/                    # logo_light/dark.png (watermark), logo_light-Photoroom.png (avatar)
│   └── src/
│       ├── App.tsx · main.tsx · index.css
│       └── components/ChatHeader · ChatInput · ChatMessage · SettingsModal
│
├── docs/
│   ├── ARCHITECTURE.md            # Mimari diyagramları
│   └── RAG_BASELINE.md            # Standart test seti + baseline tablosu
│
├── tests/
│   ├── conftest.py (autouse env mock) · test_main · test_config_v2
│   ├── test_rag_common · test_eval_integration[@slow]
│
├── ingestion_list.json            # 84 veri kaynağı manifestosu
├── ingestion_preview/             # Manuel düzenlenmiş .md dump'ları (84 kategori)
├── local_sources/                 # Lokal dosya kaynakları (gitignored)
├── qdrant_local/                  # Eski local Qdrant disk (cloud'a geçildi)
│
├── apply_preview.py               # ingestion_preview → Qdrant (⚠ QDRANT_URL bug)
├── map_url.py                     # Firecrawl URL keşif yardımcısı
├── migrate_to_cloud.py            # Local → Cloud tek seferlik migration
├── run_backend.py                 # Uvicorn shortcut
│
├── workspace.yaml                 # Dagster workspace
├── pyproject.toml · pytest.ini · .pre-commit-config.yaml
├── requirements.txt · .env.example · .gitignore
│
├── CLAUDE.md                      # Claude Code için proje referansı (single source of truth)
└── DevelopmentHistory.md          # Session bazlı değişiklik geçmişi
```

---

## 12. Daha Fazla Bilgi

- **Mimari diyagramları:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- **RAG kalite test seti:** [`docs/RAG_BASELINE.md`](docs/RAG_BASELINE.md)
- **Proje referansı (Claude Code):** [`CLAUDE.md`](CLAUDE.md)
- **Session değişiklik geçmişi:** [`DevelopmentHistory.md`](DevelopmentHistory.md)
- **Pipeline UI:** `dagster dev -w workspace.yaml` → <http://localhost:3000>
- **Qdrant Cloud konsolu:** <https://cloud.qdrant.io>

---

## Sahiplik & Lisans

**Yusuf İlbey Aydın** — yusufilbeyaydin@gmail.com
Belek Üniversitesi sene sonu bitirme tez projesi.

Bu repository içindeki kod, akademik tez kapsamında geliştirilmiştir. Üniversite içeriği (`ingestion_list.json`, `ingestion_preview/*.md`) Belek Üniversitesi'ne aittir ve halka açık kaynaklardan derlenmiştir.
