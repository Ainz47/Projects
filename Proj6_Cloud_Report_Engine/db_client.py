import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables from the .env file securely
load_dotenv()

# Fetch credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def get_supabase_client() -> Client:
    """Initializes the connection to the PostgreSQL database."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("❌ Missing Supabase credentials. Check your .env file.")
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def save_lead_to_db(lead_info: dict, result_data: dict):
    """Pushes the lead contact info and their scorecard results to the cloud."""
    supabase = get_supabase_client()
    
    # Structure the payload exactly how your Supabase columns are named
    payload = {
        "business_name": lead_info["business_name"],
        "email": lead_info["email"],
        "score": result_data["final_score"],
        "tier": result_data["tier"]
    }
    
    print("☁️ Pushing data to Supabase PostgreSQL...")
    
    # Insert data into the 'leads' table
    try:
        response = supabase.table("leads").insert(payload).execute()
        print("✅ Data successfully saved to the cloud database!")
        return response
    except Exception as e:
        print(f"⚠️ Database Error: {e}")
        return None

# Quick local test (only runs if you execute db_client.py directly)
if __name__ == "__main__":
    test_lead = {"business_name": "Test Engineering", "email": "test@example.com"}
    test_results = {"final_score": 85, "tier": "Dominant"}
    save_lead_to_db(test_lead, test_results)