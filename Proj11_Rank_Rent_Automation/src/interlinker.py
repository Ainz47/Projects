"""
interlinker.py — Injects internal and external hyperlinks into deployed page HTML.

Internal links: rule-based, matched against deployed page URLs.
External links:  Gemini suggests keywords; user supplies URLs via the UI.

All natural occurrences of each keyword inside <p> tags are linked.
Already-linked text (inside <a> tags) is never double-linked.
"""
import re
import json
import logging
import time
import os
from src.config import DeployConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Keyword injection
# ---------------------------------------------------------------------------

def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html)


def inject_links(html: str, keyword_url_map: dict[str, str],
                 new_tab_urls: set[str] | None = None,
                 max_per_keyword: int = 2) -> str:
    """
    For each keyword → URL pair, inject links inside <p>...</p> blocks,
    skipping text already inside <a> tags.

    max_per_keyword: max times each keyword is linked across the whole page (default 2).
    new_tab_urls: set of URL values that should open in a new tab (external links).
    """
    if not keyword_url_map:
        return html

    counts: dict[tuple, int] = {(kw.lower(), url): 0 for kw, url in keyword_url_map.items()}

    def replace_in_para(m: re.Match) -> str:
        para_html = m.group(0)
        for kw, url in keyword_url_map.items():
            remaining = max_per_keyword - counts[(kw.lower(), url)]
            if remaining <= 0:
                continue
            new_tab = bool(new_tab_urls and url in new_tab_urls)
            new_para, n = _safe_replace_n(para_html, kw, url, limit=remaining, new_tab=new_tab)
            if n:
                para_html = new_para
                counts[(kw.lower(), url)] += n
        return para_html

    result = re.sub(r"<p(?:\s[^>]*)?>.*?</p>", replace_in_para, html,
                    flags=re.DOTALL | re.IGNORECASE)
    return result


def _safe_replace_n(html: str, keyword: str, url: str,
                    limit: int = 2, new_tab: bool = False) -> tuple[str, int]:
    """
    Replace up to `limit` occurrences of keyword in html not inside an <a> tag.
    Returns (new_html, number_of_replacements).
    """
    segments = re.split(r"(<a\b[^>]*>.*?</a>)", html, flags=re.DOTALL | re.IGNORECASE)
    replaced = 0
    result_parts = []
    kw_pattern = re.compile(re.escape(keyword), re.IGNORECASE)
    extra = ' target="_blank" rel="noopener"' if new_tab else ''

    for i, seg in enumerate(segments):
        if i % 2 == 1:
            result_parts.append(seg)
            continue

        remaining = limit - replaced
        if remaining <= 0:
            result_parts.append(seg)
            continue

        new_seg, n = kw_pattern.subn(
            lambda m: f'<a href="{url}" style="font-weight:700;text-decoration:underline"{extra}>{m.group(0)}</a>',
            seg, count=remaining,
        )
        result_parts.append(new_seg)
        replaced += n

    return "".join(result_parts), replaced


# ---------------------------------------------------------------------------
# Internal URL map builder
# ---------------------------------------------------------------------------

def build_internal_url_map(published_urls: list[dict], services: list[str]) -> dict[str, str]:
    """
    Builds keyword → URL map from the deploy summary's published_urls list.

    Entries look like: {"label": "Concrete Driveways", "url": "https://...", "type": "page"}
    """
    url_map: dict[str, str] = {}

    label_to_url = {item["label"].lower(): item["url"] for item in published_urls if item.get("url")}

    # Service pages — use the service name as the keyword
    for svc in services:
        key = svc.lower()
        if key in label_to_url:
            url_map[svc] = label_to_url[key]

    # Standard pages — map common anchor phrases
    standard = {
        "contact us":   ["contact us", "get in touch"],
        "faqs":         ["frequently asked questions", "faqs"],
        "blog":         ["blog", "articles", "tips"],
        "services hub": ["our services", "all services"],
    }
    for label_key, phrases in standard.items():
        url = label_to_url.get(label_key)
        if not url:
            # Try partial match in either direction ("services" matches "services hub")
            for k, v in label_to_url.items():
                if label_key in k or k in label_key:
                    url = v
                    break
        if url:
            for phrase in phrases[:1]:  # only use first phrase to avoid over-linking
                url_map[phrase] = url

    return url_map


# ---------------------------------------------------------------------------
# Gemini: suggest external keywords
# ---------------------------------------------------------------------------

def suggest_external_keywords(cfg: DeployConfig, content_snippets: list[str],
                               count: int = 5,
                               exclude_keywords: list[str] | None = None) -> list[str]:
    """
    Ask Gemini to pick `count` keywords/phrases from the page content that
    would benefit from an external authoritative link.
    Returns a list of keyword strings.
    """
    def _clean(html: str) -> str:
        # Remove Gutenberg block comments and style/script blocks first
        html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        return _strip_tags(html).strip()

    combined = "\n\n".join(_clean(s) for s in content_snippets[:3])[:3000]
    combined_lower = combined.lower()

    exclude_note = ""
    if exclude_keywords:
        exclude_list = ", ".join(f'"{k}"' for k in exclude_keywords)
        exclude_note = f"\n\nDo NOT suggest any of these — they are already used as internal links:\n{exclude_list}"

    fetch_count = count * 2  # ask for extra candidates to survive strict content filter

    prompt = f"""You are an SEO expert reviewing content for a {cfg.business_name} website in {cfg.city}, {cfg.state}.

Your task: extract up to {fetch_count} keywords or short phrases (2-5 words) that ALREADY APPEAR in the page content below and would benefit from linking to an authoritative external source.

Rules:
- The phrase MUST appear word-for-word (or near word-for-word) in the content — do not invent or paraphrase
- Prefer phrases a reader might want to learn more about: materials, processes, standards, industry concepts
- Do NOT pick generic service names like "concrete driveways" or "concrete repair"{exclude_note}

Return a JSON array of the extracted phrases ONLY. No explanation.

Page content:
---
{combined}
---

Return JSON array only:"""

    try:
        from src.content_gen import _call_gemini
        raw = _call_gemini(cfg, prompt)
        cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        keywords = json.loads(cleaned)
        if isinstance(keywords, list):
            candidates = [str(k).strip() for k in keywords if k]
            # Strict: only return phrases that actually appear in the page text
            matched = [k for k in candidates if k.lower() in combined_lower]
            return matched[:count]
    except Exception as e:
        logger.error("suggest_external_keywords failed: %s", e)

    return []


# ---------------------------------------------------------------------------
# Fetch page HTML from WordPress
# ---------------------------------------------------------------------------

def fetch_page_html(wp, slug: str) -> tuple[int | None, str]:
    """
    Returns (page_id, raw_block_html) for the given slug.
    Uses context=edit to get content.raw (the stored block markup, not WP-rendered output).
    """
    try:
        r = wp._get("/pages", params={"slug": slug, "per_page": 1, "context": "edit"}, timeout=15)
        if r.status_code == 200 and r.json():
            page = r.json()[0]
            content = page.get("content", {})
            raw = content.get("raw") or content.get("rendered", "")
            return page["id"], raw
    except Exception as e:
        logger.error("fetch_page_html(%s) error: %s", slug, e)
    return None, ""


def fetch_page_rendered(wp, slug: str) -> str:
    """
    Returns the WP-rendered HTML for the given slug (no block comments, no CSS — clean paragraph text).
    Used for keyword suggestion where we need actual readable content, not raw block markup.
    """
    try:
        r = wp._get("/pages", params={"slug": slug, "per_page": 1}, timeout=15)
        if r.status_code == 200 and r.json():
            return r.json()[0].get("content", {}).get("rendered", "")
    except Exception as e:
        logger.error("fetch_page_rendered(%s) error: %s", slug, e)
    return ""


def fetch_post_html(wp, slug: str) -> tuple[int | None, str]:
    """Returns (post_id, raw_block_html) for a post by slug."""
    try:
        r = wp._get("/posts", params={"slug": slug, "per_page": 1, "context": "edit"}, timeout=15)
        if r.status_code == 200 and r.json():
            post = r.json()[0]
            content = post.get("content", {})
            raw = content.get("raw") or content.get("rendered", "")
            return post["id"], raw
    except Exception as e:
        logger.error("fetch_post_html(%s) error: %s", slug, e)
    return None, ""
