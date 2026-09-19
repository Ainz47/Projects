# Proj16: n8n Lead Capture

A self-hosted n8n pipeline. A contact form submission is validated, scored by an LLM, and logged to a Google Sheet, and a strong lead sends me a WhatsApp alert. A second workflow sends a weekly summary, and a third reports any workflow that fails.

```
Form -> Validate -> valid? -> Gemini score -> parse -> Sheet row
                      |                          `-> hot? -> WhatsApp alert
                      `-> invalid -> rejected row -> Sheet row
```

## How it behaves
- Bad submissions (no name, broken email, one-word message) never reach the LLM. They are logged as `rejected` with the reasons.
- The model only returns a score, a one-line reason and a draft reply. The tier is computed in code (`hot` 8 to 10, `warm` 5 to 7, `cold` below 5), so the model cannot label a 3/10 lead hot.
- If Gemini fails or returns something unparseable, the lead is still logged with tier `needs_review` instead of being dropped.
- The Sheet write uses the node's "Use Append" option. Without it, two leads arriving at the same moment overwrote each other, and I lost a row in two of two test rounds before turning it on.
- The weekly workflow reads the last 7 days from the Sheet, counts by tier in code, and asks the model to write three lines about it.

## What is verified
Checked automatically on every push (GitHub Actions, Windows runner): the Code-node logic has `node --test` unit tests (validation, parsing the model's reply, row shaping, weekly counts), and the three exported workflows are checked for structure, wiring, no embedded secrets, and being in sync with the generator that builds them.

Checked by hand on a local n8n 2.39.8 run, importing these exact files:
- Four sample leads (`samples/leads.json`) went through the form and landed in the Sheet as hot, warm, cold and rejected. I read the rows back from the Sheet to confirm.
- Two rounds of four leads submitted at the same moment landed all eight rows once "Use Append" was on.
- With an invalid Gemini model, a lead was logged as `needs_review`.
- A failing Sheet write triggered the error workflow.
- The weekly workflow produced its summary from the Sheet's rows.
- The WhatsApp node ran for hot leads and the WhatsApp Cloud API accepted the message. I have not confirmed each alert arrived on the phone, so treat delivery as unverified.

Not done: it is not deployed. It runs on a local n8n, and CI does not run n8n, so nothing automated proves the workflows execute.

## Set up
1. Run n8n: `npx n8n`, open http://localhost:5678 and create the owner account.
2. Make a Google Sheet with a tab named `Leads` and this header row, one cell per column: `timestamp`, `name`, `email`, `company`, `message`, `budget`, `timeline`, `status`, `tier`, `score`, `reason`, `suggested_reply`.
3. In n8n, create credentials: Google Gemini(PaLM) API, Google Sheets OAuth2 and WhatsApp API. Your keys stay in n8n and the exports contain credential names only. For Sheets, use a Web application OAuth client with `http://localhost:5678/rest/oauth2-credential/callback` as an authorized redirect URI, enable the Google Sheets and Drive APIs, and check the credential says "Account connected" (a blank popup after Sign in means it did not finish).
4. Import the three `*.workflow.json` files (workflow menu, Import from File). Open each Gemini, Google Sheets and WhatsApp node and pick your credential. Paste the Sheet URL into `Append row` and `Read leads`, and your WhatsApp phone number ID and recipient number into each WhatsApp node.
5. In `Lead capture and qualify`, Settings, set the error workflow to `Workflow error alert`, and activate that workflow too. n8n does not run an error workflow that is inactive.
6. Activate `Lead capture and qualify` and `Weekly lead summary`. The form is at http://localhost:5678/form/lead-capture.
7. To test: `py -m pip install -r requirements.txt` then `py samples/submit.py`. The form only accepts `multipart/form-data`, which the script sends.

## WhatsApp notes
- Free-form text only delivers inside 24 hours of the recipient last messaging your number. With Meta's test number, message it from your phone first.
- The test number's access token expires after about 24 hours. Use a System User token for anything longer-lived.

## Swapping parts
- **LLM.** The Gemini node feeds a `Normalize LLM output` step that copies the reply into one field, `llm_text`. Everything after it reads only that field. To use Claude, replace the Gemini node with n8n's Anthropic node (this needs an Anthropic API key, which is separate from a Claude subscription) and point the normalize step at that node's reply field.
- **Alert channel.** The alert is one node. Swap `WhatsApp alert` for Slack, Discord or email and keep the message expression.
- **Lead source.** Replace the Form Trigger with a Webhook node and map its body to the same six field names (`Name`, `Email`, `Company`, `Message`, `Budget`, `Timeline`).
- **Thresholds.** `HOT_MIN` and `WARM_MIN` in `code/parse_llm.js`, then `py tools/build_exports.py` and re-import.

## Rebuilding the exports
The workflow JSON is generated so the tested code is the shipped code: edit `code/*.js` or `tools/build_exports.py`, run `py tools/build_exports.py`, and re-import. Do not hand-edit the JSON. A test fails if it drifts from the generator.

## Known limits
- The lead's message goes into the prompt, so someone can try to talk the model into a higher score. The prompt tells it to treat the lead as data, and a bad score only costs a wasted alert, but it is not proof against it.
- The score is the model's judgment, so a lead near a threshold can land in either tier on a rerun. The sample warm lead scored 6 three times in a row, but an earlier, vaguer version flipped between warm and cold.
- The form does not validate on the server, so the Validate step is what catches bad input from scripts or other clients.
- A quiet week still produces a summary saying there were no leads.
