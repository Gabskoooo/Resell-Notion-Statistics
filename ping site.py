import requests
import time
from datetime import datetime

# L'URL de votre service Render
RENDER_SERVICE_URL = "https://resell-notion-statistics.onrender.com" # Remplacez par l'URL de votre service

def ping_service():
    try:
        response = requests.get(RENDER_SERVICE_URL)
        print(f"[{datetime.now()}] Pingé {RENDER_SERVICE_URL} - Statut : {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now()}] Erreur lors du ping de {RENDER_SERVICE_URL} : {e}")

if __name__ == "__main__":
    while True:
        ping_service()
        # Attendre 2 minutes (120 secondes) avant le prochain ping
        time.sleep(120)