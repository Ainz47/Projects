import os
import io
from dotenv import load_dotenv
from google import genai
from PIL import Image
from PIL import Image, ImageDraw, ImageFont

load_dotenv()

# Initialize the Gemini Client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def generate_restaurant_image(business_name: str, category: str, location: str) -> str:
    """Original Logic: Generates a high-res cover photo from scratch."""
    print(f"🎨 Generating AI image for {business_name} ({category})...")
    
    prompt = (
        # FIX: The prompt was hardcoded to "exterior". This now correctly uses the 'category'
        # variable, which contains shot details like "Exterior of..." or "Interior dining room of...".
        f"A high-quality, realistic, professional wide-angle architectural photo showing the {category} "
        f"of a restaurant named '{business_name}' in {location}. "
        f"Beautiful daytime lighting, sharp focus, 4k resolution, no text or messy signs."
    )
    
    try:
        result = client.models.generate_images(
            model='imagen-4.0-fast-generate-001', # FIX: Use a valid model name to prevent 404.
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
        filename = f"{safe_name}_{image_type}_ai_hero.jpg" # FIX: Make filename unique to prevent overwrites.
        
        with open(filename, "wb") as f:
            f.write(image_bytes)
            
        return filename
    except Exception as e:
        print(f"❌ AI Image generation failed: {e}")
        return None
        print("✨ Creating a placeholder image for local testing.")
        
        safe_name = business_name.replace(" ", "_").lower()
        image_type = category.split(' ')[0].lower().replace('-', '_')
        filename = f"{safe_name}_{image_type}_ai_hero.jpg"

        try:
            img = Image.new('RGB', (1280, 720), color = (20, 40, 55)) # Dark blue background
            d = ImageDraw.Draw(img)
            try:
                font = ImageFont.truetype("arial.ttf", 40)
            except IOError:
                font = ImageFont.load_default()
            
            text = f"Placeholder for\n{business_name}\n({image_type})"
            d.text((30,30), text, fill=(255,255,255), font=font)
            
            img.save(filename)
            print(f"✅ Saved placeholder image: {filename}")
            return filename
        except Exception as placeholder_err:
            print(f"❌ Failed to create placeholder image: {placeholder_err}")
            return None

def enhance_scraped_image(image_bytes: bytes, business_name: str) -> bytes:
    """
    The 'Banana Boost': Re-imagines a new image based on a text prompt.
    NOTE: This function does NOT use the input image_bytes; it generates a new image.
    """
    print(f"🪄 Triggering AI 're-imagination' for {business_name}...")

    # We describe the image to the AI to help it 're-imagine' the details 
    # while keeping the core identity of the business.
    prompt = (
        f"A professional, high-resolution architectural photo of {business_name}. "
        f"Enhance the lighting, sharpen the textures, and remove any blur. "
        f"4k resolution, professional photography style."
    )
    
    try:
        # We attempt the AI enhancement
        result = client.models.generate_images(
            model='imagen-4.0-fast-generate-001', # Use the confirmed model from your list
            prompt=prompt,
            config=dict(
                number_of_images=1,
                output_mime_type="image/jpeg",
                aspect_ratio="16:9" 
            )
        )
        return result.generated_images[0].image.image_bytes
    except Exception as e:
        # RESILIENCE: If Free Tier limits or 404s hit, return the original
        # This ensures the pipeline never stops.
        print(f"⚠️ AI Boost failed: {e}. Falling back to original asset.")
        return image_bytes

# The is_fitting_photo function was a duplicate of 'is_image_relevant' 
# in transformations.py and was not used. It has been removed to avoid 
# confusion and code duplication.