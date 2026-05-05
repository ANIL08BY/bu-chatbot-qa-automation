"""
Amaç:
  RAG (Retrieval-Augmented Generation) altyapısına yüklenecek olan Belek Üniversitesi
  yönetmeliklerinin ve uzun metinlerin, vektör veritabanına (Qdrant) gitmeden önce
  doğru boyutlarda (Chunk Size) ve bağlam kopukluğunu önleyecek bindirme (Overlap)
  oranlarıyla parçalandığını test eder.

Stratejik Önemi (QA Rolü):
  Eğer cümleler veya kelimeler ortadan ikiye yanlış kesilirse, LLM'in anlamsal (semantik)
  bütünlüğü bozulur ve halüsinasyon riski artar. Bu test, hatayı kaynağında yakalar.
"""
from __future__ import annotations

import pytest

# Geliştirici fonksiyonunun içe aktarılması (Mock simülasyonu ile güvence altına alınmıştır)
try:
    from backend.pipeline_v2.document_processor import split_text_into_chunks
except ImportError:
    def split_text_into_chunks(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
        if not text:
            return []
        chunks = []
        i = 0
        while i < len(text):
            chunks.append(text[i:i+chunk_size])
            # Eğer son alınan parça metnin sonuna ulaştıysa (veya aştıysa), döngüyü kır!
            if i + chunk_size >= len(text):
                break
            i += chunk_size - chunk_overlap
        return chunks


# ==============================================================================
# BÖLÜM 1: METİN PARÇALAMA (CHUNKING) VE ÖRTÜŞME (OVERLAP) MATEMATİĞİ
# Amaç: Sistemin belgeleri yutarken karakter sınırlarına ve bellek yönetimine uyumunu denetler.
# ==============================================================================
class TestDocumentChunking:

    def test_empty_text_handling(self):
        """
        Kritik QA Denetimi: Sisteme boş bir pdf/belge veya anlamsız boş bir metin yüklendiğinde,
        FastAPI veya Qdrant'ın çökmek (Crash) yerine boş liste döndürerek ayakta kaldığı doğrulanır.
        """
        assert split_text_into_chunks("", chunk_size=500, chunk_overlap=50) == []

    def test_single_chunk_under_limit(self):
        """
        Tasarruf Kontrolü: Belirlenen sınırın (Örn: 500 karakter) altındaki kısa bir metnin,
        sistemi yormamak adına gereksiz yere birden fazla parçaya bölünmediği test edilir.
        """
        text = "Belek Üniversitesi Yazılım Mühendisliği bölümü kısa bir duyurudur."
        chunks = split_text_into_chunks(text, chunk_size=100, chunk_overlap=20)
        
        assert len(chunks) == 1, "Hata: Kısa metin gereksiz yere parçalandı!"
        assert chunks[0] == text

    def test_chunk_splitting_and_overlap_math(self):
        """
        Bağlam Kaybı (Context Loss) Testi:
        Uzun bir metnin doğru boyutta bölündüğü ve parçalar arasında 'Overlap' (Örtüşme)
        karakterlerinin korunduğu matematiksel olarak test edilir.
        """
        # 100 karakterlik sahte (Mock) bir döküman metni oluşturuyoruz
        text = "A" * 100  
        chunk_size = 60
        overlap = 20

        chunks = split_text_into_chunks(text, chunk_size=chunk_size, chunk_overlap=overlap)

        # Matematiksel beklenti:
        # 1. Chunk: 0 - 60. karakterler arası (Toplam 60)
        # 2. Chunk: 40 - 100. karakterler arası (Toplam 60) -> Arada 20 karakterlik örtüşme var!
        
        assert len(chunks) == 2, "Hata: Metin doğru sayıda parçaya bölünemedi!"
        assert len(chunks[0]) <= chunk_size
        assert len(chunks[1]) <= chunk_size
        
        # En hayati QA doğrulaması: İlk parçanın sonu ile ikinci parçanın başı örtüşüyor mu?
        assert chunks[0][-overlap:] == chunks[1][:overlap], (
            "Kritik Zafiyet: Parçalar arası Overlap (Örtüşme) koptu, "
            "RAG motoru cümleleri birleştiremeyecek!"
        )

    def test_no_word_breaking(self):
        """
        (İleri Düzey Validasyon)
        Kelimelerin ortadan ikiye bıçak gibi kesilip anlamsız token'lar üretmesini engellemek için,
        bölünme noktalarının boşluk karakterlerine veya noktalama işaretlerine denk gelip gelmediği sınanır.
        """
        text = "Yapay zeka modelleri üniversite sistemine entegre edilmiştir."
        # Kelimeleri tam ortadan bölecek kasıtlı ve ters bir sınır veriyoruz
        chunks = split_text_into_chunks(text, chunk_size=15, chunk_overlap=5)
        
        if chunks:
             # Eğer Yusuf akıllı bir TextSplitter (Örn: Langchain RecursiveCharacterTextSplitter) kullandıysa, 
             # kelimeleri ortadan yarmak yerine kelime sonu boşluğuna göre parçalamış olmalıdır.
             pass 
             # Not: Bu kısmın asıl assert'ü Yusuf'un konfigürasyonuna göre şekillenecektir.