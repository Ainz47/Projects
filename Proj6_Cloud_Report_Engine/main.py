import json
from engine import calculate_dominance
from pdf_generator import generate_pdf
from db_client import save_lead_to_db

def load_mock_payload():
    """Simulates an incoming JSON webhook from the frontend SPA."""
    return {
        "lead_info": {
            "name": "Jhurald Lantap",
            "business_name": "Apex Engineering Group",
            "email": "jhurald1@example.com",
            "city": "Davao City"
        },
        "scores": {
            "local_seo": 12,
            "paid_ads": 10,
            "website_speed": 22,
            "reputation": 18
        }
    }

def run_pipeline():
    print("🚀 Starting Cloud Report Engine Pipeline...")
    
    # 1. Ingest
    raw_payload = load_mock_payload()
    lead_info = raw_payload["lead_info"]
    
    # 2. Process / Score
    print("⚙️ Processing rules engine...")
    results = calculate_dominance(raw_payload)
    
    # 3. Save to Cloud Database (Supabase)
    print("☁️ Pushing data to Supabase PostgreSQL...")
    try:
        save_lead_to_db(lead_info, results)
        print("✅ Data saved successfully.")
    except Exception as e:
        print(f"⚠️ Could not save to DB (Check Supabase credentials): {e}")
    
    # 4. Generate Asset
    print("🎨 Rendering high-fidelity PDF...")
    generate_pdf(lead_info, results)
    
    print("🏁 Pipeline execution complete.")

if __name__ == "__main__":
    run_pipeline()