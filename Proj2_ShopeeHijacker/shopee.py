"""Turns Shopee's search API responses into product rows. No browser code here, so it's testable offline."""
from urllib.parse import quote

SEARCH_API = "/api/v4/search/search"
PRICE_SCALE = 100_000  # Shopee sends prices as integers in 1/100000 of a peso


def search_url(keyword: str, page: int) -> str:
    """Shopee's search pages are 0-based: page=0 is the first page."""
    return f"https://shopee.ph/search?keyword={quote(keyword)}&page={page}"


def parse_search_response(data: dict) -> tuple[list[dict], int]:
    """Returns (rows, items that had no itemid/shopid and were skipped)."""
    rows, bad = [], 0
    for item in data.get("items") or []:
        info = item.get("item_basic", item) if isinstance(item, dict) else {}
        itemid, shopid = info.get("itemid"), info.get("shopid")
        if not itemid or not shopid:
            bad += 1
            continue
        rows.append({
            "itemid": itemid,
            "shopid": shopid,
            "title": info.get("name", ""),
            "price_php": (info.get("price") or 0) / PRICE_SCALE,
            "lifetime_sold": info.get("historical_sold") or 0,
            "monthly_sold": info.get("sold") or 0,
            "url": f"https://shopee.ph/product/{shopid}/{itemid}",
        })
    return rows, bad


def dedupe(rows: list[dict]) -> list[dict]:
    """One row per (shopid, itemid), first seen wins. Two products can share a title; an item can't repeat."""
    seen, kept = set(), []
    for r in rows:
        key = (r["shopid"], r["itemid"])
        if key not in seen:
            seen.add(key)
            kept.append(r)
    return kept


class SearchCollector:
    """A Playwright `response` listener that keeps every search API response it sees and counts the ones it couldn't read."""

    def __init__(self):
        self.rows: list[dict] = []
        self.responses = 0
        self.failures = 0

    def __call__(self, response) -> None:
        if SEARCH_API not in response.url:
            return
        self.responses += 1
        try:
            rows, bad = parse_search_response(response.json())
        except Exception as e:  # a body that isn't JSON, or isn't shaped like one we know
            self.failures += 1
            print(f"Could not read a search response ({type(e).__name__}): {response.url[:120]}")
            return
        self.failures += bad
        self.rows.extend(rows)
