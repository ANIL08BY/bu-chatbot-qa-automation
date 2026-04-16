import pytest
from playwright.sync_api import sync_playwright

# @pytest.fixture(scope="session"): Bu ayar, tarayıcının her testte tekrar tekrar açılıp kapanmasını engeller.
# "session" (oturum) seviyesinde olduğu için tüm test paketi koşumu boyunca tarayıcı ana motoru sadece BİR KERE açılır. 
# Bu yapı, testlerin çalışma süresini hızlandırır.
@pytest.fixture(scope="session")
def browser_context():
    """Playwright tarayıcı oturumunu başlatır ve yapılandırır."""
    
    # sync_playwright() ile Playwright'ın senkron (eşzamanlı) API'sini başlat.
    with sync_playwright() as p:
        
        # Chromium (Chrome/Edge altyapısı) tarayıcısını başlat. 
        # headless=False ayarı, testler koşulurken tarayıcı penceresini ekranda canlı olarak görmemizi sağlar. 
        # (CI/CD süreçlerinde veya arka plan testlerinde bu değer True yapılır).
        browser = p.chromium.launch(headless=False)
        
        # Tarayıcı içinde yeni bir "bağlam" (context) oluşturuyoruz. 
        # Context, sanki "Gizli Sekme" açmışız gibi çerezlerin (cookies) ve önbelleğin (cache) izole tutulduğu alandır.
        context = browser.new_context()
        
        # yield komutu, oluşturduğumuz bu context'i test fonksiyonlarının kullanımına sunar. 
        # Testler bitene kadar Python kodu tam bu satırda bekler (duraklar).
        yield context
        
        # Tüm test senaryoları bittikten sonra kaynakları tüketmemek için tarayıcıyı temiz bir şekilde kapat.
        browser.close()


# scope belirtilmediği için varsayılan olarak "function" (fonksiyon) seviyesinde.
# Yani bu blok, her bir test fonksiyonu (örn: test_theme, test_input) için baştan tetiklenir.
@pytest.fixture
def page(browser_context):
    """Her test senaryosu için tamamen izole yeni bir sayfa (sekme) açar."""
    
    # Yukarıdaki session seviyesindeki browser_context'i kullanarak yeni ve temiz bir sekme (page) aç.
    # Bu sayede testler birbirinin verisine, tıklamasına veya oturumuna müdahale edemez. Her test sıfırdan başlar.
    page = browser_context.new_page()
    
    # Açılan bu sekmeyi (page nesnesini) test fonksiyonunun içine gönder.
    yield page
    
    # Test fonksiyonu işini bitirdiğinde (test geçse de, çökse de) bu sekmeyi anında kapat.
    page.close()