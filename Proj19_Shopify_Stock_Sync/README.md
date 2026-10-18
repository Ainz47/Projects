# Proj19: Shopify order to stock sync (n8n core, Make fast path, and the Proj16 link)

When an order exists in the owner's Shopify development store (`jhurald05`), this sets the matching Airtable catalog row's `Stock` to Shopify's current stock for the ordered SKUs, and rebuilds the public storefront page ([Proj18](../Proj18_Coffee_Storefront/)) through the existing `refresh-catalog` GitHub Actions workflow. Two writers do this: an n8n workflow that polls every 5 minutes (the core, Plan 1), and a Make scenario triggered by a Shopify webhook that reacts within seconds (the fast path, Plan 2). Either alone keeps Airtable and the storefront correct; both running at once is redundant by design, not a race, since every write is Shopify's current absolute stock.

**Walkthrough video:** [architecture, failure handling and the live tests, slide by slide](https://drive.google.com/file/d/14EXVujAeACjYdeFiyBNKRSowS0WGoOjU/view)

Plan 2 (this README's second half) also adds a thank-you email for the order's own address (allow-listed, sent once, tagged), a `StockLog` sheet both writers append to, and a fourth line in Proj16's weekly summary reporting stock activity from that sheet. Both plans are built and verified live against the dev store.

## What it does

```
Every 5 minutes:
  read new/updated Shopify orders (cursor - 10 min overlap, up to 250)
    -> collect the unique SKUs ordered
      -> read each SKU's current Shopify stock
        -> for each Airtable Variants row that differs: set Stock = Shopify's number, then log it to StockLog
          -> compare what Airtable now holds with what the public page shows (the committed snapshot)
            -> if the page is behind and no rebuild is already running: dispatch refresh-catalog (GitHub Actions)
              -> advance the cursor (only after every step above succeeded)
```

- **Absolute, not subtracted.** Airtable's `Stock` is always set to Shopify's current number for the SKU. Re-reading an order, a crash mid-run, or two ticks overlapping cannot double-count, because writing the same number twice changes nothing.
- **10-minute overlap, cursor advances last.** Every tick re-reads the last 10 minutes even if nothing changed, and the cursor only moves forward once the whole chain (SKU lookup, Airtable write, GitHub dispatch) has succeeded. A failure anywhere leaves the cursor where it was, so the next tick redoes the same work rather than silently skipping it.
- **The rebuild is decided from what was published, not from what this tick wrote.** If Airtable was written and the GitHub dispatch after it failed, the retry tick finds Airtable already matching Shopify and has nothing to write, so "did I change anything" would never dispatch again and the page would stay behind. Instead every tick that saw SKUs reads the committed catalog snapshot (`Proj18_Coffee_Storefront/data/catalog.export.json` on `main`, the file `refresh-catalog` publishes) and dispatches when any SKU it just synced shows a different number there. The same check covers a Make dispatch that ran out of retries and a `refresh-catalog` run that failed on GitHub. Two guards keep it from looping: while a `refresh-catalog` run is queued or running, the tick leaves it to finish instead of dispatching a second one; and after three failed runs in a row it stops dispatching and fails the tick, which raises the error alert, rather than retrying a broken build every 5 minutes.
- **StockLog only records what reached Airtable.** The log rows are written after the Airtable update succeeds, so a failed write never leaves a log line claiming a change that didn't happen.
- **Skips are reasoned, not silent.** A SKU with no Airtable row is skipped ("no Airtable row"). A SKU Shopify doesn't know, or has no single tracked stock for (untracked, ambiguous across duplicate variants, or a non-integer/negative quantity), is rejected with a specific reason rather than guessed at.
- **At most 250 orders a tick**, and the Airtable stock query is one `productVariants` call (no pagination past 250 variants) and one `listRecords` call (no pagination past whatever a single `filterByFormula` page returns — more than that fails loudly rather than silently missing rows).

## Make and the thank-you email

The fast path: Shopify's `orders/create` webhook -> Make scenario `order-stock-sync` (team 3001359) -> verify the HMAC signature -> per line item, read the SKU's current Shopify stock -> if exactly one variant has that SKU and its stock differs from Airtable, update the row -> append a `StockLog` row (`source: make`) -> once per order, if any SKU changed, dispatch `refresh-catalog` via GitHub's `repository_dispatch` endpoint (a second, separately-scoped fine-grained token, `Contents: read and write` — `repository_dispatch` needs that permission, so n8n's `Actions: write` token cannot be reused). Make has no local test loop, so this scenario was built once by hand in Make's UI from an exact module list, then exported and locked down with a structural, no-secrets test (`tests/test_make_blueprint.py`), the same trust boundary Plan 1 used for n8n's own manual credential wiring.

The webhook runs in JSON pass-through with request headers on, so the raw body reaches Make unparsed. Module 10 reads the app secret from the `proj19-secrets` data store, and the filter in front of the Parse JSON step compares `sha256(raw body; base64; secret)` with the `X-Shopify-Hmac-Sha256` header; nothing past it runs on a request Shopify didn't sign. Stock is picked with `map(nodes; "inventoryQuantity"; "sku"; <sku>)`, the same exact-SKU rule the n8n path uses, because Shopify's `sku:"X"` search is a loose match. An Array Aggregator closes the line-item loop, so a multi-line order sends one dispatch, not one per line.

n8n owns webhook self-heal: every tick, it lists the store's `ORDERS_CREATE` webhook subscriptions and re-creates the one pointing at Make's URL if it's missing, so a subscription Shopify silently drops (or one deleted by hand) comes back within 5 minutes with no manual step.

The thank-you email is n8n-only, tag-then-send, allow-list gated: `THANK_YOU_ALLOW_LIST` (an n8n Variable, comma-separated addresses, matched case-insensitively) decides who gets one; an order is tagged `proj19-thanked` before the email goes out, and every later tick checks that tag first, so a resend never happens even if the tick re-reads the same order inside the 10-minute overlap window.

`StockLog` (the same spreadsheet as Proj16's `Leads` tab) gets one row per real stock change from either writer: `timestamp, sku, old_stock, new_stock, source (make|n8n), order_name`. Proj16's `Weekly lead summary` reads the last 7 days of this tab alongside `Leads` and adds a fourth line to its model-written summary: the number of stock updates and any newly sold-out SKU, or "No stock activity."

## What is verified

Checked automatically (`node --test` for the eleven `code/*.js` modules, 83 tests; Python `unittest` for the n8n export generator's structural/wiring/no-secrets checks and the Make blueprint's structural/no-secrets checks, 22 tests; both run in CI on the Windows runner alongside the other Proj* suites): the cursor query planner (overlap, first run, future-cursor clamping, unreadable cursor), SKU collection and per-order SKU-to-order-name mapping, the Shopify and Airtable search-string builders (SQL/formula-injection-safe quoting), exact-SKU stock picking from a looser Shopify search match, the update planner (every skip/reject reason, chunking for Airtable's 10-record batch limit), the cursor-advance rule (never backwards, never past now), the GraphQL error guard and the Shopify `userErrors` guard, webhook-registration need-detection, `StockLog` row building, thank-you planning (allow-list, already-thanked, no-email, case-insensitive matching) and its fixed email template, the rebuild planner (a SKU the page shows differently or not at all is stale, a run already queued or running is not doubled, one or two failed runs are retried, three in a row stop and fail the tick, older failures behind a success don't count), and the test-order tool. The export test suite confirms the shipped n8n workflow JSON is byte-identical to what the generator produces from that same tested code, that the cursor is written in exactly one node, that `Dispatch refresh` is reachable only through the rebuild check (which a tick with nothing to write reaches too), that the snapshot is read as JSON, that HTTP nodes use named n8n credentials with no inline secrets, that the Gmail node uses the named `Gmail account` credential with no literal addresses, and that every Code node is self-contained (no `require`, parses with `node --check`). The Make blueprint's own suite confirms it parses, has the webhook trigger and the GitHub dispatch call, the GitHub token is a datastore reference (`{{7.value}}`) never a literal, module 8 carries an automatic-retry directive, the HMAC check sits in front of every other step, stock is picked by exact SKU, the dispatch runs once per order behind an aggregator, every module carries the defaults Make needs at run time, and no secret-shaped string appears anywhere in the export.

Checked live against `jhurald05` (2026-09-20 through 2026-09-21, local n8n 2.39.8, and Make): see `AUDIT.md` for the full run-by-run record. Plan 1's live pass found and fixed two real bugs (an Airtable `POST` that needed to be `PATCH`, and a credential-matching bug in the local import script that sent an Airtable token to GitHub's API). Plan 2's live pass, driven directly through the n8n and Make MCP servers rather than manual UI clicks, verified: webhook self-heal (create when missing, no duplicate on a re-check, self-recreate after a manual delete); both writers correctly appending to `StockLog` and not double-writing when both fire on the same order; the thank-you email (sent once to an allow-listed address, correctly skipped for a non-listed one, no resend on a later tick); a clean failure (bad Airtable credential fails the tick with no cursor advance and no partial email, and recovers on the next good tick); and Proj16's `Weekly lead summary` genuinely reading `StockLog` live and reporting a real sold-out SKU in its fourth line. Two real findings came out of that pass: the Make scenario's GitHub-dispatch module hit an intermittent `BundleValidationError` mid-session that then resolved on an identical replay with no config change (confirmed transient, not structural — the scenario was hardened with a 3x/15-minute automatic-retry directive as a result, `tests/test_make_blueprint.py`); and the WhatsApp/Meta failure-alert channel used by both Proj19's and Proj16's error alerts is expired instance-wide (401, `OAuthException` code 190) — not a Proj19-specific bug, and refreshing it is outside this task (the owner needs to do it in Meta's developer console).

Checked live again on 2026-10-18 after the Make hardening: an unsigned request and one signed with the wrong key both stop at the HMAC filter; a real single-line order and a real two-line order pass it, update Airtable and `StockLog` per changed SKU, and the two-line order produced exactly one `refresh-catalog` run (`repository_dispatch`). See `AUDIT.md`.

Checked live on 2026-10-18 for the rebuild-from-snapshot change, one n8n tick at a time on a real test order: with the dispatch forced to fail, Airtable was written and the tick failed without moving the cursor; the next tick found Airtable already in sync, still saw the page behind on that one SKU, and dispatched; a tick during that rebuild left it alone; and once the rebuild committed, the next tick found nothing stale. The first tick also caught a real bug the unit tests couldn't: GitHub serves the snapshot's raw media type as something other than `application/json`, so n8n handed the planner a string and every synced SKU read as stale. The snapshot request now forces a JSON response, and a test pins it. See `AUDIT.md`.

Not done, and not claimed: a deployed/always-on n8n or Make (both ran locally/in the browser for this session's checks, then were deactivated), real customers or paid orders, a production store, and refreshing the instance-wide WhatsApp/Meta token (see "What is verified").
## Known limits

- n8n runs only while the local machine and n8n are on and this workflow is active. It is not deployed anywhere.
- Workflow static data (the cursor) is kept only while the workflow is **active**; a manual run in the editor does not persist it, and re-importing a workflow (a new workflow id) starts the cursor over.
- 250 orders and (in practice, one `productVariants(first: 250, ...)` call) 250 SKUs per tick; more than one page of matching Airtable rows for the SKUs in a tick fails the run rather than silently paginating.
- n8n's public REST API (v1) supports creating and reading credentials but not updating or deleting them — changing a credential's value programmatically means creating a new one and repointing the node(s) at it (see `AUDIT.md`'s failure-injection check), and a temporary credential made this way has to be removed by hand in the n8n UI afterward.
- Shopify's order search index is not instantly consistent: a just-created test order can miss the very next tick and get picked up on the one after (observed live, see `AUDIT.md`).
- This n8n install is Community Edition: `Settings > Variables` is paywalled/unavailable, so `MAKE_WEBHOOK_URL` and `THANK_YOU_ALLOW_LIST` cannot actually be set through the UI the workflow's code reads (`$vars.*`). A local-only, not-in-repo helper (`%USERPROFILE%\n8n-local\tools\build_stock_sync_import.py`) bakes both values in as literals on the LOCAL-IMPORT copy instead; the tracked `order-stock-sync.workflow.json` is unaffected and still reads `$vars.*`, which is what the export test asserts against.
- After three failed `refresh-catalog` runs in a row, n8n stops dispatching and fails every tick that has a stale SKU until a run succeeds. Clearing it is a person's job: fix the build, then run `refresh-catalog` once by hand (`workflow_dispatch`).
- Re-importing the Make blueprint resets the scenario's schedule to "every 15 minutes"; set it back to "Immediately as data arrives" after an import.

## Set up

1. **Shopify**: reuses Proj18's dev-store app (`jhurald05`, client-credentials grant). The Admin API scopes need `write_orders` in addition to Proj18's existing `write_inventory, write_locations, write_products, write_publications` (Shopify: a write scope implies its matching read scope, so `write_orders` alone covers reading orders too — no separate `read_orders` needed).
2. **GitHub**: two separately-scoped fine-grained tokens on the one repo — n8n's `Actions: write` only (sufficient for its `workflow_dispatch` call), and a second one for Make, `Contents: read and write` (needed for `repository_dispatch`; `Actions: write` alone is not enough for that endpoint).
3. **n8n credentials** (create via the API or UI, referenced by name in the generated workflow):
   - `Shopify client credentials` — `httpCustomAuth`, JSON body `{"body": {"grant_type": "client_credentials", "client_id": "...", "client_secret": "..."}}`
   - `Airtable token` — `httpHeaderAuth`, `Authorization: Bearer <token>`
   - `GitHub Actions token` — `httpHeaderAuth`, `Authorization: Bearer <token>`
   - `Gmail account` — `gmailOAuth2`, same Google account as `Google Sheets account` with Gmail's send scope added
4. **Import**: `tools/build_exports.py` writes `order-stock-sync.workflow.json` with the Airtable base id as the placeholder `appXXXXXXXXXXXXXX` and each credential id as `REPLACE_IN_UI`. Importing for real means substituting the real base id and the created credential ids into a copy of that file — **never commit that copy**. When two nodes share a credential *type* (`Airtable token` and `GitHub Actions token` are both `httpHeaderAuth`), match by the credential *name* already in the placeholder, not by type — matching by type alone sent the Airtable token to GitHub's API in this build (see `AUDIT.md`).
5. Set the workflow's error workflow to Proj16's `Workflow error alert`, then activate.
6. **Make**: build the `order-stock-sync` scenario once by hand from `make/order-stock-sync.blueprint.json`'s module list (a Shopify connection authorized against `jhurald05`, Airtable and Google Sheets connections, a Custom webhook trigger, and the second GitHub token in a `datastore:GetRecord`-backed value, never typed into the module). Export the blueprint after any UI change; never commit a version with a typed secret in it (`tests/test_make_blueprint.py` scans for that).
7. `tools/create_test_order.js --to jhurald05 --email <address> --sku CODE:QTY` creates a tagged (`proj19-test`), pending-payment order that decrements inventory like a real one, for repeatable live verification.
8. `.env.local` (gitignored): `SHOPIFY_SHOP`, `SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET`, `AIRTABLE_TOKEN`, `AIRTABLE_BASE_ID`, `GITHUB_ACTIONS_TOKEN`, `N8N_API_KEY`.

## How it is built

```
code/                     plain JS for the Code nodes, unit-tested with node --test
  plan_orders_query.js    cursor -> orders search query (overlap, first run, 250 cap)
  collect_skus.js         orders -> unique SKUs, and SKU -> order name(s)
  queries.js              the GraphQL queries/mutations and the webhook/tag queries
  lookups.js              injection-safe Shopify search / Airtable formula strings
  shopify_stock.js         exact-SKU stock picking from a Shopify variants response
  plan_updates.js          Shopify stock vs Airtable rows -> updates / skipped / rejected
  next_cursor.js           never backwards, never past now
  guards.js                Shopify's HTTP-200-with-errors GraphQL failures, and userErrors
  ensure_webhook.js        does an ORDERS_CREATE subscription for this URL already exist?
  stock_log_rows.js        updates + order names -> StockLog rows
  plan_rebuild.js          synced stock vs the published snapshot + recent runs -> dispatch or not
  thanks.js                allow-list/already-thanked/no-email planning, fixed email template
tools/
  build_exports.py        generates order-stock-sync.workflow.json (do not hand-edit)
  shopify.js               shared token/env/GraphQL-client helpers
  create_test_order.js     tagged test orders, --to <store> guard
make/
  order-stock-sync.blueprint.json   the Make scenario, exported as-is after a UI build
tests/                    node --test units + Python export/structure/blueprint tests
order-stock-sync.workflow.json
AUDIT.md
```

Run the tests: `node --test "tests/*.test.js"` and `py -X utf8 -m unittest discover -s tests -p "test_*.py"`. Regenerate the export after touching `code/*.js` or `tools/build_exports.py`: `py -X utf8 tools/build_exports.py`.
