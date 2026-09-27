"""Batch pipeline: Google Maps -> Gemini -> WordPress, one create-or-update per business.

    py run_pipeline.py --input businesses.json [--gallery]
"""
import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

import requests

from image_generator import generate_restaurant_image
from pipeline_processor import build_listing, generate_unique_story
from scraper import scrape_google_maps_data
from transformations import process_and_filter_image
from wp_importer import WordPressClient

GALLERY_SHOTS = ("exterior", "interior dining room")


def download_image(url: str) -> bytes | None:
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        return r.content
    except requests.RequestException as e:
        print(f"Photo download failed: {e}")
        return None


@dataclass
class Steps:
    scrape: Callable = scrape_google_maps_data
    story: Callable = generate_unique_story
    fetch: Callable = download_image
    gate: Callable = process_and_filter_image
    gallery: Callable = generate_restaurant_image


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def process_business(biz: dict, wp: WordPressClient, steps: Steps, gallery: bool = False) -> dict:
    def step(msg):
        print(f"[{biz['name']}] {msg}", flush=True)

    step("scraping Google Maps")
    raw = steps.scrape(biz["name"], biz["location"], biz["category"])
    if not raw:
        return {"business": biz["name"], "status": "not_found"}
    step("writing the story")
    story, ai_story = steps.story(raw["name"], raw["category"], raw["city"])
    listing = build_listing(raw, story)
    existing = wp.find_listing(listing["place_id"])

    featured, image = None, "none"
    if existing and existing["featured_media"]:
        featured, image = existing["featured_media"], "reused"
    else:
        step("checking the photo")
        photo = steps.fetch(raw["image_url"])
        publishable = steps.gate(photo, raw["category"], raw["name"]) if photo else None
        if publishable:
            featured, image = wp.upload_media(publishable, f"{_slug(listing['title'])}.jpg"), "uploaded"

    gallery_ids = []
    if gallery and not existing:
        for shot in GALLERY_SHOTS:
            step(f"generating the {shot} image")
            img = steps.gallery(listing["title"], shot, raw["city"])
            if img:
                gallery_ids.append(wp.upload_media(img, f"{_slug(listing['title'])}-{_slug(shot)}.jpg"))

    step("saving to WordPress")
    action, post_id = wp.save_listing(listing, post_id=existing["id"] if existing else None,
                                      featured_media=featured, gallery_ids=gallery_ids)
    return {"business": biz["name"], "status": action, "post_id": post_id, "place_id": listing["place_id"],
            "ai_story": ai_story, "image": image, "gallery": len(gallery_ids)}


def run(businesses: list[dict], wp: WordPressClient, steps: Steps | None = None, gallery: bool = False,
        report_path: Path | None = None) -> list[dict]:
    """Processes every business; one failure is recorded and the batch carries on.
    With report_path, each result is appended as a JSON line as soon as it's known."""
    steps = steps or Steps()
    report = None
    if report_path:
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        report = open(report_path, "a", encoding="utf-8")
    results = []
    try:
        for biz in businesses:
            try:
                result = process_business(biz, wp, steps, gallery)
            except Exception as e:
                result = {"business": biz["name"], "status": "error", "error": str(e)}
            results.append(result)
            print(result)
            if report:
                report.write(json.dumps(result) + "\n")
                report.flush()
    finally:
        if report:
            report.close()
    return results


def load_businesses(path) -> list[dict]:
    businesses = json.loads(Path(path).read_text(encoding="utf-8"))
    for biz in businesses:
        missing = {"name", "location", "category"} - biz.keys()
        if missing:
            raise ValueError(f"{biz.get('name', biz)} is missing {', '.join(sorted(missing))}")
    return businesses


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", default="businesses.json")
    ap.add_argument("--gallery", action="store_true", help="also generate 2 AI gallery images per new listing (needs Imagen access)")
    ap.add_argument("--report", help="JSONL report path (default runs/run_<timestamp>.jsonl)")
    args = ap.parse_args(argv)
    report = Path(args.report or f"runs/run_{datetime.now():%Y%m%d_%H%M%S}.jsonl")
    results = run(load_businesses(args.input), WordPressClient.from_env(), gallery=args.gallery, report_path=report)
    failed = [r for r in results if r["status"] in ("error", "not_found")]
    print(f"{len(results) - len(failed)}/{len(results)} saved. Report: {report}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
