import os
import json
import hashlib
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def generate_unique_story(business_name: str, category: str, location: str) -> str:
    """Uses Gemini to generate a high-quality, unique description."""
    print(f"🧠 Asking Gemini to write a story for {business_name}...")
    prompt = f"Write an engaging, premium 2-paragraph directory listing story for a {category} called '{business_name}' located in {location}. Make it sound professional and enticing."
    try:
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return response.text.strip()
    except Exception as e:
        print(f"⚠️ Gemini story generation failed: {e}")
        print("✨ Falling back to default content.")
        return "A premium local destination offering an unforgettable experience."

def process_scraped_data(raw_data: dict) -> dict:
    """Formats the data into the Ivy-Level Naperville Schema."""
    print(f"⚙️ Structuring ACF Data for {raw_data['name']}...")
    
    unique_string = f"{raw_data['name']}_{raw_data['address']}".encode('utf-8')
    place_id = hashlib.md5(unique_string).hexdigest()
    story = generate_unique_story(raw_data['name'], raw_data['category'], raw_data['city'])

    # The Enriched "Ivy-Level" Schema
    enriched_json = {
        "place_id": place_id,
        "title": raw_data["name"],
        "content": story,
        "acf_fields": {
            "business_address": raw_data["address"],
            "business_category": raw_data["category"],
            "amenities": ["Outdoor Seating", "Craft Cocktails", "Farm-to-Table"], # Mocked for Prototype
            "opening_hours": {
                "monday": "Closed",
                "tuesday_thursday": "11:00 AM - 9:00 PM",
                "friday_saturday": "11:00 AM - 10:00 PM",
                "sunday": "11:00 AM - 8:00 PM"
            },
            "gallery_images": raw_data.get("gallery_images", [])
        }
    }
    return enriched_json