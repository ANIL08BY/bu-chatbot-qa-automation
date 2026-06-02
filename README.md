# BU Chatbot - Test Otomasyonu

Bu depo, Antalya Belek Üniversitesi Chatbot sisteminin uçtan uca (E2E), API, siber güvenlik, performans ve Yapay Zeka (LLM) doğruluk metriklerinin test edilmesi için kurulmuş profesyonel ve izole bir test otomasyon altyapısıdır.

## Kullanılan Teknolojiler

- **Test Orkestratörü:** Pytest (`pytest-asyncio`, `pytest-mock`)
- **Arayüz (E2E) Testleri:** Playwright (Python)
- **Performans & Yük Testleri:** Locust
- **Yapay Zeka (RAG) Testleri:** LangChain tabanlı özel "LLM-as-a-Judge" (Hakem LLM) mimarisi (Faithfulness, Answer Relevance, Hit Rate, MRR, Toxicity)
- **Güvenlik Kontrolü & Sızma:** SlowAPI, Pytest Özel SQLi/XSS/Prompt Injection Vektörleri
- **Raporlama Altyapısı:** Allure Report

## Kurulum ve Çalıştırma (Kurulum Kılavuzu)

Test otomasyon projesini yerel makinenizde ayağa kaldırmak için aşağıdaki adımları izleyin:

1. **Sanal Ortamı Oluşturun ve Aktif Edin:**
   python -m venv venv
   .\venv\Scripts\activate # Windows için
   source venv/bin/activate # Linux/Mac için

2. **Gerekli Test Kütüphanelerini İndirin:**
   pip install -r requirements.txt

3. **Kararlı ve Modüler Test Koşumu:**
   Sistemdeki güvenlik duvarlarının test aracını engellememesi ve Groq (LLM) API kotalarının dolup asılsız test hatalarına (Flaky Tests) yol açmaması için testlerin klasör veya modül bazında ayrı ayrı çalıştırılması zorunludur:

   # 1. Birim ve Altyapı Testleri

   pytest tests/unit/ -v

   # 2. Veri Boru Hattı (Pipeline / Chunking) Testleri

   pytest tests/pipeline/ -v

   # 3. API ve Sistem Sağlık Testleri

   pytest tests/api/ -v

   # 4. Siber Güvenlik ve Sızma Testleri (Ayrı ayrı çalıştırılmalıdır)

   pytest tests/security/test_prompt_injection.py -v
   pytest tests/security/test_rate_limit.py -v
   pytest tests/security/test_sql_injection.py -v

   # 5. Yapay Zeka Doğruluk (AI Evaluation) Testleri

   # API limitlerine (Rate Limit) takılmamak için ayrı çalıştırılmalıdır!

   pytest tests/ai_eval/test_eval_integration.py -v
   pytest tests/ai_eval/test_relevance.py -v
   pytest tests/ai_eval/test_ood.py -v
   pytest tests/ai_eval/test_toxicity.py -v
   pytest tests/ai_eval/test_faithfulness.py -v

   # 6. Uçtan Uca Arayüz (E2E - Playwright) Testleri

   # Not: Bu testin çalışması için FastAPI sunucusunun ve React arayüzünün ayakta olması gerekir.

   pytest tests/e2e/ -v

   # 7. Performans ve Yük (Load - Locust) Testleri

   # Sistemin eşzamanlı kullanıcı dayanıklılığını ölçer.

   python -m locust -f tests/performance/locustfile.py

## Sistem Genel Mimarisi

Aşağıdaki diyagramda, geliştirdiğimiz QA test otomasyon ekosisteminin, Yusuf tarafından geliştirilen ana chatbot çekirdek sistemi (React, FastAPI, PostgreSQL, Qdrant) ile nasıl entegre olduğu ve hangi katmanı nasıl denetlediği modellenmiştir:

```mermaid
graph TB
    %% Kullanıcı ve Test Tetikleyicileri
    User((Üniversite<br>Kullanıcısı))
    Developer((Geliştirici / <br>Test Mühendisi))

    subgraph QASystem["QA & Test Otomasyon Ekosistemi (Test Projesi)"]
        direction TB
        Orchestrator{Pytest<br>Test Orkestratörü}

        subgraph TestMotorlari ["Test Motorları"]
            E2E[Playwright<br>UI & Feedback Testleri]
            Load[Locust<br>Yük & Hız Sınırı]
            AIEval[LLM-as-a-Judge<br>Halüsinasyon & Metrik]
            Sec[Custom Payloads<br>Güvenlik & Sızma]
        end

        Report[Allure Dashboard<br>Test Sonuçları]

        Developer -->|"Manuel / Yerel Tetikleme"| Orchestrator
        Orchestrator --> E2E
        Orchestrator --> Load
        Orchestrator --> AIEval
        Orchestrator --> Sec
        Orchestrator -->|"Sonuçları Derler"| Report
    end

    subgraph HedefSistem ["BU Chatbot Çekirdek Sistemi (Hedef Sistem)"]
        direction TB
        UI[React 19 Frontend<br>Kullanıcı Arayüzü]
        API[FastAPI Backend<br>Uç Noktalar & İş Mantığı]

        subgraph VeriKatmani ["Veri Katmanı"]
            DB[(PostgreSQL<br>İlişkisel Veritabanı)]
            VDB[(Qdrant<br>Vektör Veritabanı)]
        end

        subgraph YZBoruHatti["Yapay Zeka & Veri Boru Hattı"]
            Pipeline[Dagster & Docling<br>Belge Parçalama]
            LLM[Groq API<br>Llama-3]
        end

        UI <-->|"REST API / JSON"| API
        API <-->|Asyncpg| DB
        API <-->|"Hibrit Arama"| VDB
        API <-->|"RAG Prompting"| LLM
        Pipeline -->|"Vektörleştirme (Ingestion)"| VDB
    end

    %% Kullanıcı Etkileşimi
    User <-->|"Sohbet Eder"| UI

    %% Test Sisteminin Hedef Sistemle Etkileşimi
    E2E -.->|"DOM Simülasyonu"| UI
    Load -.->|"HTTP /ask Yükü"| API
    AIEval -.->|"RAG Bağlam Doğrulaması"| LLM
    AIEval -.->|"Vektör Doğruluğu"| VDB
    Sec -.->|"Zararlı Girdi"| API

    %% Stillendirme
    classDef user fill:#eceff1,stroke:#607d8b,stroke-width:2px,color:#000;
    classDef qa fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#000;
    classDef core fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#000;
    classDef db fill:#fff3e0,stroke:#ef6c00,stroke-width:2px,color:#000;

    class User,Developer user;
    class Orchestrator,E2E,Load,AIEval,Sec,Report qa;
    class UI,API,Pipeline,LLM core;
    class DB,VDB db;
```
