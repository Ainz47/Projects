"""Turns one scraped business into the listing payload the WordPress client writes."""
import hashlib
import unicodedata

from gemini import TEXT_MODEL, get_client

FALLBACK_STORY = "A local {category} in {location}."


def clean_text(value: str) -> str:
    """Drops the private-use icon glyphs Google Maps puts in front of fields, and tidies whitespace."""
    kept = "".join(ch for ch in value if unicodedata.category(ch) != "Co")
    return " ".join(kept.split())


def make_place_id(name: str, address: str) -> str:
    return hashlib.md5(f"{name}_{address}".encode("utf-8")).hexdigest()


def generate_unique_story(name: str, category: str, location: str, client=None) -> tuple[str, bool]:
    """Returns (story, True) from Gemini, or (fallback, False) if the call fails or comes back empty."""
    prompt = (
        f"Write an engaging two-paragraph directory listing for a {category} called '{name}' "
        f"in {location}. Professional and inviting. Do not invent prices, awards, opening hours or menu items."
    )
    try:
        response = (client or get_client()).models.generate_content(model=TEXT_MODEL, contents=prompt)
        text = (response.text or "").strip()
        if text:
            return text, True
    except Exception as e:
        print(f"Gemini story failed for {name}: {e}")
    return FALLBACK_STORY.format(category=category.lower(), location=location), False


def build_listing(raw: dict, story: str) -> dict:
    name, address = clean_text(raw["name"]), clean_text(raw["address"])
    return {
        "place_id": make_place_id(name, address),
        "title": name,
        "content": story,
        "meta": {
            "business_address": address,
            "business_category": raw["category"],
            "business_city": raw["city"],
        },
    }
