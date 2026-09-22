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

## 5. Get a Private Integration Token
Settings > Private Integrations > Create a new integration, scopes
`contacts.write`, `contacts.readonly`, `opportunities.write`,
`opportunities.readonly`, `locations/customFields.readonly`. Copy the token;
it goes into n8n's `GHL Private Integration Token` credential (Header Auth,
header name `Authorization`, value `Bearer <token>`), never into source.

## 6. Write-back (n8n, confirmed against the live sandbox)
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

## 7. Branching by tag (GHL's own workflow, after the tag is added)
Add a second trigger to the same workflow (or a new one), "Tag Added",
watching for `hot`, `warm`, `cold`:
- `hot`: SMS the owner, create a task, offer a calendar booking link.
- `warm`: enroll in a templated (non-personalized) email nurture sequence.
- `cold`: no action.

## 8. Snapshot export
Confirmed: GHL has no API for Snapshot export (`search_operations` found
zero matching operations). Export via Settings > Account Snapshots in the
UI; if GHL only offers a shareable link rather than a downloadable file for
a Marketplace Developer sandbox, document the link instead in the README.
