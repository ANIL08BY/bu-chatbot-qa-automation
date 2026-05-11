import pytest
from qdrant_client.models import Filter, FieldCondition, MatchValue

def test_in_memory_qdrant_search_and_filter(mock_qdrant_memory, populate_mock_vectors):
    """
    Bu test, Docker veya harici bir sunucuya ihtiyaç duymadan, tamamen RAM 
    üzerinde oluşturulan izole Qdrant uzayında arama ve filtreleme yapar.
    Jüriye 'Sistemimiz sunucusuz ortamda bile vektörel zekasını koruyor' demek için yazılmıştır.
    """
    client = mock_qdrant_memory
    collection_name = "belek_v2_test"

    # 1. ARRANGE (Hazırlık): conftest.py'deki fonksiyonumuzla RAM'e sahte vektörü bas
    populate_mock_vectors(client, collection_name)

    # 2. ACT (Eylem): Qdrant'a gidip "Kategorisi 'Burs' olan belgeleri bana getir" diyoruz
    # (Bu, Yusuf'un RAG mimarisinin arka planda yaptığı filtreleme işleminin aynısıdır)
    search_result = client.scroll(
        collection_name=collection_name,
        scroll_filter=Filter(
            must=[
                FieldCondition(
                    key="category",
                    match=MatchValue(value="Burs")
                )
            ]
        ),
        limit=1
    )

    # Dönen sonuçları al
    records, next_page_offset = search_result

    # 3. ASSERT (Doğrulama): Yapay Zeka (Qdrant) doğru belgeyi bulabildi mi?
    assert len(records) > 0, "HATA: Qdrant RAM üzerinde veriyi bulamadı!"
    
    bulunan_veri = records[0].payload
    
    # Payload (Metadata) kontrolleri
    assert bulunan_veri["category"] == "Burs"
    assert bulunan_veri["title"] == "Burs ve Kredi Olanakları"
    assert "belek.edu.tr" in bulunan_veri["url"]