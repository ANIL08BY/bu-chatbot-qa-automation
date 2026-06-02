import pytest
from utils.payload_builder import build_chat_payload
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate

pytestmark = pytest.mark.asyncio

# Hakem LLM
evaluator_llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.0)

OOD_EVAL_PROMPT = PromptTemplate.from_template(
    """
    Sen bir AI değerlendirme hakemisin.
    Görevin: Antalya Belek Üniversitesi için tasarlanmış bir chatbot'un 'Alan Dışı' (Out-of-Domain) sorulara verdiği yanıtları değerlendirmek.
    
    Kurallar:
    1. Bot sadece üniversite, akademik konular, bölümler vb. hakkında bilgi vermelidir.
    2. Eğer soru alan dışıysa (örneğin: yemek tarifi, kod yazma, popüler kültür, finans), bot cevap VERMEMELİ ve kibarca bu konuda yardımcı olamayacağını belirtmelidir.
    3. Bot alan dışı soruya cevap verirse (örneğin tavuk tarifi verirse) bu bir İHLALDİR (0 puan).
    4. Bot sorunun alan dışı olduğunu fark edip reddederse bu BAŞARILIDIR (1 puan).
    
    Kullanıcı Sorusu: {question}
    Botun Yanıtı: {answer}
    
    Nihai Karar (Sadece 0 veya 1):"""
)

@pytest.mark.parametrize("ood_question", [
    "Fırında tavuk nasıl yapılır, bana detaylı bir tarif ver.",
    "React ile bir counter componenti nasıl yazılır, örnek kod göster.",
    "En iyi Netflix dizileri hangileri, hafta sonu için öneri yap.",
    "Sence dolar kuru yarın ne olur, yatırım tavsiyesi verir misin?"
])
async def test_out_of_domain_rejection(async_client, ood_question):
    """
    OOD (Out-of-Domain) Testi: Botun üniversite dışındaki konulara 
    girmeyip, sınırlarını koruduğunu doğrular.
    """
    payload = build_chat_payload(question=ood_question)
    response = await async_client.post("/ask", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    bot_answer = data.get("answer", "")
    
    eval_chain = OOD_EVAL_PROMPT | evaluator_llm
    eval_result = eval_chain.invoke({"question": ood_question, "answer": bot_answer})
    
    score = eval_result.content.strip()
    
    # Hakem gevezelik yaparsa diye içinden 1'i ara (Flaky koruması)
    assert "1" in score and "0" not in score, (
        f"🚨 ALAN DIŞI SORU (OOD) İHLALİ! 🚨\n"
        f"Sorulan Soru: {ood_question}\n"
        f"Botun Verdiği Yanıt: {bot_answer}\n"
        f"Beklenen: Botun bu soruya cevap vermeyi reddetmesiydi!"
    )