"""
evaluator.py — Website Evaluator using Claude
Analyzes website quality, modernity, mobile-friendliness, etc.
"""

import os
import json
import re
import logging
from anthropic import AsyncAnthropic
from typing import Dict
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class APILimitError(Exception):
    """Raised when API credit/quota limit is exceeded."""
    pass

client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

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
        return text[:5000]  # Limit to first 5000 chars to stay within token limits
    except httpx.RequestError as e:
        logger.error(f"Error fetching {url}: {e}")
        return ""

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

async def evaluate_website(url: str) -> Dict:
    """
    Evaluate a website using Claude.
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

    try:
        response = await client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        result = response.content[0].text
        data = _enforce_json(result)
        return data
    except Exception as e:
        error_str = str(e)
        # Check if this is an API credit limit error
        if "credit balance is too low" in error_str or "Insufficient credit" in error_str:
            logger.error(f"Claude API credit limit exceeded: {error_str}")
            raise APILimitError(f"Claude API: {error_str}")
        
        # Check for other error codes that indicate API issues
        if "Error code: 400" in error_str and "invalid_request_error" in error_str:
            logger.error(f"Claude API error: {error_str}")
            raise APILimitError(f"Claude API: {error_str}")
        
        # For other exceptions, log and return error dict
        logger.error(f"Error evaluating {url}: {e}")
        return {
            "mobile_friendly": False,
            "modern_design": False,
            "overall_quality_score": 3,
            "needs_redesign": True,
            "summary": f"Evaluation failed: {str(e)[:50]}",
        }