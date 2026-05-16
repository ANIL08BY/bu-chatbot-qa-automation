# CLAUDE.md — BU Chatbot Proje Kılavuzu

> Bu dosya Claude Code (claude.ai/code) için hazırlanmış kapsamlı proje referansıdır. Her yeni session'da Claude'un projeyi sıfırdan keşfetmesine gerek kalmadan **bağlamı tek dosyadan yükleyebilmesi** amaçlanmıştır. Bu dosyadaki bilgi tek doğruluk kaynağıdır (single source of truth) — değişiklik yapıldığında bu dosya da güncellenmelidir.
>
> İlişkili dosyalar:
> - **`DevelopmentHistory.md`** — Her session'da yapılan değişikliklerin kronolojik kaydı. Yeni session başlarken **önce bu dosyayı oku** (son değişikliklerden haberdar olmak için).
> - **`docs/ARCHITECTURE.md`** — Detaylı mimari diyagramları.
> - **`README.md`** — Türkçe son kullanıcı kurulum/çalıştırma talimatları.

---

## 0. Session Başlangıç Kontrol Listesi (Claude için)

Her yeni Claude Code session'ında **ilk turda** sırasıyla:

1. **Bu dosyayı oku** (CLAUDE.md) — Genel mimari ve dosya haritası.
2. **`DevelopmentHistory.md` dosyasını oku** — Son N session'da yapılan değişiklikler.
3. **`git status` + `git log --oneline -5`** — Commitlenmemiş değişiklikler + son commitler.
4. Kullanıcının görevini netleştir; ardından ilgili dosyalara dal.

Session sonunda yapılan tüm değişiklikler `DevelopmentHistory.md`'ye **yeni bir tarihli giriş** olarak eklenmelidir (Section 14 — Dokümantasyon Güncelleme Protokolü).

---

## 1. Proje Genel Bakışı

**BU Chatbot**, Belek Üniversitesi için geliştirilmiş **RAG (Retrieval-Augmented Generation)** mimarili bir akademik sanal asistandır. Yusuf İlbey Aydın'ın **sene sonu tez projesi**dir. Kullanıcılar üniversitenin yönetmelikleri, akademik takvimleri, bölüm bilgileri ve idari belgeleri hakkında doğal dilde soru sorabilir; chatbot Qdrant üzerinde hibrit arama yaparak ilgili belge parçalarını bulur ve Groq'un Llama modelleriyle yanıt üretir.

**Olgunluk:** Final sürümüne yaklaşan; V1 (ChromaDB+BM25) tamamen kaldırılmış, **V2 (Qdrant hybrid + Groq + Dagster)** tek motor olarak stabil. Aktif geliştirmede.

### Tam Teknoloji Yığını

| Katman | Teknoloji | Versiyon | Rol |
|---|---|---|---|
| **API** | FastAPI | ≥0.129 | REST endpoint'ler, async, rate limit |
| **ASGI** | Uvicorn[standard] | ≥0.40 | Sunucu |
| **LLM** | Groq Cloud | API | Llama 3.3 70B (primary) + fallback chain |
| **LLM Framework** | LangChain + langchain-groq | ≥1.2 / ≥1.1 | Prompt template + chain orkestasyonu |
| **Vector DB** | Qdrant | ≥1.9 | Hybrid dense (768d) + BM42 sparse |
| **Embedding** | sentence-transformers | ≥5.0 | `paraphrase-multilingual-mpnet-base-v2` (768d, Türkçe destekli) |
| **Reranker** | BAAI/bge-reranker-base | Cross-encoder | Query-time rerank |
| **Pipeline** | Dagster + dagster-webserver | ≥1.7 | Asset DAG, web UI (port 3000) |
| **PDF Parse** | Docling (+ TableFormer ACCURATE) | ≥2.5 | Primary; `pdfplumber` fallback |
| **Web Scraping** | Firecrawl + BeautifulSoup4 + lxml | ≥1.3 | HTML → Markdown |
| **HTTP Client** | httpx | ≥0.28 | Async download |
| **DB** | PostgreSQL + asyncpg | 13+ / ≥0.29 | Opsiyonel etkileşim loglama |
| **Rate Limit** | slowapi | ≥0.1.9 | Endpoint başına limit |
| **Frontend** | React 19.2 + TypeScript 5.9 | — | UI |
| **Build** | Vite 7.3 + @vitejs/plugin-react | — | Dev/build |
| **Styling** | Tailwind 3.4 + @tailwindcss/typography | — | UI |
| **MD Render** | react-markdown + remark-gfm | — | Bot yanıtlarında GFM markdown |
| **HTTP (FE)** | axios 1.13 | — | API çağrıları |
| **Icons** | lucide-react 0.564 | — | UI ikonları |
| **Lint (BE)** | Ruff | — | `line-length=100`, target py311 |
| **Lint (FE)** | ESLint 9 + typescript-eslint | — | — |
| **Test** | pytest | — | `slow` marker'lı RAG eval testleri |

### Python Sürümü
Python **3.11+** zorunlu (Ruff `target-version = "py311"`, `dataclass(frozen=True)`, modern tip notasyonları).

---

## 2. Dizin Yapısı (Tam Harita)

```
bu-chatbot/
├── .env                          # API anahtarları (git-ignored)
├── .env.example                  # Şablon
├── .gitignore
├── .pre-commit-config.yaml       # Pre-commit hook'lar
├── CLAUDE.md                     # ← BU DOSYA
├── DevelopmentHistory.md         # Session değişiklik geçmişi
├── README.md                     # Türkçe kurulum kılavuzu
├── pyproject.toml                # Ruff + pytest config
├── pytest.ini                    # Pytest marker tanımları
├── requirements.txt              # 49 Python bağımlılığı
├── workspace.yaml                # Dagster workspace (backend.pipeline_v2.definitions)
├── ingestion_list.json           # 54 veri kaynağı manifestosu
├── run_backend.py                # `uvicorn backend.main:app` shortcut
├── map_url.py                    # Firecrawl URL keşfi
├── apply_preview.py              # Manuel .md → Qdrant aktarımı
│
├── backend/
│   ├── __init__.py
│   ├── main.py                   # FastAPI app: /ask, /feedback, /health
│   ├── db.py                     # asyncpg PostgreSQL logging
│   ├── query_v2.py               # RAG motoru (ask_question_v2)
│   ├── rag_common.py             # Prompt, fallback chain, regex pattern'ler
│   ├── rag_config.py             # Tunable konstantlar (frozen dataclass)
│   ├── prompts/
│   │   └── system_prompt.txt     # 12 kurallı system prompt template
│   └── pipeline_v2/
│       ├── __init__.py
│       ├── definitions.py        # Dagster Definitions: assets + jobs + resources
│       ├── jobs.py               # full_pipeline_job, incremental_job
│       ├── config_v2.py          # PipelineConfigV2 + slugify + KNOWN_CATEGORIES_V2
│       ├── models.py             # RawDocumentV2, ChunkV2 dataclass'ları
│       ├── chunker.py            # SemanticChunker (heading-aware, 800/150)
│       ├── cleaner.py            # DocumentCleanerV2 (Unicode + boilerplate)
│       ├── hash_store.py         # filter_changed(), save/load_registry()
│       ├── pipeline_v2_cache/
│       │   └── doc_hashes.json   # SHA-256 registry (dedup için)
│       ├── assets/
│       │   ├── web_assets.py            # raw_web_pages (Firecrawl)
│       │   ├── pdf_assets.py            # raw_pdf_documents (Docling)
│       │   ├── local_assets.py          # raw_local_documents
│       │   ├── hash_assets.py           # document_hashes (SHA-256 dedup)
│       │   ├── clean_assets.py          # cleaned_documents
│       │   ├── chunk_assets.py          # semantic_chunks
│       │   ├── qdrant_assets.py         # qdrant_collection (upsert)
│       │   ├── preview_assets.py        # raw_preview_dump
│       │   └── approved_preview_index_asset.py  # approved_preview_index
│       ├── resources/
│       │   ├── embedding_resource.py    # EmbeddingResource (encode/encode_one)
│       │   ├── qdrant_resource.py       # QdrantResource (local/remote auto)
│       │   └── firecrawl_resource.py    # FirecrawlResource (scrape/map/batch)
│       ├── schemas/
│       │   └── qdrant_schema.py         # COLLECTION_NAME="belek_v2", create_collection_if_not_exists()
│       └── evaluation/
│           └── eval.py                  # Hit Rate, MRR metrikleri
│
├── frontend/
│   ├── package.json              # React 19, Vite, Tailwind, axios, react-markdown
│   ├── vite.config.ts            # Proxy /api → 127.0.0.1:8000
│   ├── tsconfig.json / tsconfig.app.json / tsconfig.node.json
│   ├── tailwind.config.js        # content paths + typography plugin
│   ├── postcss.config.js
│   ├── eslint.config.js
│   ├── index.html
│   ├── .env                      # VITE_API_URL=/api
│   ├── public/
│   │   ├── logo.png              # Header logosu
│   │   ├── logo_light.png        # Light mode watermark
│   │   ├── logo_dark.png         # Dark mode watermark
│   │   └── vite.svg
│   └── src/
│       ├── main.tsx              # createRoot + StrictMode
│       ├── App.tsx               # Ana state, /ask + /feedback çağrıları
│       ├── App.css
│       ├── index.css             # Tailwind base
│       ├── components/
│       │   ├── ChatHeader.tsx
│       │   ├── ChatInput.tsx     # Auto-expanding textarea + Enter/Shift+Enter
│       │   ├── ChatMessage.tsx   # Markdown render + feedback (like/dislike)
│       │   └── SettingsModal.tsx # Dark mode toggle (ESC/overlay close)
│       └── styles/
│           ├── index.css
│           ├── tailwind.css
│           ├── theme.css         # oklch CSS custom properties
│           └── fonts.css
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py               # GROQ_API_KEY, QDRANT_* mock'ları (autouse)
│   ├── test_main.py              # /health, /ask endpoint testleri
│   ├── test_config_v2.py         # slugify + KNOWN_CATEGORIES_V2
│   ├── test_rag_common.py        # rag_config, prompt, compute_k, format_history
│   └── test_eval_integration.py  # @pytest.mark.slow — Hit Rate ≥0.5, MRR ≥0.3
│
├── docs/
│   └── ARCHITECTURE.md
│
├── ingestion_preview/            # 54 kategori alt dizini — onaylı .md dump'ları
├── local_sources/                # Lokal dosya kaynakları (txt/md/pdf)
└── qdrant_local/                 # Qdrant local disk (git-ignored)
```

---

## 3. Geliştirme Komutları

### Backend
```bash
# venv (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Bağımlılık
pip install -r requirements.txt

# API sunucusu (port 8000)
uvicorn backend.main:app --reload
# veya:
python run_backend.py
```

### Frontend
```bash
cd frontend
npm install
npm run dev      # http://localhost:5173
npm run build    # tsc -b && vite build
npm run lint
npm run preview
```

### Data Pipeline (Dagster)
```bash
# Web UI (port 3000)
dagster dev -w workspace.yaml

# CLI full ingestion
dagster job execute -m backend.pipeline_v2.definitions -j full_pipeline_job

# Incremental (sadece değişen kaynaklar)
dagster job execute -m backend.pipeline_v2.definitions -j incremental_job
```

### Test
```bash
pytest tests/ -v                 # Tüm testler (mock'lu, hızlı)
pytest -m slow tests/ -v         # RAG eval testleri (Qdrant + GROQ gerekli)
pytest tests/test_main.py -v     # Tek dosya
```

### Lint
```bash
ruff check .
ruff format .
cd frontend && npm run lint
```

---

## 4. Mimari — Query Akışı (Runtime)

```
[User] → POST /ask → backend/main.py
                      │ (sanitize, rate-limit 50/dk)
                      ▼
              query_v2.ask_question_v2(query, history)
                      │
                      ├── _init_v2() [lazy, thread-safe]
                      │    ├─ embedding model load
                      │    ├─ reranker load
                      │    ├─ Qdrant client
                      │    └─ LangChain ChatGroq chain
                      │
                      ├── analyze_query(query)   ← rag_common
                      │    └─ Groq llama-3.1-8b → (category, search_query)
                      │
                      ├── compute_k(query)        ← rag_common
                      │    └─ LIST_RE=40 / AGG_RE=18 / "madde \d+"=5 / else=15
                      │
                      ├── _hybrid_search_v2(search_query, category, k)
                      │    ├─ encode(query) → 768d
                      │    └─ Qdrant: dense (cosine) + BM42 sparse + filter(doc_category)
                      │       └─ < min_category_results(3) → category fallback to "genel"
                      │
                      ├── _rerank(query, docs, top_k)
                      │    └─ BAAI/bge-reranker-base cross-encoder
                      │       └─ LIST_RE eşleşirse skip (dense ranking korunur)
                      │
                      ├── chain.invoke({context, question, history, category_context})
                      │    └─ llama-3.3-70b-versatile
                      │       └─ 429/rate_limit → invoke_fallback():
                      │            llama-4-scout-17b → llama-3.1-8b-instant
                      │
                      └── return {answer, sources[:3], category, engine:"v2", message_id}

  → db.log_interaction(...) [fire-and-forget, asyncpg]
```

### Önemli Davranışlar
- **Sessiz fallback YOK.** Qdrant/Groq erişilemezse `RuntimeError` → HTTP 503.
- **Lazy init**, ilk istekte ~2-5 sn yükleme; sonraki istekler hızlıdır.
- **Lifespan startup**: `_preload_models()` background thread'de modelleri ısıtır.
- **Input sanitize**: `_CONTROL_CHAR_RE` ile control char/null byte temizliği + `.strip()`.

---

## 5. Mimari — Data Pipeline (Dagster)

```
ingestion_list.json (54 kaynak)
    │
    ├─→ raw_web_pages       (Firecrawl scrape + depth>=2 ise map)
    ├─→ raw_pdf_documents   (Docling TableFormer, 90s timeout, 50MB max)
    ├─→ raw_local_documents (local_sources/ dizini)
    ├─→ raw_preview_dump    (ingestion_preview/'dan dump)
    │
    └─→ document_hashes     (SHA-256 dedup → doc_hashes.json registry)
         │   - clear_registry=True (full_pipeline_job) → tüm docs is_new
         │
         └─→ approved_preview_index  (status: approved/processed olan .md'ler)
              │
              └─→ cleaned_documents (DocumentCleanerV2 + approved override)
                   │   - Approved varsa onu kullan; yoksa crawled'ı temizle
                   │   - Unicode NFC + boilerplate removal + min_content_chars
                   │
                   └─→ semantic_chunks (SemanticChunker)
                        │   - Heading-aware split (## ###)
                        │   - chunk_size=800, overlap=150
                        │   - "[Konu: {heading}]\n" prefix
                        │
                        └─→ qdrant_collection (batch 100 upsert)
                             - PointStruct id = UUID5(NAMESPACE_URL, "{url}:{chunk_idx}")
                             - vector["dense"]: 768d cosine
                             - vector["sparse"]: BM42 (auto from text)
                             - payload: tüm ChunkV2 alanları
```

### Job'lar
- **`full_pipeline_job`**: `document_hashes.clear_registry=True`, `raw_preview_dump.clear_on_full_run=True` → sıfırdan ingest.
- **`incremental_job`**: Default config — yalnız değişen kaynakları işler.

### Qdrant Şeması
- Collection: **`belek_v2`**
- Named vectors: `dense` (768d, COSINE) + `sparse` (BM42, IDF)
- HNSW: m=16, ef_construct=100
- Payload index: `doc_category`, `fmt`, `is_active`, `access_level`

---

## 6. API Sözleşmesi

### POST /ask — Rate limit: 50/dk
**Request:**
```json
{
  "question": "Yatay geçiş şartları nelerdir?",
  "history": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```
- `question`: 1-500 karakter
- `history`: opsiyonel; son 6 mesaj kullanılır

**Response 200:**
```json
{
  "answer": "...",
  "sources": [{"page": 12, "url": "https://...", "snippet": "..."}],
  "category": "kurum-ici-yatay-gecis",
  "engine": "v2",
  "message_id": 1234
}
```

**Hata kodları:** 400 (empty), 422 (validation), 503 (RuntimeError), 504 (timeout), 500 (unexpected).

### POST /feedback — Rate limit: 60/dk
```json
{ "message_id": 1234, "is_positive": true, "comment": null }
```
DB'de UPSERT (`ON CONFLICT DO UPDATE`).

### GET /health — Rate limit: 200/dk
```json
{
  "api": "ok",
  "groq_key": "ok | missing",
  "qdrant": "ok | unavailable",
  "postgres": "ok | unavailable | disabled"
}
```
Kritik bileşenler (`api`, `groq_key`, `qdrant`) → 200/503. Postgres opsiyonel.

---

## 7. Kritik Konstantlar Tablosu

### `backend/rag_config.py` (frozen dataclass)
| Konstant | Değer | Anlam |
|---|---:|---|
| `k_general` | 15 | Default retrieval |
| `k_list` | 40 | "Tümü, listele..." sorguları |
| `k_aggregation` | 18 | "Kaç, toplam..." sorguları |
| `k_specific` | 5 | "Madde X" sorguları |
| `reranker_max_length` | 512 | Cross-encoder max input |
| `max_history_messages` | 6 | Konuşma geçmişi turları |
| `min_category_results` | 3 | Altına düşerse kategori fallback |

### `backend/pipeline_v2/config_v2.py` (`BELEK_CONFIG_V2`)
| Konstant | Değer |
|---|---|
| `qdrant_collection` | `belek_v2` |
| `qdrant_vector_size` | 768 |
| `embedding_model` | `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` |
| `reranker_model` | `BAAI/bge-reranker-v2-m3` (pipeline-side) |
| `embed_batch_size` | 64 |
| `firecrawl_concurrency` | 5 |
| `max_pdf_size_mb` | 50 |
| `pdf_timeout_s` | 90.0 |
| `chunk_size` | 800 |
| `chunk_overlap` | 150 |
| `min_content_chars` | 100 |

### `backend/rag_common.py`
```python
FALLBACK_MODELS = [
    "llama-3.3-70b-versatile",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "llama-3.1-8b-instant",
]
AGGREGATION_RE = r"\b(kaç|toplam|kaçıncı|tane|adet|sayısı|yapısı|bölüm sayısı|madde sayısı)\b"
LIST_RE        = r"\b(tümü|hepsi|hepsini|listele|listeler|tüm\s+\S+lar|tüm\s+\S+ler|sırala|nelerdir|hangileri|sayar\s*mısın|söyler\s*misin)\b"
```

### Rate Limits (`backend/main.py`)
- `/ask` 50/dk · `/feedback` 60/dk · `/health` 200/dk

---

## 8. PostgreSQL Şeması (`belek_chatbot`)

Tablolar `backend/db.py` üzerinden yazılır:

```sql
CREATE SCHEMA IF NOT EXISTS belek_chatbot;

CREATE TABLE belek_chatbot.sessions (
    id SERIAL PRIMARY KEY,
    user_ip VARCHAR(45) NOT NULL,
    start_time TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE TABLE belek_chatbot.messages (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES belek_chatbot.sessions(id),
    role VARCHAR(50) NOT NULL,        -- 'user' | 'assistant'
    content TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE TABLE belek_chatbot.citations (
    id SERIAL PRIMARY KEY,
    message_id INTEGER NOT NULL REFERENCES belek_chatbot.messages(id),
    doc_name VARCHAR(255) NOT NULL,
    page_num INTEGER
);
CREATE TABLE belek_chatbot.feedback (
    id SERIAL PRIMARY KEY,
    message_id INTEGER NOT NULL UNIQUE REFERENCES belek_chatbot.messages(id),
    is_positive BOOLEAN NOT NULL,
    comment TEXT
);
CREATE TABLE belek_chatbot.system_logs (
    id SERIAL PRIMARY KEY,
    message_id INTEGER NOT NULL UNIQUE REFERENCES belek_chatbot.messages(id),
    latency_ms INTEGER,
    error_status VARCHAR(255)
);
```

**Bağlantı:** asyncpg pool (`min_size=1, max_size=5, command_timeout=5s, ssl="require"`).
**Davranış:** Herhangi bir DB env değişkeni eksikse logging **sessizce** devre dışı kalır. Bağlantı hataları **`logger.exception`** ile stack trace'li loglanır (sessiz değildir).
**RLS Uyarısı:** Supabase vb. RLS aktifse bot kullanıcısına `BYPASSRLS` veya `INSERT policy` verilmelidir.

---

## 9. Frontend Detayları

### Ana Bileşenler (`frontend/src/components/`)
| Dosya | Sorumluluk |
|---|---|
| `ChatHeader.tsx` | Logo, başlık, "Yeni Sohbet"+Ayarlar butonları. Light/Dark renkler: `#e30613` / `#9b1211` (BU kırmızısı) |
| `ChatInput.tsx` | Auto-expanding textarea (1-5 satır, max 120px), Enter=Gönder, Shift+Enter=yeni satır |
| `ChatMessage.tsx` | react-markdown + remark-gfm; bot mesajlarında 👍/👎 feedback; error mesajında "Tekrar Dene" |
| `SettingsModal.tsx` | Dark mode toggle, ESC/overlay click ile kapanır, localStorage `bu-chatbot-theme` |

### State Modeli (`App.tsx`)
```typescript
interface Message {
  id: string;            // Date.now().toString()
  text: string;
  isUser: boolean;
  sources?: SourceCard[];
  isError?: boolean;
  messageDbId?: number;  // /feedback için
  feedback?: 'like' | 'dislike' | null;
  isGreeting?: boolean;  // ilk karşılama mesajı (id='1')
}
```
- History filtre: greeting (`id==='1'`) ve error mesajları payload'a dahil edilmez.
- API base: `import.meta.env.VITE_API_URL ?? '/api'` (Vite proxy üzerinden).

### Tema
- Light bg: `#f4f6f9` · Dark bg: `#1a1a1a`
- Brand red: `#e30613` (light) / `#9b1211` (dark) / `#6b0a09` (hover)
- Watermark: `/logo_light.png` veya `/logo_dark.png` (opacity 0.05-0.08)

### Vite Proxy (`vite.config.ts`)
```ts
proxy: { '/api': { target: 'http://127.0.0.1:8000', rewrite: p => p.replace(/^\/api/, '') } }
```

---

## 10. Çevresel Değişkenler (`.env`)

| Değişken | Zorunlu | Default | Açıklama |
|---|:---:|---|---|
| `GROQ_API_KEY` | ✅ | — | Groq Cloud API anahtarı |
| `FIRECRAWL_API_KEY` | Pipeline | — | Web ingestion için |
| `QDRANT_PATH` | — | `./qdrant_local` | Local disk modu (öncelikli) |
| `QDRANT_HOST` / `QDRANT_PORT` | — | `localhost` / `6333` | Uzak Qdrant |
| `CORS_ORIGINS` | — | `http://localhost:5173,http://127.0.0.1:5173` | CSV |
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | — | — | Herhangi biri boşsa logging kapalı |

---

## 11. System Prompt (`backend/prompts/system_prompt.txt`)

12 kurallı, Türkçe RAG prompt'u. Template değişkenleri: `{context}`, `{question}`, `{history}`, `{category_context}`.

**Önemli kurallar (özet):**
1. Sadece DÖKÜMAN içeriği — uydurma yok
2. Madde alıntısı tam (kırpma yok)
3. Sayım sorgularında tüm öğeleri say
4. Kesin tarihler ("yaklaşık" yasak)
5. Liste sorularında "vb./..." yasak — tam liste
6. Dökümanda yoksa: *"Bu konu hakkında elimde yeterli bilgi bulunmuyor."*
7. Üniversite dışı konu: *"Yalnızca Belek Üniversitesi'yle alakalı soruları yanıtlayabilirim."*
8. Türkçe yanıt, teknik terimler korunur
9. Çok konulu yanıtlar paragraf/madde bazlı
10. OBS sorguları: sadece link
11. Bölüm/program sorularında link yönlendirmesi
12. Matematik sorularına doğru cevap

**Prompt güncellenirken bu kurallara dokunmayın** — RAG kalite testleri (Hit Rate ≥0.5, MRR ≥0.3) bunlara dayalıdır.

---

## 12. Veri Kaynakları (`ingestion_list.json`)

**54 kaynak** + her birinin `category`, `priority`, `depth` (1=tek URL, 2+=sublink keşfi) alanları var. Kategoriler `slugify()` ile auto-türetilir (Türkçe karakterler ASCII'ye, kebab-case).

**Örnek kategori grupları:**
- Akademik: `lisans-akademik-takvim`, `ortak-dersler`, `lisansustu-akademik-takvim`
- İdari: `ana-yonetmelik`, `kurullar`, `komisyonlar`
- Destek: `burs-olanaklari`, `engelli-ogrenci`, `kutuphane`, `yurtlar-ve-konaklama`
- Bölümler: 24 bölüm/program sayfası
- Yönetim: `mutevelli-heyeti`, `senato`, `yonetim-kurulu`
- Diğer: `iletisim`, `obs`

`KNOWN_CATEGORIES_V2` ve `CATEGORY_LABELS_V2` runtime'da bu dosyadan inşa edilir (`config_v2._build_categories_from_ingestion_list()`).

---

## 13. Tipik Görev Patternleri — Nereye Bakmalı

| Görev | İlgili Dosya(lar) |
|---|---|
| Yeni endpoint ekle | `backend/main.py` (rate limiter dekoratörü dahil) |
| Retrieval k ayarla | `backend/rag_config.py` (frozen — değiştirmek için tüm dataclass değişir) |
| Yeni LLM modeli ekle | `backend/rag_common.py` → `FALLBACK_MODELS` |
| Prompt değişikliği | `backend/prompts/system_prompt.txt` |
| Yeni kategori | `ingestion_list.json` (auto-detect) — sonra pipeline çalıştır |
| Chunk stratejisi | `backend/pipeline_v2/chunker.py` + `config_v2.chunk_size/overlap` |
| Boilerplate filtresi | `backend/pipeline_v2/cleaner.py` |
| Qdrant şema değişikliği | `backend/pipeline_v2/schemas/qdrant_schema.py` |
| Yeni Dagster asset | `backend/pipeline_v2/assets/` + `definitions.py`'a ekle |
| Yeni UI bileşeni | `frontend/src/components/` + `App.tsx`'te import |
| API base URL değişikliği | `frontend/.env` (`VITE_API_URL`) veya `vite.config.ts` proxy |
| DB tablo değişikliği | `backend/db.py` (CRUD) + README.md DDL |
| Test ekleme | `tests/test_*.py`; mock için `tests/conftest.py` autouse fixture |
| RAG kalite testi | `pytest -m slow tests/test_eval_integration.py` |

---

## 14. Dokümantasyon Güncelleme Protokolü ⚠️

**Bu projede her değişiklik dokümantasyon güncellemesi gerektirir.** Claude session sonunda:

### Her zaman yap:
1. **`DevelopmentHistory.md` dosyasının başına** yeni bir tarihli giriş ekle (Section 0 formatına göre).
   - Tarih + kısa başlık
   - Hangi dosyalar değişti
   - Ne yapıldı, neden
   - Test sonucu (geçti/geçmedi/çalıştırılmadı)
   - Kullanıcının bilmesi gereken not'lar / kırılan davranış varsa açıkça yaz

### Eğer aşağıdakilerden biri değiştiyse, ek olarak CLAUDE.md'yi güncelle:
- **Mimari** (yeni servis, kaldırılan motor, yeni katman) → Section 4, 5
- **Yeni endpoint / endpoint sözleşmesi değişti** → Section 6
- **`rag_config.py` / `config_v2.py` / `FALLBACK_MODELS` değişti** → Section 7
- **DB şeması değişti** → Section 8
- **Yeni env değişkeni** → Section 10
- **Yeni dosya/dizin eklendi** → Section 2
- **Yeni komut / script** → Section 3
- **README.md'deki kurulum adımları etkilendi** → README.md de güncellenmeli

### Eğer prompt değişti:
- `backend/prompts/system_prompt.txt` → Section 11 özetini güncelle
- Eval testlerini çalıştır: `pytest -m slow tests/test_eval_integration.py`

### Dokümantasyon kuralları:
- Yanıltıcı bilgi bırakma — bilinmiyor ise "?" veya "doğrulanmadı" yaz
- Konstant değerleri her zaman değer ile birlikte (örn. `k_general=15`)
- Mutlak dosya yolu yerine repo-relative path kullan (`backend/main.py`)
- Türkçe yaz (kullanıcının tercihi)

---

## 15. Bilinen Sınırlamalar & Tasarım Kararları

- **V1 (ChromaDB+BM25) tamamen kaldırıldı** (commit `e0dfbd4`, 2026-05-06). Geriye dönüş yok — V2 stabil tek motor.
- **Sessiz fallback yok**: V2 hataları HTTP 503 → frontend "Tekrar Dene" butonu.
- **Frontend mesajları persist edilmiyor** (sayfa yenilenince kaybolur). localStorage sadece tema için.
- **Mesaj ID'leri `Date.now().toString()`** — milisaniye altı çakışma teorik olarak mümkün.
- **Source cards extract ediliyor ama UI'da gizli** (`ChatMessage.tsx`'te `void sources`).
- **`index.html` başlığı "frontend"** — production için "BU Chatbot" yapılmalı.
- **Docker/CI yok** — manuel deploy.
- **Qdrant default local disk** — production'da Docker/uzak instance önerilir.
- **Rate limit hardcoded** (`backend/main.py` `@limiter.limit("50/minute")` gibi) — config'e taşınmadı.

---

## 16. Test Kapsamı

| Dosya | Kapsam |
|---|---|
| `tests/test_main.py` | `/health` JSON şeması, `/ask` 400/503/500/200 path'leri, `ChatRequest` validation (max 500 char) |
| `tests/test_config_v2.py` | `slugify()` Türkçe karakter dönüşümü, `KNOWN_CATEGORIES_V2` label eşleşmesi |
| `tests/test_rag_common.py` | `rag_config` frozen, prompt template placeholder'lar, `compute_k()`, `format_history()`, `is_rate_limit()` |
| `tests/test_eval_integration.py` | `@slow` — Hit Rate ≥ 0.50, MRR ≥ 0.30 (Qdrant dolu + GROQ key gerekli) |

`tests/conftest.py` `autouse=True` fixture'la `GROQ_API_KEY="test-key-not-real"` set eder; dış servis çağrılarını engeller.

---

## 17. Sık Karşılaşılan Sorunlar

| Belirti | Olası Neden | Çözüm |
|---|---|---|
| `/ask` 503 — "Qdrant unavailable" | `qdrant_local/` boş veya `QDRANT_PATH` yanlış | Pipeline çalıştır: `dagster job execute -m backend.pipeline_v2.definitions -j full_pipeline_job` |
| `/ask` 503 — "GROQ_API_KEY bulunamadı" | `.env` eksik veya yüklenmemiş | `.env`'i kontrol et, sunucuyu yeniden başlat |
| Frontend "Tekrar Dene" gözüküyor | Backend 5xx/network | Backend log'una bak; `/health` dön |
| DB logging çalışmıyor | Env eksik veya RLS engelliyor | `db.py` log'una stack trace yansır; `BYPASSRLS` veya INSERT policy ver |
| Pipeline'da PDF timeout | Docling 90s aşıldı | `config_v2.pdf_timeout_s` arttır veya o PDF'i skip et |
| Yeni kategori tanınmıyor | Pipeline çalıştırılmadı | Önce `ingestion_list.json` güncelle, sonra `full_pipeline_job` |
| `pytest -m slow` çıkış 1 | Hit Rate < 0.5 / MRR < 0.3 | Retrieval bozulmuş — son değişiklikleri kontrol et |
| Tema değişmiyor | localStorage'da `bu-chatbot-theme` çakışıyor | DevTools → Application → Local Storage temizle |

---

## 18. İletişim & Sahiplenme

- **Geliştirici:** Yusuf İlbey Aydın (yusufilbeyaydin@gmail.com)
- **Proje tipi:** Sene sonu bitirme tezi
- **Geliştirme dili:** Türkçe (kod yorumları + dokümantasyon + UI metinleri)
- **Önemli ilke:** **Hiçbir şeyi bozmadan ilerle.** Mevcut davranışı değiştiren her PR için test koşturulmalı + `DevelopmentHistory.md`'ye not düşülmeli.

---

*Bu dosya `DevelopmentHistory.md` ile birlikte session'lar arası bellek görevi görür. Lütfen her oturumda güncel tutun.*
