import requests
import json
import os

# --- CONFIGURATION ---
WEBHOOK_URL = "https://discord.com/api/webhooks/1462720943775416411/6PD0278r_8UDyxj8pTQK07-MQVXso3ZFrvWiCkEZy3gg-pdAOjeaiQhPFu0lFRPOxZ47"
URL_SITE = "https://resell-notion-statistics.onrender.com/register"
COLOR_BRAND = 0x2b2d31  # Gris Anthracite Premium

# Chemins locaux pour les images
PATHS = {
    "logo.png": r"C:\Users\bidar\PycharmProjects\resell notion stat\www.resellnotion.stats.com\static\logo.png",
    "dashboard.png": r"C:\Users\bidar\PycharmProjects\resell notion stat\www.resellnotion.stats.com\static\dashboard.png",
    "stats1.png": r"C:\Users\bidar\PycharmProjects\resell notion stat\www.resellnotion.stats.com\static\stats1.png",
    "stats2.png": r"C:\Users\bidar\PycharmProjects\resell notion stat\www.resellnotion.stats.com\static\stats2.png"
}

def send_final_pro_embeds():
    files = {}
    for filename, path in PATHS.items():
        if os.path.exists(path):
            files[filename] = open(path, "rb")
        else:
            print(f"⚠️ Image manquante : {path}")

    # Note : On ne définit plus 'username' ni 'avatar_url' pour utiliser tes réglages Discord
    payload = {
        "embeds": [
            # 1. INTRODUCTION
            {
                "title": "💎 RESELL NOTION : L'ÉLITE DU TRACKING",
                "description": (
                    "Passez d'une gestion amateur à une **maîtrise totale** de votre business.\n"
                    "Une solution conçue par des experts pour les passionnés."
                ),
                "url": URL_SITE,
                "color": COLOR_BRAND,
                "thumbnail": {"url": "attachment://logo.png"},
                "fields": [
                    {"name": "🌐 Plateforme", "value": "Dashboard Cloud", "inline": True},
                    {"name": "🎯 Focus", "value": "Sneakers & Items", "inline": True}
                ]
            },
            # 2. DASHBOARD & STOCK
            {
                "title": "🏛️ VOTRE INFRASTRUCTURE DE GESTION",
                "description": "Pilotez votre activité avec une clarté absolue.",
                "color": COLOR_BRAND,
                "fields": [
                    {
                        "name": "🖥️ Dashboard Global",
                        "value": "Consultez l'état de santé de votre business en un coup d'œil.",
                        "inline": False
                    },
                    {
                        "name": "📦 Gestion d'Inventaire",
                        "value": "Ajout rapide, suivi précis et visibilité totale sur votre stock.",
                        "inline": False
                    }
                ],
                "image": {"url": "attachment://dashboard.png"}
            },
            # 3. VENTES & STATISTIQUES
            {
                "title": "📈 PERFORMANCE & ANALYSE FINANCIÈRE",
                "description": "Transformez chaque donnée en opportunité de profit.",
                "color": COLOR_BRAND,
                "fields": [
                    {
                        "name": "💰 Tracking des Ventes",
                        "value": "Enregistrez vos bénéfices et analysez votre ROI en temps réel.",
                        "inline": True
                    },
                    {
                        "name": "📊 Statistiques Avancées",
                        "value": "Rotation, cashflow et objectifs personnalisés.",
                        "inline": True
                    }
                ],
                "image": {"url": "attachment://stats1.png"}
            },
            # 4. EXPERT IA
            {
                "title": "🤖 L'EXPERTISE IA : VOTRE AVANTAGE DÉCISIF",
                "description": "L'intelligence artificielle au service de votre rentabilité.",
                "color": COLOR_BRAND,
                "fields": [
                    {
                        "name": "🧠 Analyse & Solutions",
                        "value": (
                            "Notre IA scanne vos données pour identifier vos points faibles "
                            "et vous proposer des solutions concrètes pour scaler votre activité."
                        ),
                        "inline": False
                    }
                ],
                "image": {"url": "attachment://stats2.png"},
                "footer": {
                    "text": "Inscrivez-vous maintenant sur resell-notion-statistics.onrender.com",
                    "icon_url": "attachment://logo.png"
                }
            }
        ]
    }

    try:
        response = requests.post(
            WEBHOOK_URL,
            data={"payload_json": json.dumps(payload)},
            files=files
        )
        if response.status_code in [200, 204]:
            print("✅ Présentation envoyée avec ton profil Discord !")
        else:
            print(f"❌ Erreur {response.status_code} : {response.text}")
    finally:
        for f in files.values():
            f.close()

if __name__ == "__main__":
    send_final_pro_embeds()