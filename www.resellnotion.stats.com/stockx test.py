import requests
import json
import os

WEBHOOK_URL = "https://discord.com/api/webhooks/1295752816190820443/MoTM9SNjrSP5mtVEBLCs9_hpbaslpZExNyb-iSYwEdFRAZOg-vbO8KsqeUfXaZaNPh6U"

# Paths to your local assets
logo_path = r"C:\Users\bidar\PycharmProjects\resell notion stat\www.resellnotion.stats.com\static\logo.png"
dashboard_path = r"C:\Users\bidar\PycharmProjects\resell notion stat\www.resellnotion.stats.com\static\dashboard.png"
graph_path = r"C:\Users\bidar\PycharmProjects\resell notion stat\www.resellnotion.stats.com\static\graph.png"
stat_path = r"C:\Users\bidar\PycharmProjects\resell notion stat\www.resellnotion.stats.com\static\stat.png"

def get_avatar_url(path):
    """Uploads the logo to a temporary host to get a valid https link for the avatar."""
    try:
        with open(path, 'rb') as f:
            # Using a simple file hosting API (catbox.moe) to get a direct https link
            response = requests.post("https://catbox.moe/user/api.php", data={'reqtype': 'fileupload'}, files={'fileToUpload': f})
            return response.text if response.status_code == 200 else None
    except Exception:
        return None

avatar_link = get_avatar_url(logo_path)

# Prepare the dashboard and graph as attachments for the embeds
files = {
    "file2": ("graph.png", open(graph_path, "rb")),
    "file3": ("stat.png", open(stat_path, "rb"))
}

payload = {
    "username": "Resell Notion 2026",
    "avatar_url": avatar_link, # This is now a valid https link
    "embeds": [
        {
            "title": "🚀 Resell Notion 2026",
            "description": "Stop guessing. With Resell Notion, you can manage your stock, your sales, your logistics, all on an innovative and easy-to-use platform.",
            "color": 8388863,

        },
        {
            "title": "⚡ Professional Workflow & Strategy",
            "description": (
                "• **Full product database** : Over 12.000 products are in our database. You can enter your stock an sales in less than 10 seconds\n"
                "• **Detailed Statistics with AI:** Consult your results with periodics reports and receive some analysis by our own AI.\n"
                "• **Centralize Parcel Tracker:** You can track your parcel when you want to see how much money is stuck in transit "
            ),
            "color": 8388863,
            "thumbnail": {"url": "attachment://graph.png"}
        },
        {
            "title": "🔄 Seamless Migration",
            "description": "If you are using an Excel spreasheet, there is a feature that allow you to transfer your Excel file to the website almost automatically.",
            "color": 8388863
        },
        {
            "title": "🤝 Official Store Partnership",
            "description": (
                "**Price:** 9.99€/month\n\n"
                "**Free trial:** We offer you 2 free days with no obligations !\n\n"
                "**Exclusive:** Use code **OFFICIALSTORE10** for 10% OFF your first month!\n\n"
                "🔗 **[JOIN ON WHOP](https://whop.com/resell-notion/resell-notion/)**"


            ),
            "image": {"url": "attachment://stat.png"},

            "color": 16744448  # Orange
        }
    ]
}

response = requests.post(WEBHOOK_URL, data={"payload_json": json.dumps(payload)}, files=files)

if response.status_code in [200, 204]:
    print(f"Success! Avatar set to: {avatar_link}")
else:
    print(f"Error: {response.status_code}, {response.text}")