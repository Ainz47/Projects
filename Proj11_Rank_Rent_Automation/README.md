# Rank and Rent Deployer

One-click WordPress site builder for rank and rent local service businesses. Fill in a browser form, click Deploy, and the tool writes every page with AI, sources matching photos, and publishes a complete multi-page site.

Built as an operator tool rather than a developer script: the person running it needs no Python, no WordPress admin experience, and no knowledge of the codebase.

## Live demo

[toughgrape.s6-tastewp.com](https://toughgrape.s6-tastewp.com/) — a full run against a fresh TasteWP install, published 2026-09-26 (native Gutenberg blocks, v2), 7-day trial window. This is a free-trial WordPress sandbox and **will expire and stop resolving once the trial ends** — the screenshots below are the durable record once it does. (An earlier same-day run on a shorter-lived TasteWP trial, `abashedbike.s2-tastewp.com`, is what the screenshots and console-validation check below were taken from; it expires sooner and isn't the link to send out.)

## What's verified

Every feature claim below was checked against the actual source, not just the old description:

- **A second real end-to-end deploy, this time on the native-Gutenberg-block v2 build**: an 8-page run against a fresh TasteWP install (`abashedbike.s2-tastewp.com`) on 2026-09-26, all pages published with `"status": "success"`. Opened each published page's block editor afterward and read the browser console directly — zero block-validation errors (only unrelated host-platform CORS noise from TasteWP's own onboarding widget, and core WP deprecation notices). `screenshots/Preview_v2/` and `screenshots/Editor_v2/` are the public-facing evidence.
- **Repeated the same run against a second, longer-lived TasteWP trial** (`toughgrape.s6-tastewp.com`, 7-day window) to have a link that outlasts a single outreach cycle — also 8/8 pages published, 0 failed. This is the link in "Live demo" above.
- **The original end-to-end deploy is also on record**, not just described. `logs/run_summary_20260511_234402.json` and five per-page JSON files show a real run against a live (free-trial TasteWP) WordPress install, five service pages, all `"status": "success"` with real WP page IDs and URLs. `screenshots/Editor/` and `screenshots/Preview/` (committed to this repo, not gitignored) are actual WP admin screenshots of the published result, including real Gemini-written copy with local landmark references baked into the text.
- **Idempotent deploys are real**: `wp_client.py`'s `upsert_page`/`upsert_post` look up the target by slug first, update if found, create if not, exactly as claimed.
- **Content caching and granular retry are real**: `deployer.py`'s main `deploy()` checks `content_cache` before calling Gemini for every page type, and `deploy_retry()` re-runs only the specific failed items, then rebuilds the services hub and blog listing afterward, matching the README's description.
- **The nonce/allowlist claim on the bundled plugin is real**: `plugins/rr-contact-handler.php`'s option writer calls `check_ajax_referer('wp_rest', '_wpnonce')` and restricts writes to an explicit allowlist (`rr_footer_config`, `rr_contact_email`), with a code comment explaining why (unrestricted option writes escalate to admin via `users_can_register` + `default_role`).
- **The password-stripping claim is real**: `history.py` pops `wp_password` from every record on read, with a comment noting this scrubs entries written by older versions.
- **Cancellable and loopback-only claims are real**: `server.py` binds to `127.0.0.1`, gates `FLASK_DEBUG` behind an env var defaulting off, and checks a global `threading.Event` on every log line so a deploy in progress can be interrupted from the UI.

## What's NOT verified

- Both runs' evidence comes from disposable TasteWP trial sites (`*.s6-tastewp.com`, `*.s2-tastewp.com`), not a real production WordPress host. The tool has not been shown running against a paid/permanent WP install in this repo's history. The live link above will stop working once TasteWP deletes the trial; the committed screenshots are what survives that.
- The per-run JSON logs (`logs/`) are gitignored and local-only; they were used to verify the claims above but are not visible to someone browsing the public repo. The committed screenshots are the public-facing evidence.

## Overview

The system runs as a local Flask server with a browser UI. You supply a WordPress site, business details, and a list of services. It handles the rest:

1. **Content generation**: Gemini writes homepage copy, per-service page copy, blog posts, and FAQs, all scoped to the specific city and trade
2. **Media sourcing**: Gemini generates industry-aware image search queries, Pexels supplies the photos, and each one is uploaded into the WordPress media library
3. **Publishing**: Pages are built as pure HTML/CSS blocks on the Astra theme and pushed through the WordPress REST API, with live progress streamed back to the browser

## What It Builds

| Page | Contents |
|------|----------|
| Homepage | Hero, intro, services grid, process steps, trust section, CTA |
| Service pages | One per service: hero, four content sections with photos, CTA |
| Blog posts | AI-written posts with featured images, count configurable |
| Blog listing | Card grid linking every post |
| FAQs | 12 Q&As generated against the specific service list |
| Contact | Business details, quote form, Google Maps embed |

A standard run publishes 14 pages.

## Key Features

- **Idempotent deploys**: re-running updates existing pages instead of creating duplicates, so the tool is safe to run repeatedly against a live site
- **Content caching**: generated copy is cached per configuration, so retrying a failed item reuses the existing Gemini output instead of burning API quota
- **Granular retry**: a failed page can be re-attempted on its own without touching anything that already succeeded, and the blog listing rebuilds itself afterwards
- **Live progress streaming**: deployment logs stream to the browser over server-sent events rather than leaving the operator watching a blank screen
- **Cancellable**: a running deploy can be stopped mid-flight from the UI
- **AI-assisted interlinking**: Gemini proposes external keyword targets, filtered against the internal link map so it does not suggest terms the site already owns, then links are injected across published pages and posts
- **Deployment history**: every run is recorded with its configuration and published URLs
- **Theme handling**: verifies Astra is installed and active, installing it automatically where the host permits
- **Native Gutenberg blocks, no page builders**: pages are built from real `wp:*` block markup that validates clean in the block editor (not one big HTML dump), so they stay fast, portable, and editable by hand afterward. `docs/GUTENBERG_CONVERSION_NOTES.md` is the debug log from that conversion — 13 numbered validator mismatches found and fixed
- **MCP-addressable via a companion abilities plugin**: `rr-wp-abilities/` registers `rr/create-page`, `rr/get-page`, `rr/update-page`, and `rr/list-pages` on WordPress's Abilities API, so an MCP client (Claude Code or any other) can create and inspect real block-editor pages directly, not just through this app's own UI. Setup steps and gotchas in `docs/WP_MCP_SETUP.md`

## Architecture

```
Browser form (index.html)
    ↓ POST /deploy
server.py (Flask, SSE log stream)
    ↓
src/config.py (DeployConfig validation)
    ↓
src/deployer.py (orchestrator)
    ├── src/content_gen.py    → Gemini: page copy, image queries, FAQs
    ├── src/image_fetcher.py  → Pexels search + WP media upload
    ├── src/content_cache.py  → per-config content cache
    ├── templates/*.py        → HTML/CSS block builders per page type
    └── src/wp_client.py      → WordPress REST API + admin-ajax
    ↓
src/history.py (deployment record)
```

### Core Components

| Module | Responsibility |
|--------|----------------|
| `server.py` | Flask routes, SSE streaming, background deploy threads, cancel flag |
| `src/config.py` | `DeployConfig` dataclass and input validation |
| `src/deployer.py` | Full pipeline orchestration and retry logic |
| `src/content_gen.py` | Gemini integration for copy, image queries, and FAQ generation |
| `src/image_fetcher.py` | Pexels search and WordPress media upload |
| `src/wp_client.py` | REST API wrapper, theme management, nav rebuild, site reset |
| `src/content_cache.py` | File-based cache keyed on deployment config |
| `src/interlinker.py` | Internal link map, Gemini keyword suggestions, link injection |
| `src/history.py` | Deployment history persistence |
| `templates/` | Per-page Gutenberg block builders |
| `rr-wp-abilities/` | Companion WP plugin exposing page CRUD as MCP abilities (`rr/create-page`, `rr/get-page`, `rr/update-page`, `rr/list-pages`) |

## Installation

1. **Add API keys:**
   ```powershell
   copy .env.example .env
   ```
   Set `GEMINI_API_KEY` and `PEXELS_API_KEY`. Both have usable free tiers. Keys can also be entered directly in the UI to override for a single run.

2. **Start the server:**
   ```powershell
   .\start.bat
   ```
   On Mac or Linux use `./start.sh`. Either way it installs dependencies and launches the server.

3. **Open the UI** at `http://localhost:5000`.

## Usage

Fill in the form and click Deploy:

- **WordPress**: site URL, admin username, and an Application Password (WP Admin → Users → Profile → Application Passwords)
- **Business**: name, city, state, phone
- **Branding**: primary and dark colors, with a live preview
- **Services**: entered as tags, one dedicated page generated per service
- **Blog topics**: optional, auto-derived from the services when left blank
- **Google Maps embed**: optional, renders on the contact page

Progress streams into the log panel as it runs, and a results panel lists every published URL when it finishes. If anything fails, **Retry Failed** re-runs only those items.

## Output

- **Published site**: all pages live on the target WordPress install
- **History**: per-run record of configuration, published URLs, and failures
- **Cache**: generated content retained per configuration for cheap retries

## Requirements

| Requirement | Notes |
|-------------|-------|
| Python 3.11+ | |
| WordPress site | Any host; Astra theme, installed automatically where permitted |
| WP Application Password | Safer than storing account credentials |
| Gemini API key | Free tier is sufficient |
| Pexels API key | Free tier: 200 requests/hour, a full deploy uses roughly 30 to 50 |

## Security Notes

- Never commit `.env` with real credentials
- `.env.example` is the template for sharing
- WordPress Application Passwords are scoped and revocable, unlike account passwords
- API keys entered in the UI apply to that run only and are not persisted
- **WordPress credentials are never written to disk.** Deployment history records the site URL and username but not the password, and any password left in a history file by an older version is stripped on read
- **The bundled plugin's option endpoint is nonce-checked and allowlisted.** It accepts only the two options the plugin owns, so it cannot be used as a general option writer
- **Debug mode is off unless explicitly enabled** via `FLASK_DEBUG=1`, and the server binds to loopback only, so a deploy in progress is not reachable from the network
