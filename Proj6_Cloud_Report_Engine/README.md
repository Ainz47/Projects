# Proj6: Cloud Report Engine

A small backend pipeline that takes quiz-style lead data, scores it, saves the result to Supabase, and renders a branded PDF report with Jinja2 and WeasyPrint. Built as a prototype for a lead-generation "scorecard" funnel, not a deployed service.

## What it does

```
mock lead + quiz scores (hardcoded in main.py)
  -> engine.py sums the category scores into a total, assigns a tier, flags growth leaks
    -> db_client.py inserts business_name/email/score/tier into a Supabase "leads" table
      -> pdf_generator.py renders templates/report.html with Jinja2 and writes a PDF via WeasyPrint
```

`main.py` does not receive a real HTTP request. `run_pipeline()` calls `load_mock_payload()`, which returns one hardcoded lead (Apex Engineering Group) and a fixed set of quiz scores. There is no FastAPI route, no webhook listener, and no frontend in this repo. The "accepts JSON from a frontend SPA" idea is the intended shape of the input, not something wired up here.

Scoring, in `engine.py`: the four quiz categories (`local_seo`, `paid_ads`, `website_speed`, `reputation`) are summed directly into `final_score` (no normalization despite the 0-100 framing, so a caller supplying scores that sum above 100 would just get a score above 100). Tier is `Dominant` at 80+, `Contender` at 50+, else `Beginner`. Three of the four categories (not `website_speed`) each have a threshold that appends a canned "growth leak" string if the category is low.

## What's verified

- The pipeline has actually run and produced real output: `Sample_Dominance_Report.pdf` (committed) and `Apex_Engineering_Group_Report.pdf` (present locally, not committed) are both real PDFs, not placeholders. Opened both: same content, "Dominance Scorecard Playbook" header, "Prepared for: Apex Engineering Group," a highlighted "Score: 62/100" / "Market Tier: Contender" box, and a bulleted "Critical Growth Leaks Identified" list with all three leak strings from `engine.py`.
- That score checks out against the code: `main.py`'s mock scores are `local_seo=12, paid_ads=10, website_speed=22, reputation=18`, which sum to 62. 62 falls in the `Contender` band (50-79), and all three leak conditions in `engine.py` trigger at those values (12<15, 10<15, 18<20) - matching exactly what's in the PDF. So the scoring logic and the PDF template are confirmed to work together, at least for this one input.
- `pdf_generator.py` reads `templates/report.html` (a real Jinja2 template with `{{ business_name }}`, `{{ score }}`, `{{ tier }}`, and a `{% for leak in leaks %}` loop) and calls WeasyPrint's `HTML(string=...).write_pdf(...)`. The rendered PDF's layout (blue heading, gray score box, red leak list) matches the template's inline CSS.
- `db_client.py` uses the real `supabase-py` client (`create_client`, `.table("leads").insert(...)`) with `SUPABASE_URL`/`SUPABASE_KEY` loaded via `python-dotenv`. The insert is wrapped in try/except and `main.py` also wraps the call in try/except, so the code is written to let the PDF still generate even if the Supabase write fails.
- `.env.sample` documents the two required variables; the real `.env` is untracked (matches the root `.gitignore`'s `.env`/`*.env` patterns) and not read here.

## Not verified

- No automated tests and no CI for this project (checked: no test files, no workflow YAML anywhere in this folder).
- Whether the Supabase project behind `db_client.py` is still live or reachable is unknown - not checked here, per instructions not to hit it.
- The `save_lead_to_db` insert has never been confirmed against an actual Supabase schema in this session; the payload's column names (`business_name`, `email`, `score`, `tier`) are assumed correct, not checked against a live table.
- Only ever exercised with the one hardcoded mock lead. No input validation exists (e.g. missing `scores` keys, scores that don't sum to <=100, non-numeric values) - none of that is tested or guarded against in `engine.py`.
- No FastAPI route, Lambda handler, or any other HTTP entry point exists in this repo. "Microservice ready" in the old README meant "modularized enough that someone could wrap it," not that a route exists.
- No `requirements.txt` in the repo; the install instructions below are inferred from the actual imports (`weasyprint`, `supabase`, `python-dotenv`, `jinja2`).

## Project structure

```
Proj6_Cloud_Report_Engine/
  main.py                          orchestrator: builds the mock payload, calls the three modules in order
  engine.py                        scoring and tier/leak logic (calculate_dominance)
  db_client.py                     Supabase insert (save_lead_to_db)
  pdf_generator.py                 Jinja2 render + WeasyPrint PDF write (generate_pdf)
  templates/report.html            the report layout
  .env.sample                      documents SUPABASE_URL / SUPABASE_KEY
  Sample_Dominance_Report.pdf      committed example output
  Apex_Engineering_Group_Report.pdf   local output from running main.py (not committed)
```

## Setup

1. `pip install weasyprint supabase python-dotenv jinja2`
2. Copy `.env.sample` to `.env` and fill in a real Supabase URL and key.
3. `python main.py` - runs the mock pipeline end to end: prints progress, attempts the Supabase insert, and writes `Apex_Engineering_Group_Report.pdf` to the project root.

## Known limitations

- Hardcoded single mock lead in `main.py`; nothing here accepts real input yet.
- No normalization or validation on quiz scores.
- `website_speed` is scored but has no leak rule tied to it.
- PDF output filename is derived from `business_name` with spaces replaced by underscores, and always written to the current working directory - no output path configuration.
- Supabase failures are caught and logged but otherwise silent; the pipeline continues to PDF generation regardless of whether the DB write succeeded.
