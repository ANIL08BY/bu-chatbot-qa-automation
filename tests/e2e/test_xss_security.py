import pytest
from playwright.sync_api import expect

def test_xss_vulnerability_in_ui(page):
    """
    Siber Güvenlik Testi: Cross-Site Scripting (XSS) Arayüz Koruması.
    Kullanıcının gönderdiği zararlı Javascript kodlarının frontend (React) 
    tarafından çalıştırılmayıp (sanitize edilip), düz metin olarak işlendiğini doğrular.
    """
    # 1. Frontend arayüzünüze git (Uygulama genelde 5173'te çalışır)
    page.goto("http://localhost:5173") 
    
    # 2. Tarayıcıda bir "Alert (Uyarı) Kutusu" çıkarsa bunu yakalayacak dinleyici (Listener)
    xss_tetiklendi = False
    
    def dialog_handler(dialog):
        nonlocal xss_tetiklendi
        xss_tetiklendi = True # Eğer kod çalışıp dialog açılırsa burası True olur!
        dialog.accept()

    page.on("dialog", dialog_handler)
    
    # 3. Klasik bir XSS zararlı kodu (Payload)
    xss_payload = "<script>alert('SİSTEM HACKLENDİ')</script><img src='x' onerror='alert(\"XSS\")'>"
    
    # 4. Arayüzdeki sohbet giriş kutusuna zararlı kodu yaz
    chat_input = page.locator("textarea, input[type='text']").first
    chat_input.fill(xss_payload)
    
    # Gönder butonuna tıkla (Playwright genelde Enter tuşunu da simüle edebilir)
    chat_input.press("Enter")
    
    # DOM'un güncellenmesi için çok kısa bir bekleme
    page.wait_for_timeout(1000) 
    
    # 5. KONTROL 
    # XSS kodu çalıştı mı? (Alert kutusu ekrana çıktı mı?)
    assert not xss_tetiklendi, "🚨 XSS AÇIĞI: React, zararlı Javascript kodunun tarayıcıda çalışmasına izin verdi!"