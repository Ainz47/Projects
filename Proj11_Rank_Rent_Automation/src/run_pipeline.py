"""
run_pipeline.py — Central Orchestrator (Main Entry Point)
rank_rent_automation | Rank and Rent SEO Pipeline

Usage:
    python src/run_pipeline.py

Reads source_fleet.csv, generates SEO content via Gemini 2.0 Flash,
and pushes draft pages to WordPress.
"""

import os
import sys
import json
import logging
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Path setup — allow imports from src/ when run from project root
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent))

from pipeline_processor import generate_seo_page, test_gemini_connection
from transformations import prepare_wp_content, slugify
from wp_importer import (
    test_wp_connection,
    get_or_create_parent_page,
    push_page_to_wordpress,
    update_parent_page_links,
)
from requests.auth import HTTPBasicAuth

load_dotenv()

# ---------------------------------------------------------------------------
# Logging Setup 
# ---------------------------------------------------------------------------
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
log_path = LOG_DIR / f"pipeline_run_{run_id}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.FileHandler(log_path, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

logger = logging.getLogger("orchestrator")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
WP_BASE       = os.getenv("WP_URL")
WP_AUTH       = HTTPBasicAuth(os.getenv("WP_USERNAME"), os.getenv("WP_APP_PASSWORD"))
INPUT_FILE    = os.getenv("INPUT_FILE", "source_fleet.csv")
PARENT_NAME   = os.getenv("PARENT_PAGE_NAME", "Michigan")
TARGET_STATE  = os.getenv("TARGET_STATE", "MI")
DATA_DIR      = Path(__file__).parent.parent / "data"
USE_CACHED_GEMINI = os.getenv("USE_CACHED_GEMINI", "false").lower() in {"1", "true", "yes"}
GEMINI_CALL_DELAY_SECONDS = float(os.getenv("GEMINI_CALL_DELAY_SECONDS", "3"))

SEPARATOR = "=" * 65


def load_source_fleet(filename: str) -> pd.DataFrame:
    """Loads and validates the keyword/city CSV."""
    filepath = DATA_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(f"❌ Source file not found: {filepath}")

    df = pd.read_csv(filepath)
    required_cols = {"keyword", "city", "state"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"❌ Missing columns in CSV: {missing}")

    print(f"📋 Loaded {len(df)} row(s) from {filename}")
    return df


def load_cached_gemini_payload(keyword: str, city: str) -> dict | None:
    """Loads the newest audit JSON for a keyword/city pair when demoing without API calls."""
    slug = slugify(f"{keyword} {city}")
    matches = sorted(LOG_DIR.glob(f"{slug}_*.json"), reverse=True)
    for path in matches:
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            if "_meta" in payload:
                print(f"♻️  Using cached Gemini payload: {path.name}")
                return payload
        except (OSError, json.JSONDecodeError):
            logger.warning(f"⚠️  Could not load cached payload: {path.name}")
    return None


def run_single_entry(row: pd.Series, parent_id: int, sibling_pages: list) -> dict:
    """
    Processes one row from the fleet CSV through the full pipeline:
    1. Generate content (Gemini)
    2. Transform & apply SEO logic
    3. Push page to WP
    """
    keyword = row["keyword"]
    city    = row["city"]
    state   = row["state"]

    print(f"\n{SEPARATOR}")
    print(f"🚀 Processing: {keyword} | {city}, {state}")
    print(SEPARATOR)

    result = {
        "keyword": keyword,
        "city": city,
        "status": "pending",
        "wp_page_id": None,
        "wp_page_link": None,
    }

    try:
        # --- Step 1: AI Content Generation ---
        gemini_payload = load_cached_gemini_payload(keyword, city) if USE_CACHED_GEMINI else None
        if gemini_payload is None:
            gemini_payload = generate_seo_page(keyword, city, state)

        # --- Step 2: SEO Transformations ---
        related_pages = [
            page for page in sibling_pages
            if not (
                page.get("keyword") == keyword
                and page.get("city") == city
            )
        ]
        wp_payload = prepare_wp_content(gemini_payload, related_pages)

        # --- Step 3: Push to WordPress ---
        wp_result = push_page_to_wordpress(
            wp_payload,
            parent_id=parent_id,
            featured_media_id=None
        )

        if wp_result:
            result["status"]       = "success"
            result["wp_page_id"]   = wp_result.get("id")
            result["wp_page_link"] = wp_result.get("link")
        else:
            result["status"] = "wp_push_failed"

        # Save raw Gemini output for audit
        audit_path = LOG_DIR / f"{slugify(keyword + ' ' + city)}_{run_id}.json"
        with open(audit_path, "w") as f:
            json.dump(gemini_payload, f, indent=2)
        print(f"💾 JSON audit log saved: {audit_path.name}")

    except Exception as e:
        logger.exception(f"❌ Pipeline failed for '{keyword}' in {city}: {e}")
        result["status"] = f"error: {str(e)}"

    return result


def main():
    print(f"\n{'=' * 65}")
    print("  🏗️  rank_rent_automation — SEO Pipeline")
    print(f"  Run ID: {run_id}")
    print(f"{'=' * 65}\n")

    # --- Load Fleet Data ---
    df = load_source_fleet(INPUT_FILE)

    # --- Pre-flight: Gemini Connection Test ---
    if not USE_CACHED_GEMINI and not test_gemini_connection():
        print("❌ Aborting before WordPress writes. Check Gemini billing/key/model, then rerun.")
        sys.exit(1)

    # --- Pre-flight: WP Connection Test ---
    if not test_wp_connection():
        print("❌ Aborting: WordPress connection failed. Check .env credentials.")
        sys.exit(1)

    # --- Get / Create Parent Page ---
    parent_id = get_or_create_parent_page(PARENT_NAME, TARGET_STATE)
    print(f"📁 Parent Page ID: {parent_id}\n")

    # --- Build Sibling Page List (for internal linking) ---
    sibling_pages = [
        {
            "keyword": row["keyword"],
            "city":    row["city"],
            "slug":    slugify(f"{row['keyword']} {row['city']}"),
        }
        for _, row in df.iterrows()
    ]

    # --- Main Processing Loop ---
    run_results = []
    for index, row in df.iterrows():
        result = run_single_entry(row, parent_id, sibling_pages)
        run_results.append(result)
        if not USE_CACHED_GEMINI and index < len(df) - 1:
            print(f"⏳ Waiting {GEMINI_CALL_DELAY_SECONDS:g}s before next Gemini call...")
            time.sleep(GEMINI_CALL_DELAY_SECONDS)

    # --- Summary Report ---
    print(f"\n{SEPARATOR}")
    print("  📊 PIPELINE SUMMARY")
    print(SEPARATOR)
    success  = [r for r in run_results if r["status"] == "success"]
    failures = [r for r in run_results if r["status"] != "success"]

    print(f"  ✅ Succeeded: {len(success)}/{len(run_results)}")
    for r in success:
        print(f"     └─ {r['keyword']} | {r['city']} → WP ID: {r['wp_page_id']}")

    if failures:
        print(f"\n  ❌ Failed: {len(failures)}/{len(run_results)}")
        for r in failures:
            print(f"     └─ {r['keyword']} | {r['city']} → {r['status']}")

    if success:
        update_parent_page_links(parent_id, PARENT_NAME, TARGET_STATE, success)

    # Save summary JSON
    summary_path = LOG_DIR / f"run_summary_{run_id}.json"
    with open(summary_path, "w") as f:
        json.dump(run_results, f, indent=2)
    print(f"\n💾 Run summary saved: {summary_path}")
    print(f"📝 Full log: {log_path}")
    print(f"\n{'=' * 65}")
    print("  🎯 Pipeline execution complete.")
    print(f"{'=' * 65}\n")


if __name__ == "__main__":
    main()
