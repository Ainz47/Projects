# Proj20: GHL Lead Qualifier & Router

A FastAPI backend scores inbound leads from a GoHighLevel (GHL) funnel with
an LLM, and an n8n workflow glues GHL's webhook to that backend and writes
the result back into GHL: a tag, custom fields, and a pipeline stage move,
then GHL's own workflow branches by tier.

```
GHL funnel -> contact + opportunity created -> GHL workflow webhook
      -> n8n: Call backend /qualify -> merge tier/score/reason/reply
      -> n8n writes back to GHL -> GHL workflow branches by tag
            hot  -> Email (score/reason from the write-back)
            warm -> templated nurture email (auto-sent, not personalized)
            cold -> no action
```

## Status
Built, deployed, and verified end to end against a live GHL sandbox. The
backend runs on Render (`https://projects-f8p2.onrender.com`); the n8n
workflow (`27AgIzoreHN8ssGK`) is published and wired to the sandbox's `From
Form` webhook through a Cloudflare tunnel exposing the local n8n instance.
Three real GHL contacts (hot/warm/cold) were run through the full chain -
webhook -> qualify -> tag -> custom fields -> opportunity stage move -> GHL's
own tag-triggered workflows firing - and confirmed via the GHL API and CRM
UI, not just n8n's own execution log. See `docs/screenshots/` for the
pipeline, CRM record, funnel canvas, and both GHL workflow canvases from
that run.

## What is verified
Checked automatically: `backend/tests` (pytest, 14 tests) covers the
qualification logic's tier boundaries, malformed-output handling, and the
`/qualify` and `/health` endpoints via `TestClient`. `tests/test_exports.py`
(unittest, 17 tests) checks the n8n export's structure, wiring, that it
contains no secrets, and that it matches the generator that built it.

Checked live, this session: all three test contacts (hot, warm, cold)
replayed clean through the fully-wired chain via `n8n-mcp`
`execute_workflow` / `get_workflow_execution`, including real GHL
opportunity-stage moves. GHL's own tag-triggered workflows (Hot Leads, Warm
Leads) were independently confirmed to fire - not inferred from n8n's "200
OK" on the tag write - by pulling each contact's conversation via the
`leadconnector` API and finding the score/reason custom fields correctly
populated in the sent message. Two real bugs were caught this way that
would not have shown up in unit tests: GHL's webhook Custom Data sending an
empty `opportunityId` for an opportunity that already existed (fixed by
having n8n look the id up itself instead of trusting the webhook field),
and the GHL API rejecting camelCase `contactId` despite the `leadconnector`
MCP's own docs saying otherwise (real API wants snake_case `contact_id`).

Known gap: the Hot Leads GHL workflow's original SMS action fails (sandbox
has no SMS-capable number) and was left in place alongside a working Email
action rather than deleted, since it fails harmlessly and Email already
covers the hot-lead notification.

## Set up
1. Backend: `cd backend && py -m pip install -r requirements.txt`, set
   `GEMINI_API_KEY`, run `py -m uvicorn app.main:app --reload` (or deploy,
   e.g. to Render).
2. n8n: import `ghl-lead-router.workflow.json`, paste the running backend's
   `/qualify` URL into the `Call backend /qualify` node.
3. GHL: follow `docs/ghl-build-steps.md`.

## Rebuilding the export
`tools/build_exports.py` generates `ghl-lead-router.workflow.json`. Never
hand-edit the JSON; edit the generator and re-run `py tools/build_exports.py`.

## Cross-project links
Proj20 is its own standalone case study (own backend, own repo, own
README/CI) but shares the local n8n instance with Proj16 (lead capture) and
Proj19 (Shopify stock sync), and links to both through real, already-existing
infrastructure rather than merged workflows:
- **Shared error alerting**: `settings.errorWorkflow` points at the same
  `Workflow error alert` workflow Proj19 already uses - one failure channel
  across all three, not three separate ones.
- **Shared reporting**: `Append lead log` writes each qualified GHL lead to a
  `LeadLog` tab in the same spreadsheet Proj19 writes `StockLog` to. Proj16's
  `Weekly lead summary` workflow reads `Leads`, `StockLog`, and `LeadLog`
  together, so one weekly digest covers leads, stock, and CRM activity.
  `LeadLog` uses the same column shape as Proj16's `Leads` sheet
  (`code/rows.js`'s `SHEET_COLUMNS`), so Proj16's `summarize()` handles both
  with no new parsing logic.
- **Shared alert channel**: `WhatsApp hot lead alert` reuses the same
  `WhatsApp account` credential Proj16's own hot-lead alert uses.
The spreadsheet ID and error-workflow ID are filled in at import time (or
already resolve automatically inside the one shared local n8n instance) -
never committed, same convention as every other credential/ID in this repo.

## Known limits
- The lead's message goes into the prompt, so someone can try to talk the
  model into a higher score, same known limit as Proj16's qualifier.
- Render's free tier spins the backend down after 15 minutes idle; a cold
  start takes roughly 15-36s and can occasionally surface a transient
  `ECONNRESET` on the first request after a spin-down, which a retry clears.
- The GHL sandbox has no SMS-capable number, so the Hot Leads workflow's
  notification runs over Email instead of SMS.
