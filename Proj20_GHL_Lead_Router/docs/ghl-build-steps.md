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
- `inquiry_blocker` (large text) - the funnel form's page-2 "Biggest blocker"
  question, collected only on the "Under $5,000" branch.

## 2. The funnel
Build a two-page funnel.

Page 1: form collecting Name, Email, Company (optional), Message (maps to
`inquiry_message`), and Budget range as a **dropdown** (changed from the
original free-text field) with exactly two options: "Under $5,000" /
"$5,000+" (maps to `inquiry_budget`). `inquiry_timeline` is no longer
collected on page 1.

Page 2: conditional on page 1's Budget range answer, using the funnel
builder's page-level conditional logic (GHL exposes this as either a
show/hide condition on the page or on the individual question, depending on
the sandbox's funnel editor version - confirm the exact mechanism live and
note which one it was in the README):
- Budget range = "$5,000+" -> show a "Timeline" question, mapped to the
  existing `inquiry_timeline` field (moved here from page 1).
- Budget range = "Under $5,000" -> show a "Biggest blocker" question, mapped
  to the new `inquiry_blocker` field above.

On submit, create a Contact and an Opportunity in the existing "Lead Router"
pipeline (unchanged, still lands in `New`).

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
  "contactId": "{{contact.id}}",
  "opportunityId": "{{opportunity.id}}",
  "name": "{{contact.first_name}} {{contact.last_name}}",
  "email": "{{contact.email}}",
  "company": "{{contact.company_name}}",
  "message": "{{contact.inquiry_message}}",
  "budget": "{{contact.inquiry_budget}}",
  "timeline": "{{contact.inquiry_timeline}}"
}
```
`contactId` and `opportunityId` are not sent to the backend's `/qualify`
call (it only uses the six lead fields) but pass straight through n8n's
`Merge qualification onto lead` step, so the write-back nodes below can
address the right contact and opportunity. Confirm the exact merge-field
syntax against the sandbox's own workflow editor when building this live;
GHL's merge-field picker inside the webhook action body editor is the
source of truth if it differs from the above.

## 5. Create a Calendar (prerequisite for the Hot branch's booking link)
Settings > Calendars > new Calendar (any type, e.g. "Round Robin" or
"Event"), name it something like "Proj20 Intro Call". No new signup or cost;
this is a native GHL object. Its public booking link is what the Hot
branch's email links to (section 8).

## 6. Get a Private Integration Token
Settings > Private Integrations > Create a new integration, scopes
`contacts.write`, `contacts.readonly`, `opportunities.write`,
`opportunities.readonly`, `locations/customFields.readonly`. Copy the token;
it goes into n8n's `GHL Private Integration Token` credential, never into
source. Use credential type **HTTP Templated Custom Auth**, not Header
Auth - n8n rejects creating a new plain Header Auth credential on this
node (confirmed live via n8n-mcp validation). Template:
`{"headers":{"Authorization":"Bearer {{api_key}}"}}`, then paste the raw
token (no `Bearer ` prefix) into the credential's `api_key` field.

## 7. Write-back (n8n, confirmed against the live sandbox)
The router (n8n) calls GHL's REST API directly with the token above:
- `PUT https://services.leadconnectorhq.com/contacts/{contactId}` with
  `customFields: [{id, fieldValue}]` for `lead_score`, `lead_reason`,
  `lead_suggested_reply` (field IDs looked up once, see the plan's Task 4).
- `POST https://services.leadconnectorhq.com/contacts/{contactId}/tags`
  with `{tags: [tier]}`.
- `PUT https://services.leadconnectorhq.com/opportunities/{opportunityId}`
  with `{pipelineStageId}` (the Hot/Warm/Cold stage ID for that tier, see
  the plan's Task 4), moving it out of `New`.
Every write needs the header `Version: 2021-07-28` alongside the Bearer
token.

## 8. Branching by tag (GHL's own workflow, after the tag is added)
The existing "Tag Added" trigger (watching `hot`, `warm`, `cold`) now
branches into real multi-step sequences per tier.

### Hot
1. Email action (existing, unchanged) - the score/reason write-back email.
2. Add a "Create Task" action: assign to the location owner, title
   `Follow up: hot lead {{contact.first_name}} {{contact.last_name}}`, due
   immediately.
3. Edit the existing Email action's body to add a calendar booking link:
   use the workflow email editor's merge-field picker to insert section 5's
   Calendar's public booking link (the exact merge-tag name is whatever the
   picker offers live - confirm and record it in the README).

### Warm
Replace the single templated email action with a 3-step drip:
1. Wait step: 0 (immediate) -> Email action 1 (Day 0 nurture email,
   templated, not personalized).
2. Wait step: 3 days -> Email action 2 (Day 3 nurture email, templated).
3. Wait step: 4 days (3 + 4 = 7 total elapsed) -> Email action 3 (Day 7
   nurture email, templated).

Add two behavior-driven re-branch triggers off this sequence:
- "Email Link Clicked" (on any of the three nurture emails) -> Add Tag
  `hot` (re-enters the Hot branch above via the existing Tag Added
  trigger). Confirm live whether GHL automatically removes the contact from
  the remaining wait steps once this fires, or whether that needs an
  explicit "Remove from workflow" action; record whichever is true in the
  README.
- If no "Email Link Clicked" event has fired by the end of the Day-7 wait
  -> Add Tag `cold` (re-enters the Cold branch below).

### Cold
1. Wait step: 30 days.
2. Email action: single long-term re-engagement email.
3. Sequence ends (no further action).

### Live-test methodology
For the live verification run, shrink every wait step above (3 days,
4 days, 30 days) to a few minutes each, run the verification, then
immediately restore every wait step to its real production duration
(3 days / 4 days / 30 days) before considering the phase done. This is
documented in full, with the actual shrunk values used and the exact
restoration timestamp, in the README's "What is verified" section.

## 9. Snapshot export
Confirmed: GHL has no API for Snapshot export (`search_operations` found
zero matching operations). Export via Settings > Account Snapshots in the
UI; if GHL only offers a shareable link rather than a downloadable file for
a Marketplace Developer sandbox, document the link instead in the README.
