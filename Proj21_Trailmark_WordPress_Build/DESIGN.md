# Trailmark design system (as shipped)

Derived from the live site on 2026-10-04 (https://framelake.s6-tastewp.com), not from the plan.
Direction contract: `.impeccable/surfaces/pages-home.md` (Pre-flight Checklist). Product brief: `PRODUCT.md`.

## Where things live

| What | Where | Edited by |
|---|---|---|
| Colour and font tokens | Elementor Site Settings, kit post 7 (system slots + `tm_*` custom globals) | Elementor editor (EMCP free cannot write system slots) |
| Everything widgets cannot express | `trailmark.css` -> `py build_css.py` -> `py emcp_call.py push-css` | this repo, one copy |
| Where that CSS loads | HTML widget 40a983b inside the UAE header template (post 176), so it reaches every page incl. WooCommerce and blog | generated, never hand-edited |
| Header / footer | UAE templates 176 / 180, menus Primary (18) and Footer (19) | Elementor |
| Audience pages | one saved template (55) -> For CS teams 52, Implementation 57, RevOps 59 | Elementor |

## Colour

| Token | Hex | Kit slot | Use |
|---|---|---|---|
| laminate | #EDEFEA | `tm_laminate` | page ground |
| card | #FAFAF7 | `tm_card` | cards, sheets, dropdowns, text on ink |
| ink | #14171B | system primary + text, `tm_ink` | text, rules, the one solid button, footer and CTA bands |
| yellow | #F2C200 | system accent, `tm_yellow` | card tabs, definition bands, CTA button on ink, focus ring on ink |
| HOLD red | #D2261C | `tm_hold` | the HOLD state only, never decoration |
| graphite | #4F575F | system secondary, `tm_graphite` | secondary text (darkened from the contract's #5B636B for AA on laminate) |
| rule | ink at 14% | CSS only | hairlines, dotted leaders |

Kit system colours must stay mapped as above: third-party widgets (UAE nav menu) colour themselves from the system slots, so Elementor's defaults (#6EC1E4 / #61CE70) leak straight into the header and footer.

## Type

- Archivo: headings 700 (H1 56, H2 36, H3 22), body 400 at 18, buttons 600 at 17. Kit globals `tm_display`, `tm_h2`, `tm_h3`, `tm_body`, `tm_button`; system slots also Archivo.
- B612 Mono 400 at 14: checklist lines, states, leaders, labels, breadcrumbs, product meta (`tm_mono`). Not for prices: its full-width "." reads as "$0. 00".
- No custom typography may reuse a system id (primary/secondary/text/accent). Those collisions squashed the hero tab titles until removed.

## Components

- **Checklist row** (`.tm-list > .tm-item`): box, NAME (mono caps), dotted leader, STATE. Four colour-independent states, each with its own box: CHECK (filled tick), IN PROGRESS (half box), HOLD (red outline box + red state label "HOLD N DAYS"), NOT STARTED (empty box, graphite). Leaders drop below 768px.
- **Sample card** (native Tabs widget, `.tm-card`): yellow tabs per account, ring-binding strip, one open card. Becomes an accordion on phones.
- **Sheet** (`.tm-sheet-wrap` + `.tm-tab`): a tabbed card for hold lists and notes.
- **Definition band** (`.tm-def`): yellow full-bleed section, numbered rows.
- **Counter board** (`.tm-board`): native Counter widgets with ink left rules, labelled "Sample data".
- **Carousel** (`.tm-carousel`): native Image Carousel, square ink dots, slides are renders of the live sample card.
- **Buttons**: Book a demo is the only solid ink button on laminate (header and heroes); on ink bands it inverts to yellow. Every other action is the 2px ink outline. CF7 submit is solid because it is the demo request.
- **HOLD rule** for every sample: "HOLD N DAYS" counts days since the previous step and N must exceed that step's limit (team invited 3, data source 5, first report 5, second team 10). `fix_hold_days.py` enforces it on the audience pages.

## Motion

One card switch transition (transform, 200ms, `cubic-bezier(.16,1,.3,1)`), off under `prefers-reduced-motion`. Counters animate once on scroll. Carousel autoplays at 5 s and pauses on hover and interaction. No scattered hover effects.

## Layout rules (Elementor V3)

- Column containers: `content_width: full` + explicit `width`. `boxed` silently ignores `width`.
- Always pass `flex_align_items` for text columns (build-page defaults it to `center`).
- Verify layout writes in the compiled `uploads/elementor/css/post-N.css`, not the tool's success flag.
- Phones: 16px side gutter; header is logo | Book a demo | menu toggle. UAE leaves its hidden dropdown in flow at full width, so `trailmark.css` lifts it out below 1025px. Check `document.documentElement.scrollWidth` equals the viewport after any header change.

## Raster provenance

| File | Media id | Made by | Source |
|---|---|---|---|
| card-halden-co.png, card-brightwell-freight.png, card-oakline-studio.png | 206, 207, 208 | `media_capture.py cards` | screenshots of the live Home tabs widget 97ad0d5, 2x |
| walkthrough.webm | 209 | `media_capture.py video` | Playwright screen recording of the live Home page |
| product_cover.png | 135 | `checklist_pdf/build_pdf.py` | first page of the checklist PDF, rendered from `checklist.html` |
| trailmark-onboarding-checklist.pdf | 134 | `checklist_pdf/build_pdf.py` | `checklist.html` printed by Chromium |

No generated or stock imagery. All people and accounts are made up and labelled "Sample data".

## Third-party markup fixes

Script widget 4ec6148 in the header template (hidden wrapper, `.tm-jsonld`), runs on every page:
- removes `role="tablist"` from Elementor Tabs' content wrapper (it holds tabpanels: invalid ARIA);
- turns the phone-only tab titles (`.elementor-tab-mobile-title`, which lost their tablist parent with the role above) into `role="button"` with `aria-expanded`, kept in sync with Elementor's `elementor-active` class by a MutationObserver;
- gives UAE's skip link a `#content` target (Elementor pages have none).
Source: `a11y_fixes.html` -> `py emcp_call.py push-a11y`. Never edit the widget in Elementor directly.
Contrast: `.tm-steps .tm-item p.tm-ink-text` must out-rank `.tm-steps .tm-item p` (graphite on yellow is 4.36:1, ink passes).
Accessibility 100 on Home, About and Product, mobile and desktop (`polish` rows, 2026-10-04).

## Finish review (2026-10-04, against the direction contract)

Verdict: **ships**, with the deviations below recorded rather than hidden.

Holds: laminate / ink / yellow / HOLD-red world; red only on HOLD; four colour-independent states; Archivo + B612 Mono; ring-bound tabbed card with dotted leaders; Book a demo the only solid ink button on laminate; no logo bar, no three-card grid, no invented customers or stats; every proof slot labelled "Sample data"; every raster has provenance (table above); one card transition under 250 ms with a reduced-motion guard.

Deviations:
- No B612 Mono kicker above the H1 (dropped by decision: no kickers anywhere).
- Phones: the sample card is Elementor's Tabs-as-accordion (all three account titles, first open), not a Toggle that unfolds from the HOLD line.
- Graphite is #4F575F, not the contract's #5B636B (AA on laminate).
- The Home carousel repeats the hero's three cards. It exists for feature parity with the target, and it is the only place the cards autoplay.
