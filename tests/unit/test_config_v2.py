"""
Amaç: Backend tarafında kurulan Türkçe-İngilizce metin dönüştürücü motorun (slugify) 
  ve RAG kategori filtreleme sisteminin eksiksiz ve hatasız çalıştığını test eder.

  Sistemi internete, veritabanına ya da tarayıcıya bağlamadan, saniyenin onda biri sürede 
  SADECE Python mantığını sınarız. (NFR.03 Kapsamındadır)
"""

from __future__ import annotations

# Test edilecek backend algoritması kodlarını import et
from backend.pipeline_v2.config_v2 import (
    CATEGORY_LABELS_V2,     # Kullanıcıya gösterilen kategori isimleri (Örn: Burslar ve Krediler)
    KNOWN_CATEGORIES_V2,    # Veritabanının okuduğu teknik isimleri (Örn: burslar-ve-krediler)
    slugify,                # Türkçe özel ve karmaşık kelimeleri İngilizce formatlı link (slug) şekline çeviren fonksiyon
)


# ==============================================================================
# BÖLÜM 1: TÜRKÇE FORMATTAN SLUG YAPISINA DÖNÜŞÜM TESTLERİ
# Amaç: Vektör aramalarda (Qdrant vb) url/konu eşleşmesinin "ÇÖŞĞÜİ" gibi Türkçe 
# karakterlerle çökmemesi ve standarda uyarlanması güvence altına alınır.
# ==============================================================================
class TestSlugify:
    
    def test_turkish_chars(self):
        """
        Türkçe harfleri (ş,ç,ö,ğ,ü,ı) yakalar. 'burs olanakları' yazısının hatasız
        ve tire '-' ayrımlı şekilde 'burs-olanaklari' dönüştüğünü garanti eder.
        """
        assert slugify("burs olanakları") == "burs-olanaklari"

    def test_multiple_spaces(self):
        """
        Dikkatsizce girilen iki veya daha fazla boşluk durumunu simüle eder.
        Birden çok yan yana duran boşluğun çökme yapmayıp "tek tire(-)" haline getirildiği testtir.
        """
        assert slugify("çok  boşluklu  metin") == "cok-bosluklu-metin"

    def test_uppercase(self):
        """
        Kategori adı tamamen veya yarıyarıya BÜYÜK harflerle verilirse
        Bunu küçük karakter (lower) durumuna çeken filtre doğrulanır.
        """
        assert slugify("Büyük Harf") == "buyuk-harf"

    def test_special_chars(self):
        """
        (XSS vs) veya yanlış etiket ile metin içine sokulmuş garip sembollerin/parantezlerin '() ! vs' 
        filtre takılamaması için yutulduğunu dener (FR.15 Validasyon Uyumlu).
        """
        assert slugify("test (deneme)") == "test-deneme"


# ==============================================================================
# BÖLÜM 2: SİSTEM ETİKET VE KATEGORİ ENTEGRASYONU
# Amaç: Öğrencinin sistem üzerinde "Öğrenci işlerine dair" (Örn 54 Kategori Etiketi - FR.07) 
# soru sorma durumunun mimaride çöküntüsüz kayıtlandığı birim kontrolleridir.
# ==============================================================================
class TestCategorySystem:
    
    def test_categories_loaded(self):
        """
        Dökümanda yazan veya botta var olan Kategori etiket (Listesinin) sıfırdan "boş ve unutulmuş"
        halde gelip gelmediği kontrolüdür. Veri tabanı başlamadan kural patlarsa boş geleni engeller!
        """
        assert len(KNOWN_CATEGORIES_V2) > 0  # Kategori arşivi en az 1 bileşene sahip olmak zorundadır!

    def test_labels_match_categories(self):
        """
        Bot RAG esnasında teknik Kategori link (Slug) arar (Örn: spor_merkezi) 
        Sonrasında onu kullanıcı dilinde geri yansıtmalı. "Acaaba bütün slug olan başlıkların
        Cidden düzgün (Label) isim çevrilmiş bir Türkçe kelimesi/listesi var mıdır?" doğrulaması yapılır.
        Eksik kalan/uyumsuz tek madde varsa Test kırmızı patlatır ve CI durdurulur!
        """
        for slug in KNOWN_CATEGORIES_V2:
            assert slug in CATEGORY_LABELS_V2, f"Kategori sistemimizde metin açıklaması(Label) unutulmuş eksik hata tespiti!: {slug}"

    def test_slug_format(self):
        """
        Yine sistemdeki RAG (Kategori Algılama Bot) zekası hatasından kaçış eylemidir.
        Kategorilerin arasında kalmış "büyük harfli bir yapı" yahut arada kalmış 
        tesadüfi veya gözden kaçmış bir "Boşluk karakter" kalıp kalmadığını QA Testler döngüsü testidir. 
        """
        for slug in KNOWN_CATEGORIES_V2:
            assert slug == slug.lower(), f"Beklenen Teknik format 'Slug' tamamen 'küçük' yazımlıdır ve büyük karakter olamaz!: {slug}"
            assert " " not in slug, f"Beklenen Format Tireleme üzerineydi ve burada tehlikeli bir boşluk kaldı: {slug}"