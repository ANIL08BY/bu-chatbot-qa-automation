import pytest

def test_empty_message_validation(page):
    """FR.15: Boş mesaj gönderimi engellenmelidir."""
    
    # Testin başlayacağı ana sayfaya (Chatbot arayüzüne) git.
    page.goto("http://localhost:5173")
    
    # Ekranda etkileşime girilecek HTML elementlerini bul.
    # Not: 'aria-label' kullanmak, erişilebilirlik (accessibility) ve sayfa tasarımı değişse bile testin kırılmasını engeller (sağlam seçicilerdir).
    input_area = page.locator("textarea[aria-label='Soru girin']")
    send_button = page.locator("button[aria-label='Mesaj gönder']")
    
    # ASSERTION (Doğrulama) Aşaması:
    # Sayfa ilk açıldığında (mesaj kutusu boşken), gönder butonunun tıklanamaz (disabled) 
    # durumda olup olmadığını kontrol et. Eğer aktifse test hata mesajıyla çöker.
    assert send_button.is_disabled(), "Hata: Kutu boş olmasına rağmen gönder butonu aktif!"

def test_input_resizing(page):
    """FR.17: Giriş alanı yazılan metne göre genişlemelidir."""
    
    # Test ortamını hazırlamak için tekrar ana sayfaya git.
    page.goto("http://localhost:5173")
    
    # Mesaj yazdığımız text alanını (textarea) bul.
    input_area = page.locator("textarea[aria-label='Soru girin']")
    
    # 1. DURUM TESPİTİ: Kutu boşken ekranda ne kadar piksel (height) yer kapladığını ölç.
    # bounding_box() fonksiyonu, elementin ekrandaki x, y, genişlik ve yükseklik değerlerini verir.
    initial_height = input_area.bounding_box()['height']
    
    # 2. ETKİLEŞİM: Kutuya klavyeden yazıyormuş gibi çok satırlı bir metin gönder.
    # '\n' karakteri klavyedeki 'Enter' tuşunu (yeni satıra geçmeyi) simüle eder.
    input_area.fill("Satır 1\nSatır 2\nSatır 3")
    
    # 3. YENİ DURUM TESPİTİ: Metin girildikten sonra kutunun yeni yüksekliğini ölç.
    expanded_height = input_area.bounding_box()['height']
    
    # ASSERTION (Doğrulama) Aşaması:
    # Yeni yüksekliğin, eski yükseklikten daha büyük olduğunu doğrular.
    # Bu sayede frontend'deki 'otomatik boyutlandırma' (auto-resize) CSS/JS kodlarının çalıştığını kanıtlarız.
    assert expanded_height > initial_height, "Hata: Metin girilmesine rağmen Input alanı otomatik genişlemedi!"