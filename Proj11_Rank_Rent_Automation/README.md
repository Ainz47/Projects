# Rank and Rent Deployer

One-click WordPress site builder for rank and rent local service businesses. Fill in a browser form, click Deploy, and the tool writes every page with AI, sources matching photos, and publishes a complete multi-page site.

Built as an operator tool rather than a developer script: the person running it needs no Python, no WordPress admin experience, and no knowledge of the codebase.

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
- **No page builders**: output is plain HTML/CSS blocks, so pages stay fast and portable

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
| `templates/` | Per-page HTML/CSS block builders |

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
