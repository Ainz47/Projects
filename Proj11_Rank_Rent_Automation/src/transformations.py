"""
transformations.py — SEO Logic & HTML Processing
Handles slugification, keyword density checks, and internal linking injection.
"""

import re
import logging

logger = logging.getLogger(__name__)


def slugify(text: str) -> str:
    """
    Converts a string to a clean, URL-safe slug.
    e.g. "Stamped Concrete Patios Farmington Hills" -> "stamped-concrete-patios-farmington-hills"
    """
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)       # Remove special chars
    text = re.sub(r"[\s_]+", "-", text)         # Spaces/underscores -> hyphens
    text = re.sub(r"-+", "-", text)             # Collapse multiple hyphens
    return text


def clean_html(html: str) -> str:
    """
    Light sanitization pass on AI-generated HTML.
    - Strips residual markdown fences
    - Normalizes whitespace between tags
    - Ensures no bare <script> or <style> tags (safety)
    """
    # Remove markdown code fences if Gemini wrapped the HTML
    html = re.sub(r"```(?:html)?", "", html).strip()
    html = re.sub(r"```", "", html).strip()

    # Strip script and style tags (security)
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)

    # Normalize extra whitespace between tags
    html = re.sub(r">\s{2,}<", "> <", html)

    return html.strip()


def count_keyword_occurrences(html: str, keyword: str) -> int:
    """Returns case-insensitive count of keyword in HTML (ignores tags)."""
    # Strip HTML tags to count in visible text only
    text_only = re.sub(r"<[^>]+>", " ", html)
    return len(re.findall(re.escape(keyword.lower()), text_only.lower()))


def ensure_keyword_floor(html: str, keyword: str, city: str, minimum: int = 5) -> str:
    """Adds a short natural CTA paragraph if AI output misses the keyword floor."""
    current_count = count_keyword_occurrences(html, keyword)
    if current_count >= minimum:
        return html

    missing = minimum - current_count
    mentions = " ".join([keyword] * missing)
    return (
        f"{html}\n"
        f"<p>For homeowners comparing options in {city}, {mentions} can be planned "
        "around the home's layout, drainage, and long-term curb appeal goals.</p>"
    )


def inject_internal_links(html: str, sibling_pages: list) -> str:
    """
    Injects internal anchor links into content to build SEO silos.

    sibling_pages: list of dicts with keys 'keyword', 'city', 'slug'
    e.g. [{"keyword": "Concrete Driveways", "city": "Troy", "slug": "concrete-driveways-troy"}]

    Strategy: finds the first mention of each sibling's keyword in the HTML 
    (within a <p> tag) and wraps it in an <a> tag. One injection per sibling.
    """
    if not sibling_pages:
        return html

    injected_count = 0
    for page in sibling_pages:
        keyword = page.get("keyword", "")
        slug = page.get("slug", "")
        city = page.get("city", "")

        if not keyword or not slug:
            continue

        # Build the anchor — uses relative path for portability
        anchor = f'<a href="/{slug}/" title="{keyword} {city}">{keyword}</a>'

        # Only inject once; target keyword inside a <p> block
        pattern = re.compile(
            rf"(<p[^>]*>(?:(?!<a\b).)*?)({re.escape(keyword)})(.*?</p>)",
            re.IGNORECASE | re.DOTALL
        )

        def replacer(m):
            return f"{m.group(1)}{anchor}{m.group(3)}"

        new_html, count = re.subn(pattern, replacer, html, count=1)

        if count > 0:
            html = new_html
            injected_count += 1
            logger.info(f"🔗 Internal link injected: '{keyword}' -> /{slug}/")

    print(f"🔗 {injected_count} internal link(s) injected into content.")
    return html


def build_yoast_meta(payload: dict) -> dict:
    """
    Packages Yoast-compatible SEO meta fields for the WP REST payload.
    Maps title_tag and meta_description to the yoast_head_json convention.
    """
    return {
        "yoast_title": payload.get("title_tag", ""),
        "yoast_meta_description": payload.get("meta_description", ""),
    }


def prepare_wp_content(payload: dict, sibling_pages: list = None) -> dict:
    """
    Master transformation pipeline. Takes the raw Gemini payload and returns
    a clean, WP-ready dict with all SEO transformations applied.
    """
    keyword = payload["_meta"]["keyword"]
    city = payload["_meta"]["city"]

    # 1. Slugify
    slug = payload.get("slug") or slugify(f"{keyword} {city}")

    # 2. Clean HTML
    content_html = clean_html(payload.get("content_html", ""))

    # 3. Keyword density report
    content_html = ensure_keyword_floor(content_html, keyword, city)
    kw_count = count_keyword_occurrences(content_html, keyword)
    print(f"📊 Keyword '{keyword}' appears {kw_count} time(s) in content.")
    if kw_count < 4:
        logger.warning(f"⚠️  Low keyword density ({kw_count}). Target is 5+ mentions.")

    # 4. Internal linking
    if sibling_pages:
        content_html = inject_internal_links(content_html, sibling_pages)

    # 5. Assemble final WP payload
    wp_payload = {
        "title":   payload.get("h1", f"{keyword} {city}"),
        "content": content_html,
        "slug":    slug,
        "status":  "draft",
        "meta": {
            "rank_math_title":            payload.get("title_tag", ""),
            "rank_math_description":      payload.get("meta_description", ""),
            "_yoast_wpseo_title":         payload.get("title_tag", ""),
            "_yoast_wpseo_metadesc":      payload.get("meta_description", ""),
        },
        "excerpt": payload.get("meta_description", ""),
    }

    return wp_payload
