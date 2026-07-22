import requests
import threading
import time

BASE = "http://127.0.0.1:8000"

EMAIL = "tuo_utente_test@email.com"
PASSWORD = "tua_password"

def worker():
    s = requests.Session()

    # LOGIN
    r = s.post(f"{BASE}/login", data={
        "email": EMAIL,
        "password": PASSWORD
    })

    if r.status_code not in (200, 302):
        print("Login fallito")
        return

    # ACQUISTO CREDITI
    s.post(f"{BASE}/app/billing/buy", data={
        "credits": 10,
        "price": 19
    })

    # CREA 5 LOTTI
    for i in range(5):
        s.post(f"{BASE}/app/new-wine", data={
            "winery_id": 1,
            "wine_name": f"StressWine_{i}",
            "volume_ml": 750
        })

    print("Worker completato")

threads = []

for i in range(20):
    t = threading.Thread(target=worker)
    t.start()
    threads.append(t)

for t in threads:
    t.join()

print("Stress completato")
