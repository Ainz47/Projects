# Proj20: GHL Lead Qualifier & Router

A FastAPI backend scores inbound leads from a GoHighLevel (GHL) funnel with
an LLM, and an n8n workflow glues GHL's webhook to that backend and (once
Phase 2 lands) writes the result back into GHL: a tag, custom fields, and a
pipeline stage move, then GHL's own workflow branches by tier.

```
GHL funnel -> contact + opportunity created -> GHL workflow webhook
      -> n8n: Call backend /qualify -> merge tier/score/reason/reply
      -> [Phase 2] n8n writes back to GHL -> GHL workflow branches by tag
            hot  -> SMS + task + booking link
            warm -> templated nurture sequence (auto-sent, not personalized)
            cold -> no action
```

## Status
Phase 1 (this commit): the backend service and the webhook-to-backend half
of the n8n workflow are built and tested. Phase 2 (GHL write-back, the
manual GHL build, deployment, and live verification) is blocked on creating
a free GHL Marketplace Developer sandbox account - see
`docs/ghl-build-steps.md`.

## What is verified
Checked automatically: `backend/tests` (pytest) covers the qualification
logic's tier boundaries, malformed-output handling, and the `/qualify` and
`/health` endpoints via `TestClient`. `tests/test_exports.py` (unittest)
checks the n8n export's structure, wiring, and that it contains no secrets
and matches the generator that built it.

Not yet done (Phase 2): no live GHL sandbox exists yet, so nothing here has
been run end to end against a real funnel submission.

## Set up
1. Backend: `cd backend && py -m pip install -r requirements.txt`, set
   `GEMINI_API_KEY`, run `py -m uvicorn app.main:app --reload`.
2. n8n: import `ghl-lead-router.workflow.json`, paste the running backend's
   `/qualify` URL into the `Call backend /qualify` node.
3. GHL: follow `docs/ghl-build-steps.md`.

## Rebuilding the export
`tools/build_exports.py` generates `ghl-lead-router.workflow.json`. Never
hand-edit the JSON; edit the generator and re-run `py tools/build_exports.py`.

## Known limits
- The lead's message goes into the prompt, so someone can try to talk the
  model into a higher score, same known limit as Proj16's qualifier.
- Phase 1 has no deployment; the backend runs locally until Phase 2.
