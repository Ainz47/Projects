"""
wp_importer.py — WordPress REST API Handshake (Fault-Tolerant)
Handles page creation, parent/child hierarchy, and idempotent upserts.
"""

import os
import logging
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

WP_BASE    = os.getenv("WP_URL")
AUTH       = HTTPBasicAuth(os.getenv("WP_USERNAME"), os.getenv("WP_APP_PASSWORD"))
PAGES_URL  = f"{WP_BASE}/pages"

print(f"DEBUG: WP target -> {WP_BASE}")


# ---------------------------------------------------------------------------
# Connection Handshake
# ---------------------------------------------------------------------------

def test_wp_connection() -> bool:
    """
    Validates the WP REST API connection and Application Password auth
    before the pipeline runs. Fails fast rather than silently.
    """
    print("🔌 Testing WordPress REST API connection...")
    try:
        response = requests.get(f"{WP_BASE}/users/me", auth=AUTH, timeout=10)
        if response.status_code == 200:
            user = response.json()
            print(f"✅ WP Handshake successful — logged in as: {user.get('name', 'Unknown')}")
            return True
        else:
            logger.error(f"❌ WP auth failed. Status: {response.status_code} | {response.text[:200]}")
            return False
    except requests.RequestException as e:
        logger.error(f"❌ WP connection error: {e}")
        return False


# ---------------------------------------------------------------------------
# Parent Page Logic
# ---------------------------------------------------------------------------

def get_or_create_parent_page(parent_name: str, state: str) -> int:
    """
    Looks up the parent page by slug. Creates it if it doesn't exist.
    Returns the parent page ID (0 = top-level if creation fails).
    """
    from transformations import slugify
    parent_slug = slugify(parent_name)

    print(f"🔍 Looking up parent page: '{parent_name}' (slug: {parent_slug})...")

    # Search for existing page
    try:
        response = requests.get(PAGES_URL, params={"slug": parent_slug, "status": "any"}, auth=AUTH, timeout=10)
        pages = response.json()
        if isinstance(pages, list) and pages:
            parent_id = pages[0]["id"]
            print(f"✅ Parent page found (ID: {parent_id})")
            return parent_id
    except (requests.RequestException, ValueError) as e:
        logger.warning(f"⚠️  Parent page lookup failed: {e}")

    # Create parent page
    print(f"📄 Parent page not found — creating '{parent_name}'...")
    parent_data = {
        "title":   parent_name,
        "slug":    parent_slug,
        "status":  "draft",
        "content": f"<p>Service pages for {parent_name} — {state}.</p>",
    }

    try:
        response = requests.post(PAGES_URL, json=parent_data, auth=AUTH, timeout=15)
        if response.status_code == 201:
            parent_id = response.json()["id"]
            print(f"✅ Parent page created (ID: {parent_id})")
            return parent_id
        else:
            logger.error(f"❌ Failed to create parent page. Status: {response.status_code}")
    except requests.RequestException as e:
        logger.error(f"❌ Parent page creation exception: {e}")

    return 0  # Fallback: publish as top-level page


def update_parent_page_links(parent_id: int, parent_name: str, state: str,
                             child_pages: list) -> bool:
    """Updates the parent page with links to successfully created child pages."""
    if not parent_id or not child_pages:
        return False

    items = []
    for page in child_pages:
        title = f"{page.get('keyword')} in {page.get('city')}, {state}"
        link = page.get("wp_page_link") or "#"
        items.append(f'<li><a href="{link}">{title}</a></li>')

    content = (
        f"<p>Service pages for {parent_name} — {state}.</p>"
        "<h2>Concrete Service Areas</h2>"
        "<ul>"
        f"{''.join(items)}"
        "</ul>"
    )

    try:
        response = requests.post(
            f"{PAGES_URL}/{parent_id}",
            json={"content": content, "status": "draft"},
            auth=AUTH,
            timeout=15,
        )
        if response.status_code == 200:
            print(f"✅ Parent page updated with {len(child_pages)} child service link(s).")
            return True
        logger.error(f"❌ Parent page link update failed. Status: {response.status_code}")
    except requests.RequestException as e:
        logger.error(f"❌ Parent page link update exception: {e}")

    return False


# ---------------------------------------------------------------------------
# Page Upsert (Idempotent)
# ---------------------------------------------------------------------------

def _find_existing_page(slug: str) -> int | None:
    """Checks if a page with the given slug already exists. Returns ID or None."""
    try:
        response = requests.get(PAGES_URL, params={"slug": slug, "status": "any"}, auth=AUTH, timeout=10)
        pages = response.json()
        if isinstance(pages, list) and pages:
            return pages[0]["id"]
    except (requests.RequestException, ValueError):
        pass
    return None


def push_page_to_wordpress(wp_payload: dict, parent_id: int = 0,
                            featured_media_id: int = None) -> dict | None:
    """
    Core upsert function. Creates a new draft page or updates an existing one
    by slug to ensure idempotency (safe to re-run).

    Returns the full WP response dict on success, None on failure.
    """
    slug = wp_payload.get("slug", "")
    title = wp_payload.get("title", "Unknown")

    # Attach parent and featured image if provided
    if parent_id:
        wp_payload["parent"] = parent_id
    if featured_media_id:
        wp_payload["featured_media"] = featured_media_id

    # Idempotency check
    existing_id = _find_existing_page(slug)

    try:
        if existing_id:
            print(f"🔄 Page exists (ID: {existing_id}) — updating '{title}'...")
            response = requests.post(
                f"{PAGES_URL}/{existing_id}",
                json=wp_payload,
                auth=AUTH,
                timeout=30
            )
            action = "updated"
        else:
            print(f"📤 Creating new draft page: '{title}'...")
            response = requests.post(
                PAGES_URL,
                json=wp_payload,
                auth=AUTH,
                timeout=30
            )
            action = "created"

        if response.status_code in (200, 201):
            result = response.json()
            page_id   = result.get("id")
            page_link = result.get("link", "N/A")
            print(f"✅ Page {action} successfully!")
            print(f"   └─ ID:     {page_id}")
            print(f"   └─ Slug:   {slug}")
            print(f"   └─ Status: {result.get('status')}")
            print(f"   └─ Link:   {page_link}")
            return result
        else:
            logger.error(
                f"❌ WP page push failed for '{title}'. "
                f"Status: {response.status_code} | {response.text[:300]}"
            )
            return None

    except requests.RequestException as e:
        logger.error(f"❌ WP request exception for '{title}': {e}")
        return None
