# WebPulse: AI Lead Generator for Web Services

A lead-generation pipeline for web design agencies: scrapes local service businesses from Google Maps via Apify, then has an LLM (Gemini or Claude) read each business's website text and score it for mobile-friendliness, design modernity, and overall quality. Two additional modules can turn a scored lead into a redesign preview and a cold email, but neither is wired into the pipeline that actually runs.

## What's verified

- **The scraper is real**: `scraper.py` uses `apify_client.ApifyClientAsync` against Apify's Google Maps Scraper actor, fails loudly if `APIFY_API_TOKEN` is missing, and polls the run until it has enough results with websites.
- **The evaluation is real and produces genuinely differentiated output**: `data/demo_gemini_bathroom_remodeler_Farmington_Hills_MI_20260512_170755.json` has 10 real Farmington Hills, MI businesses (real names, addresses, phone numbers) with per-site Gemini critiques that cite specific, plausible problems, e.g. "visible shortcodes and broken placeholder text" for one site, "severe keyword stuffing" for another. These read like a model that actually looked at each site's content, not templated filler.
- **Two working entry points exist** (`main.py` for Gemini, `main_claude.py` for Claude, plus `demo.py` which auto-picks a model), each doing scrape -> evaluate -> save to CSV/JSON, with a timestamped run summary written to `logs/`.

## What's NOT verified, and real corrections to the old README

- **The old README's architecture diagram and "Core Components" table described a different project.** They listed `demonstrate_enhancement_fallback.py`, `pipeline_processor.py`, `image_generator.py`, and `wp_importer.py`, none of which exist anywhere in this repo. Those are file names from the Proj9 WordPress pipeline; this rewrite replaces that section with the actual `src/` files (below).
- **"Enrichment" (redesign previews) and "Outreach" (personalized emails) are not part of the pipeline that runs.** `preview_generator.py` / `preview_generator_gemini.py` and `outreach.py` / `outreach_gemini.py` are real, working modules (Claude/Gemini calls with JSON-enforcing parsers), but nothing in `main.py`, `main_claude.py`, or `demo.py` imports or calls them. A grep across `src/` for their imports outside their own files confirms this: zero call sites. They're functional standalone pieces, not a wired step 3/4 of an automated workflow.
- **Website quality scoring evaluates 3 metrics, not the 4 the old README implied.** `evaluator_gemini.py`'s own prompt says "Focus on these 3 core metrics ONLY: Mobile Friendly, Modern Design, Overall Quality Score." There is no SEO evaluation anywhere in this codebase; the old README's "SEO fundamentals" claim doesn't correspond to anything in the code.
- **The mobile-friendliness and design checks have no visual signal at all.** `fetch_website_content()` does a plain `httpx` GET, parses with BeautifulSoup, strips every tag (`soup.stripped_strings`), and hands the model up to 8000 characters of bare text. There's no screenshot, no HTML/CSS inspection, no viewport meta tag check, no rendering of any kind anywhere in `src/` (confirmed by grep). "Mobile friendly: true/false" is an LLM's guess from text content alone, not a structural or visual test. Whether that guess is reliable is a real open question this repo doesn't answer.
- The demo output above has two businesses appearing twice ("Luxury Kitchen & Bath", "Gittleman Construction") with slightly different summaries each time. `demo.py` scrapes in batches until it hits `max_results` successful evaluations and doesn't dedupe across batches, so a business can be scraped and scored more than once in a single run.

## Architecture (corrected)

```
Google Maps (via Apify)
    |
scraper.py (extraction)
    |
evaluator.py / evaluator_gemini.py (text-only LLM scoring)
    |
data/leads_*.csv + data/leads_*.json (output)
```

`preview_generator.py`, `preview_generator_gemini.py`, `outreach.py`, and `outreach_gemini.py` exist alongside this pipeline as standalone, callable modules but are not invoked by it.

### Core Components (corrected)

| Module | Responsibility |
|--------|----------------|
| `scraper.py` | Apify Google Maps scraping |
| `evaluator.py` | Website scoring via Claude (fetch text, score 3 metrics) |
| `evaluator_gemini.py` | Same, via Gemini |
| `main.py` | Orchestrator: scrape -> evaluate -> CSV/JSON (Gemini) |
| `main_claude.py` | Same orchestrator, Claude |
| `demo.py` | Small-batch demo runner, auto-detects available model |
| `preview_generator.py` / `preview_generator_gemini.py` | Standalone: generates a redesign description and mockup HTML for a lead. Not called by any pipeline entry point. |
| `outreach.py` / `outreach_gemini.py` | Standalone: generates a personalized cold email from a lead + preview. Not called by any pipeline entry point. |

## Installation

```bash
pip install -r requirements.txt
cp .env.example .env
```

Set `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, and `APIFY_API_TOKEN`.

## Usage

```bash
python src/main.py "bathroom remodeler" "Farmington Hills" "MI" --max_results 10
python src/main_claude.py "plumber" "Chicago" "IL" --max_results 10
python src/demo.py "electrician" "Austin" "TX" --max_results 5 --mode auto
```

- Service category, city, and 2-letter state code are positional arguments.
- `--max_results`: number of leads to process.
- `demo.py`'s `--mode` picks `gemini`, `claude`, or `auto` (first available API key).

## Output

- `data/leads_<model>_<category>_<city>_<state>_<run_id>.csv` and matching `.json`: scraped leads with scores and summaries.
- `data/demo_<model>_..._<run_id>.json`: output from `demo.py`.
- `logs/`: a `pipeline_run_*.log` and a `run_summary_*.json` per run.

## Security Notes

- Never commit `.env` with real credentials (it's gitignored; only `.env.example` is tracked).
- API keys are read from environment variables at runtime.
