# Proj3: PDF Extractor

`PDFExtractor.py` is a single Playwright function that opens a page in headless Chromium and pulls out any `<a>` tag whose `href` contains `.pdf`. That is the entire working script. The name and the rest of this repo's history point at a larger pipeline (download the PDFs, extract text, write rows to SQLite), but none of that is implemented here. This README describes what is actually in the file, not what the project was meant to become.

## What the code does

`robust_discovery(target_url)`:

1. Launches headless Chromium via `sync_playwright`.
2. Navigates to `target_url` with `wait_until="networkidle"` and a 30 second timeout.
3. If the response status is not 200, prints an error and returns `[]`.
4. Takes a full-page screenshot and saves it to `debug_view.png` in the working directory.
5. Runs `eval_on_selector_all('a', ...)` in the page to collect every anchor's `href`, filtered (case-insensitively) to hrefs containing `.pdf`.
6. Prints the count found and returns the list of URLs.
7. Any exception during the above is caught, printed, and results in `[]`. The browser is closed in a `finally` block either way.

The `if __name__ == "__main__":` block calls `robust_discovery` once against a hardcoded URL (`https://www.lausd.org/Page/13501`) and stores the result in `found_pdfs`. Nothing further is done with it: the list isn't printed, saved, or passed anywhere. Running the script as-is discovers PDF links and then discards them.

## What it does not do

The script imports `requests`, `io`, and `pdfplumber`, and none of the three are ever called. There is no download step, no PDF text extraction, no regex cleaning, no SQLite table, no database file, and no CSV or JSON output. The previous README described a three-layer pipeline (discovery, in-memory ingestion, extraction into SQL) and a `school_data.db` schema with columns like `doc_type` and `meeting_date`. None of that exists in `PDFExtractor.py`. If that pipeline was built at some point, it isn't in this file or this folder now.

## On "in-memory, no disk writes"

The old README claimed a "No-Disk" architecture. That's not accurate for the current code: step 4 above (`page.screenshot(path="debug_view.png")`) writes a file to disk on every successful run, unconditionally, for debugging. There's no other disk I/O in the script, but the no-disk-writes claim as stated was false and has been dropped rather than qualified.

## No sample output in this repo

There is no committed sample CSV, database, screenshot, or JSON output for this project, and this is the only Playwright-based project in this repo with none. `robust_discovery` has not been run as part of writing this README, so there's nothing here to cite as evidence of what a real run against `lausd.org` (or anywhere else) actually returns, how many links it finds, or whether the site's structure still matches what the selector expects. Anyone picking this up should treat "does it currently find PDF links on a real page" as an open question, not something this README is asserting.

## Setup

```bash
pip install playwright requests pdfplumber pandas
playwright install chromium
```

Only `playwright` is required for the code that currently runs. `requests`, `pdfplumber`, and `pandas` are imported but unused; installing them avoids nothing breaking if code that uses them gets added later, but the script doesn't need them today.

```bash
python PDFExtractor.py
```

This runs `robust_discovery` against the hardcoded `lausd.org` URL in the `__main__` block. To point it at a different page, edit `test_url` directly, since there's no CLI argument or config for it.

## Known limitations

- The target URL is hardcoded in `__main__`; there's no argument parsing.
- `debug_view.png` is overwritten on every run with no cleanup step and isn't gitignored specifically for this project's folder (check the repo's root `.gitignore` before committing after a run).
- The `.pdf` filter is a plain substring match on `href` (case-insensitive), so it will also match links that merely contain `.pdf` outside a real file extension (e.g. a query string), and will miss PDFs served without a `.pdf` in the URL at all.
- `wait_until="networkidle"` with a fixed 30 second timeout means slow or long-polling pages will fail discovery outright rather than degrading.
- No retry logic beyond the single try/except around the whole navigation-and-extraction block.
