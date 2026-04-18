import pytest
from playwright.sync_api import Page, expect

def test_bot_markdown_rendering(page: Page):
    """
    Bot yanıtı geldiğinde ReactMarkdown kütüphanesinin kalın yazıları, italik yazıları, 
    linkleri ve listeleri HTML elementlerine doğru parse edip edemediğini kontrol eder.
    """
    # 1. HAZIRLIK: API henüz yok. FastAPI Backend yerine sahte cevap (Mock Payload) ayarla
    markdown_text = """Bu yanıtta **kalın**, *italik* kelimeler ve [Belek Üniversitesi](https://belek.edu.tr) linki var.
    
* Öğrenci İşleri
* Kütüphane
"""
    
    def handle_api_route(route):
        # /ask isteği gidince gerçek sunucuyu bekleme, JSON'u saniyesinde Frontend de kullan
        route.fulfill(
            status=200,
            json={
                "answer": markdown_text,
                "sources":[],
                "category": "Genel",
                "engine": "v1"
            }
        )

    # Ağ üzerinden gidecek "**/ask" adresli tüm HTTP post işlemlerine el koy
    page.route("**/ask", handle_api_route)
    
    # 2. AKSİYON: Kullanıcı arayüzüne git ve soru gönder
    page.goto("http://localhost:5173")
    
    textarea = page.locator("textarea[aria-label='Soru girin']")
    send_button = page.locator("button[aria-label='Mesaj gönder']")
    
    textarea.fill("Markdown yeteneğini göster!")
    send_button.click()
    
    # 3. DOĞRULAMA (Assertion): Mesaj UI'a yüklendiğinde etiketleri test et
    # ChatMessage.tsx dosyasında class ismi "prose" verildiği için kolayca hedeflenir
    bot_response_area = page.locator(".prose").last
    
    # Strong etiketi (kalın) çevrilmiş mi?
    expect(bot_response_area.locator("strong")).to_have_text("kalın")
    
    # em etiketi (İtalik) çevrilmiş mi?
    expect(bot_response_area.locator("em")).to_have_text("italik")
    
    # a (link) çevrilmiş mi ve yeni sekmede açılıyor mu?
    link = bot_response_area.locator("a")
    expect(link).to_have_text("Belek Üniversitesi")
    expect(link).to_have_attribute("href", "https://belek.edu.tr")
    expect(link).to_have_attribute("target", "_blank")  # Güvenli bağlantı formatı
    
    # Madde listesi (ul -> li) iki öğeye ayrılmış mı?
    list_items = bot_response_area.locator("ul li")
    expect(list_items).to_have_count(2)
    expect(list_items.nth(0)).to_have_text("Öğrenci İşleri")
    expect(list_items.nth(1)).to_have_text("Kütüphane")