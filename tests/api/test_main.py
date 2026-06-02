"""
Amaç:
  Chatbot sisteminin arayüze bağlanmadan (React olmadan) dış dünyaya sunduğu /health 
  ve /ask uç noktalarının veri bütünlüğü, hata yönetimi (Error Handling) ve HTTP kod  
  güvenilirliğini senkron ve mock destekli "FastAPI TestClient" aracı ile denetler.

Stratejik Önemi (QA Rolü):
  Daha henüz veri tabanının bağlanmadığı (Test Çiftleri/Mocking atandığı) ve "Eğer veriler Pydantic 
  500 Karakter kısıtı dışındaysa DB tarafına kir bırakmadan aradan çöktürt" FR.15 Sanitizasyonu vb.
  kalite kriterlerini tam garanti testidir.
"""

from __future__ import annotations

from unittest.mock import patch, AsyncMock
import pytest

from fastapi.testclient import TestClient


# ==============================================================================
# ANA APİ OTURUM DEKLARASYONU VE SİMULATÖR BAŞLATMASI (Test Fixtures)
# Amaç: Uygulamaya test aşamasında tarayıcı ya da local host gerekmeksizin bellekte açtırıp  
# test paketi kapsamında hazır ol / bekle talimatı sağlatılan alan.
# ==============================================================================
@pytest.fixture
def client():
    """ 
    Sunucunun Uvicorn gibi araçlar yerine RAM/iç sunucuda hayaleten ve şimşek 
    hızıyla asıl fastapi core nesnesine tutunuşudur. Gözsüz(Headless) denemelere 
    kalan eylemleri en uygun halde izole eder. 
    """
    from backend.main import app
    return TestClient(app)

# ==============================================================================
# BÖLÜM 1: MİMARİ/SAĞLIK YÖNETİM TESTLERİ (The /health API Routes )
# Amaç: Sistemin kilit ayaklarındaki hizmet çökmesini asenkron yapımız dışında denetleme 
# ==============================================================================
class TestHealthEndpoint:
    
    @patch("backend.main.db.check_health", new_callable=AsyncMock, return_value="ok")
    @patch("backend.main.db.get_pool", return_value="fake_pool")
    @patch("qdrant_client.QdrantClient")
    def test_health_returns_json(self, mock_qdrant, mock_pool, mock_db_health, client):
        """ 
        Bot çalışmasa veya sunucu düşse bile "HTML veya çorba Error yerine her zaman 
        Uluslararası REST (Json) dilinde log okunabilmesini!" ölçer ve ana motor (api:'ok') onayını arar. 
        """
        response = client.get("/health")
        data = response.json()
        
        # Testçi onay kalemi: Mutlaka json key olarak api içersin ve OK yazsın ki Frontend patlamasın.
        assert "api" in data
        assert data["api"] == "ok"

    @patch("backend.main.db.get_pool", return_value="fake_pool")
    @patch("qdrant_client.QdrantClient")
    def test_health_checks_groq_key(self, mock_qdrant, mock_pool, client):
        """ AI Llama (RAG Motoru) Bulut Güvencesindeki dışa kapı bağ anahtarımızın (Env Checking'i) çalışırlılığının taranıp denetlendiğini teyit eyler.  """
        response = client.get("/health")
        data = response.json()
        assert "groq_key" in data

    @patch("backend.main.db.get_pool", return_value="fake_pool")
    @patch("qdrant_client.QdrantClient")
    def test_health_checks_qdrant(self, mock_qdrant, mock_pool, client):
        """ Bizim bellek içi (:memory: izole QA) yahutta hoca/ve asıl buluttaki vektor Veri sunucu bağlantısının kontrol bloklarındaki isminden eksik durmamasını Test Garantiler!"""
        response = client.get("/health")
        data = response.json()
        assert "qdrant" in data


# ==============================================================================
# BÖLÜM 2: DÜZENBAZ MESAJA (SECURITY SANITIZATION - LIMIT)  VEYA /ask ÇEKİRDEK İŞLEVLİ DENETLEMELER! 
# Amaç: Pydantic sınır kontrolleri, dış/yükleme API Limit Red ve asenkron mock yanıtlı test denemeler! 
# ==============================================================================
class TestAskEndpoint:

    def test_empty_question_rejected(self, client):
        """Kullanıcının boş veya (Hiç karakter tuşsuz sadece send bot) aksiyon fırlatmasına istinaden 'İçi boş kayıt verisini 422 Validasyon Pydantic Kılıfıyla fırlatarak/engeller veritabanımızı' testini başarı yapar! """
        response = client.post("/ask", json={"question": "", "history":[]})
        assert response.status_code == 422

    def test_too_long_question_rejected(self, client):
        """
        Makine limitlerine stres veya gereksiz DB log dolumları yaratmaya(500karakter son limit FR Kuralınıza Atfen) dayalı olan karakter aşırı zorlayıcılarına set çakıldı. QA/XSS Engelli sınama Onay!
        """
        response = client.post("/ask", json={"question": "x" * 501, "history":[]})
        assert response.status_code == 422

    @patch("backend.main.db.log_interaction", new_callable=AsyncMock, return_value=999)
    @patch("backend.main.db.get_pool", return_value="fake_pool")
    @patch("backend.main.ask_question")
    def test_successful_response(self, mock_ask, mock_pool, mock_log, client):
        """ 
        Hayırlı ve 10 numara 200 Statüsü Geçirici Mutlu Path(Senaryosu) - Backend/DB tarafının LLM faturanızı/vaktini ÇÖP ETMESİN/Test Hızlanmasını kesmesin için Dış bağımlılık fonksiyonunu 'YARA BANDI: patch ' atılmış mocklu başarı yanıtıdır!  
        """
        mock_ask.return_value = {
            "answer": "Test yanıtı",
            "sources":[],
            "category": "genel",
            "engine": "v2",
        }
        
        response = client.post("/ask", json={"question": "Test sorusu", "history":[]})
        
        assert response.status_code == 200 # Harikasınız API uyanıp 200 (Success vererek cevaba sarıldı!) 
        
        data = response.json()
        assert data["answer"] == "Test yanıtı"
        assert data["engine"] == "v2"
        # RLS veritabanı yaması test ediliyor: Yeni message_id eklendi mi?
        assert data.get("message_id") == 999

    @patch("backend.main.ask_question")
    def test_runtime_error_returns_503(self, mock_ask, client):
        """ Test senaryosunda (Exception Fails Safe Test Plan). Örneğin LLM in ve Groq model apiniz Timeout(limit patladı) veya RuntimeError yaşanırsa Chatbottumuz ne olacak? Sistem DB yi RollBack için (Exception / 503 erroru dondurebilir mi??) """
        
        mock_ask.side_effect = RuntimeError("GROQ_API_KEY bulunamadı")
        
        response = client.post("/ask", json={"question": "Test", "history":[]})
        assert response.status_code == 503  # Çökmesi (Yeniden tekrak buton basar kullanıcı ve test güvende!) 

    @patch("backend.main.ask_question")
    def test_unexpected_error_returns_500(self, mock_ask, client):
        """ 
        Sistemde öngörülemeyen ve kodla yakalanmayan bir Python hatası (örneğin 
        ValueError veya bellek taşması) oluştuğunda; uygulamanın (FastAPI) tamamen 
        çökmek yerine arayüze güvenli bir şekilde HTTP 500 (Internal Server Error) 
        hata kodunu döndürerek ayakta kalabildiğini test eder. 
        """
        mock_ask.side_effect = ValueError("Beklenmeyen bir kod hatası fırlatıldı")
        
        response = client.post("/ask", json={"question": "Test sorusu", "history": []})
        
        assert response.status_code == 500