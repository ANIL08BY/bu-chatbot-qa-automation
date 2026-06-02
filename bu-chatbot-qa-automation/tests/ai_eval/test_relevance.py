import pytest
from utils.payload_builder import build_chat_payload
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate

pytestmark = pytest.mark.asyncio

# Hakem LLM
evaluator_llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.0)

RELEVANCE_EVAL_PROMPT = PromptTemplate.from_template(
    """
    Kullanıcı Sorusu: {question}
    Botun Yanıtı: {answer}
    
    Aşağıdaki soruya SADECE VE SADECE "1" veya "0" olarak cevap ver:
    Botun yanıtı, kullanıcının sorusundaki bilgiyi içeriyor mu? (Evet ise 1, Hayır ise 0)
    
    Cevap (Sadece tek bir rakam yaz, açıklama yapma):"""
)

@pytest.mark.parametrize("relevant_question", [
        "Belek Üniversitesi nerede bulunmaktadır?",
        "Üniversitenin kütüphane çalışma saatleri nedir?",
        "Üniversitenin misyonu ve vizyonu tam olarak nedir?"
    ])
async def test_answer_relevance_metric(async_client, relevant_question):
    """
    Answer Relevance Testi: Botun sorulara dolambaçlı değil, 
    doğrudan ve ilgili cevaplar verdiğini doğrular.
    """
    payload = build_chat_payload(question=relevant_question)
    response = await async_client.post("/ask", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    bot_answer = data.get("answer", "")
    
    eval_chain = RELEVANCE_EVAL_PROMPT | evaluator_llm
    eval_result = eval_chain.invoke({"question": relevant_question, "answer": bot_answer})
    
    score = eval_result.content.strip()
    
    assert "1" in score and "0" not in score, (
        f"🚨 CEVAP İLGİLİLİĞİ (RELEVANCE) DÜŞÜK! 🚨\n"
        f"Sorulan Soru: {relevant_question}\n"
        f"Botun Yanıtı: {bot_answer}\n"
        f"Durum: Bot kullanıcının sorusuna doğrudan cevap vermedi veya lafı dolandırdı."
    )