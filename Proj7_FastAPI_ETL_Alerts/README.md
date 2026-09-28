# Restaurant Labor Alerts (FastAPI webhooks -> Postgres -> Discord)

A FastAPI service that takes the daily sales webhook from a restaurant's POS (modeled on Toast) and the daily labor webhook from its scheduler (modeled on 7shifts), joins them per store and day, computes Cost Per Labor Hour and Labor % of Sales, stores the result in Postgres (Supabase), and posts one Discord alert when labor goes over 25% of sales.

Architecture diagram: [docs/architecture-diagram.md](./docs/architecture-diagram.md) | [docs/architecture-diagram.svg](./docs/architecture-diagram.svg) | [docs/architecture-diagram.png](./docs/architecture-diagram.png)

## What it does

The two systems don't talk to each other and don't arrive in a fixed order, so each webhook saves its half of the day and returns `202 Accepted` straight away. A background job then checks whether both halves are in. When they are, it computes the metrics, saves them, and alerts if labor is over the threshold.

The parts that make that safe to run against real webhook senders, which retry and re-deliver:

- **One row per store-day, written atomically.** `schema.sql` puts a unique constraint on `(store_id, date)` and every write is a Postgres `INSERT ... ON CONFLICT DO UPDATE` through Supabase's REST API. Each webhook only touches its own columns, so the sales webhook can't wipe the labor figures and two webhooks arriving together can't create two rows.
- **At most one alert per store-day.** The alert is claimed with a single conditional update (`alert_sent_at` set only where it's still empty). Re-delivered webhooks recompute the metrics but don't alert again. If Discord rejects the message, the claim is released so the next webhook for that day retries.
- **Zero isn't missing.** A day with zero sales is processed. Its labor % is recorded as undefined rather than 0%, since $800 of labor on no sales isn't "0% labor".
- **Authenticated webhooks.** Both need an `X-Webhook-Secret` header. A server started without a secret refuses everything (503) rather than accepting everything.
- **Validated input.** Real dates, no negative amounts, store IDs limited to letters, digits, `_` and `-`. Anything else gets a 422 before it reaches the database.
- **Failures the sender can act on.** A storage outage returns 502 so the POS or scheduler retries later. A failed alert never fails the webhook. Every outbound call has a timeout.

## Local run

Run on 2026-09-27 with the in-memory store and a real Discord webhook: `mock_data_sender.py` sent the sales webhook, the labor webhook, then the labor webhook again (a re-delivery). Server log ([runs/local_demo.log](./runs/local_demo.log)):

```
POS sends sales: HTTP 202
Store_104 2026-02-24: waiting
Scheduler sends labor: HTTP 202
Store_104 2026-02-24: alerted
Scheduler re-sends labor: HTTP 202
Store_104 2026-02-24: already_alerted
```

The stored row ([runs/local_demo.json](./runs/local_demo.json)) has CPLH $20.00 ($1,500 / 75 hours) and labor 30.00% ($1,500 / $5,000), with `alert_sent_at` set once.

## Live Supabase run

Run on 2026-09-28 against a live Supabase project with the service-role key and the same Discord webhook, same three webhooks for Store_104 on 2026-09-28. All three returned 202, the health check reported `SupabaseStore` with alerts on, and the server log ([runs/live_supabase_2026-09-28.log](./runs/live_supabase_2026-09-28.log)) shows one `alerted` and one `already_alerted` for the day. Read back from Supabase afterwards: a single row for the store-day with CPLH 20 and labor 30%, `alert_sent_at` set once ([runs/live_supabase_2026-09-28.json](./runs/live_supabase_2026-09-28.json)). A request without the key was refused (401).

The project also holds the row from the service's first version (2026-02-24, same figures), which the run left untouched. That table predated `alert_sent_at` and the unique `(store_id, date)` constraint, so both were added with `alter table` instead of recreating it.

The Supabase store's requests (the upsert, the conditional claim, the filters and auth headers) are also covered by tests against a mocked HTTP transport.

## Running it

```bash
pip install -r requirements.txt
```

Settings go in `.env` (see [.env.example](./.env.example)):

| Setting | Needed? | Without it |
|---|---|---|
| `WEBHOOK_SECRET` | yes | every webhook gets 503 |
| `ALERT_WEBHOOK_URL` | no | metrics are stored, no alert is sent |
| `SUPABASE_URL`, `SUPABASE_KEY` | no | an in-memory store (lost on restart) |
| `LABOR_ALERT_PCT` | no | 25 |

For Supabase, run `schema.sql` once in the project's SQL editor and use the **service-role** key: the table has row-level security on with no policies, so the public anon key can't read or write it.

```bash
uvicorn main:app
python mock_data_sender.py          # in a second terminal
```

Endpoints: `POST /webhook/sales`, `POST /webhook/labor`, `GET /metrics/{store_id}/{date}` (all need the secret header), and `GET /health`, which reports which store is in use and whether alerts are on.

**Tests** (no network, no accounts; they run in CI):

```bash
python -m pytest tests -q
```

They cover the math and the undefined cases, both arrival orders, re-delivery not re-alerting, a failed alert being retried, 20 threads racing for one alert claim, the secret check, invalid payloads, a storage outage, the Discord message and its failure modes, and the exact PostgREST requests the Supabase store sends.

## Project structure

```text
main.py               FastAPI app: webhooks, validation, the secret check, the background job
store.py              MemoryStore and SupabaseStore (PostgREST over httpx): upsert, read, alert claim
schema.sql            The daily_metrics table: unique (store_id, date), RLS on
transformations.py    CPLH and labor % math, and the threshold check
notifier.py           Formats and sends the Discord alert
mock_data_sender.py   Plays sales, labor and a re-delivered labor webhook at a running server
tests/                The test suite
runs/                 Server logs and stored rows from the local and live Supabase runs
```

## Stack

Python · FastAPI · Pydantic · PostgreSQL (Supabase, via PostgREST) · httpx · Discord webhooks
