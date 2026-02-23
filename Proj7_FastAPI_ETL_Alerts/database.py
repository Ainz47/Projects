import os
from dotenv import load_dotenv
from supabase import create_client, Client
from postgrest.exceptions import APIError

load_dotenv()

URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_KEY")

def get_db() -> Client:
    return create_client(URL, KEY)

def get_daily_record(store_id: str, date: str):
    try:
        supabase = get_db()
        response = supabase.table("daily_metrics").select("*").eq("store_id", store_id).eq("date", date).execute()
        if response.data:
            return response.data[0]
    except APIError as e:
        print(f"❌ Supabase Connection Error: {e.message}")
    return None

def upsert_daily_record(payload: dict):
    """Inserts or Updates the record in the database."""
    supabase = get_db()
    
    # Supabase allows us to 'upsert' based on a unique conflict, 
    # but for this MVP, we will just use a simple insert/update approach based on the ID if it exists.
    existing = get_daily_record(payload["store_id"], payload["date"])
    
    if existing:
        # Update existing record
        record_id = existing["id"]
        response = supabase.table("daily_metrics").update(payload).eq("id", record_id).execute()
        print(f"🔄 Updated existing record for {payload['store_id']} on {payload['date']}.")
    else:
        # Insert new record
        response = supabase.table("daily_metrics").insert(payload).execute()
        print(f"📝 Created new record for {payload['store_id']} on {payload['date']}.")
        
    return response.data[0] if response.data else None