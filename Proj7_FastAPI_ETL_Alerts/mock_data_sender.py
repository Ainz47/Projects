import requests
import time

BASE_URL = "http://127.0.0.1:8000"

print("🚀 Simulating Toast POS sending daily sales data...")
sales_payload = {
    "store_id": "Store_104",
    "date": "2026-02-24",
    "gross_sales": 5000.00
}
# Capture the response
response_sales = requests.post(f"{BASE_URL}/webhook/sales", json=sales_payload)
print(f"📡 Server Response: HTTP {response_sales.status_code} -> {response_sales.text}\n")

print("⏳ Waiting 3 seconds (simulating delay between systems)...")
time.sleep(3)

print("🚀 Simulating 7shifts sending daily labor data...")
labor_payload = {
    "store_id": "Store_104",
    "date": "2026-02-24",
    "labor_hours": 75.0,
    "labor_cost": 1500.00
}
# Capture the response
response_labor = requests.post(f"{BASE_URL}/webhook/labor", json=labor_payload)
print(f"📡 Server Response: HTTP {response_labor.status_code} -> {response_labor.text}\n")

# Error Verification Logic
if response_sales.status_code == 200 and response_labor.status_code == 200:
    print("✅ Webhooks successfully processed! Check your Discord for alerts!")
else:
    print("❌ Webhook failed. The server crashed. Check the Uvicorn terminal for the traceback.")