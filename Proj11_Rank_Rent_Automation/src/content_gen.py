"""
content_gen.py — Gemini content generation for all page types.
"""
import os
import re
import json
import time
import logging
from src.config import DeployConfig

logger = logging.getLogger(__name__)


def _get_client(cfg: DeployConfig):
    from google import genai
    key = cfg.gemini_api_key or os.getenv("GEMINI_API_KEY", "")
    return genai.Client(api_key=key)


def _call_gemini(cfg: DeployConfig, prompt: str) -> str:
    client = _get_client(cfg)
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    for attempt in range(3):
        try:
            resp = client.models.generate_content(model=model, contents=prompt)
            return resp.text.strip()
        except Exception as e:
            logger.warning("Gemini attempt %d failed: %s", attempt + 1, e)
            if attempt < 2:
                time.sleep(5)
    raise RuntimeError("Gemini failed after 3 attempts")


def _parse_json(raw: str) -> dict:
    cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    # Try direct parse first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # Extract outermost {} block
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = cleaned[start:end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            # Last resort: strip control characters and retry
            candidate = re.sub(r"[\x00-\x1f\x7f]", " ", candidate)
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
    raise ValueError("Could not parse JSON from Gemini response")


def test_connection(cfg: DeployConfig) -> bool:
    try:
        result = _call_gemini(cfg, "Reply with OK only.")
        return "OK" in result.upper()
    except Exception as e:
        logger.error("Gemini connection test failed: %s", e)
        return False


# ------------------------------------------------------------------
# Service page content
# ------------------------------------------------------------------

def generate_service_page(cfg: DeployConfig, service: str) -> dict:
    prompt = f"""You are a professional local SEO copywriter.

Generate content for a local service business page. Return ONLY valid JSON, no markdown, no explanation.

SERVICE: {service}
CITY: {cfg.city}, {cfg.state}
BUSINESS: {cfg.business_name}
PHONE: {cfg.phone}

Choose 4 relevant H2 section topics for this specific service (e.g. for a plumber: Installation, Repairs, Emergency Service, Maintenance — pick what fits naturally).

Return this exact JSON structure:
{{
  "h1": "{service} in {cfg.city}, {cfg.state}",
  "meta_title": "string (under 60 chars)",
  "meta_description": "string (under 155 chars with CTA)",
  "intro": "2-3 sentence intro paragraph about {service} in {cfg.city}",
  "sections": [
    {{"h2": "section name", "body": "120-180 word paragraph for this section"}}
  ],
  "cta_text": "Short CTA sentence (1 line, encouraging them to call)"
}}

sections must have exactly 4 items."""

    raw = _call_gemini(cfg, prompt)
    data = _parse_json(raw)
    data["service"] = service
    return data


# ------------------------------------------------------------------
# Homepage content
# ------------------------------------------------------------------

def generate_homepage(cfg: DeployConfig, services: list[str]) -> dict:
    services_str = "\n".join(f"- {s}" for s in services)
    prompt = f"""You are a local SEO copywriter for a local service business website.

Generate homepage content. Return ONLY valid JSON, no markdown.

BUSINESS: {cfg.business_name}
CITY: {cfg.city}, {cfg.state}
PHONE: {cfg.phone}
SERVICES:
{services_str}

Return this exact JSON structure:
{{
  "hero_h1": "short punchy headline (e.g. Detroit's Trusted Plumbing Experts)",
  "hero_tagline": "1 sentence under the H1 (mention {cfg.city} and the value of the service)",
  "intro_paragraph": "2-3 sentences about {cfg.business_name} serving {cfg.city}",
  "best_h2": "Why Choose {cfg.business_name}",
  "best_body": "3-4 sentences about quality, experience, local expertise in {cfg.city}",
  "cta_h2": "Ready to Get Started? (write one relevant to the service)",
  "cta_body": "1-2 sentences encouraging contact",
  "service_cards": [
    {{"title": "service name", "description": "2-3 sentence description"}}
  ],
  "process_steps": [
    {{"title": "step name", "description": "1 sentence"}}
  ],
  "why_body": "2-3 sentences on why {cfg.business_name} is the best choice in {cfg.city}"
}}

service_cards should have one card per service listed above.
process_steps should have exactly 5 steps."""

    raw = _call_gemini(cfg, prompt)
    return _parse_json(raw)


# ------------------------------------------------------------------
# Blog posts
# ------------------------------------------------------------------

def generate_blog_post(cfg: DeployConfig, topic: str) -> dict:
    prompt = f"""You are a local SEO blog writer for a local service business.

Write a blog post. Return ONLY valid JSON, no markdown, no code fences.

TOPIC: {topic}
CITY: {cfg.city}, {cfg.state}
BUSINESS: {cfg.business_name}

Return this exact JSON (keep content_html under 2000 chars, use simple HTML only):
{{
  "title": "blog post title",
  "slug": "url-safe-slug",
  "meta_description": "under 155 chars",
  "content_html": "<h2>Heading</h2><p>paragraph</p><h2>Heading 2</h2><p>paragraph</p><ul><li>point</li></ul><p>closing paragraph</p>"
}}

IMPORTANT: content_html must be a single-line JSON string with no unescaped double quotes inside."""

    raw = _call_gemini(cfg, prompt)
    return _parse_json(raw)


# ------------------------------------------------------------------
# FAQ content
# ------------------------------------------------------------------

def generate_faqs(cfg: DeployConfig) -> dict:
    services_str = ", ".join(cfg.services) if cfg.services else "our services"
    prompt = f"""Generate FAQ content for a local service business website.

BUSINESS: {cfg.business_name}, {cfg.city}, {cfg.state}
SERVICES: {services_str}

Return ONLY valid JSON:
{{
  "faqs": [
    {{"question": "string", "answer": "2-3 sentence answer"}}
  ]
}}

Include 12 FAQs relevant to the specific services listed above. Cover: pricing, timeline, what to expect, maintenance, hiring tips, service area, guarantees."""

    raw = _call_gemini(cfg, prompt)
    return _parse_json(raw)


# ------------------------------------------------------------------
# Image search queries (Gemini-generated, industry-aware)
# ------------------------------------------------------------------

def generate_image_queries(cfg: DeployConfig) -> dict:
    """Ask Gemini to produce Pexels-optimised search queries for this specific business.
    Returns a dict with keys: hero, best, svc1, svc2, svc3, blog_queries (list), faq, contact.
    Falls back to simple service-name queries if Gemini fails.
    """
    services_str = ", ".join(cfg.services) if cfg.services else "general services"
    s = cfg.services or ["service"]

    prompt = f"""You are a stock photo search expert. Generate Pexels search queries for a local service business website.

BUSINESS: {cfg.business_name}
CITY: {cfg.city}, {cfg.state}
SERVICES: {services_str}

Return ONLY valid JSON with short, specific Pexels search queries (2-5 words each) that will return professional, high-quality photos relevant to this exact business type.

{{
  "hero": "query for main hero banner (show workers/team or finished work)",
  "best": "query for 'why choose us' section (quality work, residential setting)",
  "svc1": "query for '{s[0]}' service image",
  "svc2": "query for '{s[1] if len(s) > 1 else s[0]}' service image",
  "svc3": "query for '{s[2] if len(s) > 2 else s[0]}' service image",
  "blog": ["query1", "query2", "query3", "query4", "query5"],
  "faq": "query for FAQ page hero (professional worker or team)",
  "contact": "query for contact page hero (residential exterior or professional team)"
}}

Rules:
- Use real Pexels-friendly terms (no brand names, no abstract concepts)
- Prefer "[trade] professional", "[service] worker", "[result] residential"
- blog must have exactly 5 queries, one per major topic area of this business
- All queries must be relevant to {services_str}, not generic"""

    try:
        raw = _call_gemini(cfg, prompt)
        data = _parse_json(raw)
        # Validate expected keys exist
        required = {"hero", "best", "svc1", "svc2", "svc3", "blog", "faq", "contact"}
        if required.issubset(data.keys()):
            return data
        logger.warning("Gemini image queries missing keys — using fallback")
    except Exception as e:
        logger.warning("generate_image_queries failed: %s — using fallback", e)

    # Fallback: build from service names
    primary = s[0].lower()
    return {
        "hero": f"{primary} contractor professional",
        "best": f"{primary} service quality residential",
        "svc1": f"{s[0].lower()} professional work",
        "svc2": f"{s[1].lower() if len(s) > 1 else primary} service",
        "svc3": f"{s[2].lower() if len(s) > 2 else primary} contractor",
        "blog": [f"{svc.lower()} service work" for svc in s[:5]],
        "faq": f"{primary} professional worker",
        "contact": f"{primary} residential home",
    }


# ------------------------------------------------------------------
# Contact page
# ------------------------------------------------------------------

def generate_contact(cfg: DeployConfig) -> dict:
    return {
        "h1": f"Contact {cfg.business_name}",
        "intro": f"Ready to get started on your project in {cfg.city}, {cfg.state}? "
                 f"Call us at {cfg.phone} or fill out the form below and we'll get back to you within 24 hours.",
        "address_note": f"Serving {cfg.city} and surrounding {cfg.state} communities.",
    }
