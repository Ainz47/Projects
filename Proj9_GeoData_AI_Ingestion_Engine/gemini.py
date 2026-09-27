"""One shared Gemini client, created on first use so importing a module never needs an API key.

Model names can be overridden in .env (GEMINI_TEXT_MODEL, GEMINI_IMAGE_MODEL) when Google retires one.
"""
import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()
TEXT_MODEL = os.getenv("GEMINI_TEXT_MODEL", "gemini-flash-latest")
IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image")


@lru_cache(maxsize=1)
def get_client():
    from google import genai

    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
