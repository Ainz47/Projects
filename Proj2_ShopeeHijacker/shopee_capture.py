"""Capture Shopee search results from your own logged-in Chrome, then store them.

Opens a new tab in a Chrome you already started with remote debugging and logged into Shopee, pages through
the search, and reads the product data from the search API responses the page itself loads. Each run is
appended to SQLite with its timestamp, and written to a CSV.

    chrome.exe --remote-debugging-port=9222 --user-data-dir=chrome-cdp   (then log in to shopee.ph there)
    py shopee_capture.py "mechanical keyboard" --pages 3
"""
import argparse
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from shopee import SEARCH_API, SearchCollector, dedupe, search_url
from storage import save_run, write_csv


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def capture_from_chrome(keyword: str, pages: int, cdp_url: str) -> tuple[SearchCollector, int]:
    """Returns the collector and how many pages produced a search API response."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    from playwright.sync_api import sync_playwright

    collector, pages_ok = SearchCollector(), 0
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(cdp_url)
        if not browser.contexts:
            raise SystemExit("Connected to Chrome, but it has no window open. Open shopee.ph and log in first.")
        page = browser.contexts[0].new_page()  # our own tab, never one of yours
        page.on("response", collector)
        try:
            for n in range(pages):
                try:
                    with page.expect_response(lambda r: SEARCH_API in r.url, timeout=15000):
                        page.goto(search_url(keyword, n))
                    pages_ok += 1
                    print(f"Page {n + 1}/{pages}: {len(collector.rows)} rows so far")
                    page.mouse.wheel(0, 2000)
                    page.wait_for_timeout(1000)
                except PlaywrightTimeout:
                    if "/buyer/login" in page.url:
                        raise SystemExit("Shopee sent the tab to its login page. Log in in that Chrome window and run again.")
                    print(f"Page {n + 1}/{pages}: no search response within 15s, skipped")
        finally:
            page.close()  # leaves your browser and your other tabs as they were
    return collector, pages_ok


def run(keyword: str, pages: int, db: Path, csv_path: Path, cdp_url: str = "http://localhost:9222",
        capture: Callable = capture_from_chrome) -> dict:
    started = now()
    collector, pages_ok = capture(keyword, pages, cdp_url)
    rows = dedupe(collector.rows)
    summary = {"keyword": keyword, "pages_requested": pages, "pages_ok": pages_ok,
               "parse_failures": collector.failures, "started_at": started, "finished_at": now()}
    if rows:
        summary["run_id"] = save_run(db, summary, rows)
        write_csv(csv_path, rows)
    summary.update(items=len(rows), duplicates_dropped=len(collector.rows) - len(rows))
    return summary


def main(argv=None, capture: Callable = capture_from_chrome) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("keyword")
    ap.add_argument("--pages", type=int, default=3)
    ap.add_argument("--db", type=Path, default=Path("market_intelligence.db"))
    ap.add_argument("--csv", type=Path, help="default runs/<keyword>_<timestamp>.csv")
    ap.add_argument("--cdp", default="http://localhost:9222")
    args = ap.parse_args(argv)
    if args.pages < 1:
        ap.error("--pages must be at least 1")
    slug = re.sub(r"[^a-z0-9]+", "_", args.keyword.lower()).strip("_")
    csv_path = args.csv or Path(f"runs/{slug}_{datetime.now():%Y%m%d_%H%M%S}.csv")

    s = run(args.keyword, args.pages, args.db, csv_path, args.cdp, capture=capture)
    print(f"{s['items']} unique products from {s['pages_ok']}/{s['pages_requested']} pages "
          f"({s['duplicates_dropped']} duplicates dropped, {s['parse_failures']} unreadable).")
    if not s["items"]:
        print("Nothing captured: nothing was saved.")
        return 1
    print(f"Run {s['run_id']} saved to {args.db}, CSV at {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
