# Proj20: GHL Lead Qualifier & Router

A FastAPI backend scores inbound leads from a GoHighLevel (GHL) funnel with
an LLM, and an n8n workflow glues GHL's webhook to that backend and writes
the result back into GHL: a tag, custom fields, and a pipeline stage move,
then GHL's own workflow branches by tier.

**Walkthrough video:** [architecture, failure handling and the live tests, slide by slide](https://drive.google.com/file/d/1AS-D9x4JyWVsEDsPT01QjONwbYDKQszz/view)

```
GHL funnel (Survey) -> "From Survey" workflow: opportunity in New + webhook
      -> n8n: read the contact, fingerprint the inquiry
         (same fingerprint as the one stored on the contact = a replay: stop)
      -> Call backend /qualify (X-API-Key) -> merge tier/score/reason/reply
      -> n8n writes back to GHL -> GHL workflow branches by tag
            hot  -> Email (score/reason from the write-back)
            warm -> templated nurture email (auto-sent, not personalized)
            cold -> no action
```

## Status
Built, deployed, and verified end to end against a live GHL sandbox. The
backend runs on Render (`https://projects-f8p2.onrender.com`); the n8n
workflow (`27AgIzoreHN8ssGK`) is published and wired to the sandbox's `From
Survey` (the live funnel) and `From Form` webhooks through a Cloudflare tunnel
exposing the local n8n instance.
Three real GHL contacts (hot/warm/cold) were run through the full chain -
webhook -> qualify -> tag -> custom fields -> opportunity stage move -> GHL's
own tag-triggered workflows firing - and confirmed via the GHL API and CRM
UI, not just n8n's own execution log. See `docs/screenshots/` for the
pipeline, CRM record, funnel canvas, and both GHL workflow canvases from
that run.

A second, GHL-native advanced-workflows phase (built and live-verified
2026-09-23/24) replaced the thin single-action hot/warm/cold branches and
single-page funnel with real multi-step, conditional GHL-native depth: a
Hot branch with a Task action and a calendar-booking link, a Warm branch
with a 3-step wait-stepped nurture drip that re-branches to hot on a real
email click, a Cold branch with a single re-engagement email, and a
two-page conditional funnel built as a GHL Survey (Budget answer drives a
Jump-To condition to a Timeline or Blocker question). Backend and n8n were
untouched for this phase; it's entirely GHL-sandbox-native.

## What is verified
Checked automatically: `backend/tests` (pytest, 23 tests) covers the
qualification logic's tier boundaries, the survey's blocker answer reaching
the prompt, malformed-output handling, the
retry-then-review path when the model call fails, the API key check (no key,
wrong key, key unset on the server), and the `/qualify` and `/health`
endpoints via `TestClient`. `tests/test_exports.py` (unittest, 30 tests)
checks the n8n export's structure, wiring, retries, the replay guard and the
order it writes in, tier-tag clearing, the run order of routing vs.
reporting, that it contains no secrets, and that it matches the generator
that built it.

Checked live, funnel to router (2026-10-18): the two-page Survey funnel had
never reached the router. `From Form` only triggers on the old Form, and its
webhook didn't send the survey's blocker answer. Fixed with a `From Survey`
workflow (Survey Submitted trigger, same opportunity + webhook actions), a
`blocker` key in both webhooks, and `blocker` in the backend prompt and the
inquiry fingerprint. One real submission through the funnel's preview page
("Under $5,000", so the Blocker slide) was checked against the GHL API:
- n8n exec 124 received the blocker text; the model scored it warm, 7, with
  a reason that weighs the blocker against the budget.
- The contact (source `Survey 0`) has tags exactly `["warm"]`, score,
  reason, reply and `lead_qualified_hash` stored, and its opportunity moved
  New -> Warm about 10 s after submit. GHL's Warm drip sent its first email
  to the test inbox.

Checked live, the replay and auth pass (2026-10-18): one fresh sandbox
contact with an opportunity in New, fired at the published workflow and
checked against the GHL API.
- **Auth**: the deployed backend answers 401 with no key or a wrong key,
  200 with the right one; `/health` stays open for Render's health check.
- **Hot** (exec 116): score 9, tags exactly `["hot"]`, opportunity
  New -> Hot, and the inquiry fingerprint stored in `lead_qualified_hash`.
- **Replay** of the same payload (exec 117): stopped at `New inquiry?`. No
  model call, and the contact's `dateUpdated` did not move.
- **New inquiry** from the same contact (exec 118): scored again (warm, 6),
  the `hot` tag removed, tags exactly `["warm"]`, opportunity Hot -> Warm.
- The first run (exec 114) failed before any write: `/qualify` still read
  its input from `$json`, which after the replay check is the fingerprint,
  not the webhook body. It now reads the webhook node by name, and a test
  pins that.

Checked live, the hardening pass (2026-10-17): five fresh sandbox contacts,
each with an opportunity in New, fired at the published workflow and checked
against the GHL API and the LeadLog sheet, not n8n's own status.
- **Hot** (exec 108): score 9, `hot` tag, opportunity New -> Hot, one
  LeadLog row; `First time hot?` passed, so the WhatsApp alert node fired.
- **Replay** of the same lead (exec 109): same tier and stage, `First time
  hot?` saw the `hot` tag from `Read contact before write` and skipped the
  alert; the LeadLog still holds one row for that email (counted with a CSV
  parser), where the old append-only node had left up to four per lead.
- **Warm** (exec 107): score 7, opportunity New -> Warm. **Cold** (exec 110):
  score 1, opportunity New -> Cold.
- **Forced review** (exec 113): the backend from this commit, run with an
  invalid model key, retried the call three times and returned
  `tier: review, score: 0, reason: "model call failed: InvalidArgument"`
  (logged with its request id). The contact got `needs-review`, no stage
  move (the opportunity's `lastStageChangeAt` never changed), no alert.
- **Reporting can't block routing** (exec 105): with the Sheets credential
  expired, a warm lead still moved New -> Warm, then the run failed on the
  log write and went to the shared error workflow. Before the fix, the same
  failure stopped exec 101 ahead of the stage move.

One thing the pass turned up that is not code: the Sheets OAuth token had
expired after a few idle weeks, since the Google app is in testing mode.
Reconnecting it was the fix.

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

Checked live, the advanced-workflows phase (2026-09-23/24): all four
branches verified against the GHL API and a real Gmail inbox, not just the
sandbox UI. **Hot**: a contact tagged `hot` directly via API produced a
correctly-titled, correctly-due Task on the contact record within
`get-all-tasks`, and `{{user.calendar_link}}` in the Hot email resolves to
the live "Proj20 Intro Call" booking link. **Warm-to-hot re-branch**: a
warm-tagged test contact (`+proj20warmclick` Gmail alias) received the
Day-0 nurture email; a real human click on its tracked link (automated
`WebFetch` clicks do not register with GHL's click tracking, confirmed
twice) added the `hot` tag within about a minute and correctly fired the
Hot branch's Task. **Warm-to-cold**: a warm-tagged contact that never
opened or clicked (`+proj20warmcold` alias) picked up the `cold` tag after
its drip completed, and a distinct re-engagement email ("Still thinking
about it, Proj20?") landed about 3.5 minutes later - confirmed as a
separate send, not a repeat of the nurture emails. **Funnel**: a live
submission with Budget "$5,000+" produced a contact with `inquiry_timeline`
populated and no blocker field; a submission with "Under $5,000" produced
`inquiry_blocker` populated and no timeline field, proving the Survey's
Jump-To condition branches per-contact, not just per-slide-order. A
correctness gap not in the original spec was also caught and fixed here:
neither the Hot nor Cold workflow moved the opportunity's pipeline stage on
a re-branch, desyncing the tag from the CRM Kanban view; both workflows now
include a Find Opportunity -> Update Opportunity step, verified live by
watching a real opportunity move New -> Hot via the API.

Live-test methodology: all three wait steps (Warm's two, Cold's one) were
temporarily shrunk to 3 minutes each to make same-session verification
possible, then restored to their production durations (Warm: 3 days, 4
days; Cold: 30 days) on 2026-09-24 once every branch above had been
confirmed.

Known, accepted deviation: the spec for the advanced-workflows phase called
for dropping the Hot Leads workflow's original SMS action entirely. It was
left in place instead - an explicit decision, not an oversight - since the
sandbox has no SMS-capable number so it fails harmlessly, and the new Task
action plus Email (with the calendar-booking link) already cover the
hot-lead notification.

## Set up
1. Backend: `cd backend && py -m pip install -r requirements.txt`, set
   `GEMINI_API_KEY` and `QUALIFY_API_KEY` (any long random string; with it
   unset, `/qualify` refuses every call), run
   `py -m uvicorn app.main:app --reload` (or deploy, e.g. to Render).
2. n8n: import `ghl-lead-router.workflow.json`, paste the running backend's
   `/qualify` URL into the `Call backend /qualify` node, and create its
   `Proj20 qualify API key` credential (Simplified Custom Auth, template
   `{"headers":{"X-API-Key":"{{api_key}}"}}`, the key as `api_key`).
3. GHL: follow `docs/ghl-build-steps.md`, plus a `lead_qualified_hash`
   text field on contacts; its id goes in `New inquiry?` and
   `Mark inquiry routed`. Point a Survey Submitted workflow at the same
   webhook (Custom Data as in `From Form`, plus `blocker` =
   `{{contact.inquiry_blocker}}`).

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
- **Shared reporting**: `Upsert lead log` writes each qualified GHL lead to a
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

## At 10x the volume
What breaks first, in order, and what would change:
- **Render's free tier.** One instance that sleeps after 15 idle minutes.
  A paid always-on instance, then more than one behind its load balancer;
  the backend keeps no state, so it scales out as is.
- **The model call inside the request.** n8n waits up to 60 s per lead. At
  volume the webhook would only queue the lead (a queue such as Redis or
  SQS), workers would call the model with a concurrency cap matching the
  Gemini quota, and the write-back would run when the result lands.
- **GHL's API rate limit.** Every lead costs about seven GHL calls. Spread
  them through the same queue with backoff on 429, and drop the separate
  opportunity lookup once the webhook's own `opportunityId` can be trusted.
- **n8n on one machine.** Move it to a hosted instance in queue mode with
  its own workers, so one slow lead doesn't hold up the rest.
- **The lead log in Google Sheets.** Fine for a weekly digest, not for
  thousands of rows a day; it would move to a database table.

## Known limits
- The lead's message goes into the prompt, so someone can try to talk the
  model into a higher score, same known limit as Proj16's qualifier.
- Render's free tier spins the backend down after 15 minutes idle; a cold
  start takes roughly 15-36s and can occasionally surface a transient
  `ECONNRESET` on the first request after a spin-down, which a retry clears.
- The sandbox funnel has no domain attached, so it has no real public URL;
  live testing used GHL's own preview link instead. The preview domain's
  Cloudflare Turnstile check occasionally fails silently (a form submit
  produces no error and no contact) - a short pause before submitting
  clears it, confirmed by retrying a failed submission successfully.
