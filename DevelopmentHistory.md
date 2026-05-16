# Development History — BU Chatbot

> Bu dosya **Claude Code session'larında yapılan tüm değişikliklerin kronolojik kaydıdır**. Amaç: yeni bir oturum açıldığında Claude'un projenin en son halini ve son değişiklik gerekçelerini hızla anlaması.
>
> **Format kuralı:** Yeni girişler **en üste** eklenir (en yeni → en eski). Her giriş Section 0'daki şablona uyar. Bu dosya `CLAUDE.md` ile birlikte tek doğruluk kaynağıdır.

---

## 0. Şablon — Her Yeni Giriş İçin

Her Claude Code session'ı sonunda aşağıdaki bloğu kopyalayıp dosyanın **en üstüne** ekleyin. Alanları doldurun, boş bırakmayın (gerekirse "yok" veya "uygulanmadı" yazın).

```markdown
## YYYY-MM-DD — [Kısa Başlık]

**Session bağlamı:** [Kullanıcının ne istediği — 1-2 cümle]
**Hedef:** [Bu session'da varılması istenen sonuç]

### Yapılan Değişiklikler
- `path/to/file1.py` — [ne değişti, neden]
- `path/to/file2.tsx` — [ne değişti, neden]

### Yeni Dosyalar
- `path/to/newfile` — [amaç]

### Silinen Dosyalar
- `path/to/oldfile` — [neden]

### Mimari / Davranış Etkisi
[Davranış değişti mi? Yeni endpoint? Breaking change? Yoksa "İç refaktör, davranış aynı."]

### Test Durumu
- `pytest tests/ -v`: [geçti / X failed / çalıştırılmadı]
- `pytest -m slow`: [geçti / çalıştırılmadı / N/A]
- Frontend lint: [temiz / hata / çalıştırılmadı]
- Manuel test: [neyi denediniz, sonuç]

### CLAUDE.md Güncellemesi
- [ ] Section 2 (dizin yapısı)
- [ ] Section 4-5 (mimari)
- [ ] Section 6 (API)
- [ ] Section 7 (konstantlar)
- [ ] Section 8 (DB şeması)
- [ ] Section 10 (env)
- [ ] Diğer: ____
- [x] Güncelleme gerekmedi

### Kullanıcıya Notlar
[Bilmesi gereken kritik detay, breaking change uyarısı, sonraki adım önerisi]

### Commitlenmemiş Değişiklikler / TODO
[git status'a ne kaldı; sonraki session'da ele alınacak şeyler]
```

---

## 2026-05-16 — Kapsamlı Proje Dokümantasyonu Oluşturuldu (CLAUDE.md + DevelopmentHistory.md)

**Session bağlamı:** Kullanıcı, proje final sürümüne yaklaşırken Claude Code'un her session'da projeyi sıfırdan keşfetmek zorunda kalmaması için kapsamlı bir kalıcı bellek altyapısı istedi. Token tasarrufu ve tutarlılık öncelik.
**Hedef:** Tüm projenin (backend + frontend + pipeline + testler + mimari + konstantlar + env + bilinen sorunlar) tek dosyada özetlendiği bir `CLAUDE.md` ve session'lar arası değişiklik kaydı için `DevelopmentHistory.md` oluşturmak.

### Yapılan Değişiklikler
- `CLAUDE.md` — Sıfırdan yeniden yazıldı. 18 bölüm halinde:
  - Session başlangıç kontrol listesi (Claude için talimatlar)
  - Tam teknoloji yığını + dizin haritası
  - Dev komutları (backend / frontend / Dagster / test / lint)
  - Query akışı diyagramı (lazy init → analyze → hybrid search → rerank → LLM fallback)
  - Data pipeline asset DAG'ı
  - API sözleşmesi (`/ask`, `/feedback`, `/health` — request/response/status)
  - Tüm kritik konstantların değerleriyle birlikte tablosu (`rag_config.py`, `config_v2.py`, `FALLBACK_MODELS`, rate limit'ler)
  - PostgreSQL şeması (DDL)
  - Frontend bileşen ve state modeli
  - Env değişkenleri tablosu
  - System prompt 12 kuralının özeti
  - Veri kaynakları (`ingestion_list.json` 54 kaynak)
  - "Görev → ilgili dosya" hızlı bakış tablosu
  - **Dokümantasyon güncelleme protokolü** (Section 14)
  - Bilinen sınırlamalar / test kapsamı / sık sorun-çözüm

### Yeni Dosyalar
- `CLAUDE.md` — (eski içerik üzerine yazıldı; 93 satırdan ~400+ satıra genişledi)
- `DevelopmentHistory.md` — Bu dosya. Şablon + ilk giriş.

### Silinen Dosyalar
Yok.

### Mimari / Davranış Etkisi
**Sıfır kod değişikliği.** Yalnız dokümantasyon. Runtime davranışına etkisi yok.

### Test Durumu
- Test çalıştırılmadı (sadece dokümantasyon değişikliği).
- Frontend lint çalıştırılmadı.

### CLAUDE.md Güncellemesi
- [x] Tamamen yeniden yazıldı (yukarıda detaylı).

### Kullanıcıya Notlar
1. **Her yeni Claude session'ında işaretin:** `CLAUDE.md` → `DevelopmentHistory.md` → `git status` sırasıyla okutmak. Section 0 (CLAUDE.md) bu sırayı zaten talimatlandırıyor.
2. **Önemli kural:** Her session sonunda Claude'a "DevelopmentHistory.md'ye giriş ekle" demeyi unutmayın. Şablon dosyanın başında hazır.
3. **Eski CLAUDE.md'de "16 kaynak" yazıyordu** — bu yanlış idi (gerçek sayı 54). Düzeltildi.
4. **Ek dosya önerileri (opsiyonel):**
   - `docs/DECISIONS.md` — büyük mimari kararlar için ADR (Architecture Decision Records) tarzı kalıcı kayıt. Şu an pipeline V1→V2 geçişi gibi tarihsel kararlar `DevelopmentHistory.md` içinde, ama büyürse ayrılabilir.
   - `.claude/instructions.md` — Claude'a sadece kişisel tercih/stil (örn. "Türkçe açıklama, İngilizce kod yorumu") iletmek isterseniz. Şu an gerekmiyor.
   - `TROUBLESHOOTING.md` — Section 17 büyürse buraya taşınabilir.
   - **Önerim:** Şimdilik **sadece CLAUDE.md + DevelopmentHistory.md** yeterli. Proje büyürse yukarıdaki dosyalar eklenebilir.

### Commitlenmemiş Değişiklikler / TODO
**git status (session öncesi tespit edilen mevcut durum — bu session'da değiştirilmedi):**
- Değişmiş: `backend/db.py`, `backend/main.py`, `frontend/src/App.tsx`, `frontend/src/components/ChatMessage.tsx`
- Untracked: `.pre-commit-config.yaml`, `pyproject.toml` (ayrıca bu session'da güncellenen `CLAUDE.md` ve yeni `DevelopmentHistory.md`)

**Sonraki session önerileri:**
1. Yukarıdaki commitlenmemiş değişikliklerin niyetini netleştir; commit'le veya geri al.
2. `frontend/index.html`'deki `<title>frontend</title>` → `BU Chatbot` yap.
3. `frontend/src/components/ChatMessage.tsx`'de gizli source card render'ını aktif etmek isterseniz tasarımı belirleyelim.
4. Eval testlerini (`pytest -m slow`) son commit (`e0dfbd4` — V1 kaldırma) sonrası çalıştırıp baseline kaydet.

---

## 2026-05-06 — V1 Motoru Tamamen Kaldırıldı (commit e0dfbd4)

> Not: Bu giriş retroaktif olarak git log'undan rekonstrükte edildi. Detay için `git show e0dfbd4`.

**Session bağlamı:** ChromaDB + BM25 + RRF tabanlı V1 motorunun kaldırılması, V2 (Qdrant hybrid) tek motor olarak bırakılması.
**Hedef:** Kod tabanını sadeleştirmek, ikili sürdürme yükünü ortadan kaldırmak.

### Yapılan Değişiklikler
- `backend/query.py` — **silindi** (V1 query engine).
- `backend/query_v2.py` — V1 fallback path'leri kaldırıldı.
- `backend/rag_common.py` — `rrf_weights()` ve V1-only yardımcılar silindi.
- `backend/rag_config.py` — V1 RRF/BM25 konstantları temizlendi.
- `backend/main.py` — `/health` endpoint'inden ChromaDB check'i kaldırıldı; kritik bileşenler: api/groq/qdrant.
- Hata yönetimi: V2 hataları artık `logger.exception()` ile stack trace + RuntimeError → HTTP 503 (önceki sessiz fallback yok).

### Mimari / Davranış Etkisi
**Breaking change:** V1 API path'leri ve env değişkenleri artık yok. `engine` response alanı her zaman `"v2"`.

### Test Durumu
Bu commit sonrası çalıştırma kaydı yok.

### Kullanıcıya Notlar
- ChromaDB bağımlılığı hâlâ `requirements.txt`'te (`chromadb>=1.5.0`, `langchain-chroma>=1.1.0`) — kullanılmıyor, ileride temizlenebilir.

---

## 2026-05-04 — `.claude/` git takibinden çıkarıldı (commit e2378d9)

Kullanıcının yerel Claude Code worktree'sinin git'te yer kaplaması engellendi. `.gitignore`'a `.claude/` eklendi.

---

## 2026-05-04 — README + ARCHITECTURE.md güncellendi (commit be21685)

Kaynak sayısı 16 → 54 olarak düzeltildi. PostgreSQL DDL ve RLS uyarısı eklendi. Windows kurulum komutları eklendi. Reranker model (`bge-reranker-base`) dokümante edildi.

---

## 2026-05-04 — İlk commit (f6f7a4c)

Proje scaffold'u. V1 (ChromaDB+BM25+RRF) + V2 (Qdrant hybrid) çift motor olarak. 26,726 satır.

---

*Yeni giriş eklerken: Section 0'daki şablonu kopyala, doldur, **bu dosyanın en üstüne** (Section 0'dan sonra, en yeni girişin üstüne) yapıştır.*
