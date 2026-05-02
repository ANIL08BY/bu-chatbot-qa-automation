"""
Amaç: 
  Chatbot'un anlamsal (semantik) zekâsını yöneten iç ayarların test edildiği yerdir.
  İşin mükemmel tarafı: Veritabanına (DB) veya maliyetli dış yapay zeka servisine (Groq LLM)
  bağlanmadan; uygulamanın hesaplama, metin filtreleme ve ağırlık algoritmalarını "saf fonksiyon"
  gibi milisaniyeler içinde yerel RAM üzerinde izole test eder. Mimaride hızı artırır, parayı korur.
"""
from __future__ import annotations

from backend.rag_common import (
    AGGREGATION_RE,
    CATEGORY_LABELS,
    KNOWN_CATEGORIES,
    LIST_RE,
    PROMPT_TEMPLATE,
    compute_k,
    format_history,
    is_rate_limit,
    rrf_weights,
)
from backend.rag_config import RAGConfig, rag_config


# ==============================================================================
# BÖLÜM 1: YAPAY ZEKA SİSTEM LİMİTLERİ (RAG Config) 
# Amaç: Arama sırasında Qdrant'tan kaç adet belge(chunk) alınacağının bozulmadığı sınanır.
# ==============================================================================
class TestRAGConfig:
    def test_defaults_exist(self):
        """
        Model varsayılan belge çekim sayılarının (k=10 vb.) ve gürültü filtre (noise threshold) 
        hassasiyetlerinin izinsiz bir değişikliğe uğramadan kod içerisinde varlığını doğrular.
        """
        assert rag_config.k_general == 10
        assert rag_config.k_list == 30
        assert rag_config.noise_threshold == 0.35

    def test_frozen(self):
        """
        DEĞİŞMEZLİK TESTİ (Immutability): RAG konfigürasyon dosyaları, sistem çalışırken yanlışlıkla 
        başka bir fonksiyon tarafından güncellenememeli. Bu test; uygulamanın configleri kilitlediğini
        (Frozen) ve değiştirilmeye çalışılırsa hatayı 'AtributeError' fırlatarak yakaladığını teyit eder.
        """
        import pytest
        with pytest.raises(AttributeError):
            rag_config.k_general = 999  # type: ignore[misc]


# ==============================================================================
# BÖLÜM 2: MODEL DAVRANIŞ BİÇİMİ / SYSTEM PROMPT TASARIMLARI
# Amaç: Modele kurumu nasıl tanıtacağımızı bildiren iç prompt değişkenlerini arar.
# ==============================================================================
class TestPromptTemplate:
    def test_template_loaded(self):
        """
        Model İstemine (System Prompt) çalışma esnasında dinamik olarak beslenecek (Context, Geçmiş 
        sorular gibi) ilgili zorunlu kapsayıcı veri anahtarlarının şablonda unutulmadığını denetler.
        """
        assert "{context}" in PROMPT_TEMPLATE
        assert "{question}" in PROMPT_TEMPLATE
        assert "{history}" in PROMPT_TEMPLATE
        assert "{category_context}" in PROMPT_TEMPLATE

    def test_turkish_content(self):
        """Llama/Gemma vb AI Modelini dizginleyerek yabancı dile kaymasını önleyen ana dil standartlarına ve kilit komut uyarılarına sahip olduğumuzu doğrular."""
        assert "DÖKÜMAN" in PROMPT_TEMPLATE
        assert "KURALLAR" in PROMPT_TEMPLATE


# ==============================================================================
# BÖLÜM 3: ETİKET (LABEL) VE BİLGİ İSTİF KATEGORİSİ EŞLEŞMELERİ
# ==============================================================================
class TestCategories:
    def test_known_categories_not_empty(self):
        """Sistemin eğitim vektörü kategorilerinin veri iskeletine tanıtıldığı denetlenir (Erişebilirlik Testi)"""
        assert len(KNOWN_CATEGORIES) > 0

    def test_labels_cover_categories(self):
        """Modelden çıkacak teknik isim ile Kullanıcı ekranındaki Başlıkların bir Türkçe Label çevirisi bulunması güvencesidir! Eksiği veya kod unutulmasını kırar!"""
        for cat in KNOWN_CATEGORIES:
            assert cat in CATEGORY_LABELS, f"Label eksik: {cat}"


# ==============================================================================
# BÖLÜM 4: ZEKİ (DYNAMIC K) DÖKÜMAN KOPARMA STRATEJİSİ ÖLÇÜMLERİ
# ==============================================================================
class TestComputeK:
    """
    RAG aramalarında gereksiz token faturası ve vakit şişirmesi yaratılmaması amaçlı
    Bot; "Bana X hakkında HERŞEYİ / TAMAMINI listele dendiğinde ÇOK belge koparacak; spesifik "madde neresi" dendiğinde DAHA AZ, nokta atışı belge kesecektir." Bunu algoritma bazında test ediyoruz.
    """
    def test_list_query(self):
        assert compute_k("Tüm bursları listele") == rag_config.k_list

    def test_aggregation_query(self):
        assert compute_k("Kaç madde var?") == rag_config.k_aggregation

    def test_specific_query(self):
        assert compute_k("Madde 5 ne diyor?") == rag_config.k_specific

    def test_general_query(self):
        assert compute_k("Kayıt nasıl yapılır?") == rag_config.k_general


# ==============================================================================
# BÖLÜM 5: RRF HİBRİT ARAMA (SEMANITIK vs. KEYWORD AĞIRLIĞI DENGESİ)
# ==============================================================================
class TestRRFWeights:
    """
    Model Vektörlerimizde hibrit yapıyı çalıştırıyor. RRF ağırlığını anında karar dengeleme şovuydu. 
    İstiyor ki : Modelden madde/hesap tarzı sert eşleme ararsam "Tam Eşleme=BM25' ağırlık atıp" baskın gelsin. Felsefe kelimesini aratırsak Vektör(Cosine) semantik zeka devreye girip ağırlıklı davransın ki hata/yanlış okutmasın. 
    """
    def test_aggregation_bm25_dominant(self):
        bm25_w, sem_w = rrf_weights("Toplam kaç burs var?")
        assert bm25_w > sem_w # Saf Kelime algısı AI yı dövmelidir!

    def test_general_semantic_dominant(self):
        bm25_w, sem_w = rrf_weights("Kayıt nasıl yapılır?")
        assert sem_w > bm25_w # Derin mantıklı Anlam YapayZekası baskın çıkar!

    def test_weights_sum_to_one(self):
        for q in ["Kaç madde?", "Madde 5", "Genel soru"]:
            bm25_w, sem_w = rrf_weights(q)
            # Ağırlık total matematiğinde sistemin dağılma hatasına yol açmamasi ölçülmektedir, Tolerasyon Max 1% olmalidir. 
            assert abs(bm25_w + sem_w - 1.0) < 0.01


# ==============================================================================
# BÖLÜM 6: BELLEK (SOHBET TARİHÇESİ PENCERESİ) SIKIŞTIRILMASI 
# ==============================================================================
class TestFormatHistory:
    """ AI Prompları biriken Tokeni patlatıp sunucu hatası HTTP Hatası basılmasını koruması senkron kilit kontrol testiyel onanmıştır """
    
    def test_empty_history(self):
        # Bağımsız geçmişte de düz çalişıyoruz hatasi basması gerekir!
        assert format_history(None) == ""
        assert format_history([]) == ""

    def test_basic_formatting(self):
        # Modele Prompt yediriliş dili doğrulamadır
        history =[
            {"role": "user", "content": "Merhaba"},
            {"role": "assistant", "content": "Nasıl yardımcı olabilirim?"},
        ]
        result = format_history(history)
        assert "Kullanıcı: Merhaba" in result
        assert "Asistan: Nasıl yardımcı olabilirim?" in result
        assert "KONUŞMA GEÇMİŞİ:" in result

    def test_max_messages_limit(self):
        """ Sistemdeki (Limit token optimizasyon koruması): Test Seneryosu bot'u kandırmak adına hafıza sonu mesaj taşırırcasına atıldığında ;
        Geçmişin FR Belgelenen  Sadece ilk x ve son günceli hatırlamaya dayatılan korunak algoritasına  %100 girdiğini Test etmektedir (eskiye yer verme at gitsin eylem kılıfı) """
        history =[{"role": "user", "content": f"msg{i}"} for i in range(20)]
        result = format_history(history)
        # Son 6 mesaj kuralının çalıştığı Onayı olmalı (Indexle)
        assert "msg14" in result
        assert "msg19" in result
        assert "msg0" not in result # msg0 uçup (temizleme çöp limit denendiğini pass attı!)


# ==============================================================================
# BÖLÜM 7: API KORUMALARI / DÜŞMAN ZAMANI DENETLEMESİ
# ==============================================================================
class TestIsRateLimit:
    """ Rate-Limit hatalarından Fail Yiyecekmi yoksa Doğrudan Hatasını Algılabilcek mi Tespit Onaylanışı """
    
    def test_detects_429(self):
        assert is_rate_limit(Exception("Error 429: rate limit"))

    def test_detects_rate_limit_text(self):
        assert is_rate_limit(Exception("rate_limit_exceeded"))

    def test_detects_token_limit(self):
        assert is_rate_limit(Exception("tokens per day limit reached"))

    def test_normal_error(self):
        """ Farklı bir db hata/baglanamazda Hızı limitlendi gibi yalana(Yalan exception yutumsu) kapılmayacağı anafikri onaylatildi """
        assert not is_rate_limit(Exception("connection refused"))


# ==============================================================================
# BÖLÜM 8: KISA KELİME(REGEX) ŞABLON TANIMA BOT GÜVENİLİRLİĞİ (LLMsiz İrade Tespit)
# ==============================================================================
class TestRegexPatterns:
    
    def test_aggregation_patterns(self):
        # Cümlenin manasını kelime eklerine ve kalıba yapısından yorumlar / Onay Testleri 
        assert AGGREGATION_RE.search("Kaç madde var?")
        assert AGGREGATION_RE.search("toplam sayısı")
        assert not AGGREGATION_RE.search("Kayıt nasıl yapılır?")

    def test_list_patterns(self):
        assert LIST_RE.search("Tüm bursları listele")
        assert LIST_RE.search("Hangileri var?")
        assert not LIST_RE.search("Ne zaman başlıyor?")