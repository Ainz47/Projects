"""One shared Gemini client, created on first use so importing a module never needs an API key.

Model names can be overridden in .env (GEMINI_TEXT_MODEL, GEMINI_IMAGE_MODEL) when Google retires one.
"""
import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()
TEXT_MODEL = os.getenv("GEMINI_TEXT_MODEL", "gemini-flash-latest")
IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image")
# Without a timeout one stalled call holds up the whole batch; every caller already has a fallback.
TIMEOUT_MS = 120_000


@lru_cache(maxsize=1)
def get_client():
    from google import genai
    from google.genai import types

    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"), http_options=types.HttpOptions(timeout=TIMEOUT_MS))
