# Proj19: Shopify order to stock sync (n8n core)

When an order exists in the owner's Shopify development store (`jhurald05`), this n8n workflow sets the matching Airtable catalog row's `Stock` to Shopify's current stock for the ordered SKUs, and rebuilds the public storefront page ([Proj18](../Proj18_Coffee_Storefront/)) through the existing `refresh-catalog` GitHub Actions workflow.

This is Plan 1 of two: the n8n core only, built and verified live against the dev store. Make, a thank-you email, a `StockLog` sheet, and Proj16's weekly-summary link are Plan 2, not built here.

## What it does

```
Every 5 minutes:
  read new/updated Shopify orders (cursor - 10 min overlap, up to 250)
    -> collect the unique SKUs ordered
      -> read each SKU's current Shopify stock
        -> for each Airtable Variants row that differs: set Stock = Shopify's number
          -> if anything changed: dispatch refresh-catalog (GitHub Actions)
            -> advance the cursor (only after every step above succeeded)
```

- **Absolute, not subtracted.** Airtable's `Stock` is always set to Shopify's current number for the SKU. Re-reading an order, a crash mid-run, or two ticks overlapping cannot double-count, because writing the same number twice changes nothing.
- **10-minute overlap, cursor advances last.** Every tick re-reads the last 10 minutes even if nothing changed, and the cursor only moves forward once the whole chain (SKU lookup, Airtable write, GitHub dispatch) has succeeded. A failure anywhere leaves the cursor where it was, so the next tick redoes the same work rather than silently skipping it.
- **Skips are reasoned, not silent.** A SKU with no Airtable row is skipped ("no Airtable row"). A SKU Shopify doesn't know, or has no single tracked stock for (untracked, ambiguous across duplicate variants, or a non-integer/negative quantity), is rejected with a specific reason rather than guessed at.
- **At most 250 orders a tick**, and the Airtable stock query is one `productVariants` call (no pagination past 250 variants) and one `listRecords` call (no pagination past whatever a single `filterByFormula` page returns — more than that fails loudly rather than silently missing rows).

## What is verified

Checked automatically (`node --test` for the seven `code/*.js` modules; Python `unittest` for the export generator and its structural/wiring/no-secrets checks; both run in CI on the Windows runner alongside the other Proj* suites): the cursor query planner (overlap, first run, future-cursor clamping, unreadable cursor), SKU collection (dedup, trim, tolerant of custom/missing SKUs), the Shopify and Airtable search-string builders (SQL/formula-injection-safe quoting), exact-SKU stock picking from a looser Shopify search match, the update planner (every skip/reject reason, chunking for Airtable's 10-record batch limit), the cursor-advance rule (never backwards, never past now), the GraphQL error guard (Shopify returns HTTP 200 with an `errors` array on failure, so the HTTP node alone wouldn't catch it), and the test-order tool. The export test suite confirms the shipped workflow JSON is byte-identical to what the generator produces from that same tested code, that the cursor is written in exactly one node, that HTTP nodes use named n8n credentials with no inline secrets, and that every Code node is self-contained (no `require`, parses with `node --check`).

Checked live against `jhurald05` (2026-09-20 through 2026-09-21, local n8n 2.39.8): see `AUDIT.md` for the full run-by-run record, including two real bugs found and fixed during the live run (an Airtable `POST` that needed to be `PATCH`, and a credential-matching bug in the local import script that sent an Airtable token to GitHub's API).

Not done, and not claimed: Make, a thank-you email, a `StockLog` sheet or the Proj16 weekly-summary link (Plan 2), a deployed/always-on n8n, real customers or paid orders, HMAC verification of anything (there is no webhook in Plan 1 — n8n only polls), or a production store.

## Known limits

- n8n runs only while the local machine and n8n are on and this workflow is active. It is not deployed anywhere.
- Workflow static data (the cursor) is kept only while the workflow is **active**; a manual run in the editor does not persist it, and re-importing a workflow (a new workflow id) starts the cursor over.
- 250 orders and (in practice, one `productVariants(first: 250, ...)` call) 250 SKUs per tick; more than one page of matching Airtable rows for the SKUs in a tick fails the run rather than silently paginating.
- n8n's public REST API (v1) supports creating and reading credentials but not updating or deleting them — changing a credential's value programmatically means creating a new one and repointing the node(s) at it (see `AUDIT.md`'s failure-injection check), and a temporary credential made this way has to be removed by hand in the n8n UI afterward.
- Shopify's order search index is not instantly consistent: a just-created test order can miss the very next tick and get picked up on the one after (observed live, see `AUDIT.md`).

## Set up

1. **Shopify**: reuses Proj18's dev-store app (`jhurald05`, client-credentials grant). The Admin API scopes need `write_orders` in addition to Proj18's existing `write_inventory, write_locations, write_products, write_publications` (Shopify: a write scope implies its matching read scope, so `write_orders` alone covers reading orders too — no separate `read_orders` needed).
2. **GitHub**: a fine-grained personal access token scoped to the one repo, **Actions: write** only (confirmed sufficient for the workflow-dispatch endpoint; no `Contents` permission needed).
3. **n8n credentials** (create via the API or UI, referenced by name in the generated workflow):
   - `Shopify client credentials` — `httpCustomAuth`, JSON body `{"body": {"grant_type": "client_credentials", "client_id": "...", "client_secret": "..."}}`
   - `Airtable token` — `httpHeaderAuth`, `Authorization: Bearer <token>`
   - `GitHub Actions token` — `httpHeaderAuth`, `Authorization: Bearer <token>`
4. **Import**: `tools/build_exports.py` writes `order-stock-sync.workflow.json` with the Airtable base id as the placeholder `appXXXXXXXXXXXXXX` and each credential id as `REPLACE_IN_UI`. Importing for real means substituting the real base id and the created credential ids into a copy of that file — **never commit that copy**. When two nodes share a credential *type* (`Airtable token` and `GitHub Actions token` are both `httpHeaderAuth`), match by the credential *name* already in the placeholder, not by type — matching by type alone sent the Airtable token to GitHub's API in this build (see `AUDIT.md`).
5. Set the workflow's error workflow to Proj16's `Workflow error alert`, then activate.
6. `tools/create_test_order.js --to jhurald05 --email <address> --sku CODE:QTY` creates a tagged (`proj19-test`), pending-payment order that decrements inventory like a real one, for repeatable live verification.
7. `.env.local` (gitignored): `SHOPIFY_SHOP`, `SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET`, `AIRTABLE_TOKEN`, `AIRTABLE_BASE_ID`, `GITHUB_ACTIONS_TOKEN`, `N8N_API_KEY`.

## How it is built

```
code/                     plain JS for the Code nodes, unit-tested with node --test
  plan_orders_query.js    cursor -> orders search query (overlap, first run, 250 cap)
  collect_skus.js         orders -> unique SKUs
  queries.js              the two GraphQL query strings
  lookups.js              injection-safe Shopify search / Airtable formula strings
  shopify_stock.js         exact-SKU stock picking from a Shopify variants response
  plan_updates.js          Shopify stock vs Airtable rows -> updates / skipped / rejected
  next_cursor.js           never backwards, never past now
  guards.js                Shopify's HTTP-200-with-errors GraphQL failures
tools/
  build_exports.py        generates order-stock-sync.workflow.json (do not hand-edit)
  shopify.js               shared token/env/GraphQL-client helpers
  create_test_order.js     tagged test orders, --to <store> guard
tests/                    node --test units + Python export/structure tests
order-stock-sync.workflow.json
AUDIT.md
```

Run the tests: `node --test "tests/*.test.js"` and `py -X utf8 -m unittest discover -s tests -p "test_*.py"`. Regenerate the export after touching `code/*.js` or `tools/build_exports.py`: `py -X utf8 tools/build_exports.py`.
