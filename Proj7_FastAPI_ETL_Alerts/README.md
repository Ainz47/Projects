# FastAPI ETL Alerts

A FastAPI microservice that takes daily sales and labor webhooks from two restaurant systems (modeled on Toast POS and 7shifts), computes Cost Per Labor Hour and Labor % of Sales, stores the result in Supabase, and posts a Discord/Slack webhook alert when labor cost crosses 25% of sales.

## What it does

Two POST endpoints, `/webhook/sales` and `/webhook/labor`, each write their payload to a `daily_metrics` table in Supabase (keyed on `store_id` + `date`) and hand off to a FastAPI `BackgroundTasks` job so the webhook caller gets an immediate response instead of waiting on the calculation. That background job re-reads the row; once both a sales figure and a labor figure exist for the same store and date, it runs `transformations.py`'s math (CPLH = labor cost / labor hours, labor % = labor cost / gross sales * 100, both guarded against a zero denominator), writes the computed metrics back, and fires a Discord-formatted webhook alert if labor % is over 25.

## What's verified

Read through all five source files (`main.py`, `database.py`, `transformations.py`, `notifier.py`, `mock_data_sender.py`) to confirm the architecture actually works as described: `BackgroundTasks` is used correctly (the webhook response returns before the metrics job runs), the math in `transformations.py` is correct for the two formulas above, and the alert payload/threshold logic in `notifier.py` matches what's described here.

There is a `mock_data_sender.py` script that fires one hardcoded sales payload and one hardcoded labor payload (a single fictional `Store_104`) at a locally running server. That's the only way this has ever been exercised: nothing here has been run against real Toast POS or 7shifts data, or against a real Supabase instance as part of writing this README.

**The "idempotent upsert" claim in earlier documentation for this project overstates what `database.py` actually does.** It doesn't use Supabase's native upsert; the code's own comment says so ("for this MVP, we will just use a simple insert/update approach"). Instead it does a manual read-then-write: check whether a row exists for that store and date, then either `UPDATE` or `INSERT`. That produces the same end result as a real upsert when calls happen one at a time, but it's not atomic: two webhooks for the same store and date arriving close together could both read "no existing row" and both try to insert, which either fails or duplicates depending on whether the table has a unique constraint on `(store_id, date)` (not something checked here, since there's no schema file in this repo to read).

## What is NOT verified

- No automated tests and no CI for this project (only Proj14-19 are wired into `.github/workflows/tests.yml`).
- Never run against real POS or scheduling data, only the one hardcoded mock payload described above.
- Whether the Supabase project behind this ever existed live, or still does, isn't something this README confirms.
- The race condition described above has not been reproduced; it's a read of the code, not an observed failure.

## Stack

Python · FastAPI · Pydantic · Supabase (PostgreSQL) · Discord/Slack webhooks

## Project structure

```text
main.py               FastAPI app: the two webhook routes and the background orchestrator
database.py           Supabase client, read-then-write upsert-style storage
transformations.py    CPLH and labor % math, isolated from the API and storage code
notifier.py           Formats and sends the Discord/Slack alert
mock_data_sender.py   Fires one hardcoded sales + labor payload at a local server for a manual smoke test
docs/architecture-diagram.{md,svg,png}
```

`.env.sample` documents the two required variables (`SUPABASE_URL`, `SUPABASE_KEY`) plus `ALERT_WEBHOOK_URL`; there's no code here to read them from anywhere else.

## Running it locally

```bash
pip install fastapi uvicorn supabase python-dotenv requests pydantic
uvicorn main:app --reload
```

In a second terminal, with a real `.env` populated:

```bash
python mock_data_sender.py
```

This fires the one hardcoded sales payload, waits 3 seconds, then fires the one hardcoded labor payload, and prints the server's HTTP response for each. Since the mock labor % works out above 25% for the hardcoded numbers, a successful run should also produce a webhook alert if `ALERT_WEBHOOK_URL` is set.
