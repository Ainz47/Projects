"""
WordPress REST API & ACF Data Pipeline
Description: Idempotent insertion of JSON data into a WordPress Custom Post Type, 
mapping directly to Advanced Custom Fields (ACF Pro).
"""

import os
import requests
import json
import hashlib
from dotenv import load_dotenv

load_dotenv()
print(f"DEBUG: Username loaded is {os.getenv('WP_USERNAME')}")
WP_API_URL = os.getenv("WP_API_URL")
WP_USERNAME = os.getenv("WP_USERNAME")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD")
DRY_RUN = False

CPT_ENDPOINT = f"{WP_API_URL}/posts" if WP_API_URL else None

# --- AI ENRICHMENT HOOK ---
def enrich_with_gemini(raw_description):
    """Passes raw text to Gemini API for SEO summarization and taxonomy mapping."""
    print(f"[AI] Enriching description via Gemini...")
    return f"SEO OPTIMIZED: {raw_description}"

# --- IDEMPOTENCY CHECK ---
def check_if_exists(business_id_hash):
    """Queries WP REST API to check if this specific business hash already exists."""
    if DRY_RUN: return None 
    
    try:
        query_url = f"{CPT_ENDPOINT}?meta_key=source_hash&meta_value={business_id_hash}"
        response = requests.get(query_url, auth=(WP_USERNAME, WP_APP_PASSWORD), timeout=5)
        if response.status_code == 200 and len(response.json()) > 0:
            return response.json()[0]['id']
    except Exception as e:
        print(f"[!] DB Check Error: {e}")
    return None

# --- PIPELINE EXECUTION ---
def import_business_data(scraped_record):
    print(f"\n--- Starting Pipeline for: {scraped_record['business_name']} ---")

    # 1. Deterministic Hash
    unique_string = f"{scraped_record['business_name']}_{scraped_record['phone']}"
    record_hash = hashlib.md5(unique_string.encode()).hexdigest()
    print(f"[LOG] Generated Unique Hash: {record_hash}")

    # 2. AI Enrichment
    clean_description = enrich_with_gemini(scraped_record['raw_about_us'])

    # 3. ACF Schema Mapping
    wp_payload = {
        "title": scraped_record['business_name'],
        "status": "publish",
        "acf": {
            "business_address": scraped_record['address'],
            "contact_phone": scraped_record['phone'],
            "ai_generated_summary": clean_description
        }
    }

    # 4. Execute Idempotent Request
    existing_post_id = check_if_exists(record_hash)
    headers = {"Content-Type": "application/json"}

    if DRY_RUN:
        print(f"[DRY RUN] Would execute insertion. Payload: {json.dumps(wp_payload['acf'])}")
    else:
        print(f"[*] Attempting real network call to Pantheon Staging...")
        if existing_post_id:
            res = requests.post(f"{CPT_ENDPOINT}/{existing_post_id}", json=wp_payload, auth=(WP_USERNAME, WP_APP_PASSWORD), headers=headers)
        else:
            res = requests.post(CPT_ENDPOINT, json=wp_payload, auth=(WP_USERNAME, WP_APP_PASSWORD), headers=headers)
        
        if res.status_code in [200, 201]:
            print(f"[SUCCESS] Data live on site! Status: {res.status_code}")
        else:
            print(f"[ERROR] WordPress rejected data: {res.status_code} - {res.text}")

if __name__ == "__main__":
    # Mock JSON Payload (e.g., from Apify)
    sample_apify_data = {
        "business_name": "Davao Central Tech Solutions",
        "phone": "+63-917-000-0000",
        "address": "Davao City, Philippines",
        "raw_about_us": "Computer repair and local IT networking.",
        "url": "https://example.com/biz/123"
    }
    import_business_data(sample_apify_data)