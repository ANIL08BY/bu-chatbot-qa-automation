import sys
import os

# Python'un klasör arama yoluna (sys.path) "tests" klasörünü ZORLA ekle:
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from utils.payload_builder import build_chat_payload
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate

pytestmark = pytest.mark.asyncio

# Groq LLM'i "Hakem (Judge)" olarak tanımla
# Not: .env dosyasındaki GROQ_API_KEY'i otomatik kullanacaktır
evaluator_llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.0)

# Hakem Yapay Zekaya vereceğim değerlendirme talimatı (Prompt)
FAITHFULNESS_PROMPT = PromptTemplate.from_template(
    """
    Sen tarafsız bir kalite kontrol hakemisin.
    Görevin, verilen 'Asistan Cevabı'nın, tamamen 'Sağlanan Kaynak Metinler'e sadık kalıp kalmadığını değerlendirmektir.
    Cevap, kaynak metinlerde bulunmayan yeni bir bilgi uyduruyorsa (halüsinasyon) puan 0 olmalıdır.
    Cevap tamamen kaynak metinlerden çıkarılabiliyorsa puan 1 olmalıdır.
    
    Sağlanan Kaynak Metinler:
    {context}
    
    Asistan Cevabı:
    {answer}
    
    Kararını SADECE '1' veya '0' olarak ver. Başka hiçbir açıklama yazma.
    """
)

async def test_rag_faithfulness_metric(async_client):
    """
    AI Değerlendirme Testi: Faithfulness (Sadakat/Halüsinasyon)
    Botun verdiği cevabın, kendi bulduğu referans belgelere %100 sadık olduğunu test eder.
    """
    # 1. Botumuza üniversite ile ilgili spesifik bir soru sor
    payload = build_chat_payload(question="Antalya Belek Üniversitesi'nde çift anadal (ÇAP) yapma şartları nelerdir?")
    response = await async_client.post("/ask", json=payload)
    
    assert response.status_code == 200, "API yanıt veremedi."
    data = response.json()
    
    answer = data.get("answer", "")
    sources = data.get("sources", [])
    
    # Eğer kaynak (context) bulamadıysa ancak yine de cevap uydurduysa, bu kesin bir halüsinasyondur!
    if not sources and "bilmiyorum" not in answer.lower() and "bulunamadı" not in answer.lower():
        pytest.fail(f"🚨 HALÜSİNASYON TESPİTİ! Kaynak belge yok ama bot cevap uydurdu:\nCevap: {answer}")

    # Kaynakları tek bir metinde birleştir
    context_text = "\n".join([f"- {s.get('content', '')}" for s in sources])
    
    # 2. Hakem LLM'e (Llama-3) soruyu, bağlamı ve bizim botun cevabını verip puanlamasını iste
    eval_chain = FAITHFULNESS_PROMPT | evaluator_llm
    eval_result = eval_chain.invoke({"context": context_text, "answer": answer})
    
    score = eval_result.content.strip()
    
    # 3. KONTROL: Hakem botumun cevabını 1 (Sadık) olarak puanlamalı!
    assert score == "1", (
        f"🚨 FAITHFULNESS HATASI (Sadakat Testi Başarısız)! 🚨\n"
        f"Hakem Puanı: {score}\n"
        f"Bulunan Kaynak: {context_text}\n"
        f"Botun Verdiği Cevap: {answer}\n"
        f"Durum: Bot kaynaklarda olmayan bilgiler uydurdu (Halüsinasyon)!"
    )