"""
preview_generator_gemini.py — Redesign Preview Generator using Gemini
Generates mockup previews for qualified leads.
"""

import os
import json
import re
import logging
import google.generativeai as genai
from typing import Dict

logger = logging.getLogger(__name__)

try:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment variables.")
    genai.configure(api_key=api_key)
except (ValueError, Exception) as e:
    logger.error(f"Failed to configure Gemini: {e}")

def _enforce_json(raw_text: str) -> Dict:
    """
    Fault-tolerant JSON parser. Strips markdown fences and extracts
    the first valid JSON object from the model's response.
    """
    cleaned = re.sub(r"```(?:json)?", "", raw_text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Direct JSON parsing failed, attempting to find JSON block.")
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON enforcement failed: could not parse extracted block: {e}")
    raise ValueError("JSON enforcement failed: no JSON object found in model response.")

async def generate_preview(lead: Dict) -> Dict:
    """
    Generate a redesign preview using Gemini.
    For simplicity, generate a description or simple HTML.
    """
    prompt = f"""
Based on this business lead, generate a redesign preview.

Business: {lead['name']}
Website: {lead['website']}
Category: {lead['category']}
City: {lead['city']}, {lead['state']}
Current quality: {lead.get('overall_quality_score', 5)}/10

Generate a JSON with:
- preview_description: string describing the proposed redesign
- key_improvements: list of strings
- mockup_html: simple HTML snippet for homepage mockup
- estimated_cost: rough estimate for redesign

Return only the JSON.
"""

    primary_model = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    fallback_models_str = os.getenv("GEMINI_FALLBACK_MODELS", "")
    models_to_try = [primary_model] + [m.strip() for m in fallback_models_str.split(',') if m.strip()]

    last_exception = None
    for model_name in models_to_try:
        try:
            logger.info(f"Attempting preview generation for {lead['name']} with Gemini model: {model_name}")
            model = genai.GenerativeModel(model_name)
            response = await model.generate_content_async(prompt)
            data = _enforce_json(response.text)
            return data
        except Exception as e:
            logger.warning(f"Model {model_name} failed during preview generation for {lead['name']}: {e}")
            last_exception = e

    logger.error(f"All Gemini models failed for preview generation for {lead['name']}. Last error: {last_exception}")
    return {
        "preview_description": "Error generating preview",
        "key_improvements": [],
        "mockup_html": "",
        "estimated_cost": "Unknown"
    }