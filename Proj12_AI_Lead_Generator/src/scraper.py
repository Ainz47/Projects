"""
scraper.py — Google Maps Scraper using Apify
Scrapes business leads from Google Maps using Apify's Google Maps Scraper actor.
"""

import os
import json
import logging
import asyncio
from apify_client import ApifyClientAsync
from typing import List, Dict

logger = logging.getLogger(__name__)

async def scrape_leads(category: str, city: str, state: str, max_results: int = 10) -> List[Dict]:
    """
    Scrape business leads using Apify Google Maps Scraper.
    Fails if APIFY_API_TOKEN is not set in the environment.
    """
    api_token = os.getenv("APIFY_API_TOKEN")
    if not api_token:
        logger.error("APIFY_API_TOKEN is not configured. Please set it in your .env file.")
        raise ValueError("Apify client is not initialized. API token is missing.")

    client = ApifyClientAsync(api_token)
    run_client = None
    try:
        run_input = {
            "searchStringsArray": [f"{category} in {city}, {state}"],
            "location": f"{city}, {state}",
            "maxResults": max_results,
            "language": "en",
            "maxReviews": 0,
            "reviewsSort": "newest"
        }
        # Start the actor, but do not wait for it to finish
        run = await client.actor("compass/crawler-google-places").start(run_input=run_input)
        logger.info(f"Apify run started: {run['id']}")
        run_client = client.run(run['id'])

        # Wait for the run to start before streaming results to avoid a race condition
        logger.info("Waiting for Apify run to start...")
        while True:
            run_detail = await run_client.get()
            status = run_detail.get('status')
            if status in ['RUNNING', 'SUCCEEDED', 'FAILED', 'TIMED_OUT', 'ABORTED']:
                logger.info(f"Apify run has started with status: {status}")
                break
            await asyncio.sleep(1)

        businesses = []
        seen_places = set()

        logger.info("Monitoring dataset for new leads...")
        while True:
            run_detail = await run_client.get()
            status = run_detail.get('status')

            # Stream results from the dataset
            async for item in run_client.dataset().iterate_items():
                place_id = item.get("placeId") or item.get("title")
                if not place_id or place_id in seen_places:
                    continue
                seen_places.add(place_id)

                # Only process items that have a website
                if not item.get("website"):
                    continue

                business = {
                    "name": item.get("title", ""),
                    "address": item.get("address", ""),
                    "phone": item.get("phone", ""),
                    "website": item.get("website", ""),
                    "rating": str(item.get("rating", "")),
                    "reviews": str(item.get("reviewsCount", "")),
                    "category": category,
                    "city": city,
                    "state": state
                }
                businesses.append(business)

                if len(businesses) >= max_results:
                    break

            # If we have enough results, abort the run on Apify's side and stop collecting
            if len(businesses) >= max_results:
                logger.info(f"Reached {max_results} results with websites. Aborting Apify run...")
                await run_client.abort()
                break

            if status in ['SUCCEEDED', 'FAILED', 'TIMED_OUT', 'ABORTED']:
                logger.info(f"Apify run finished with status: {status}")
                break

            # Wait a few seconds before checking for new items again
            await asyncio.sleep(3)

        logger.info(f"Finished scraping with {len(businesses)} items from Apify.")
        return businesses

    except Exception as e:
        logger.error(f"Error during scraping with Apify: {e}")
        # Ensure the run is aborted if an error occurs mid-stream
        if run_client:
            try:
                await run_client.abort()
                logger.info("Aborted Apify run due to an exception.")
            except Exception as abort_exc:
                logger.error(f"Failed to abort Apify run after an error: {abort_exc}")
        return []