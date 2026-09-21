# Directory ETL Pipeline (Google Maps -> Gemini -> WordPress)

A three-phase ETL pipeline: scrape a business listing off Google Maps with Playwright, enrich it with the Gemini API (text description, image quality gates, AI image generation), and push the result into a WordPress REST API as a custom post type. Built as a prototype against a single test business ("Allegory", a restaurant in Naperville, IL), not run against a live WordPress site.

Architecture diagram: [docs/architecture-diagram.md](./docs/architecture-diagram.md) | [docs/architecture-diagram.svg](./docs/architecture-diagram.svg) | [docs/architecture-diagram.png](./docs/architecture-diagram.png)

## What's verified

- **The scraper is real and targets live Google Maps**, not a fixture (`scraper.py`, Playwright against `google.com/maps/search/...`, DOM selectors for the cover photo and address). The one demo run on record (`pipeline_demonstration_output.json`) has a real address string scraped off a live page, complete with a stray private-use Unicode icon glyph sitting in front of the street address, the kind of artifact a real scrape produces and a mock never would.
- **The idempotency check is real**: `wp_importer.py`'s `ingest_to_wordpress` queries the target endpoint by `place_id` meta before deciding create vs. update. `place_id` is `md5(name + address)` (`pipeline_processor.py`), matching what the old README claimed.
- **The quality gates are real code, not aspirational**: `transformations.py` runs a Gemini Vision relevance check (rejects menus, crowds, parking lots) and a local resolution check (PIL, threshold 1200px wide) before deciding whether an image needs AI enhancement.
- **The fallback logic is real and was specifically exercised**: `demonstrate_enhancement_fallback.py` exists to force the AI-generation failure path (its own comment: "This is expected to fail on a free tier, triggering the except block") and confirm the pipeline still completes and writes a JSON payload. That's a genuine resilience test, not a happy-path demo pretending to be one.
- **WordPress ingestion was tested against `mock_wp.py`** (a small FastAPI stand-in that tracks place_id -> post_id in memory), not against a real WordPress install. There's no evidence in this repo of a live WP CMS ever receiving this data.

## What's NOT verified (and one real finding)

- **The demo gallery images are not AI-generated, despite the filenames.** `demo_allegory_exterior_ai_hero.jpg` and `demo_allegory_interior_ai_hero.jpg` are byte-for-byte identical (same MD5). Tracing why: `demonstrate_enhancement_fallback.py` calls the demo image generator twice, once for "exterior," once for "interior dining room," and both calls hit the expected Gemini quota failure and fall back to writing a copy of the single scraped cover photo. So both files are the same real, non-AI exterior photo; the "interior" one is mislabeled. This is the fallback path working as designed, not a bug in the fallback logic, but it means there is no artifact anywhere in this repo showing the actual Gemini image-generation call succeeding.
- **"AI upscaling/enhancement" of low-res images is really full regeneration, not enhancement.** `image_generator.py`'s `enhance_scraped_image` docstring says it plainly: "This function does NOT use the input image_bytes; it generates a new image." A low-res scraped photo triggers a brand-new Gemini image generated from a text description of the business, not an upscale of the original pixels. The old README's "AI upscaling/enhancement process" phrasing overstates what actually happens.
- **The one recorded pipeline run also shows the Gemini text-generation fallback firing.** `pipeline_demonstration_output.json`'s `content` field reads "A premium local destination offering an unforgettable experience." That's the literal hardcoded fallback string in `pipeline_processor.py`'s `generate_unique_story`, used when the Gemini call raises. So on this run, none of the three Gemini calls (story text, image generation x2) produced real output; only the Vision relevance check may have (it defaults to `True` on error too, so even that's not confirmed either way from the artifact).
- **A `supabase/` directory sits in this project's root** (config.toml, a full CLI scaffold) but nothing in any `.py` file imports or references it. It's dead scaffolding unrelated to the pipeline, not a real integration.
- The `amenities` field in every generated payload is a hardcoded list ("Outdoor Seating", "Craft Cocktails", "Farm-to-Table"), not scraped or AI-derived. The old README didn't claim otherwise; noting it here for completeness.

## System Architecture

1. **Extraction:** Playwright scrapes name, address, and a cover photo URL from a Google Maps search result.
2. **Transformation:** Gemini generates a description; scraped images go through a relevance filter and a resolution gate, with low-res images routed to AI regeneration (see caveat above).
3. **Loading:** The structured payload and processed images post to a WordPress REST API, keyed by an MD5 `place_id` for idempotent create-or-update.

## Repository Structure

- `run_pipeline.py`: main orchestrator (happy path), imports `image_generator.py`.
- `demonstrate_enhancement_fallback.py`: forces the AI-failure path to prove the pipeline degrades gracefully; imports `image_generator_demo.py`, a variant that falls back to copying the original scraped image instead of a text placeholder.
- `scraper.py`: Playwright extraction from Google Maps.
- `pipeline_processor.py`: builds the `place_id`, calls Gemini for the description, structures the ACF schema.
- `transformations.py`: relevance filter (Gemini Vision) and resolution gate.
- `image_generator.py` / `image_generator_demo.py`: Gemini image generation, with the demo variant's failure-path fallback described above.
- `wp_importer.py`: media upload and idempotent create/update against the WP REST API.
- `mock_wp.py`: FastAPI stand-in for WordPress, used for all ingestion testing so far.
- `check_models.py`: lists Gemini models available to the configured API key.

## Setup & Installation

```bash
pip install requests python-dotenv playwright google-genai pillow fastapi uvicorn
playwright install chromium
```

Create a `.env` in the project root (see `.env.sample`):

```env
GEMINI_API_KEY=your_gemini_api_key_here
WP_BASE_URL=http://127.0.0.1:8000
WP_USERNAME=mock_admin
WP_APP_PASSWORD=mock_password
```

## Running It

**Happy path** (against the mock WP server):
```bash
uvicorn mock_wp:app --reload
python run_pipeline.py
```

**Resilience demo** (forces the AI-generation failure path and shows the fallback):
```bash
uvicorn mock_wp:app --reload
python demonstrate_enhancement_fallback.py
```
