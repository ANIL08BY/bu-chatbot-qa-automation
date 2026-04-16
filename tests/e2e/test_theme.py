import re
from playwright.sync_api import expect, Page

def test_theme_persistence(page: Page):
    """FR.18: Tema desteği ve kalıcılığını doğrular."""
    page.goto("http://localhost:5173")
    
    # 1. Adım: Ayarlar menüsünü aç
    settings_button = page.locator("button[aria-label='Ayarlar']")
    settings_button.click()
    
    theme_toggle = page.locator("button[aria-label='Tema değiştir']")
    modal_dialog = page.locator("div[role='dialog']")
    
    # Tema düğmesinin ilk halini bul ("false" ya da "true" olacak)
    initial_checked = theme_toggle.get_attribute("aria-checked")
    
    # Temaya tıkla, yani bu durum tam tersine dönecek
    target_checked = "true" if initial_checked == "false" else "false"
    
    # 2. Adım: Temayı değiştirmek için butona tıkla
    theme_toggle.click()
    
    # 3. Adım: Statik `time.sleep` gibi beklemelere ihtiyaç kalmadan DOM'da değişim gerçekleşene 
    # kadar bekler. Bu yöntem "AssertionError" gibi hata atımlarının önüne geçer.
    expect(theme_toggle).to_have_attribute("aria-checked", target_checked)
    
    # 4. Adım (İsteğe Bağlı CSS Kontrolü): 
    # HTML tagı yerine bileşenin doğrudan class'ını teyit et.
    if target_checked == "true":
        # Eğer Karanlık mod aktifse div '#1e1e1e' arkaplanına geçer.
        expect(modal_dialog).to_have_class(re.compile(r"bg-\[#1e1e1e\]"))
    else:
        expect(modal_dialog).to_have_class(re.compile(r"bg-white"))
    
    # ------------------
    # 5. Adım: Kalıcılık (Persistence) Kontrolü (İsim Gereği)
    # Temanın değişip değişmediğini doğrulamak için sayfayı F5 (yenileme) yap 
    # Eğer uygulamanız localStorage/cookie temelliyse seçilen mod kaybolmamalıdır!
    # ------------------
    page.reload()
    
    # Sayfa yenilendikten sonra menüyü tekrar aç
    page.locator("button[aria-label='Ayarlar']").click()
    persisted_theme_toggle = page.locator("button[aria-label='Tema değiştir']")
    
    # Son teyit: Seçilen/tıklanan son değer ekranda sayfayı yenilemeye rağmen korundu mu?
    expect(persisted_theme_toggle).to_have_attribute("aria-checked", target_checked)

    # 6. Adım: Testi temiz bitirmek için kapat
    close_button = page.locator("button[aria-label='Kapat']")
    close_button.click()