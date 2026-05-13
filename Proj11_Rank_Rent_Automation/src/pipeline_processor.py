"""
pipeline_processor.py — Gemini 2.0 Flash Content Engine
Handles strict JSON enforcement and local SEO content generation.
"""

import os
import json
import re
import logging
import time
from google import genai
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
GEMINI_FALLBACK_MODELS = [
    model.strip()
    for model in os.getenv(
        "GEMINI_FALLBACK_MODELS",
        "gemini-flash-lite-latest,gemini-3.1-flash-lite,gemini-3-flash-preview",
    ).split(",")
    if model.strip()
]
GEMINI_MODELS = list(dict.fromkeys([GEMINI_MODEL, *GEMINI_FALLBACK_MODELS]))
GEMINI_RETRY_SECONDS = float(os.getenv("GEMINI_RETRY_SECONDS", "8"))

# ---------------------------------------------------------------------------
# Local SEO Landmark Database (Oakland County, MI)
# ---------------------------------------------------------------------------
LANDMARK_DATABASE = {
    "Farmington Hills": ["Heritage Park", "Orchard Lake Road", "Twelve Oaks Mall area",
                         "Grand River Avenue", "Farmington Hills City Center"],
    "Troy":             ["Somerset Collection", "Big Beaver Road", "Coolidge Highway",
                         "Troy Historic Village", "Oakland County Campus"],
    "Auburn Hills":     ["Great Lakes Crossing Outlets", "Auburn Hills Community Center",
                         "Squirrel Road", "University Drive"],
    "Rochester Hills":  ["Stoney Creek Metropark", "Adams Road", "Tienken Road",
                         "Paint Creek Trail"],
    "Pontiac":          ["Phoenix Center", "Woodward Avenue", "Pontiac Lake State Recreation Area",
                         "Wide Track Drive"],
}

FALLBACK_LANDMARKS = ["Woodward Avenue", "Telegraph Road", "M-59 Corridor",
                      "Oakland County Executive Office", "Great Lakes Crossing area"]


def test_gemini_connection() -> bool:
    """Runs a tiny Gemini request before WordPress writes begin."""
    print(f"Testing Gemini API with model: {GEMINI_MODEL}...")
    try:
        response = client.models.generate_content(
            model=GEMINI_MODELS[0],
            contents="Reply with OK only."
        )
        if response.text and "OK" in response.text.upper():
            print("Gemini handshake successful.")
            return True
        print("Gemini responded, but not with the expected smoke-test text.")
        return True
    except Exception as e:
        logger.error(f"Gemini preflight failed: {e}")
        print(f"Gemini preflight failed: {e}")
        return False


def _get_landmarks(city: str) -> list:
    """Returns the two best local landmarks for a given city."""
    landmarks = LANDMARK_DATABASE.get(city, FALLBACK_LANDMARKS)
    return landmarks[:2]


def _build_prompt(keyword: str, city: str, state: str) -> str:
    """Constructs the strict JSON-enforcement prompt for Gemini."""
    landmarks = _get_landmarks(city)
    landmark_str = " and ".join(landmarks)

    return f"""You are a professional local SEO copywriter specializing in the concrete niche.

Your task is to generate a fully optimized page for a "Rank and Rent" SEO website.

TARGET KEYWORD: {keyword}
TARGET CITY: {city}, {state}
LOCAL LANDMARKS TO INCLUDE (mandatory): {landmark_str}

CRITICAL RULES:
1. You MUST return ONLY a valid JSON object. No preamble, no markdown fences, no explanation.
2. The `content_html` field MUST be 800+ words of clean, semantic HTML.
3. The `title_tag` MUST be under 60 characters.
4. The `meta_description` MUST be under 155 characters and have a clear CTA.
5. The `h1` MUST target "{keyword} {city}".
6. The `content_html` MUST naturally mention BOTH "{landmarks[0]}" AND "{landmarks[1]}" 
   to demonstrate local relevancy. Do not force them — weave them into context.
7. Use proper HTML structure: H2s for sections, H3s for sub-points, <ul>/<li> for bullet lists.
8. Keyword density: mention "{keyword}" at least 5 times naturally throughout the content.
9. Include a local trust statement referencing {city} homeowners or neighborhoods.

REQUIRED JSON STRUCTURE (return exactly this, populated):
{{
    "title_tag": "string (under 60 chars)",
    "meta_description": "string (under 155 chars, includes CTA)",
    "h1": "string (targets '{keyword} {city}')",
    "slug": "string (URL-safe, hyphenated, e.g. stamped-concrete-patios-farmington-hills)",
    "content_html": "string (800+ words of semantic HTML)",
    "landmark_references": ["{landmarks[0]}", "{landmarks[1]}"],
    "keyword_count_estimate": "number"
}}

Generate the JSON now:"""


def _enforce_json(raw_text: str) -> dict:
    """
    Fault-tolerant JSON parser. Strips markdown fences and extracts
    the first valid JSON object from the model's response.
    """
    # Strip markdown code fences if present
    cleaned = re.sub(r"```(?:json)?", "", raw_text).strip()

    # Attempt direct parse first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Fallback: find the first {...} block
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as e:
            raise ValueError(f"❌ JSON enforcement failed — could not parse model output: {e}")

    raise ValueError("❌ JSON enforcement failed — no JSON object found in model response.")


def _validate_payload(payload: dict, keyword: str, city: str) -> dict:
    """
    Post-parse validation. Checks character limits, landmark presence,
    and enforces fallback values for any missing fields.
    """
    warnings = []

    # Title tag length check
    if len(payload.get("title_tag", "")) > 60:
        payload["title_tag"] = payload["title_tag"][:57] + "..."
        warnings.append("⚠️  title_tag truncated to 60 chars.")

    # Meta description length check
    if len(payload.get("meta_description", "")) > 155:
        payload["meta_description"] = payload["meta_description"][:152] + "..."
        warnings.append("⚠️  meta_description truncated to 155 chars.")

    # Landmark presence check in content_html
    content = payload.get("content_html", "")
    landmarks = _get_landmarks(city)
    for lm in landmarks:
        if lm.lower() not in content.lower():
            warnings.append(f"⚠️  Landmark '{lm}' NOT found in content_html. Local SEO check FAILED.")

    # Slug normalization keeps WordPress upserts and internal links stable.
    from transformations import slugify
    expected_slug = slugify(f"{keyword} {city}")
    if payload.get("slug") != expected_slug:
        payload["slug"] = expected_slug
        warnings.append("⚠️  Slug normalized from keyword + city.")

    for w in warnings:
        logger.warning(w)
        print(w)

    return payload


def generate_seo_page(keyword: str, city: str, state: str) -> dict:
    """
    Main entry point. Calls Gemini 2.0 Flash, enforces JSON output,
    validates the payload, and returns a clean structured dict.
    """
    print(f"\n🧠 Gemini is generating content for: '{keyword}' in {city}, {state}...")
    prompt = _build_prompt(keyword, city, state)

    last_error = None
    raw_output = ""
    for model in GEMINI_MODELS:
        for attempt in range(1, 3):
            try:
                print(f"   └─ Model: {model} (attempt {attempt}/2)")
                response = client.models.generate_content(
                    model=model,
                    contents=prompt
                )
                raw_output = response.text.strip()
                logger.info(f"Raw Gemini output received from {model} ({len(raw_output)} chars).")
                last_error = None
                break
            except Exception as e:
                last_error = e
                message = str(e)
                logger.error(f"Gemini API call failed on {model}: {e}")
                if "RESOURCE_EXHAUSTED" in message and "prepayment credits" in message:
                    raise ConnectionError(f"❌ Gemini billing/prepay failed: {e}")
                if attempt == 1:
                    print(f"   └─ Temporary Gemini error on {model}; retrying in {GEMINI_RETRY_SECONDS:g}s...")
                    time.sleep(GEMINI_RETRY_SECONDS)
        if raw_output:
            break

    if not raw_output:
        raise ConnectionError(f"❌ Gemini API call failed on all configured models: {last_error}")

    # Enforce JSON structure
    payload = _enforce_json(raw_output)
    print(f"✅ JSON enforcement passed. Fields: {list(payload.keys())}")

    # Validate and patch payload
    payload = _validate_payload(payload, keyword, city)

    # Attach metadata for downstream modules
    payload["_meta"] = {
        "keyword": keyword,
        "city": city,
        "state": state,
        "landmarks_used": _get_landmarks(city),
    }

    return payload
