import os

import google.generativeai as genai

TIMEOUT_SECONDS = 20


def call_gemini(prompt: str) -> str:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel(
        "gemini-2.5-flash",
        generation_config={"response_mime_type": "application/json"},
    )
    return model.generate_content(prompt, request_options={"timeout": TIMEOUT_SECONDS}).text
