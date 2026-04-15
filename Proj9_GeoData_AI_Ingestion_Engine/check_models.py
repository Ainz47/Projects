import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

print("📡 Fetching available models for your API key...")
print("-" * 60)

try:
    models = client.models.list()
    for m in models:
        # We print the name and the capabilities we care about
        # In this SDK, capabilities are often in 'supported_methods' or 'capabilities'
        name = getattr(m, 'name', 'Unknown')
        
        # Check if this model is one of the new Gemini 3 Flash Image (Nano Banana 2) models
        if "image" in name.lower() or "imagen" in name.lower():
            print(f"🌟 FOUND IMAGE MODEL: {name}")
        else:
            print(f"  - {name}")

except Exception as e:
    print(f"❌ Error during model list: {e}")