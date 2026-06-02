import pytest
from playwright.sync_api import Page, expect

def test_accessibility_aria_labels(page: Page):
    """
    Kullanıcının etkileşime gireceği tüm alanlarda screen-reader (ekran okuyucu) 
    desteğinin ('aria-label') bulunduğunu doğrular. (SRS NFR.07 ve FR.17 uyumluluğu)
    """
    page.goto("http://localhost:5173") # Frontend (Vite) default adresi

    # 1. ChatInput.tsx kontrolleri
    textarea = page.locator("textarea[aria-label='Soru girin']")
    send_btn = page.locator("button[aria-label='Mesaj gönder']")
    
    expect(textarea).to_be_visible()
    expect(textarea).to_be_empty()
    expect(send_btn).to_be_visible()
    # Gönder butonu başlangıçta inaktif(disabled) olmalı
    expect(send_btn).to_be_disabled()

    # 2. ChatHeader.tsx kontrolleri
    new_chat_btn = page.locator("button[aria-label='Yeni sohbet başlat']")
    settings_btn = page.locator("button[aria-label='Ayarlar']")
    
    expect(new_chat_btn).to_be_visible()
    expect(settings_btn).to_be_visible()

def test_decorative_elements_aria_hidden(page: Page):
    """
    Salt dekoratif ikonların (Gönder butonu içindeki Send, Yeni Sohbet butonu içindeki Plus vb.)
    ekran okuyucularda gürültü yapmaması için aria-hidden="true" aldığını test eder.
    """
    page.goto("http://localhost:5173")
    
    # Gönder butonunun içindeki ikon (Send lucide-react componenti)
    send_icon = page.locator("button[aria-label='Mesaj gönder'] svg[aria-hidden='true']")
    expect(send_icon).to_be_visible()