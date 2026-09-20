# Proj18: Lantern Roasters (demo), a dynamic coffee storefront

A storefront for a made-up coffee shop, built to show the parts of a real store that take care: search and filters you can share as a link, options such as weight and grind that change the price and stock, and a cart that survives a reload. Try it: [ainz47.github.io/Projects/coffee-store/](https://ainz47.github.io/Projects/coffee-store/).

![The listing with the light roast filter on](screenshots/listing.png)

The products are made up, there is no checkout, and nothing is sold.

## What it does
- **Listing.** Search over title, tags, vendor, type, origin and roast (every word must match), filters for type, origin, roast, in stock and price, and four sort orders. All of it lives in the URL hash, so a filtered view is a link you can send. Under "Featured", sold-out products sort last. The result count is announced to screen readers.
- **Product page.** Options such as weight and grind choose a variant, and the price and stock update for each combination. Values with no stock are marked and struck through but stay selectable, so nobody is stuck; choosing a sold-out combination says "Sold out" and turns Add off. Stock of 5 or fewer is labelled.
- **Cart.** A drawer with quantity steppers capped at stock, a subtotal and a free-shipping bar. It is saved in the browser. On load, any line whose variant no longer exists is dropped and quantities are clamped to stock. Checkout is a disabled demo button.
- **When things go wrong.** A catalog that fails to load, or has no valid products, shows a screen that says why. An unknown product link shows a not-found page. Blocked or corrupt browser storage means an empty cart and a note, not a broken page.

![A product page where the 1kg option is sold out](screenshots/product.png)

## What is verified
Checked automatically (vitest, and on every push in GitHub Actions on a Windows runner): the product normalizer, which rejects a bad product with a reason instead of guessing; search, filters, sorting and the URL round trip; variant selection; the cart reducer, stock clamping and tolerant storage; the generated art (well-formed, deterministic, no external references); the whole app driven through its rendered pages and drawer in jsdom; the exporter against fake API responses (pagination, throttling, retries, missing credentials, no token in output); the stylesheet rules (transform and opacity only, nothing over 300ms, reduced motion honoured); the type check; a size budget on the built JavaScript; a check that the page makes no request to another origin; and a check that the committed page is exactly what the source builds. The Airtable client and mapper are tested against fake responses, including a round trip that turns the fixture into Airtable rows and back and gets the same catalog. The refresh workflow's safety rules (what can start it, where the secrets are used, what it may commit, the order of its steps) are pinned by a test that reads the workflow file.

Checked by hand in a real browser (Chromium via Playwright), against the built page: search/filter/sort by URL with correct back-button and reload behaviour, the sold-out variant styling, adding to cart with focus moving correctly on open/close/Escape, cart persistence across a reload, a full keyboard-only pass with visible focus rings, no horizontal overflow at 390px width, `prefers-reduced-motion` actually swapping the animation used, a blocked-storage fallback that degrades to an in-memory cart with a visible note instead of breaking, an unknown-product route showing the not-found page, and that every network request stays on the same origin. Also reviewed against a design/accessibility guideline checklist and a UI-pattern detector, twice (before and after adding the front-page hero). Full results, including two items intentionally left as-is with reasons: `AUDIT.md`.

Not done, and not claimed: the published page showing Shopify data (it shows the Airtable snapshot; see below), a checkout of my own (the development store's checkout is Shopify's, and I never placed an order), payments, accounts, a backend, or that the products exist.

## Using data from a real Shopify store
`data/catalog.fixture.json` has the same shape as the `products` query in `exporter/client.mjs` (Admin GraphQL API version 2026-07). To try a real store, create an app in the Shopify Dev Dashboard, install it on a development store, then in a Bash shell. I ran everything below with the scopes `write_products`, `write_inventory`, `write_locations` and `write_publications` (the seed needs to read the store's stock location and Online Store channel as well as write products); I have not tried a read-only set or narrowed that list, so treat it as more than the minimum.

    SHOPIFY_SHOP=your-store SHOPIFY_CLIENT_ID=your-client-id SHOPIFY_CLIENT_SECRET=your-client-secret npm run export

That writes `data/catalog.export.json`. The built page picks it up automatically. The `custom.origin` and `custom.roast` metafields feed the origin and roast filters; without them those filters are empty.

To load the 30 fixture products into an empty development store first, run `npm run seed:shopify -- --to your-store` (the store has to be named on the command line as well as in `.env.local`, so a wrong `.env.local` cannot seed the wrong store). It checks the store before writing anything, and it updates products by handle, so a second run does not duplicate them.

This has run against a real development store: the token request in `exporter/auth.mjs` worked as written, the seed loaded 30 products and 124 variants and published them, and an export from the store matched the fixture apart from ids and tag order (Shopify returns a product's tags sorted; 24 of the 30 products had the same tags in a different order). Results are in `AUDIT.md`. The exporter never prints or writes the token. The published page still shows the Airtable snapshot, not the Shopify store.

The seed loads data only, so `npm run seed:store -- all --to your-store` finishes the job: it gives each product a picture (the demo page's generated art, rendered to PNG with `@resvg/resvg-js` and uploaded through Shopify's staged uploads) and creates five rule-based collections (Coffee, Brewing gear, and three by roast) plus the products on the front page collection. `images` or `collections` run one half. It has the same `--to` guard, checks the store before writing, and a second run changes nothing. On the development store all 30 products got a picture and the collection counts match the fixture, read back from the public storefront (results in `AUDIT.md`). The store itself is a public development store on Shopify's default theme with fictional products. Payments are switched off (see the theme paragraph below), and the theme text (store name, hero, banner, menu) is still Shopify's default.

The same app also builds as a Shopify theme. `npm run build:theme` writes one script and one stylesheet to `theme/assets/`, and `theme/` holds the layout, one template per Shopify route, and a Liquid snippet that prints the store's products into the page as JSON in the same shape as the fixture, so the app reads its products from Shopify. Its Checkout button fills Shopify's own cart and opens Shopify's checkout. To try it: `npx @shopify/cli theme push --path theme --store your-store.myshopify.com --unpublished --theme "Lantern storefront"` (the CLI asks you to approve a browser login), then open the preview link it prints. It does not touch your live theme, and you publish it yourself if you want it live. I pushed it to the development store as an unpublished theme and shopped through it in a browser (results in `AUDIT.md`). It is now the live theme of the development store: https://jhurald05.myshopify.com. It is a public store with made-up products, and payments are switched off, so checkout reads "This store can't accept payments right now" with a disabled Pay now button and no order can be placed; I never placed one. Shopping through it turned up two things, both fixed: PayPal had been left on, and the store currency was PHP while the prices are dollar amounts. The store is now in USD, and the page reads its currency from the store. The layout is a custom storefront, so it is not editable in Shopify's theme editor, and a Liquid loop stops at 50 products.

## Using data from Airtable
The catalog can come from an Airtable base with two linked tables, Products and Variants. `npm run seed:airtable` creates them and loads the 30 fixture products, and `npm run export:airtable` reads them back into `data/catalog.export.json`. The page never talks to Airtable: the export is a snapshot you commit and the build reads it, so no token is ever in the page.

1. In Airtable, create an empty base and a personal access token with the scopes `data.records:read`, `data.records:write`, `schema.bases:read` and `schema.bases:write`, limited to that base.
2. Create `Proj18_Coffee_Storefront/.env.local` (it is gitignored) with two lines: `AIRTABLE_TOKEN=` followed by your token, and `AIRTABLE_BASE_ID=` followed by the `app...` id in the base's URL.
3. `npm run seed:airtable` creates the tables and loads the fixture. Add `-- --allow-existing` to write into tables that already hold rows.
4. Edit products in Airtable, then run `npm run export:airtable` and `npm run build`, and commit `data/catalog.export.json` together with the rebuilt page.

There is also a workflow, `refresh-catalog`, that does step 4 for you. It starts from a repository dispatch with the event type `catalog-refresh` (the call a Make scenario or an Airtable automation would send) or from a manual run, and both need write access to the repo. It exports from Airtable with two repo secrets that only the export step can see, runs the type check, the tests and the build, and only then commits the refreshed snapshot and page to `main`. If a row in Airtable is broken, for example a blank price, the run fails at the export and nothing is committed. A run takes about a minute and the published page updates soon after. I ran it once by repository dispatch and once by workflow dispatch, both sent with the GitHub CLI (results in `AUDIT.md`). I have not connected Make or an Airtable automation to it, and I have not checked that either can send that call. The commits it makes do not start the `tests` workflow, because GitHub does not run workflows for commits made with the built-in token, so the refresh runs the type check, tests and build itself before it commits.

This has run against a live Airtable base: the seed loaded 30 products and 124 variants, and the export matched the fixture apart from ids. I then changed one variant's price (18 to 19) and another's stock (18 to 2) in Airtable through its API, re-exported and rebuilt, and the product page showed $19.00 and "Only 2 left" for those variants. The published page shows the latest snapshot, refreshed on request, not live Airtable data, and the products are still made up.

![The product page after the edits, showing 1kg with only 2 left](screenshots/airtable-live-check.png)

`data/catalog.export.json` is written by whichever exporter ran last, this one or the Shopify one, in the same shape. When it exists the built page uses it; the tests always read the fixture. Columns are matched by name, so renaming one in Airtable makes the export fail with a message naming the row, instead of publishing a half-empty page. Each product holds up to two options (for example Weight and Grind) and its rows keep their order through a Position column. `npm run compare -- <catalog a> <catalog b>` shows what differs between two catalogs, ignoring ids and the order of tags.

## Known limits
- The catalog is 30 made-up products, prices in US dollars, held in an Airtable base and shown as a committed snapshot (the fixture is the fallback and what the tests use).
- The cart is per browser. It is not synced across tabs or devices.
- Routing uses the URL hash, because GitHub Pages cannot rewrite paths.
- Product art is generated SVG, not photography.

## How it is built
```
data/catalog.fixture.json     Shopify-shaped products, made by tools/make_fixture.mjs
exporter/                     Admin GraphQL client (auth, pagination, throttling, retries)
airtable/                     Airtable client, record mapper, seed and export scripts
src/model/                    the Product type and the GraphQL normalizer
src/lib/                      search and filters, variants, cart, money: plain tested functions
src/art/                      generated SVG for bags, drippers, kettles and grinders
src/ui/                       React components that only render the modules above
src/data/source.ts            the one place that decides snapshot or fixture (tests always use the fixture)
```
The logic lives in plain modules and the components only render it, which is why most of the tests need no browser. Product art is shown through `<img src="data:image/svg+xml,...">` and never injected as HTML, and a test fails if the source ever writes HTML from a string. Nothing loads from another origin: no CDN, no web fonts, no analytics.

## Run and rebuild
```
cd Proj18_Coffee_Storefront
npm ci
npm test               # Node 24
npm run typecheck
npm run dev            # http://localhost:5173/Projects/coffee-store/
npm run build          # writes ../docs/coffee-store, which GitHub Pages serves
npm run fixture        # regenerate data/catalog.fixture.json
```
Do not hand-edit `docs/coffee-store/`. Change the source, rebuild, and commit the result; CI fails if the committed page differs from what the source builds.
