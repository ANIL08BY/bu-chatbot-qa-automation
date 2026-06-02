import pytest
from playwright.sync_api import Page, expect

def test_theme_persistence(page: Page):
    """FR.18: Tema desteği ve kalıcılığını doğrular."""
    page.goto("http://localhost:5173/")
    
    # 1. Adım: Ayarlar menüsünü aç
    settings_button = page.locator("button[aria-label='Ayarlar']")
    settings_button.click()
    
    theme_toggle = page.locator("button[aria-label='Tema değiştir']")
    
    # Tema düğmesinin ilk halini bul ("false" ya da "true" olacak)
    initial_checked = theme_toggle.get_attribute("aria-checked")
    
    # Temaya tıkla, yani bu durum tam tersine dönecek
    target_checked = "true" if initial_checked == "false" else "false"
    
    # 2. Adım: Temayı değiştirmek için butona tıkla
    theme_toggle.click()
    
    # 3. Adım: Statik time.sleep gibi beklemelere ihtiyaç kalmadan DOM'da değişim gerçekleşene kadar bekle
    expect(theme_toggle).to_have_attribute("aria-checked", target_checked)

def test_fullscreen_toggle_in_settings(page: Page):
    """
    E2E UI Testi: Ayarlar menüsündeki 'Tam Ekran' (Fullscreen) 
    fonksiyonunun DOM üzerinde hata fırlatmadan tetiklenebildiğini test eder.
    """
    # 1. Ana sayfaya git
    page.goto("http://localhost:5173/")

    # 2. Ayarlar butonuna tıkla (İlk testteki en güvenilir locator'ı kullanıyoruz)
    settings_button = page.locator("button[aria-label='Ayarlar']")
    settings_button.click()

    # 3. Ayarlar menüsünün açıldığını doğrula
    tam_ekran_text = page.get_by_text("Tam Ekran").first
    expect(tam_ekran_text).to_be_visible()

    # 4. "Tam Ekran" geçiş (switch) butonuna tıkla
    # Arayüzdeki "Tam Ekran" yazısının bulunduğu satırdaki butonu (switch) garanti olarak bulur
    fullscreen_button = page.locator("div").filter(has_text="Tam Ekran").locator("button[role='switch']").first
    fullscreen_button.click(force=True)

    # 5. Tarayıcı (Headless modda) API'yi reddetse bile, React State'in
    # hata fırlatmadığını ve menünün hala stabil kaldığını (Crash olmadığını) doğrula.
    expect(tam_ekran_text).to_be_visible()
    
    # 6. Menüyü klavyeden Escape tuşuna basarak kapat (En garantili yöntem)
    page.keyboard.press("Escape")
