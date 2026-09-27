"""Playwright scrape of one Google Maps search result: name, address and the cover photo URL."""
import json
import sys
import urllib.parse

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

# Wider than transformations.MIN_WIDTH, so a real photo passes the resolution gate as-is.
PHOTO_SIZE = "=w1600-h1067-k-no"


def high_res_url(src: str) -> str:
    """Google photo URLs end in size options (=w256-h256-k-no); swap them for a larger size."""
    return src.split("=")[0] + PHOTO_SIZE


def scrape_google_maps_data(business_name: str, location: str, category: str = "Restaurant") -> dict | None:
    query = urllib.parse.quote(f"{business_name} {location}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(f"https://www.google.com/maps/search/{query}", wait_until="domcontentloaded", timeout=15000)
            photo = 'button[aria-label*="Photo"] img'
            page.wait_for_selector(photo, timeout=10000)
            image_url = high_res_url(page.locator(photo).first.get_attribute("src"))
            name = page.locator("h1").first.inner_text() or business_name
            try:
                page.wait_for_selector('button[data-item-id="address"]', timeout=5000)
                address = page.locator('button[data-item-id="address"]').first.inner_text()
            except PlaywrightTimeout:
                address = location
            return {"name": name.strip(), "category": category, "address": address.strip(), "city": location, "image_url": image_url}
        except PlaywrightTimeout as e:
            print(f"Google Maps scrape timed out for {business_name}: {e}")
            return None
        finally:
            browser.close()


if __name__ == "__main__":
    print(json.dumps(scrape_google_maps_data(*sys.argv[1:3]), indent=2))
