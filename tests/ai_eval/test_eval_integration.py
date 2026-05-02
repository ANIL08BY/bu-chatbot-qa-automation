"""
Amaç: 
  Yapay Zekanın "RAG" (Arama Geliştirmeli Çıkarsama) yaparken Vektör (Qdrant) içerisinden bulduğu verilerin ne kadar doğru belgelerden beslendiğinin (Bilimsel kalibresi - Retrieval Metrics) otomasyonudur.

Nasıl Çalışır? (DevOps Uyarısı):
  '@pytest.mark.slow' (Gecikmeli/Ağır İşlem) tagı (etiketi) atılmıştır! 
  Anında saniyesine ve normal eyleme tepki atacak "Amele usul test (Hızlı Commitlerde)" devreye binmesin ki makine kasmayı engellesin. Test çalıştırana bağlı özel "pytest -m slow" olarak sadece derin Entegrasyon veya haftalık raporlama anlarında Vurkaç(Trigger) emredilmesi ile harekete başlar! 
  
Bağımlılık (Pre-requisite): Test "Vektörel Veritabanının In-memory ya da Dev Qdrant (belek_v2 Testleri vs)" varlığını/yüklendiği emrini almadan yürütülemez (Bkz Test Pipeline Qdrant Tasarım Planı Madde-6/NFR.03).
"""
from __future__ import annotations

import pytest


# ==============================================================================
# BÖLÜM 1: İSABET ORANI (HIT RATE / BAĞLAM YAKALAMAS) METRİK ÖLÇÜMÜ (FR.07 Test İçi Eşiği)
# Amaç: Öğrencinin "Ders Notu nasıldır?" diye Chatbot sisteminde attığında dönen ilk K=Adet parçalar(Döküman Parçacığı(Chunks)) 
# kısmında bizim GERÇEKTEN istediğimiz asıl hedefe yarayan kilit metinin tutuşma, denk düşüp içine çekilebilme durumudur.  
# ==============================================================================
@pytest.mark.slow
def test_evaluation_hit_rate():
    """
    RAG (Yapay Zeka Bot Retrieval - Arama) Mekanizması asgari %50 (> 0.50 Puan ve Güvence Hiti) getirim yetisini geçer akçe kabul etmektedir. Sınır aşılıp gerisinde kalıp ÇÖKER (fail verirse) 'Cevapların Uyuşma İkmal Skalası Kaliteden Şaşırmış/Bağlam Eksik Kirlilik Yapmış Demektir.' 
    """
    # Gerekli Ragas veya Öz değerlendirmeyi koşturacak Metrik Modeli / Evaluator çağırma
    from backend.pipeline_v2.evaluation.eval import run_evaluation

    # Modül koşusu yapılır. Beklenen format içerisinde sözlük döner -> Örn: {"hit_rate": 0.65} 
    results = run_evaluation()
    
    # 0.5 Oran sınır ihlallerinden muhafaf ve doğru aradığımız/bota sorduğumuz parça metinin %50 üzerinde bulunduğunu tasdik et!.
    assert results["hit_rate"] >= 0.5, (
        f"Kritik QA Zafiyeti: Vektörel DB İsabet ve Konu Tutturma Yeteneği Hit Rate Beklentilerin Epey Çok Altında Patladı / Uydurdu: Skorumuz (Gözlemlenen= {results['hit_rate']:.2f}) (Zorunlu En Asgari Geçer Akçemiz İse= 0.50 dir)!!"
    )


# ==============================================================================
# BÖLÜM 2: MEAN RECIPROCAL RANK (Ortalama Sıralama Puanları Skalası / MRR Kontrolü)
# Amaç: Vektör Sistem Hibrit Modelleri evet konu/işlenen hedeflerde bilgiyi taşıyor fakat Asıl soru için iş yapacak Altından/Böyle Hayat Kurtaracak o Pırlanta Bilgili olan Döküman Parçasını ne kadar BİRİNCİ, TEPE, LİDER (Geniş Algoritma RRF vs formülü En Tepeye Taşıyışı Performansı)'nı inceliyoruz (Kıyas-K) 
# ==============================================================================
@pytest.mark.slow
def test_evaluation_mrr():
    """
    Algoritmamız asgari '30 Skalası üstünde RRF MRR performansı sağlamış' durumuna onay vermeli/pass bırakmalıdır.. "Yanıtın aradığı Belgesi Belki getirilmiş Olabilir AMAA ÇOOK ARKADAKİLERDE İŞİMİZE YARAMAYACAK Kadar en dip Sıraya itildiyse ve bu sayede de Doğruluk Sapması Yaşatırtıldıysa / Metin Bozulması" krizlerine engellemek için.   
    """
    from backend.pipeline_v2.evaluation.eval import run_evaluation

    # Koşunun puan getirisinin (Result Data) içerisindeki Rank ve Kalibresine ok yönlendirilişi. 
    results = run_evaluation()
    
    # En Az K=Arama skoraj Puan Getirimleri Çarpan Faktöresi olarak Skoru '0.3' bareminin ÜST KATMANLARA Oturtur İlgililik Teşhisi Doğrulama
    assert results["mrr"] >= 0.3, (
        f"MRR Optimizasyonu Kötü Tepki Döndü Algoritması UYARISI: {results['mrr']:.2f} ! İdeal Sıraya Puan Enjeksiyon / Getirme Hata Kalibresi Gözlendi ! Ağırlıkta (K=Threshold >0.30  Düştü))"
    )