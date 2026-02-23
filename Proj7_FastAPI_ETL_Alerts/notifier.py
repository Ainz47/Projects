import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# We will put this in your .env file shortly
WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL")

def send_labor_alert(store_id: str, date: str, labor_pct: float, cplh: float):
    """Triggers an alert if labor metrics exceed profitable thresholds."""
    
    if not WEBHOOK_URL:
        print("⚠️ No Webhook URL found in .env. Skipping alert.")
        return

    # Formatting the payload for Discord/Slack
    payload = {
        "content": (
            f"🚨 **HIGH LABOR COST ALERT: {store_id}** 🚨\n"
            f"📅 **Date:** {date}\n"
            f"📈 **Labor %:** {labor_pct}%\n"
            f"🕒 **CPLH (Cost Per Labor Hour):** ${cplh}\n"
            f"⚠️ *Action Required: Review 7shifts scheduling immediately.*"
        )
    }

    print(f"🔔 Firing alert to Operations Team for {store_id}...")
    
    response = requests.post(WEBHOOK_URL, json=payload)
    
    if response.status_code == 204 or response.status_code == 200:
        print("✅ Alert successfully delivered!")
    else:
        print(f"❌ Failed to send alert. Status Code: {response.status_code}")

# Quick local test (only runs if you execute this file directly)
if __name__ == "__main__":
    send_labor_alert("Store_104", "2026-02-23", 28.5, 22.50)