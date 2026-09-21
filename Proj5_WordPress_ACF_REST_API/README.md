# WordPress ACF REST API Importer

A single Python script (`wp_acf_importer.py`) that takes one scraped business record and posts it into WordPress through the REST API, mapping fields onto Advanced Custom Fields (ACF) and running a hash-based check first to decide whether to create a new post or update an existing one.

## What it does

- Builds a payload from a record with `business_name`, `phone`, `address`, and `raw_about_us`, and sends it to `{WP_API_URL}/posts`, which is WordPress's default `posts` endpoint (not a custom post type, despite the module docstring saying "Custom Post Type").
- Maps three fields into the `acf` block of the payload: `business_address`, `contact_phone`, `ai_generated_summary`. This part matches the old README's "Schema Mapping" claim.
- Runs everything through `enrich_with_gemini()` before mapping. This function does not call Gemini, or any external API. It returns the input string prefixed with `"SEO OPTIMIZED: "`. There is no API key for it, no network call, no model. It is a placeholder, not an AI enrichment layer.
- Authenticates with HTTP Basic Auth, passing `WP_USERNAME` / `WP_APP_PASSWORD` as the `auth` tuple on every `requests` call. This is the correct way to use a WordPress Application Password, so that part of the old README holds up.
- Computes `record_hash = md5(business_name + "_" + phone)` and logs it, then calls `check_if_exists()`, which queries `{CPT_ENDPOINT}?meta_key=source_hash&meta_value={record_hash}` and returns the matching post ID if the API returns a non-empty list.
- Only ever runs against one hardcoded sample record in `if __name__ == "__main__"` (a fake business, "Davao Central Tech Solutions"). There is no file loading, no CLI argument, no loop over a JSON dataset. Calling it a "pipeline" for "scraped JSON datasets" overstates what's in this file today; as written it processes exactly one hardcoded record per run.

## A real gap in the idempotency logic

The old README's "Deterministic Hashing (Idempotency)" and "Pre-Flight Conflict Resolution" claims are half true. The hash is genuinely computed and the pre-flight query genuinely runs. But `wp_payload` never includes a `source_hash` field anywhere (not in `acf`, not at top level) when a post is created. So nothing in this script ever writes the `source_hash` postmeta that `check_if_exists()` searches for. Read straight through, on a fresh site this check will never find a match, because nothing here ever creates the thing it's looking for. It only works if `source_hash` gets populated by some other mechanism outside this script (an ACF field configured server-side, for instance), which isn't shown here and isn't something the script itself sets up.

## Other things the old README overstated

- **"Switches between POST and PUT"**: it doesn't. Both branches use `requests.post`, once to the collection endpoint (`/posts`) for a new record, once to the item endpoint (`/posts/{id}`) for an existing one. WordPress's REST API does accept POST to an item endpoint as an update, so this isn't broken, but there is no PUT request anywhere in the file.
- **"Production-grade Security"**: the script loads credentials from `.env` via `python-dotenv`, which is reasonable, but it also unconditionally prints `DEBUG: Username loaded is {WP_USERNAME}` to stdout on every run, a leftover debug line, not something you'd want in anything actually production-grade.
- **"Fully tested and deployed on a live Pantheon WebOps staging server"**: nothing in this repo backs that up (see below).
- `check_if_exists()` catches any exception from the pre-flight request (timeout, connection error, bad JSON) and just logs it, returning `None`. A failed check is treated identically to "no existing record," so a transient network error during the check would fall through to an insert attempt rather than stopping the run.
- `DRY_RUN` is a hardcoded `False` at module level. There's no CLI flag or env var to toggle it, only editing the source.

## What is verified

Nothing. This folder has no committed run output, no log file, no screenshot, and no test file. The repo history for this script is one commit ("Uploaded script"). Everything above comes from reading `wp_acf_importer.py` directly, not from having watched it run against a real WordPress/ACF site. If it has been run successfully against the Pantheon staging site referenced in `.env.example`, that run left no artifact in this repo.

## Setup

```bash
pip install requests python-dotenv
```

Copy `.env.example` to `.env` and fill in:

```
WP_API_URL=https://your-site.pantheonsite.io/wp-json/wp/v2
WP_USERNAME=your_admin_username
WP_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
```

Run:

```bash
python wp_acf_importer.py
```

This will attempt a real POST against whatever `WP_API_URL` points to, using the one hardcoded sample record in the script. There's no dry-run switch exposed at the CLI; to test without hitting a live site, edit `DRY_RUN = True` in the source first.

## Files

- `wp_acf_importer.py`: the entire pipeline (hashing, the pre-flight check, the Gemini stub, the ACF payload mapping, and the POST calls, all in one file).
- `.env.example`: credential template (WordPress REST API URL, username, Application Password).
