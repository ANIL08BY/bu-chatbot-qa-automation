import re
from playwright.sync_api import Page, expect

def test_user_can_submit_positive_feedback(page: Page):
    """
    E2E UI Testi: Kullanıcının bota soru sorup, gelen cevaba 
    'Beğendim' (Thumbs Up) geri bildirimi verebildiğini test eder.
    """
    # 1. Uygulamanın ana sayfasına git (Frontend genelde 5173 portunda çalışır.).
    # Eğer conftest.py içinde base_url ayarlı ise burası sadece "/" yapapılabilir.
    page.goto("http://localhost:5173/") 

    # 2. Bota bir soru sor
    chat_input = page.get_by_role("textbox")
    chat_input.fill("Belek Üniversitesi nerede?")
    chat_input.press("Enter")

    # 3. Botun "Yazıyor..." animasyonunun bitmesini bekle
    expect(page.locator(".animate-bounce").first).not_to_be_visible(timeout=45000)

    # 4. Asistanın verdiği son cevaptaki "Like" (Thumbs Up) butonunu bul
    # Butonu class'ından veya sayfanın en altındaki (en son cevap) buton yapısından bul.
    # App.tsx koduna göre ThumbsUp ikonunun olduğu butonu yakalamak için en güvenli yol
    like_button = page.locator("button svg.lucide-thumbs-up").last.locator("..")

    # 5. KRİTİK NOKTA: Butona basıldığında Frontend'in Backend'e istek atıp atmadığını yakala!
    with page.expect_response(lambda response: "/feedback" in response.url and response.request.method == "POST") as response_info:
        like_button.click(force=True)

    # 6. KONTROLLER
    feedback_response = response_info.value
    
    # API isteği başarılı döndü mü?
    assert feedback_response.status == 200, "Frontend, backend'e feedback isteğini iletemedi veya API çöktü!"