import requests
import json
import random
import urllib.parse
import os
import time


def get_random_proxy():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    proxy_path = os.path.join(current_dir, 'static', 'proxy_tracker.txt')
    with open(proxy_path, 'r') as f:
        lines = [l.strip() for l in f.readlines() if l.strip()]
    line = random.choice(lines)
    host, port, user, password = line.split(':')
    return f"http://{urllib.parse.quote(user)}:{urllib.parse.quote(password)}@{host}:{port}"


def debug_full_response(tracking_number):
    session = requests.Session()
    session.proxies = {"http": get_random_proxy(), "https": get_random_proxy()}

    headers = {
        'authority': 'api.ordertracker.com',
        'accept': 'application/json, text/plain, */*',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36',
        'referer': 'https://www.ordertracker.com/',
        'origin': 'https://www.ordertracker.com',
        'accept-language': 'fr-FR,fr;q=0.9',
        'content-type': 'application/json'
    }

    try:
        # Séquence de confiance
        url_html = f"https://www.ordertracker.com/fr/track/{tracking_number}"
        session.get(url_html, headers=headers, timeout=20)
        time.sleep(1)

        session.get(f"https://api.ordertracker.com/public/trackinglinks?trackingstring={tracking_number}",
                    headers=headers, timeout=20)
        time.sleep(1)

        url_final = f"https://api.ordertracker.com/public/track/{tracking_number}?lang=FR"
        response = session.get(url_final, headers=headers, timeout=20)

        if response.status_code == 200:
            data = response.json()
            print("\n--- STRUCTURE JSON REÇUE ---")
            # On affiche tout pour trouver la bonne clé
            print(json.dumps(data, indent=4, ensure_ascii=False))
            return "Analyse terminée"
        else:
            print(f"Erreur {response.status_code}")
    except Exception as e:
        print(f"Erreur : {e}")


debug_full_response("XW305613635TS")