import requests
import threading
import random
import string
import time

BASE = "http://127.0.0.1:8000"

def random_string(n=8):
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(n))

def create_user_session():
    s = requests.Session()

    email = f"test_{random_string()}@test.com"
    password = "Test123!"

    # REGISTRAZIONE CANTINA (adatta endpoint se diverso)
    s.post(f"{BASE}/register", data={
        "email": email,
        "password": password,
        "name": "Cantina Test"
    })

    # LOGIN
    s.post(f"{BASE}/login", data={
        "email": email,
        "password": password
    })

    # ACQUISTA CREDITI (manual)
    s.post(f"{BASE}/app/billing/buy", data={
        "credits": 10,
        "price": 19
    })

    # CREA LOTTO
    s.post(f"{BASE}/app/new-wine", data={
        "winery_id": 1,
        "wine_name": "VinoStress",
        "volume_ml": 750
    })

    print("OK:", email)

threads = []

for _ in range(20):  # 20 utenti concorrenti
    t = threading.Thread(target=create_user_session)
    t.start()
    threads.append(t)

for t in threads:
    t.join()

print("Stress test completato")
