# Schedule PWA

An offline-first daily schedule app that runs as a phone-installable PWA, syncs across devices through CouchDB, and turns a routine into a game: streaks, coins, penalties and a reward shop. It pushes the week to Google Calendar and publishes a daily note to Obsidian.

The interesting part is not the UI. It is keeping two devices, a hand-edited template and a live database in agreement without losing anyone's edits.

## Highlights

- **Offline-first.** PouchDB keeps a local IndexedDB replica, so ticking a block works with no signal and syncs when the connection returns.
- **No build step, no hosting.** The app is served straight out of CouchDB as `_design/app` attachments. `deploy.py` uploads `src/` and `vendor/` in one PUT, so a deploy is atomic: the whole app updates or none of it does.
- **Network-first service worker.** With no content hashing, the only way new files reach an installed device is to prefer the network and fall back to the cached shell, which `sw.js` does.
- **Conflict resolution that keeps both sides.** CouchDB picks a winner among conflicting revisions and silently discards the rest. `conflicts.js` folds every revision into one: later timestamp wins per entry, and on an exact tie the completion wins.
- **A seed script that respects who owns what.** `seed.py` merges the hand-edited template with the live document. Structural keys (days, streaks, attributes) come from the file. `checks` and `tasks`, which the app edits in place, come from the database. Ids that only exist in the file are added on top.
- **Zero dependencies in the tooling.** The CouchDB, Google Calendar and Obsidian clients use only the standard library, and the front end has no bundler. PouchDB is vendored (Apache-2.0).
- **Pure logic, tested without a network.** Calendar planning (`calendar_plan.py`) and note rendering (`vault_render.py`) do no I/O, which is what makes idempotency directly testable.

## Tests

```bash
npm test                                                  # 282 tests, node --test
py -X utf8 -m unittest discover -s tests -p "test_*.py"   # 88 tests
```

## Layout

| Path | What it is |
|---|---|
| `src/` | The PWA: ES modules, service worker, manifest, UI |
| `src/data/schedule-template.json` | The routine: days and blocks, streaks, checks, tasks, penalties, shop. This is a neutral demo. Replace it with your own |
| `src/conflicts.js`, `src/db.js` | Sync and revision merging |
| `scripts/seed.py` | Create the database and write the reference documents. Safe to re-run |
| `scripts/deploy.py` | Ship the app to CouchDB as one atomic PUT |
| `scripts/sync_calendar.py` | Upsert the next week into a dedicated Google Calendar. Every event carries a `scheduleKey`, so a run reconciles instead of duplicating |
| `scripts/export_to_vault.py` | Publish the schedule as a generated Obsidian note. Output only, the app never reads it |
| `scripts/google_auth.py` | One-time OAuth helper for a desktop client (RFC 8252) |
| `tests/` | JS and Python suites |

## Run it

Needs a CouchDB instance and Python 3.12+ / Node 20+.

```bash
cp .env.example .env      # fill in CouchDB credentials, use a dedicated non-admin user
py scripts/seed.py        # create the database and write the template
py scripts/deploy.py      # upload the app
```

Then open the design-doc URL on your phone and add it to the home screen. Google Calendar and Obsidian are optional integrations. Their settings are in `.env.example`.

## Engineering notes

Two bugs worth knowing about, because they shaped the design:

1. **Template edits never reached the phone.** `seed.py` skipped writing the template entirely whenever the document already existed, to protect the two collections the app edits at runtime. Fix: a per-key merge (`merge_template`) so the file wins everywhere except `checks` and `tasks`. The app's own conflict-merge code was the wrong tool here, because a hand-edited file carries no timestamps to compare.
2. **A metadata field that could never sync.** CouchDB rejects unknown underscore-prefixed top-level fields, so a `_notes` key had silently never made it to the database. Renamed to `notes`.
