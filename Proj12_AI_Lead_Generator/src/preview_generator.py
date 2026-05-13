"""
preview_generator.py — Redesign Preview Generator
Generates mockup previews for qualified leads.
"""

import os
import json
import re
import logging
from anthropic import Anthropic
from typing import Dict

logger = logging.getLogger(__name__)

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def _enforce_json(raw_text: str) -> Dict:
    """
    Fault-tolerant JSON parser. Strips markdown fences and extracts
    the first valid JSON object from the model's response.
    Inspired by reference/rank_rent_automation-main/src/pipeline_processor.py
    """
    # Strip markdown code fences if present (e.g., ```json ... ```)
    cleaned = re.sub(r"```(?:json)?", "", raw_text).strip()

    # Attempt direct parse first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Direct JSON parsing failed, attempting to find JSON block.")

    # Fallback: find the first {...} block
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON enforcement failed: could not parse extracted block: {e}")

    raise ValueError("JSON enforcement failed: no JSON object found in model response.")

def generate_preview(lead: Dict) -> Dict:
    """
    Generate a redesign preview using Claude.
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

    try:
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        result = response.content[0].text
        data = _enforce_json(result)
        return data
    except (ValueError, json.JSONDecodeError, Exception) as e:
        logger.error(f"Error generating preview for {lead['name']}: {e}")
        return {"preview_description": "Error generating preview", "key_improvements": [], "mockup_html": "", "estimated_cost": "Unknown"}