# BU Chatbot - Test Otomasyonu

Bu depo, "BU Chatbot" sisteminin uçtan uca (E2E), API, performans ve Yapay Zeka (LLM) doğruluk metriklerinin test edilmesi için kurulmuş profesyonel bir test otomasyon altyapısıdır.

## Kullanılan Teknolojiler

- **Test Orkestratörü:** Pytest (`pytest-asyncio`)
- **Arayüz (E2E) Testleri:** Playwright
- **Performans Testleri:** Locust
- **Yapay Zeka (RAG) Testleri:** Ragas & Promptfoo
- **Raporlama:** Allure Report

## Kurulum ve Çalıştırma (Kurulum Kılavuzu)

Projeyi kendi bilgisayarınızda çalıştırmak için aşağıdaki adımları izleyin:

1. **Sanal Ortamı Oluşturun ve Aktif Edin:**
   python -m venv venv
   .\venv\Scripts\activate # Windows için

2. **Gerekli Test Kütüphanelerini İndirin:**
   pip install -r requirements.txt

3. **Testleri Başlatın:**
   pytest -v

## Sistem Genel Mimarisi

```mermaid
graph TB
    %% Kullanıcı ve CI/CD Tetikleyicileri
    User((Üniversite<br>Kullanıcısı))
    Developer((Geliştirici / <br>Test Mühendisi))

    subgraph QASystem["QA & Test Otomasyon Ekosistemi (Senin Projen)"]
        direction TB
        CICD[GitHub Actions<br>CI/CD Pipeline]
        Orchestrator{Pytest<br>Test Orkestratörü}

        subgraph TestMotorlari ["Test Motorları"]
            E2E[Playwright<br>UI & A11y Testleri]
            Load[Locust<br>Yük & Hız Sınırı]
            AIEval[Ragas / DeepEval<br>Halüsinasyon Skoru]
            Sec[Promptfoo<br>Güvenlik / Injection]
        end

        Report[Allure Dashboard<br>Test Sonuçları]

        Developer -->|"Push/PR"| CICD
        CICD -->|Tetikler| Orchestrator
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
            VDB[(Qdrant / ChromaDB<br>Vektör Veritabanı)]
        end

        subgraph YZBoruHatti["Yapay Zeka & Veri Boru Hattı"]
            Pipeline[Dagster & Docling<br>Belge Parçalama]
            LLM[Groq API<br>Llama-3.3-70b]
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
    class CICD,Orchestrator,E2E,Load,AIEval,Sec,Report qa;
    class UI,API,Pipeline,LLM core;
    class DB,VDB db;
```
