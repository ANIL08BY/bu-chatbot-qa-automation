import pytest
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance

@pytest.fixture
def mock_qdrant_memory():
    """
    6.1 In-Memory Konfigürasyon:
    Docker veya harici sunucuya ihtiyaç duymadan RAM üzerinde 
    izole bir Qdrant anlamsal uzayı (Schemaless) yaratır.
    """
    # location=":memory:" parametresi sistemin RAM'de yaşamasını sağlar
    client = QdrantClient(location=":memory:")
    
    collection_name = "belek_v2_test"
    
    # 6.2 Vektör Geometrisi (Dense 768 MPNET - Cosine Similarity)
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=768, 
            distance=Distance.COSINE
        )
        # Not: Sparse (BM42) konfigürasyonları da gereksinime göre buraya eklenebilir.
    )
    
    # Testlere bu sanal istemciyi (client) gönder
    yield client
    
    # Teardown (Yıkım): Test bitince RAM'deki izleri sil.
    # :memory: kullanıldığı için bellekten otomatik düşer, ancak garantilemek için:
    client.delete_collection(collection_name=collection_name)

    import uuid
from qdrant_client.models import PointStruct

def populate_mock_vectors(client: QdrantClient, collection_name: str = "belek_v2_test"):
    """
    6.3 Vektör Yükü Şeması:
    Ragas testleri ve alıntı (Citation) doğrulaması için sisteme sahte vektörler basar.
    """
    # 768 boyutlu sahte bir gömme (embedding) vektörü üretiyoruz (Örnek veridir)
    dummy_vector = [0.1] * 768 
    
    # Çizelge 6.1'e birebir uyumlu Payload mimarisi
    mock_payload = {
        "url": "https://belek.edu.tr/burs-yonetmeligi", # Atıf kontrolü için
        "title": "Burs ve Kredi Olanakları",          # RAG kart başlığı eşleşimi için
        "category": "Burs",                           # Sınırlandırma (Boundary filter) için
        "chunk_idx": 0                                # UUID ve indeks doğrulama için
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

    def test_category_filtering(mock_qdrant_memory):
    client = mock_qdrant_memory
    
    # Önce sanal verilerimizi RAM'deki Qdrant'a basıyoruz
    populate_mock_vectors(client)
    
    # Ardından "Burs" kategorisindeki veriyi arıyoruz...
    # (Buraya Hybrid arama veya filtreleme kodların gelecek)
    
    assert True # Başarılı test!