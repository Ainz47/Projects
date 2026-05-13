"""
evaluator_gemini.py — Website Evaluator using Gemini
Analyzes website quality, modernity, mobile-friendliness, etc.
"""

import os
import json
import re
import logging
import google.generativeai as genai
from typing import Dict
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

try:
    # Ensure the GEMINI_API_KEY is set in your .env file
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment variables.")
    genai.configure(api_key=api_key)
except (ValueError, Exception) as e:
    logger.error(f"Failed to configure Gemini: {e}")

async def fetch_website_content(url: str) -> str:
    """Fetch the HTML content of a website."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(url, timeout=10, headers=headers, follow_redirects=True)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        # Remove scripts and styles
        for script in soup(["script", "style"]):
            script.decompose()
        # Use stripped_strings to get cleaner text and join with spaces
        text = " ".join(soup.stripped_strings)
        return text[:8000]  # Gemini can handle a larger context
    except httpx.RequestError as e:
        logger.error(f"Error fetching {url}: {e}")
        return ""

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

async def evaluate_website(url: str) -> Dict:
    """
    Evaluate a website using Gemini.
    Returns dict with scores and analysis.
    """
    content = await fetch_website_content(url)
    if not content:
        return {
            "mobile_friendly": False,
            "modern_design": False,
            "overall_quality_score": 0,
            "needs_redesign": True,
            "summary": "Could not fetch or parse website content."
        }

    prompt = f"""
You are an expert AI assistant evaluating a business website.

Website URL: {url}

Content snippet:
{content}

Your task is to analyze the website based on the provided content snippet.
Focus on these 3 core metrics ONLY:
1. Mobile Friendly (true/false): Does the site work on mobile devices?
2. Modern Design (true/false): Is the design current & professional-looking (not dated)?
3. Overall Quality Score (1-10): Rate the site's appeal & functionality (1=terrible, 10=excellent).

Based on your analysis, also determine if it `needs_redesign` and provide a short `summary`.

Provide a JSON object with ONLY these fields:
{{
  "mobile_friendly": <boolean>,
  "modern_design": <boolean>,
  "overall_quality_score": <1-10>,
  "needs_redesign": <boolean>,
  "summary": "<1-2 sentence assessment>"
}}

Return only the JSON, no explanation.
"""

    primary_model = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    fallback_models_str = os.getenv("GEMINI_FALLBACK_MODELS", "")
    models_to_try = [primary_model] + [m.strip() for m in fallback_models_str.split(',') if m.strip()]

    last_exception = None
    for model_name in models_to_try:
        try:
            logger.info(f"Attempting evaluation for {url} with Gemini model: {model_name}")
            model = genai.GenerativeModel(model_name)
            response = await model.generate_content_async(prompt)
            data = _enforce_json(response.text)
            return data
        except Exception as e:
            logger.warning(f"Model {model_name} failed during evaluation for {url}: {e}")
            last_exception = e

    logger.error(f"All Gemini models failed for {url}. Last error: {last_exception}")
    return {
        "mobile_friendly": False,
        "modern_design": False,
        "overall_quality_score": 3,
        "needs_redesign": True,
        "summary": f"Evaluation failed: {str(last_exception)[:50]}",
    }