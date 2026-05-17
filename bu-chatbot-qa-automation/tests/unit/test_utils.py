"""
Amaç: 
  Sistemin genel (Utility) fonksiyonlarını izole bir şekilde test eder. 
  Girdi temizleme (Sanitization) ve Veritabanı DSN oluşturucu gibi 
  yardımcı araçların dış bağımlılık olmadan doğru mantıkla çalıştığı doğrulanır.
"""

import os
from unittest.mock import patch
from backend.main import _sanitize_input, _build_dsn

# ==============================================================================
# BÖLÜM 1: GİRDİ SANİTİZASYONU (INPUT SANITIZATION)
# ==============================================================================
class TestInputSanitization:
    
    def test_removes_control_characters(self):
        """
        Kötü niyetli veya hatalı kopyalanmış görünmez ASCII kontrol karakterlerinin 
        (\x00, \x08 vb.) metinden başarıyla temizlendiğini doğrular (FR.15).
        """
        dirty_text = "Merhaba\x00Dünya\x08!"
        clean_text = _sanitize_input(dirty_text)
        assert clean_text == "MerhabaDünya!"

    def test_strips_whitespaces(self):
        """
        Metnin başındaki ve sonundaki gereksiz boşlukların temizlendiğini doğrular.
        """
        text_with_spaces = "   Burslar ne zaman yatar?   "
        assert _sanitize_input(text_with_spaces) == "Burslar ne zaman yatar?"

    def test_normal_text_unaffected(self):
        """
        Temiz ve normal bir metnin fonksiyondan bozulmadan çıktığını teyit eder.
        """
        normal_text = "Mezuniyet şartları nelerdir?"
        assert _sanitize_input(normal_text) == normal_text


# ==============================================================================
# BÖLÜM 2: VERİTABANI BAĞLANTI METNİ (DSN) OLUŞTURUCU
# ==============================================================================
class TestDSNBuilder:
    
    @patch.dict(os.environ, {
        "DB_HOST": "localhost",
        "DB_PORT": "5432",
        "DB_NAME": "belek_test",
        "DB_USER": "admin",
        "DB_PASSWORD": "secret_password"
    }, clear=True)
    def test_build_dsn_success(self):
        """
        Ortam değişkenleri (Environment Variables) tam verildiğinde, 
        doğru PostgreSQL URL (DSN) formatının üretildiğini doğrular.
        """
        expected_dsn = "postgresql://admin:secret_password@localhost:5432/belek_test"
        assert _build_dsn() == expected_dsn

    @patch.dict(os.environ, {
        "DB_HOST": "localhost",
        "DB_PORT": "5432",
        # Eksik değişkenler simüle ediliyor (Kullanıcı adı ve şifre yok)
    }, clear=True)
    def test_build_dsn_missing_vars(self):
        """
        Ortam değişkenlerinden herhangi biri eksik olduğunda sistemin çökmediğini,
        sadece boş string ("") dönerek DB bağlantısını güvenlice devre dışı bıraktığını test eder.
        """
        assert _build_dsn() == ""

    @patch.dict(os.environ, {
        "DB_HOST": "localhost",
        "DB_PORT": "5432",
        "DB_NAME": "belek_test",
        "DB_USER": "admin@user",
        "DB_PASSWORD": "p@ssword!"
    }, clear=True)
    def test_build_dsn_url_encoding(self):
        """
        Veritabanı şifresinde veya kullanıcı adında URL'i bozabilecek özel karakterler 
        (Örn: @, !) varsa, bunların (quote_plus ile) doğru şekilde encode edildiğini doğrular.
        """
        dsn = _build_dsn()
        # "admin@user" url içinde "admin%40user" olarak encode edilmeli
        assert "admin%40user" in dsn
        # "p@ssword!" url içinde "p%40ssword%21" olarak encode edilmeli
        assert "p%40ssword%21" in dsn