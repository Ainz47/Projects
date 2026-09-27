"""Quality gates on the scraped photo: is it relevant, and is it big enough to use as-is."""
import io

from PIL import Image

from gemini import TEXT_MODEL, get_client
from image_generator import enhance_scraped_image

MIN_WIDTH = 1200


def is_image_relevant(image_bytes: bytes, business_category: str, client=None) -> bool:
    """Gemini Vision check. On an API error the photo is kept rather than lost."""
    prompt = (
        f"Is this a clear exterior or interior photo of a {business_category}? Answer only YES or NO. "
        f"Answer NO for menus, blurry crowds, parking lots or food close-ups."
    )
    try:
        img = Image.open(io.BytesIO(image_bytes))
        response = (client or get_client()).models.generate_content(model=TEXT_MODEL, contents=[prompt, img])
        return "YES" in (response.text or "").upper()
    except Exception as e:
        print(f"Relevance check failed, keeping the photo: {e}")
        return True


def get_image_resolution(image_bytes: bytes) -> tuple[int, int]:
    return Image.open(io.BytesIO(image_bytes)).size


def process_and_filter_image(image_bytes, category, business_name, relevance=is_image_relevant, enhance=enhance_scraped_image):
    """Returns the bytes to publish, or None if the photo should not be used."""
    if not relevance(image_bytes, category):
        print(f"Rejected an irrelevant photo for {business_name}")
        return None
    width, _ = get_image_resolution(image_bytes)
    if width >= MIN_WIDTH:
        return image_bytes
    print(f"Photo for {business_name} is {width}px wide, below {MIN_WIDTH}: regenerating")
    return enhance(image_bytes, business_name)
