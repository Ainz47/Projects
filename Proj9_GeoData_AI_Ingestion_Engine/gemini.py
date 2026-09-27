"""One shared Gemini client, created on first use so importing a module never needs an API key."""
import os
from functools import lru_cache

from dotenv import load_dotenv

TEXT_MODEL = "gemini-2.5-flash"
IMAGE_MODEL = "imagen-4.0-fast-generate-001"


@lru_cache(maxsize=1)
def get_client():
    from google import genai

    load_dotenv()
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
