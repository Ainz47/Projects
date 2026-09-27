"""Gemini image calls. Both return bytes and never raise: callers get None, or the original photo back."""
from google.genai import types

from gemini import IMAGE_MODEL, get_client


def _generate(prompt: str, client=None) -> bytes | None:
    try:
        response = (client or get_client()).models.generate_content(
            model=IMAGE_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio="16:9"),
            ),
        )
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.data:
                return part.inline_data.data
        print("Image generation returned no image")
    except Exception as e:
        print(f"Image generation failed: {e}")
    return None


def generate_restaurant_image(business_name: str, shot: str, location: str, client=None) -> bytes | None:
    """A gallery image for `shot` (e.g. "exterior"), or None if Imagen is unavailable."""
    prompt = (
        f"A realistic, professional wide-angle photo showing the {shot} of a restaurant named "
        f"'{business_name}' in {location}. Daytime lighting, sharp focus, no text or signs."
    )
    return _generate(prompt, client)


def enhance_scraped_image(image_bytes: bytes, business_name: str, client=None) -> bytes:
    """Regenerates (does not upscale) a small photo from a text prompt; keeps the original if that fails."""
    prompt = (
        f"A professional, high-resolution architectural photo of {business_name}. "
        f"Even lighting, sharp textures, professional photography style."
    )
    return _generate(prompt, client) or image_bytes
