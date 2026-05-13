"""
main_claude.py — Main Orchestrator for WebPulse Lead Generation (Claude Version)
Scrapes Google Maps, evaluates websites, generates leads.
"""

import os
import sys
import json
import logging
import asyncio
from datetime import datetime
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
# Path setup
sys.path.insert(0, str(Path(__file__).parent))

from scraper import scrape_leads
from evaluator import evaluate_website, APILimitError


# Logging Setup
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
log_path = LOG_DIR / f"pipeline_run_claude_{run_id}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.FileHandler(log_path),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

async def run_pipeline(category: str, city: str, state: str, max_results: int = 10):
    """
    Main pipeline: scrape -> evaluate -> save leads
    """
    logger.info(f"Starting CLAUDE pipeline for {category} in {city}, {state}")

    # Step 1: Scrape leads
    logger.info("Scraping Google Maps...")
    leads = await scrape_leads(category, city, state, max_results)
    logger.info(f"Scraped {len(leads)} leads")

    # Step 2: Evaluate websites
    leads_with_websites = [lead for lead in leads if lead.get('website')]
    leads_without_websites = [lead for lead in leads if not lead.get('website')]

    logger.info(f"Evaluating {len(leads_with_websites)} websites concurrently...")
    evaluation_tasks = [evaluate_website(lead['website']) for lead in leads_with_websites]
    
    try:
        evaluations = await asyncio.gather(*evaluation_tasks, return_exceptions=True)
    except APILimitError as e:
        logger.critical(f"Claude API limit exceeded: {e}")
        logger.critical("Exiting pipeline due to API limit.")
        sys.exit(1)

    evaluated_leads = []
    # Process successful evaluations
    for lead, evaluation in zip(leads_with_websites, evaluations):
        # Check if evaluation is an APILimitError
        if isinstance(evaluation, APILimitError):
            logger.critical(f"Claude API limit exceeded during evaluation: {evaluation}")
            logger.critical("Exiting pipeline due to API limit.")
            sys.exit(1)
            
        if isinstance(evaluation, Exception):
            logger.error(f"Evaluation for {lead['website']} failed with an exception: {evaluation}")
            lead.update({
                "has_website": True,
                "mobile_friendly": False,
                "modern_design": False,
                "overall_quality_score": 1,
                "needs_redesign": True,
                "summary": f"Critical evaluation error: {str(evaluation)[:100]}"
            })
        else:
            lead.update(evaluation)
            lead['has_website'] = True
        evaluated_leads.append(lead)

    # Process leads that had no website to begin with
    for lead in leads_without_websites:
        lead.update({"has_website": False, "mobile_friendly": False, "modern_design": False, "overall_quality_score": 0, "needs_redesign": True, "summary": "No website"})
        evaluated_leads.append(lead)

    logger.info("All evaluations complete.")

    # Step 3: Save to CSV and JSON
    output_dir = Path(__file__).parent.parent / "data"
    output_dir.mkdir(exist_ok=True)
    
    # Save CSV
    df = pd.DataFrame(evaluated_leads)
    output_file = output_dir / f"leads_claude_{category.replace(' ', '_')}_{city}_{state}_{run_id}.csv"
    df.to_csv(output_file, index=False)
    logger.info(f"Saved {len(evaluated_leads)} evaluated leads to {output_file}")
    
    # Save structured JSON for demo
    json_output = {
        "run_id": run_id,
        "model": "claude",
        "category": category,
        "city": city,
        "state": state,
        "total_scraped": len(leads),
        "evaluated_leads": len(evaluated_leads),
        "leads": [
            {
                "name": lead.get('name', ''),
                "website": lead.get('website', ''),
                "phone": lead.get('phone', ''),
                "rating": lead.get('rating', ''),
                "mobile_friendly": lead.get('mobile_friendly', False),
                "modern_design": lead.get('modern_design', False),
                "overall_quality_score": lead.get('overall_quality_score', 0),
                "needs_redesign": lead.get('needs_redesign', False),
                "summary": lead.get('summary', '')
            }
            for lead in evaluated_leads
        ]
    }
    json_file = output_dir / f"leads_claude_{category.replace(' ', '_')}_{city}_{state}_{run_id}.json"
    with open(json_file, 'w') as f:
        json.dump(json_output, f, indent=2)
    logger.info(f"Saved structured JSON output to {json_file}")

    # Log summary
    summary = {
        "run_id": run_id,
        "model": "claude",
        "category": category,
        "city": city,
        "state": state,
        "scraped": len(leads),
        "evaluated": len(evaluated_leads),
        "timestamp": datetime.now().isoformat()
    }
    summary_file = LOG_DIR / f"run_summary_claude_{run_id}.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)

    logger.info("Pipeline completed")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="WebPulse Lead Generation Pipeline (Claude Version)")
    parser.add_argument("category", help="Business category, e.g., 'bathroom remodeler'")
    parser.add_argument("city", help="City, e.g., 'Farmington Hills'")
    parser.add_argument("state", help="State, e.g., 'MI'")
    parser.add_argument("--max_results", type=int, default=10, help="Max leads to scrape")
    args = parser.parse_args()

    asyncio.run(run_pipeline(args.category, args.city, args.state, args.max_results))