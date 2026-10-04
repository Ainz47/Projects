# Trailmark: a B2B software site in WordPress, built and fixed through code

**See it:** [static copy on GitHub Pages](https://ainz47.github.io/Projects/trailmark/) (permanent). The original runs on a TasteWP WordPress sandbox at [framelake.s6-tastewp.com](https://framelake.s6-tastewp.com/), which is a trial and will stop resolving when it ends; the static copy is the record after that.

Trailmark is a fictional onboarding-analytics product. I built its site to match the page set and functions of a real small-business software site from a job post (not its design or copy), so I could show the rebuild that job asked for: mobile-first pages, working demo and contact paths, a WooCommerce shop, technical SEO, redirects from old Shopify URLs, speed and accessibility, all measured before and after.

Every number, customer and account on the site is made up and labelled "Sample data". The footer says it's a demo.

## What's on it

- **15 public pages** in Elementor (V3 containers and widgets) on the Hello Elementor theme: Home, Product, three audience pages generated from one saved template, About, a six-step guide with a walkthrough video, Resources, two Notes posts, Book a demo (Calendly + Contact Form 7), Contact (CF7), and a WooCommerce shop with one free PDF product.
- **Site-wide header and footer** as Elementor Header & Footer templates, with the mobile header rebuilt so nothing scrolls sideways.
- **One stylesheet, one place:** `trailmark.css` is the source, `build_css.py` minifies it, `emcp_call.py push-css` writes it into a single widget inside the header template, so it reaches every page (WooCommerce and blog included) instead of being pasted per page.
- **A working checkout:** guest checkout of the $0 product was tested end to end, including the PDF download matching the local build. The test order was deleted afterwards.

## Measured before and after

Local Lighthouse 12 (lab numbers on one machine; mobile = Moto G emulation on simulated slow 4G). Full log in [`lighthouse/scores.csv`](lighthouse/scores.csv).

| Page | Strategy | Performance | Accessibility | SEO |
|---|---|---|---|---|
| Home | mobile | 72 → 77 | 93 → 100 | 92 → 100 |
| Home | desktop | 96 → 96 | 93 → 100 | 92 → 100 |
| About | mobile | 88 → 90 | 96 → 100 | 92 → 100 |
| About | desktop | 98 → 99 | 96 → 100 | 92 → 100 |
| Product | mobile | 80 → 86 | 100 → 100 | 92 → 100 |
| Product | desktop | 94 → 98 | 100 → 100 | 92 → 100 |

Home mobile Largest Contentful Paint went from 4.66 s to 4.2 s.

## The problems worth pointing to

**The SEO plugin that wasn't running.** Rank Math showed as active but never booted on this WordPress 7.1 / PHP 8.5 install: no admin menu, no REST routes, nothing in the page output. I moved to Yoast and wrote titles and descriptions for all 15 URLs from a script (`seo.py`, through Yoast's own bulk-editor route, because the generic post-meta route refuses Yoast's protected keys). Cart, checkout and account are noindexed and out of the sitemap, the header/footer template and author sitemaps are gone, and the schema graph carries Organization plus a SoftwareApplication linked by `@id`.

**Redirects from old Shopify URLs.** Seven 301s (`/products/...`, `/collections/...`, `/pages/...`, `/blogs/news`, plus one renamed page) in the redirect manager that ships with the EMCP Tools plugin, since free Yoast has none. Its API only accepts a logged-in admin session, so the rules went in with `fetch` and a REST nonce from a logged-in admin page, then each one was checked with curl.

**Accessibility fixes in markup I don't control.** Elementor's Tabs widget puts `role="tablist"` on a wrapper that also holds the panels, which is invalid. Removing it left the phone-only tab titles without a parent, so on phones they now act as accordion buttons with `aria-expanded`, kept in sync with Elementor's own state by a MutationObserver ([`a11y_fixes.html`](a11y_fixes.html)). The About page failed contrast because two CSS rules had equal specificity and the wrong one came later in the file.

**Speed.** The biggest render-blocking request was Google Fonts asking for every weight from 300 to 900 with italics. Switching Elementor to serve the fonts from the site itself removed the third-party requests.

**A static copy that still reads like the site.** [`static_export.py`](static_export.py) fetches every public page and every asset it and its CSS reference, including image URLs Elementor hides inside entity-encoded JSON, and rewrites the site address for a GitHub Pages subfolder.

## What's NOT done or NOT verified

- GA4 and Google Tag Manager are not installed on this site.
- Font Awesome is still loaded by the header plugin (about 0.3 s render-blocking on mobile). Removing it needs a PHP dequeue, which this sandbox gives no route for.
- In the static copy, forms and checkout are switched off with a note pointing to the live site. Calendly still loads, because it's an external embed.
- Lighthouse numbers are local lab runs, not field data.

## Files

| File | What it does |
|---|---|
| [`DESIGN.md`](DESIGN.md) | Design tokens, components, image provenance, third-party fixes, and the finish review |
| [`trailmark.css`](trailmark.css), [`build_css.py`](build_css.py) | The one stylesheet and its minifier |
| [`a11y_fixes.html`](a11y_fixes.html) | Script widget that repairs Elementor and header-plugin markup on every page |
| [`emcp_call.py`](emcp_call.py) | Calls EMCP Tools (Elementor MCP server) from a script: pushes the stylesheet and the a11y script |
| [`seo.py`](seo.py) | Writes and checks titles and descriptions through Yoast's REST route |
| [`lighthouse.py`](lighthouse.py) | Local Lighthouse runs, one CSV row per page and strategy |
| [`static_export.py`](static_export.py) | Builds the GitHub Pages copy |
| [`wp_api.py`](wp_api.py) | Shared REST helper. Credentials come from the local MCP config at run time and are never stored here |

The live copy is in [`docs/trailmark/`](../docs/trailmark/).
