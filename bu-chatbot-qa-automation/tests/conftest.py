import sys
import os

import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

# Backend VS Code projesi klasörünün tam yolunu (Absolute Path) buraya ekle!
BACKEND_PROJE_YOLU = r"C:\Users\ANIL\OneDrive\Masaüstü\Mezuniyet Projesi 4.Sınıf Bahar Dönemi Dersi\AI Destekli Chatbot Projesi\Kodlar\Backend\backend"

if BACKEND_PROJE_YOLU not in sys.path:
    sys.path.append(BACKEND_PROJE_YOLU)

# Şimdi test projem, Backend klasörünün içini kendi klasörüymüş gibi okuyabilir!
from backend.main import app as fastapi_app

import pytest
import pytest_asyncio
from httpx import AsyncClient
from playwright.sync_api import sync_playwright
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock

# @pytest.fixture(scope="session"): Bu ayar, tarayıcının her testte tekrar tekrar açılıp kapanmasını engeller.
# "session" (oturum) seviyesinde olduğu için tüm test paketi koşumu boyunca tarayıcı ana motoru sadece BİR KERE açılır. 
# Bu yapı, testlerin çalışma süresini hızlandırır.
@pytest.fixture(scope="session")
def browser_context():
    """Playwright tarayıcı oturumunu başlatır ve yapılandırır."""
    
    # sync_playwright() ile Playwright'ın senkron (eşzamanlı) API'sini başlat.
    with sync_playwright() as p:
        
        # Chromium (Chrome/Edge altyapısı) tarayıcısını başlat. 
        # headless=False ayarı, testler koşulurken tarayıcı penceresini ekranda canlı olarak görmemizi sağlar. 
        # (CI/CD süreçlerinde veya arka plan testlerinde bu değer True yapılır).
        browser = p.chromium.launch(headless=False)
        
        # Tarayıcı içinde yeni bir "bağlam" (context) oluşturuyoruz. 
        # Context, sanki "Gizli Sekme" açmışız gibi çerezlerin (cookies) ve önbelleğin (cache) izole tutulduğu alandır.
        context = browser.new_context()
        
        # yield komutu, oluşturduğumuz bu context'i test fonksiyonlarının kullanımına sunar. 
        # Testler bitene kadar Python kodu tam bu satırda bekler (duraklar).
        yield context
        
        # Tüm test senaryoları bittikten sonra kaynakları tüketmemek için tarayıcıyı temiz bir şekilde kapat.
        browser.close()


# scope belirtilmediği için varsayılan olarak "function" (fonksiyon) seviyesinde.
# Yani bu blok, her bir test fonksiyonu (örn: test_theme, test_input) için baştan tetiklenir.
@pytest.fixture
def page(browser_context):
    """Her test senaryosu için tamamen izole yeni bir sayfa (sekme) açar."""
    
    # Yukarıdaki session seviyesindeki browser_context'i kullanarak yeni ve temiz bir sekme (page) aç.
    # Bu sayede testler birbirinin verisine, tıklamasına veya oturumuna müdahale edemez. Her test sıfırdan başlar.
    page = browser_context.new_page()
    
    # Açılan bu sekmeyi (page nesnesini) test fonksiyonunun içine gönder.
    yield page
    
    # Test fonksiyonu işini bitirdiğinde (test geçse de, çökse de) bu sekmeyi anında kapat.
    page.close()

@pytest_asyncio.fixture
async def async_client():
    """
    FastAPI uygulamasını ayağa kaldırarak doğrudan arka yüze (API) 
    sanal HTTP istekleri atmamızı sağlayan Asenkron Test İstemcisi.
    """

    # Yeni httpx sürümleri için ASGITransport katmanı oluştur.
    transport = ASGITransport(app=fastapi_app)

    # app=fastapi_app YERİNE transport=transport parametresini kullan. 
    # httpx kütüphanesinin yeni sürümlerinde FastAPI uygulamasını doğrudan app= parametresiyle vermek yerine, bir "Taşıyıcı" (ASGITransport) katmanı üzerinden vermek zorunlu
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

@pytest.fixture
def mock_db_and_query(mocker):
    """
    Gerçek veritabanı ve LLM bağlanmadan (çünkü şema daha yok)
    API Endpointlerinin (Uç Nokta) çalışıp çalışmadığını test edebilmemiz için
    sistemin arkaplan bileşenlerini (DB loglama ve RAG query) izole eder.
    """
    # 1. RAG Motoru (ask_question) hep başarılı dönmüş gibi davran (Halüsinasyon testi değil)
    mocker.patch(
        "backend.main.ask_question",
        return_value={
            "answer": "Bu test ortamından dönen sahte cevaptır.",
            "sources":[],
            "category": "Test Kategori",
            "engine": "Test v1"
        }
    )
    
    # 2. Asenkron DB log kaydını atla (Şema şu an olmadığı için test patlamasın)
    # db.log_interaction ASENKRON (await) olduğu için AsyncMock ZORUNLUDUR!
    mocker.patch("backend.main.db.log_interaction", new_callable=AsyncMock)

    # ==============================================================================
# BÖLÜM 3: QDRANT (VEKTÖR DB) IN-MEMORY TEST MİMARİSİ (MADDE 6.1 - 6.3)
# ==============================================================================

@pytest.fixture
def mock_qdrant_memory():
    """
    6.1 In-Memory Konfigürasyon:
    Docker veya harici sunucuya ihtiyaç duymadan sadece RAM üzerinde çalışan 
    izole bir Qdrant anlamsal uzayı (Schemaless) yaratır. Test bitince otomatik silinir.
    """
    # location=":memory:" parametresi sistemin tamamen RAM'de yaşamasını sağlar
    client = QdrantClient(location=":memory:")
    
    collection_name = "belek_v2_test"
    
    # 6.2 Vektör Geometrisi Tasarımı (Dense 768 Boyutlu MPNET - Cosine Similarity)
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=768, 
            distance=Distance.COSINE
        )
    )
    
    yield client
    
    # Teardown (Yıkım): Test bitince RAM'deki izleri temizle.
    client.delete_collection(collection_name=collection_name)


@pytest.fixture
def populate_mock_vectors():
    """
    6.3 Vektör Yükü Şeması:
    Ragas testleri ve alıntı (Citation) doğrulaması için In-Memory Qdrant 
    istemcisine sahte (mock) vektörler ve payload'lar basan yardımcı araçtır.
    """
    def _populate(client: QdrantClient, collection_name: str = "belek_v2_test"):
        # 768 boyutlu sahte bir embedding vektörü üretiyoruz (Sadece matematiği simüle etmek için)
        dummy_vector = [0.1] * 768 
        
        # Çizelge 6.1'e birebir uyumlu Payload (Metadata) yapısı
        mock_payload = {
            "url": "https://belek.edu.tr/burs-yonetmeligi",
            "title": "Burs ve Kredi Olanakları",
            "category": "Burs",
            "chunk_idx": 0
        }
        
        client.upsert(
            collection_name=collection_name,
            points=[
                PointStruct(
                    id=str(uuid.uuid4()), 
                    vector=dummy_vector, 
                    payload=mock_payload
                )
            ]
        )
        return True
        
    return _populate

    # ==============================================================================
# BÖLÜM 4: POSTGRESQL VERİTABANI TEST MİMARİSİ (RESTRICT TESTLERİ İÇİN)
# ==============================================================================

@pytest_asyncio.fixture
async def db_pool():
    """
    Yusuf'un db.py mimarisini kullanan, testler için gerçek PostgreSQL bağlantı havuzu.
    Not: Bu testlerin çalışması için yerel bilgisayarda (veya .env ile)
    belek_chatbot şemasına sahip bir PostgreSQL veritabanının ayakta olması gerekir.
    """
    from backend import db  # Yusuf'un veritabanı modülü
    
    # .env dosyasındaki DB_DSN'i al (Yusuf'un sisteminde nasıl tanımlıysa)
    # Eğer .env kullanmıyorsanız, geçici olarak buraya postgres:// URL'sini hardcode edebilirsiniz:
    # dsn = "postgresql://kullanici_adi:sifre@localhost:5432/veritabani_adi"
    dsn = os.getenv("DB_DSN", "postgresql://postgres:postgres@localhost:5432/postgres")
    
    # 1. SETUP (Hazırlık): Yusuf'un init_pool fonksiyonunu çalıştır
    await db.init_pool(dsn)
    
    # Yusuf'un global _pool nesnesini al
    pool = db.get_pool()
    
    if pool is None:
        pytest.fail("Veritabanı bağlantı havuzu (Pool) başlatılamadı! Lütfen PostgreSQL'in açık olduğundan ve DB_DSN ayarlarının doğruluğundan emin olun.")
        
    # 2. YIELD (Teslim): Havuzu teste gönder
    yield pool
    
    # 3. TEARDOWN (Temizlik): Test bitince bağlantıları güvenli şekilde kapat
    await db.close_pool()