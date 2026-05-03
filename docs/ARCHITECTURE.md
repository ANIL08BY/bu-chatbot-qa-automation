# BU Chatbot — Mimari Dokümantasyon

## Veri Akışı

```
ingestion_list.json (16 kaynak, 16 kategori)
        │
        ├─ raw_web_pages ──── Firecrawl API (HTML → Markdown)
        ├─ raw_pdf_documents ─ Docling + TableFormer (PDF → Markdown)
        └─ raw_local_documents ─ Doğrudan dosya okuma
                │
        document_hashes ─── SHA-256 deduplikasyon
                │
        cleaned_documents ── Unicode normalizasyon, boilerplate temizliği
                │
        semantic_chunks ──── Heading-aware chunking (800 char, 150 overlap)
                │
        qdrant_collection ── Dense (768d) + BM42 sparse vektörler
```

## Sorgu Akışı

```
Kullanıcı sorusu
        │
    analyze_query() ─── LLM ile kategori tespiti + sorgu optimizasyonu
        │                (llama-3.1-8b-instant, max 60 token)
        │
    ┌───┴──────────────────────────┐
    V2 (birincil)                  V1 (Qdrant erişilemezse fallback)
    │                              │
    Qdrant hybrid search           ChromaDB MMR + BM25
    (dense + BM42 sparse)          Reciprocal Rank Fusion
    │                              │
    Cross-Encoder Reranking        (reranking yok)
    (BAAI/bge-reranker-base)       │
    └──────────────┬───────────────┘
                   │
    LLM yanıt üretimi ── Groq llama-3.3-70b-versatile
        │                   ↓ 429 rate limit
        │                 meta-llama/llama-4-scout-17b-16e-instruct
        │                   ↓ 429 rate limit
        │                 llama-3.1-8b-instant
        │
    { answer, sources, category, engine }
        │
    PostgreSQL log_interaction() ── sessions / messages / citations / system_logs
```

## Fallback Zinciri

1. **Query V2** (Qdrant hybrid + reranker) → Qdrant bağlantı hatası →
2. **Query V1** (ChromaDB + BM25 + RRF) → LLM rate limit →
3. **Model fallback** (70b → llama-4-scout-17b → 8b) → Tüm modeller tükendi → RuntimeError

## Kategori Sistemi

- 16 kategori `ingestion_list.json`'daki `category` alanından otomatik türetilir
- Slug normalizasyon: `"burs olanakları"` → `"burs-olanaklari"` (Türkçe karakter → ASCII)
- Sorgu analizi LLM ile kategori eşleşmesi yapar
- Eşleşen kategoride < 3 sonuç varsa otomatik `"genel"` fallback

## Teknoloji Seçimleri

| Bileşen | Teknoloji | Neden |
|---------|-----------|-------|
| LLM | Groq (Llama 3.3 70B) | Ücretsiz tier, düşük latency |
| Vector DB (V2) | Qdrant | Built-in hybrid search, BM42 sparse |
| Vector DB (V1) | ChromaDB | Basit kurulum, disk-tabanlı |
| Embedding | paraphrase-multilingual-mpnet-base-v2 | Türkçe desteği, 768d |
| Reranker | BAAI/bge-reranker-base | Cross-encoder, query_v2.py runtime modeli |
| Pipeline | Dagster | Asset-based DAG, incremental processing |
| PDF Parsing | Docling + TableFormer | Tablo algılama, yapısal çıktı |
| Web Scraping | Firecrawl | onlyMainContent, temiz markdown |
| Frontend | React 19 + Vite | Hızlı HMR, TypeScript desteği |
| Logging DB | PostgreSQL (asyncpg) | Her /ask isteği için atomik transaction kaydı |
| Rate Limiter | slowapi | /ask → 50/dk, /health → 200/dk |
