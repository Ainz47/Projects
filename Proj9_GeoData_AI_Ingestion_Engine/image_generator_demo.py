import os
import io
from dotenv import load_dotenv
from google import genai
from PIL import Image, ImageDraw, ImageFont

load_dotenv()

# Initialize the Gemini Client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def generate_restaurant_image(business_name: str, category: str, location: str, fallback_image_bytes: bytes = None) -> str:
    """
    DEMO VERSION: Generates a high-res photo, but on failure, it saves
    a copy of the provided fallback image instead of a placeholder.
    """
    print(f"🎨 DEMO: Generating AI image for {business_name} ({category})...")
    
    prompt = (
        f"A high-quality, realistic, professional wide-angle architectural photo showing the {category} "
        f"of a restaurant named '{business_name}' in {location}. "
        f"Beautiful daytime lighting, sharp focus, 4k resolution, no text or messy signs."
    )
    
    try:
        # This is expected to fail on a free tier, triggering the except block.
        result = client.models.generate_images(
            model='imagen-4.0-fast-generate-001',
            prompt=prompt,
            config=dict(
                number_of_images=1,
                output_mime_type="image/jpeg",
                aspect_ratio="16:9"
            )
        )
        
        image_bytes = result.generated_images[0].image.image_bytes
        safe_name = business_name.replace(" ", "_").lower()
        image_type = category.split(' ')[0].lower().replace('-', '_')
        filename = f"{safe_name}_{image_type}_ai_hero.jpg"
        
        with open(filename, "wb") as f:
            f.write(image_bytes)
            
        return filename
    except Exception as e:
        print(f"❌ AI Image generation failed as expected: {e}")
        
        # --- DEMONSTRATION FALLBACK LOGIC ---
        if fallback_image_bytes:
            print("✨ DEMO: Falling back to saving a copy of the original scraped image.")
            safe_name = business_name.replace(" ", "_").lower()
            image_type = category.split(' ')[0].lower().replace('-', '_')
            filename = f"demo_{safe_name}_{image_type}_ai_hero.jpg" # Prefix to avoid name clashes
            
            with open(filename, "wb") as f:
                f.write(fallback_image_bytes)
            
            print(f"✅ Saved fallback copy for demo: {filename}")
            return filename
        else:
            # If no fallback is provided, return None.
            return None

def enhance_scraped_image(image_bytes: bytes, business_name: str) -> bytes:
    """
    The 'Banana Boost': Re-imagines a new image based on a text prompt.
    NOTE: This function does NOT use the input image_bytes; it generates a new image.
    """
    print(f"🪄 Triggering AI 're-imagination' for {business_name}...")

    prompt = (
        f"A professional, high-resolution architectural photo of {business_name}. "
        f"Enhance the lighting, sharpen the textures, and remove any blur. "
        f"4k resolution, professional photography style."
    )
    
    try:
        result = client.models.generate_images(
            model='imagen-4.0-fast-generate-001',
            prompt=prompt,
            config=dict(
                number_of_images=1,
                output_mime_type="image/jpeg",
                aspect_ratio="16:9" 
            )
        )
        return result.generated_images[0].image.image_bytes
    except Exception as e:
        # RESILIENCE: If Free Tier limits hit, return the original
        print(f"⚠️ AI Boost failed: {e}. Falling back to original asset.")
        return image_bytes