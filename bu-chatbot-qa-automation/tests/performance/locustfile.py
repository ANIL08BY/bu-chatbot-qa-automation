from locust import HttpUser, task, between
import json

class ChatbotLoadTest(HttpUser):
    """
    Sistemin /ask uç noktasına dakikada 50 istek hız sınırını (Rate Limit) 
    ve eşzamanlı yük dayanıklılığını test eden Locust sınıfı.
    """
    # Her bir simüle edilmiş kullanıcının istekler arası bekleme süresi (1-3 saniye)
    wait_time = between(1, 3)
    
    @task
    def ask_question_load(self):
        payload = {
            "question": "Belek Üniversitesi Yazılım Mühendisliği bölümü nerede?",
            "history": []
        }
        headers = {'Content-Type': 'application/json'}
        
        # catch_response=True ile HTTP 429'u (Hız Sınırı Aşımı) hata değil, beklenen başarı olarak işaretliyoruz.
        with self.client.post("/ask", json=payload, headers=headers, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:
                # 429 Too Many Requests -> Sistem rate limit'i doğru uyguluyor, kendini koruyor.
                response.success()
            else:
                response.failure(f"Beklenmeyen Sunucu Hatası (Çökme): Status {response.status_code}")