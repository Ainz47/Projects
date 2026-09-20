# Proj18 audit

Two passes: a guideline review of the code and a check by hand in a real browser. Every row is a real finding or a real result, with what was done about it.

## Guideline review
Reviewed with: web-design-guidelines (accessibility and UX), the motion checklist from emil-design-eng, the applicable subset of vercel-react-best-practices, and a forbidden-patterns list. Files: `src/ui/*.tsx`, `src/App.tsx`, `src/styles/*.css`.

| # | Source | Finding | Verdict | What changed |
|---|--------|---------|---------|--------------|
| 1 | web-design-guidelines | `App.tsx`: the "Loading product" fallback didn't end with an ellipsis | fixed | now "Loading product…" |
| 2 | web-design-guidelines | `SearchBox.tsx`: the search placeholder didn't end with an ellipsis | fixed | now "Search coffee and gear…" |
| 3 | web-design-guidelines | `ProductPage.tsx`: the not-found copy used first person ("We could not find that product.") | fixed | reworded to "That product could not be found." |
| 4 | web-design-guidelines | `components.css` `.drawer`: the scrollable cart panel had no `overscroll-behavior`, so an overscroll on touch could scroll the page behind it | fixed | added `overscroll-behavior: contain` |
| 5 | web-design-guidelines | Headings and button labels use sentence case throughout, not Title Case | not changed | a consistent, intentional voice choice across every screen and the committed screenshots; rewriting it now is a copy-wide change for a style call, not a functional issue |
| 6 | emil-design-eng (motion) | The cart drawer animates in (240ms slide and fade) but unmounts instantly on close, with no exit transition | not changed | an exit animation needs a delayed-unmount state machine around the drawer's mount lifecycle, which touches the tested focus-trap and focus-restore logic; out of scope for this audit pass. Entrance motion, reduced-motion handling and interruptibility (Escape, backdrop click) are all correct and covered by `tests/styles.test.ts` |
| 7 | vercel-react-best-practices | Product route code-split, cart context memoized, derived state (qty clamp, filtered list) not stored, list keys are stable ids, document listeners cleaned up, no barrel-file imports (`art/index.ts` is a real module, not a re-export barrel) | pass | none needed |
| 8 | forbidden-patterns | Checked the four committed screenshots and the running page against the list (gradients, glass, emoji-as-design, identical-shadow cards, centred-hero-plus-columns, lorem ipsum, invented social proof, one radius everywhere, low-contrast "elegant" grey, showy looping animation) | pass | none apply |
| 9 | Hero addition (this session) | Real hero + CTA added to the front page after the pass above, so it wasn't covered by rows 1-8. `impeccable`'s detector was run before and after as a second automated check: 0 findings both times | pass | none needed |
| 10 | `taste-skill` (`redesign-existing-projects` variant, pinned locally, see `PROVENANCE.txt`) | Full redesign audit against the checklist. Most items already satisfied (serif/sans pairing, tabular-nums, single warm accent with tinted shadows, `dvh` not `vh`, real CSS Grid, hover/active/focus states, empty/error/404 states, sentence-case copy, semantic HTML). Real findings: (a) no favicon or OG/Twitter meta tags; (b) product-page loading state was plain text, not a shape-matched placeholder; (c) every interactive control (buttons, badges, chips, qty stepper) used the identical `border-radius: 999px`, contradicting row 8's "one radius everywhere: none apply" (the earlier forbidden-patterns pass missed this); (d) flat surfaces with no texture | fixed (a), (b), (c); (d) applied | (a) `public/favicon.svg` (on-brand SVG, not stock) + OG/Twitter meta in `index.html`; (b) `ProductSkeleton.tsx`, static (no shimmer, respects this app's "nothing loops" motion rule), wired into the `ProductPage` Suspense fallback; (c) buttons/cart-button stay pill (999px) as the actual CTAs, badges/chips/qty stepper moved to `--radius-sm`/`--radius`; (d) faint static noise (~3.5% alpha, inline SVG `feTurbulence`) on the body background. Not changed: uppercase filter-group legends, flagged by the tool as an "all-caps subheader" anti-pattern, judged a false positive (standard e-commerce facet-label convention, not a marketing subheader) |

## Hand check
Chromium via Playwright MCP, `vite preview` on port 4173, checked 2026-09-20 against commit `0937a3a`.

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Load listing page | Pass | 30 products render, zero console errors |
| 2 | Search by URL, reload, back button | Pass | `history.length` stays flat across keystrokes, confirming `replaceState` doesn't stack entries |
| 3 | Combined filters + empty state + Clear-all | Pass | Resets every filter including the search text |
| 4 | Price sort | Pass | Ascending/descending both correct |
| 5 | Sold-out variant (Boquete Reserve Panama) | Pass | Struck-through, dashed, still selectable, not color-only |
| 6 | Add three to cart: focus, subtotal, Escape, opener-focus-return | Pass | One apparent anomaly (focus landing on the brand link instead of the disabled opener) traced to a stray leftover browser tab, re-tested in isolation and confirmed correct |
| 7 | Reload persistence | Pass | Cart survives a reload when storage is available |
| 8 | Full keyboard-only pass | Pass | Skip link -> search -> sort -> card -> product page -> Add to cart, visible focus rings throughout; Tab wraps both directions inside the open drawer |
| 9 | 390px width | Pass | Zero horizontal overflow on the listing; Filters toggle opens and closes correctly |
| 10 | `prefers-reduced-motion: reduce` | Pass | Verified via computed styles: `.hero`'s animation swaps from `hero-in` (translate+fade) to `fade-in` (opacity only); button press transitions become `none` |
| 11 | Blocked storage (`localStorage.setItem` made to throw) | Pass | No crash, no console errors; cart still works in memory; drawer shows "Your cart could not be saved on this device, so it will be empty after a reload." |
| 12 | `#/product/nope` (unknown handle) | Pass | Shows "Not found" / "That product could not be found." with a working "Back to all products" link, zero console errors |
| 13 | `browser_network_requests`, full reload + a client-side route change | Pass | Every request is to `localhost:4173`; nothing external |

## Airtable source: live check (2026-09-20)

Run against a real Airtable base (two linked tables, Products and Variants) with a personal access token kept in the gitignored `.env.local`. Results are the actual output of each step.

| # | Step | Result | Notes |
|---|---|---|---|
| 1 | `npm run seed:airtable` on an empty base | Pass | Output: `Products: table created`, `Variants: table created`, `Products: 30 records loaded`, `Variants: 124 records loaded`, `seeded 30 products and 124 variants`. The create-records batch size of 10 was accepted. |
| 2 | `npm run export:airtable`, then `npm run compare -- data/catalog.fixture.json data/catalog.export.json` | Pass | `exported 30 products (124 variants)`, then `identical apart from ids (30 products)`: the live round trip returns the fixture. |
| 3 | Two cells changed through Airtable's API (not by hand): `YIRGACHE-250g-WH` Price 18 to 19, `YIRGACHE-1kg-WH` Stock 18 to 2 | Pass | Read back from Airtable straight after: Price=19, Stock=2. |
| 4 | Re-export and compare again | Pass | `yirgacheffe-washed-ethiopia: differs in variants`. The snapshot holds `YIRGACHE-250g-WH` price 19.00 and `YIRGACHE-1kg-WH` stock 2. |
| 5 | Built page, product page, in Chromium via Playwright | Pass | 250g / Whole bean showed `$19.00` (fixture: $18.00). Selecting 1kg / Whole bean showed `$65.00` and "Only 2 left". Screenshot: `screenshots/airtable-live-check.png`. |
| 6 | Network requests from that page | Pass | 3 requests, all to `localhost:4173`, none to Airtable. |
| 7 | Suite with the snapshot committed | Pass | Typecheck clean; 25 test files, 154 tests passing (the snapshot test now runs); entry bundle 88.33 kB gzip as reported by the build, inside the size test's budget. |
| 8 | Preview server stopped | Pass | Checked by process command line: none left. |

Not checked: how the tool behaves when Airtable rate-limits a request (fake responses only), a token with fewer scopes than the four listed (the 401, 403 and 404 messages are tested against fake responses only), a table with more than 100 rows (paging is tested against fake responses only), and what happens to the base or its API access when the Airtable trial ends. The automated rebuild is checked in the next section.

## Airtable refresh workflow: live check (2026-09-20)

The `refresh-catalog` workflow, run on GitHub Actions against the same Airtable base, with the token and base id held as repo secrets. Results are the actual output of each step. Run ids are from `Ainz47/Projects`.

| # | Step | Result | Notes |
|---|---|---|---|
| 1 | Set the two secrets by piping from the gitignored `.env.local` into `gh secret set` (never printed) | Pass | `gh secret list` shows `AIRTABLE_BASE_ID` and `AIRTABLE_TOKEN` with update times and no values. |
| 2 | One cell changed through Airtable's API: `YIRGACHE-250g-WH` Price 19 to 23.45 | Pass | Output: `Price 19 -> 23.45`. Before it, the live entry bundle `index-CHxL1_Di.js` had 0 matches for `23.45`. |
| 3 | Repository dispatch with event type `catalog-refresh`, sent with the GitHub CLI (run 35503759707) | Pass | Succeeded in 55 s. Log: `exported 30 products (124 variants)`, 26 test files passed, then a commit and push. |
| 4 | The commit that run made (`075a11d`, by `github-actions[bot]`) | Pass | One line changed in `data/catalog.export.json`, `"19.00"` to `"23.45"`, plus 3 rebuilt files in `docs/coffee-store/`. |
| 5 | The live page after that commit | Pass | The entry bundle changed to `index-B-5TPdHI.js` and had a match for `23.45` at the first check after the run. So GitHub Pages rebuilt after a push made with the built-in token. |
| 6 | Cell put back (`23.45 -> 19`), then a manual run, workflow dispatch (run 35503868532) | Pass | Succeeded in 58 s, commit `c72ec3b`. `git diff c3c410b HEAD` on the snapshot is empty. The live bundle went back to `index-CHxL1_Di.js` with 0 matches: the same file name as before the test, so the CI build reproduced the earlier build. |
| 7 | A bad edit: `YIRGACHE-250g-WH` Price cleared in Airtable, then a manual run (run 35503978132) | Pass | Failed in 33 s at the export step: `export failed: Airtable data is not usable (1 problem): - Variants recb9NI5QUKfK3ouX: Price must be a number of 0 or more`. Nothing was committed; `main` stayed at `c72ec3b`. |
| 8 | Cell put back to 19, then `npm run export:airtable` locally | Pass | `exported 30 products (124 variants)`, and `git status` on `data/` is clean: the export equals the committed snapshot. |
| 9 | The `tests` workflow after the bot commits | Observed | It ran for the commit that added the workflow (`eaeb339`) and did not run for `075a11d` or `c72ec3b`, as GitHub documents for commits made with the built-in token. That is why the refresh runs the type check, tests and build itself before committing. |
| 10 | The three run logs searched for the shape of a base id or a token | Pass | 0 matches in each. GitHub masks secret values in logs. |
| 11 | `tests/refresh-workflow.test.ts` | Pass | 9 tests on the workflow file (triggers, where the secrets are used, permissions, what is committed, step order). Suite: 26 test files, 163 tests. |

Not checked: a token with only the two read scopes in the secret (the runs used the same token as the seed, which can also write), Make or an Airtable automation sending the dispatch (only the GitHub CLI was used), starting the workflow without write access to the repo, two dispatches overlapping (the queueing is configured, not exercised), what a refresh does after the Airtable trial ends (it should fail at the export and commit nothing, as in step 7, but I have not run that), and Linux CI.
