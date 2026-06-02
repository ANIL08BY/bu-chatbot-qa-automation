# Belek AI

> **Belek Üniversitesi için RAG mimarili Türkçe akademik sanal asistan.**
> Yusuf İlbey Aydın'ın bitirme tez projesi.

Belek AI; üniversitenin yönetmelikleri, akademik takvimleri, bölüm/program sayfaları, idari belgeleri ve duyurularına dayalı doğal dil soru-cevap sağlar. Kullanıcı sorduğu soruyu, Qdrant üzerinde **hibrit arama** (dense embedding + BM42 sparse) ile en alakalı belge parçalarına eşleştirir; cross-encoder ile yeniden sıralar; ardından Groq Llama 3.3 70B (veya OpenAI/Gemini) üzerinde, sıkı kurallarla yazılmış bir prompt ile yanıt üretir.

---

## İçindekiler

1. [Proje Amacı](#1-proje-amacı)
2. [Mimari Özet](#2-mimari-özet)
3. [Teknoloji Yığını](#3-teknoloji-yığını)
4. [Hızlı Başlangıç](#4-hızlı-başlangıç)
5. [Detaylı Kurulum](#5-detaylı-kurulum)
6. [Çalıştırma](#6-çalıştırma)
7. [Veri Pipeline'ı](#7-veri-pipelineı-dagster)
8. [API Sözleşmesi](#8-api-sözleşmesi)
9. [Konfigürasyon (`.env`)](#9-konfigürasyon-env)
10. [Test & Kalite](#10-test--kalite)
11. [Proje Yapısı](#11-proje-yapısı)
12. [Daha Fazla Bilgi](#12-daha-fazla-bilgi)

---

## 1. Proje Amacı

Üniversite öğrencileri ve adayları, akademik yönetmelikler ve idari süreçler hakkında bilgi ararken genellikle uzun PDF'ler ve dağınık web sayfaları arasında kaybolur. Belek AI bu problemi şöyle çözer:

- **Tek arayüz:** Tüm akademik bilgiyi tek bir sohbet arayüzünde topla.
- **Doğru kaynak:** Yanıtlar yalnızca üniversite belgelerinden üretilir; halüsinasyon (uydurma URL, dosya adı, madde no) prompt seviyesinde engellenir.
- **Türkçe odaklı:** Türkçe destekli multilingual embedding modeli + Türkçe yazılmış 13 kurallı prompt + Türkçe arayüz.
- **Asistif davranış:** Belgede olmayan veya öznel sorularda tek satırlık ret yerine, semantik olarak yakın konuları önerir ve diyaloğu sürdürür.

---

## 2. Mimari Özet

```
                                 ╭───────────── Pipeline (Dagster) ──────────────╮
ingestion_list.json (84 kaynak)  │  Firecrawl  │  Docling  │  Local files       │
            ───────────────────▶ │   raw_*  →  hash_dedup  →  clean  →  chunk   │
                                 │                                  ↓            │
                                 │                          Qdrant Cloud         │
                                 │                          (dense 768d + BM42)  │
                                 ╰───────────────────────────────────────────────╯
                                                  ▲
                                                  │ retrieval
                                                  │
   ┌────────── Frontend ──────────┐   POST /ask  ┌──────────── Backend (FastAPI) ────────┐
   │ React 19 + Vite + Tailwind   │ ───────────▶ │ analyze_query (Groq llama-3.1-8b)     │
   │ ChatHeader · ChatMessage     │              │     ↓                                 │
   │ ChatInput · SettingsModal    │              │ Qdrant hybrid search (k = 5/15/18/40) │
   │ localStorage persist         │              │     ↓                                 │
   │ Markdown render + feedback   │              │ Cross-encoder rerank (bge-base)       │
   └──────────────────────────────┘              │     ↓                                 │
                                                 │ LLM (Groq/OpenAI/Gemini)              │
                                                 │     fallback zinciri (429 → next)     │
                                                 │     ↓                                 │
                                                 │ PostgreSQL log_interaction (ops.)     │
                                                 └───────────────────────────────────────┘
```

**Davranış garantileri:**

- **Sessiz fallback yok.** Qdrant/LLM erişilemezse `RuntimeError → HTTP 503`. Frontend "Tekrar Dene" butonu gösterir.
- **Halüsinasyon engelleme.** Prompt'ta URL/PDF adı/madde no/telefon/tarih uydurma yasağı — yalnızca DÖKÜMAN'da harfi harfine geçenler aktarılır.
- **Kategori sızıntısı yok.** LLM yanıta hiçbir zaman kategori adı/etiketi yazmaz; nötr "elimdeki kaynaklarda" ifadesi kullanır.

Detaylı mimari için: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · [`docs/RAG_BASELINE.md`](docs/RAG_BASELINE.md)

---

## 3. Teknoloji Yığını

| Katman             | Teknoloji                                                                                              |
| ------------------ | ------------------------------------------------------------------------------------------------------ |
| **Backend**        | FastAPI · Uvicorn · slowapi (rate limit) · python-dotenv                                               |
| **LLM**            | Groq (Llama 3.3 70B + fallback) · OpenAI (gpt-4o-mini) · Gemini (2.5-flash) — `LLM_PROVIDER` ile seçim |
| **LLM framework**  | LangChain · langchain-groq · langchain-openai · langchain-google-genai                                 |
| **Vector DB**      | Qdrant ≥1.9 (Cloud aktif, dense 768d + BM42 sparse)                                                    |
| **Embedding**      | `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` (Türkçe destekli)                        |
| **Reranker**       | `BAAI/bge-reranker-base` (cross-encoder, query-time)                                                   |
| **Pipeline**       | Dagster ≥1.7 (asset DAG, incremental dedup, web UI)                                                    |
| **PDF**            | Docling + TableFormer ACCURATE · pdfplumber fallback                                                   |
| **Web scraping**   | Firecrawl · BeautifulSoup4 · lxml                                                                      |
| **DB (opsiyonel)** | PostgreSQL 13+ · asyncpg (interaksiyon loglama)                                                        |
| **Frontend**       | React 19 · TypeScript · Vite 7 · Tailwind 3 · axios · react-markdown + remark-gfm · lucide-react       |

Tam sürüm listesi: [`requirements.txt`](requirements.txt) · [`frontend/package.json`](frontend/package.json)

---

## 4. Hızlı Başlangıç

> **Ön koşul:** Python 3.11+, Node.js 18+, [Groq API anahtarı](https://console.groq.com), [Qdrant Cloud cluster](https://cloud.qdrant.io) (veya local).

```bash
# 1. Repo'yu klonla ve .env oluştur
git clone <repo-url> && cd bu-chatbot
cp .env.example .env
# .env'i editöre aç → GROQ_API_KEY, QDRANT_URL, QDRANT_API_KEY doldur

# 2. Backend
python -m venv venv
.\venv\Scripts\Activate.ps1                # Windows PS — Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload          # http://127.0.0.1:8000

# 3. Frontend (yeni terminal)
cd frontend && npm install && npm run dev  # http://localhost:5173
```

> **Not:** Qdrant Cloud'a `QDRANT_URL` + `QDRANT_API_KEY` ile bağlandığında veri pipeline'ı çalıştırmaya gerek yok (proje sahibinin yüklediği 1582 vektör hazır gelir). Sıfırdan ingest için bkz. §7.

---

## 5. Detaylı Kurulum

### 5.1 Python ortamı

```bash
python -m venv venv
```

**Aktivasyon:**

```powershell
# Windows PowerShell
.\venv\Scripts\Activate.ps1
```

```cmd
:: Windows CMD
venv\Scripts\activate
```

```bash
# Linux / macOS
source venv/bin/activate
```

```bash
<<<<<<< HEAD
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

| Değişken                                                  | Açıklama                                                         |    Zorunlu    |
| --------------------------------------------------------- | ---------------------------------------------------------------- | :-----------: |
| `GROQ_API_KEY`                                            | Groq LLM API anahtarı                                            |      ✅       |
| `FIRECRAWL_API_KEY`                                       | Firecrawl web scraping API                                       | Pipeline için |
| `QDRANT_PATH`                                             | Qdrant local disk dizini (varsayılan: `./qdrant_local`)          |       —       |
| `QDRANT_HOST`, `QDRANT_PORT`                              | `QDRANT_PATH` boşsa kullanılır (Docker / uzak)                   |       —       |
| `CORS_ORIGINS`                                            | İzin verilen origin'ler (virgülle ayrılmış)                      |       —       |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | PostgreSQL bağlantı bilgileri (eksikse logging devre dışı kalır) |       —       |

### 3. (Opsiyonel) PostgreSQL şemasını kur

# Interaksiyon loglaması istiyorsanız aşağıdaki tabloları `belek_chatbot` şeması altında oluşturun:

pip install -r requirements.txt

````

> İlk kurulumda sentence-transformers + Docling modelleri ~1.5 GB indirebilir. İlk `/ask` isteğinde de embedding + reranker modelleri ısıtılır (~2-5 sn).

### 5.2 `.env` Dosyası

```bash
cp .env.example .env       # Linux/Mac/Git Bash
Copy-Item .env.example .env   # Windows PowerShell
copy .env.example .env     # Windows CMD
````

Düzenlenmesi gerekenler:

| Değişken                            | Zorunluluk                                                 |
| ----------------------------------- | ---------------------------------------------------------- |
| `GROQ_API_KEY`                      | ✅ Daima (analyze_query Groq kullanır)                     |
| `QDRANT_URL` + `QDRANT_API_KEY`     | ✅ (Cloud — önerilen)                                      |
| `QDRANT_PATH`                       | Local disk modu (alternatif, `QDRANT_URL` yoksa)           |
| `FIRECRAWL_API_KEY`                 | Pipeline çalıştırılacaksa                                  |
| `LLM_PROVIDER`                      | `groq` (default) \| `openai` \| `gemini`                   |
| `OPENAI_API_KEY` / `GOOGLE_API_KEY` | İlgili provider seçilirse                                  |
| `DB_*`                              | PostgreSQL kaydı için; herhangi biri boşsa logging kapanır |
| `CORS_ORIGINS`                      | Default `http://localhost:5173,http://127.0.0.1:5173`      |

Tam liste: [`CLAUDE.md` §10](CLAUDE.md) · Şablon: [`.env.example`](.env.example)

### 5.3 (Opsiyonel) PostgreSQL Şeması

İnteraksiyon loglaması istiyorsan `belek_chatbot` şemasını kur:

> > > > > > > ortak-yeni/main

```sql
CREATE SCHEMA IF NOT EXISTS belek_chatbot;
SET search_path TO belek_chatbot;

CREATE TABLE sessions (
<<<<<<< HEAD
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

> **RLS Uyarısı:** Eğer PostgreSQL'de Row-Level Security (örn. Supabase) etkinse, `db.py`'nin bağlandığı kullanıcının INSERT yetkisi olmalıdır. Aksi halde `log_interaction()` sessizce başarısız olur. Çözüm seçenekleri:
>
> 1. DB kullanıcısına `BYPASSRLS` ver: `ALTER USER bot_user BYPASSRLS;`
> 2. Veya tabloya açık INSERT policy yaz: `CREATE POLICY bot_insert ON belek_chatbot.sessions FOR INSERT TO bot_user WITH CHECK (true);`
>
> Bu fix uygulandıktan sonra DB hataları log'larda **stack trace ile birlikte** görünür hale gelir (`logger.exception`).

### 4. Veri pipeline'ını çalıştır

```bash
# Dagster web arayüzü ile (önerilen)
dagster dev -w workspace.yaml

# Komut satırından tek seferlik
dagster job execute -m backend.pipeline_v2.definitions -j full_pipeline_job
```

Bu adım `ingestion_list.json`'daki kaynakları çekip Qdrant'a indeksler. Bitince `qdrant_local/` klasörü oluşur.

### 5. Frontend bağımlılıklarını kur

=======
id SERIAL PRIMARY KEY,
user_ip VARCHAR(45) NOT NULL,
start_time TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE TABLE messages (
id SERIAL PRIMARY KEY,
session_id INTEGER NOT NULL REFERENCES sessions(id),
role VARCHAR(50) NOT NULL,
content TEXT NOT NULL,
timestamp TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE TABLE citations (
id SERIAL PRIMARY KEY,
message_id INTEGER NOT NULL REFERENCES messages(id),
doc_name VARCHAR(255) NOT NULL,
page_num INTEGER
);
CREATE TABLE feedback (
id SERIAL PRIMARY KEY,
message_id INTEGER NOT NULL UNIQUE REFERENCES messages(id),
is_positive BOOLEAN NOT NULL,
comment TEXT
);
CREATE TABLE system_logs (
id SERIAL PRIMARY KEY,
message_id INTEGER NOT NULL UNIQUE REFERENCES messages(id),
latency_ms INTEGER,
error_status VARCHAR(255)
);

````

> **RLS Uyarısı** (Supabase vb.): `db.py` `INSERT INTO belek_chatbot.*` yazar. RLS aktifse bot kullanıcısına ya `ALTER USER bot_user BYPASSRLS;` ver, ya da açık INSERT policy yaz. Aksi halde `log_interaction()` sessizce fail eder (loglarda stack trace görünür).

### 5.4 Frontend
>>>>>>> ortak-yeni/main

```bash
cd frontend
npm install
````

<<<<<<< HEAD
`frontend/.env` dosyası `VITE_API_URL=/api` olarak ayarlıdır — Vite proxy üzerinden backend'e yönlendirir.

---

## Çalıştırma

=======
`frontend/.env` zaten `VITE_API_URL=/api` olarak ayarlı — Vite dev sunucusu `/api/*` isteklerini `http://127.0.0.1:8000`'e proxy eder ([`vite.config.ts`](frontend/vite.config.ts)).

---

## 6. Çalıştırma

> > > > > > > ortak-yeni/main

### Terminal 1 — Backend

```bash
<<<<<<< HEAD
# Uvicorn ile (önerilen)
uvicorn backend.main:app --reload

# Veya Python script ile
python run_backend.py
```

# API: `http://127.0.0.1:8000` · Swagger: `http://127.0.0.1:8000/docs`

uvicorn backend.main:app --reload

# veya

python run_backend.py

````

- API: <http://127.0.0.1:8000>
- Swagger UI: <http://127.0.0.1:8000/docs>
- Sağlık kontrolü: `curl http://127.0.0.1:8000/health`
>>>>>>> ortak-yeni/main

### Terminal 2 — Frontend

```bash
cd frontend && npm run dev
````

<<<<<<< HEAD
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

| Script             | Amaç                                                                            |
| ------------------ | ------------------------------------------------------------------------------- |
| `run_backend.py`   | `.env` yükleyip uvicorn'u başlatan kısayol                                      |
| `map_url.py`       | Firecrawl ile URL keşfi → `ingestion_list.json` güncelleme                      |
| `apply_preview.py` | `ingestion_preview/`'daki manuel düzenlenmiş `.md` dosyalarını Qdrant'a aktarma |

Detaylı kullanım her script'in dosyasındaki docstring'de.

---

## API Endpoints

| Method | Endpoint  | Rate Limit | Açıklama                                         |
| ------ | --------- | :--------: | ------------------------------------------------ |
| POST   | `/ask`    |   50/dk    | Soru sor — cevap + kaynak + kategori + motor     |
| GET    | `/health` |   200/dk   | Bağımlılık durumu (Qdrant, Groq key, PostgreSQL) |
| GET    | `/docs`   |     —      | Swagger UI                                       |

# Limit aşılırsa `429 Too Many Requests` döner.

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

> > > > > > > ortak-yeni/main

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

# <<<<<<< HEAD

- `question`: 1-500 karakter
- `history`: opsiyonel; son 6 mesaj prompt'a aktarılır, son 3 mesaj analyze_query bağlamına gider

> > > > > > > ortak-yeni/main

### `/ask` Response

```json
{
  "answer": "Yatay geçiş için...",
  "sources": [
    { "page": 12, "url": "https://...", "snippet": "Madde 15 - Yatay geçiş..." }
  ],
  "category": "kurum-ici-yatay-gecis",
<<<<<<< HEAD
  "engine": "v2"
}
```

=======
"engine": "v2",
"message_id": 1234
}

````

**Hata kodları:** 400 (boş soru) · 422 (validation) · 429 (rate limit) · 503 (Qdrant/LLM unavailable) · 504 (timeout) · 500 (diğer)

### `/feedback` Request

```json
{ "message_id": 1234, "is_positive": true, "comment": null }
````

PostgreSQL `feedback` tablosunda `ON CONFLICT (message_id) DO UPDATE` ile yazılır — kullanıcı fikrini değiştirebilir.

> > > > > > > ortak-yeni/main

### `/health` Response

```json
{
  "api": "ok",
  "groq_key": "ok",
  "qdrant": "ok",
  "postgres": "ok"
}
```

<<<<<<< HEAD
**Kritik bileşenler** (`api`, `groq_key`, `qdrant`) `ok` ise HTTP 200; aksi halde 503.
PostgreSQL opsiyoneldir — `disabled` veya `unavailable` durumu API'yi servis dışı bırakmaz.

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
│   ├── query_v2.py           # RAG motoru (Qdrant + Reranker + LLM)
│   ├── rag_common.py         # Paylaşılan: chain, prompt, kategori, model fallback
│   ├── rag_config.py         # Merkezi RAG konfigürasyonu (k değerleri vb.)
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
=======
Kritik bileşenler (`api`, `groq_key`, `qdrant`) için `ok` → HTTP 200; aksi → 503. PostgreSQL opsiyonel (`disabled`/`unavailable` durumu servis dışı bırakmaz).

---

## 9. Konfigürasyon (`.env`)

Tam env değişkenleri listesi: [`.env.example`](.env.example) · [`CLAUDE.md` §10](CLAUDE.md)

**Qdrant bağlantı önceliği** (her bileşen — query, health, pipeline, eval — aynı sırayı kullanır):

```

QDRANT_URL set? ─yes→ Cloud modu (api_key opsiyonel)
↓no
QDRANT_PATH set? ─yes→ Local disk (embedded, Docker gerekmez)
↓no
Host:port modu (QDRANT_HOST:QDRANT_PORT, default localhost:6333)

````

**LLM provider değiştirme:**

```env
LLM_PROVIDER=gemini
GOOGLE_API_KEY=AIza...
````

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
>>>>>>> ortak-yeni/main
```

---

<<<<<<< HEAD

## Daha Fazla Bilgi

- **Mimari diyagramı:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- **Pipeline asset DAG'ı:** `dagster dev -w workspace.yaml` ile Dagster UI üzerinden
- **Evaluation rubric:** `backend/pipeline_v2/evaluation/eval.py` (Hit Rate, MRR)
- # **Tailwind tema özelleştirmesi:** `frontend/tailwind.config.js`

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

> > > > > > > ortak-yeni/main
