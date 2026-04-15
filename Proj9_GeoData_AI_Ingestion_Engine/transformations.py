import io
import os
from PIL import Image
from google import genai
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Import here to avoid circular dependency
from image_generator import enhance_scraped_image

def is_image_relevant(image_bytes: bytes, business_category: str) -> bool:
    """
    The 'Fitting' Filter: Uses Gemini Vision to ensure the photo 
    is a high-quality representation of the business.
    """
    print("🧠 AI is inspecting image relevance...")
    prompt = (
        f"Analyze this image. Is it a high-quality exterior or interior photo "
        f"of a {business_category}? Answer only 'YES' or 'NO'. "
        f"Reject photos of menus, blurry crowds, or parking lots."
    )
    
    try:
        # FIX: Convert bytes to a PIL Image object, which is the expected format for the 'contents' list.
        img = Image.open(io.BytesIO(image_bytes))
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            # Pass the prompt and the PIL Image object.
            contents=[prompt, img]
        )
        return "YES" in response.text.upper()
    except Exception as e:
        print(f"⚠️ Relevance check failed: {e}")
        return True # Default to True to avoid missing good data on API error

def get_image_resolution(image_bytes: bytes):
    """The 'Resolution' Gate: Checks dimensions locally."""
    img = Image.open(io.BytesIO(image_bytes))
    return img.size # Returns (width, height)

def process_and_filter_image(image_bytes: bytes, category: str, business_name: str):
    """
    The 'Happy Path' Branching Logic. This function now fully encapsulates
    the image validation and enhancement process.
    """
    # 1. Relevance Check
    if not is_image_relevant(image_bytes, category):
        print(f"🗑️ Rejected: Irrelevant photo for {business_name}. Skipping this asset.")
        return None

    # 2. Resolution Check
    width, height = get_image_resolution(image_bytes)
    print(f"📏 Image Resolution: {width}x{height}")

    if width >= 1200:
        print(f"✅ High-Res ({width}px): Using original Ground Truth.")
        return image_bytes
    else:
        # BANANA BOOST: Low Res - Enhance via AI
        print(f"🪄 Low-Res ({width}px): Triggering AI Enhancement.")
        return enhance_scraped_image(image_bytes, business_name)