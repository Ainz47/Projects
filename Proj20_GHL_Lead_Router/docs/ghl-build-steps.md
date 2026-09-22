# Building the GHL side of Proj20 (manual, in the sandbox UI)

GHL exposes no API for constructing funnels, pipelines or workflow logic, so
this side is built by hand in the sandbox UI, once it exists (see Task 6).
Everything here is written so it can be followed exactly.

## 1. Contact custom fields
Create these custom fields on the Contact object (Settings > Custom Fields):
- `inquiry_message` (large text) - the funnel form's message field.
- `inquiry_budget` (single line) - optional.
- `inquiry_timeline` (single line) - optional.
- `lead_score` (number) - written back by the router (see step 4).
- `lead_reason` (single line) - written back by the router.
- `lead_suggested_reply` (large text) - written back by the router, never auto-sent.

## 2. The funnel
Build a single-page funnel with a form collecting: Name, Email, Company
(optional), Message (maps to `inquiry_message`), Budget (optional, maps to
`inquiry_budget`), Timeline (optional, maps to `inquiry_timeline`). On submit,
create a Contact and an Opportunity in a new pipeline (step 3).

## 3. The pipeline
Create a pipeline named "Lead Router" with four stages: `New`, `Hot`, `Warm`,
`Cold`. New submissions land in `New`.

## 4. The workflow: trigger and webhook out
Create a workflow triggered by "Form Submitted" (the funnel from step 2). Add
a Webhook action as the first step, method POST, URL set to this n8n
instance's webhook endpoint for `ghl-lead-router` (fill in once n8n is
running: `http://<n8n-host>/webhook/ghl-lead-router`). Set the webhook's body
to this JSON, using GHL's merge fields:
```json
{
  "name": "{{contact.first_name}} {{contact.last_name}}",
  "email": "{{contact.email}}",
  "company": "{{contact.company_name}}",
  "message": "{{contact.inquiry_message}}",
  "budget": "{{contact.inquiry_budget}}",
  "timeline": "{{contact.inquiry_timeline}}"
}
```
Confirm the exact merge-field syntax against the sandbox's own workflow
editor when building this live; GHL's merge-field picker inside the webhook
action body editor is the source of truth if it differs from the above.

## 5. Branching by tier (blocked on Task 7)
The router (n8n) writes `lead_score`, `lead_reason`, `lead_suggested_reply`
and a tag (`hot` / `warm` / `cold`) back onto the contact, and moves the
opportunity to the matching pipeline stage. The exact API calls n8n's
write-back nodes use, and whether OAuth or a Private Integration Token is
the smoother auth path, are confirmed in Task 7 (the pre-build check) once
the sandbox and the `leadconnector` MCP exist - not written here to avoid
guessing at an unconfirmed API shape. Once Task 7 lands, this workflow adds:
a wait step (or a second trigger, "Tag Added") that branches on the tag:
- `hot`: SMS the owner, task created, offer a calendar booking link.
- `warm`: enroll in a templated (non-personalized) email nurture sequence.
- `cold`: no action.

## 6. Snapshot export
Once the full build above is done, export a Snapshot (Settings > Account
Snapshots) for the portfolio deliverable. Confirm during the live build
whether GHL offers a downloadable file or only a shareable link - the spec
flags this as unconfirmed for a Marketplace Developer sandbox specifically.
