"""
demo.py — WebPulse micro-demo harness

This script scrapes a small batch of Google Maps leads, evaluates each lead's website
with either Gemini or Claude, and writes a structured JSON report for demo review.
"""

import os
import sys
import json
import logging
import argparse
import asyncio
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from scraper import scrape_leads
from evaluator import evaluate_website as evaluate_claude, APILimitError
from evaluator_gemini import evaluate_website as evaluate_gemini

LOG_DIR = Path(__file__).parent.parent / "logs"
DATA_DIR = Path(__file__).parent.parent / "data"
LOG_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def resolve_mode(requested_mode: str) -> str:
    if requested_mode in ["gemini", "claude"]:
        return requested_mode

    gemini_key = os.getenv("GEMINI_API_KEY")
    claude_key = os.getenv("ANTHROPIC_API_KEY")
    if gemini_key:
        return "gemini"
    if claude_key:
        return "claude"

    raise ValueError("No AI mode selected and no Gemini or Anthropic API key is configured.")


def get_evaluator(mode: str):
    if mode == "gemini":
        return evaluate_gemini
    return evaluate_claude


async def run_demo(category: str, city: str, state: str, max_results: int, mode: str):
    mode = resolve_mode(mode)
    evaluator = get_evaluator(mode)
    logger.info(f"Demo mode: {mode.upper()}")

    demo_leads = []
    total_scraped = 0

    # Keep scraping until we have enough successful evaluations
    while len(demo_leads) < max_results:
        logger.info(f"Scraping batch for {category} (need {max_results - len(demo_leads)} more successful leads)...")
        leads = await scrape_leads(category, city, state, max_results)
        
        if not leads:
            logger.warning("No leads were scraped in this batch. Please check your APIFY_API_TOKEN and query settings.")
            break

        total_scraped += len(leads)
        logger.info(f"Scraped {len(leads)} lead(s) in this batch (total: {total_scraped}).")

        leads_with_websites = [lead for lead in leads if lead.get("website")]
        if not leads_with_websites:
            logger.warning("No scraped leads contain a website URL to evaluate.")
            continue

        logger.info(f"Evaluating {len(leads_with_websites)} website(s) with {mode.upper()}...")
        tasks = [evaluator(lead["website"]) for lead in leads_with_websites]
        
        try:
            evaluations = await asyncio.gather(*tasks, return_exceptions=True)
        except APILimitError as e:
            logger.critical(f"API limit exceeded: {e}")
            logger.critical("Exiting demo due to API limit.")
            sys.exit(1)

        for lead, evaluation in zip(leads_with_websites, evaluations):
            if len(demo_leads) >= max_results:
                break
            
            # Handle APILimitError from individual tasks
            if isinstance(evaluation, APILimitError):
                logger.critical(f"API limit exceeded during evaluation: {evaluation}")
                logger.critical("Exiting demo due to API limit.")
                sys.exit(1)
                
            if isinstance(evaluation, Exception):
                logger.warning(f"Evaluation failed for {lead['website']}: {evaluation}")
                continue
            
            # Filter out evaluations with error markers
            if evaluation.get("summary", "").startswith("Evaluation failed") or evaluation.get("summary", "") == "Could not fetch or parse website content.":
                logger.warning(f"Skipping lead {lead['website']}: {evaluation.get('summary', '')[:80]}")
                continue
            
            lead.update(evaluation)
            lead["has_website"] = True
            demo_leads.append(lead)

    logger.info(f"Successfully gathered {len(demo_leads)} qualified lead(s).")

    summary = {
        "run_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "model": mode,
        "category": category,
        "city": city,
        "state": state,
        "total_scraped": len(demo_leads),
        "evaluated_leads": len(demo_leads),
        "timestamp": datetime.now().isoformat(),
        "leads": demo_leads,
    }

    file_name = f"demo_{mode}_{category.replace(' ', '_')}_{city.replace(' ', '_')}_{state}_{summary['run_id']}.json"
    output_path = DATA_DIR / file_name
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    logger.info(f"Demo output saved to: {output_path}")
    logger.info("Demo completed successfully.")
    print(json.dumps({
        "run_id": summary["run_id"],
        "model": summary["model"],
        "scraped": summary["total_scraped"],
        "evaluated": summary["evaluated_leads"],
        "output": str(output_path)
    }, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a WebPulse micro-demo for lead scraping and website evaluation.")
    parser.add_argument("category", help="Business category, e.g. 'bathroom remodeler'")
    parser.add_argument("city", help="City, e.g. 'Farmington Hills'")
    parser.add_argument("state", help="State, e.g. 'MI'")
    parser.add_argument("--max_results", type=int, default=5, help="Max number of leads to scrape")
    parser.add_argument("--mode", default="auto", choices=["auto", "gemini", "claude"], help="AI mode to use")
    args = parser.parse_args()

    asyncio.run(run_demo(args.category, args.city, args.state, args.max_results, args.mode))
