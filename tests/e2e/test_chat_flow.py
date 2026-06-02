import pytest
from playwright.sync_api import Page, expect

def test_basic_chat_flow_happy_path(page: Page):
    """
    Kullanıcının standart bir soru sorduğu ve botun sorunsuz bir şekilde
    cevap döndüğü "Mutlu Yol" (Happy Path) E2E senaryosudur. (US.04)
    """
    # 1. API İsteklerini Dinle ve Sahte(Mock) Cevap Dön
    def handle_ask(route):
        route.fulfill(
            status=200,
            json={
                "answer": "Yazılım Mühendisliği bölümünde eğitim görmektesiniz.",
                "sources":[],
                "category": "Ogrenci Isleri",
                "engine": "v2"
            }
        )

    # UI "/ask" isteği atmaya kalktığında handle_ask fonksiyonunu tetikle
    page.route("**/ask", handle_ask)

    # 2. Arayüze git
    page.goto("http://localhost:5173")

    textarea = page.locator("textarea[aria-label='Soru girin']")
    send_button = page.locator("button[aria-label='Mesaj gönder']")

    # 3. Mesajı gir ve gönder
    user_message = "Hangi bölümde okuyorum?"
    textarea.fill(user_message)
    send_button.click()

    # 4. Doğrulamalar (Assertions)
    # A. Kullanıcının girdiği mesaj, sağa hizalı balonda görünüyor mu?
    # Kullanıcı mesajları <p> etiketi ile render ediliyordu
    user_bubble = page.locator("p", has_text=user_message)
    expect(user_bubble).to_be_visible()

    # B. Textarea gönderimden sonra temizlenmiş mi?
    expect(textarea).to_be_empty()

    # C. Bot cevabı arayüzde ekrana (.prose classı içine) düştü mü?
    bot_response = page.locator(".prose", has_text="Yazılım Mühendisliği bölümünde eğitim görmektesiniz.")
    expect(bot_response).to_be_visible()


def test_chat_error_and_retry_flow(page: Page):
    """
    Sistemin (veya API'nin) geçici bir HTTP 500 veya 504 hatası verdiğinde, 
    Kullanıcı UI'ında 'Tekrar Dene' butonunun çıkması ve butona tıklandığında
    sürecin başarıyla tekrarlanması senaryosu.
    """
    # Önlem: API her istek attığında önce bir HATA döndür, sonra düzeltmek için global olmayan, scope içi bir sayaç tut.
    call_count = 0

    def handle_retry_route(route):
        nonlocal call_count
        call_count += 1
        
        if call_count == 1:
            # İlk istekte 503 Servis Yok hatası
            route.fulfill(status=503, body="Servis çöktü")
        else:
            # İkinci istekte (Kullanıcı tekrar dene dediğinde) başarılı ol
            route.fulfill(
                status=200,
                json={"answer": "Bağlantı tekrar sağlandı!", "sources":[], "engine": "v2"}
            )

    page.route("**/ask", handle_retry_route)
    page.goto("http://localhost:5173")

    textarea = page.locator("textarea[aria-label='Soru girin']")
    send_button = page.locator("button[aria-label='Mesaj gönder']")

    # 1. Hata alacak soruyu gönder
    textarea.fill("Merhaba, orada mısın?")
    send_button.click()

    # 2. Doğrulama: 'Tekrar Dene' butonu belirdi mi? 
    # ChatMessage bileşenindeki <button> onClick={onRetry}>Tekrar Dene</button> mantığı.
    retry_button = page.get_by_role("button", name="Tekrar Dene")
    expect(retry_button).to_be_visible()

    # 3. İkinci Aşama: Butona tıklayıp tekrar istek atma süreci (Kurtarma Yolu)
    retry_button.click()

    # 4. Son Doğrulama: Tekrar dene butonuna tıklanınca bot başardığı için o buton kaybolur
    # ve başarılı "Bağlantı tekrar sağlandı!" metni UI'a düşer.
    expect(retry_button).not_to_be_visible()
    
    bot_success_response = page.locator(".prose", has_text="Bağlantı tekrar sağlandı!")
    expect(bot_success_response).to_be_visible()