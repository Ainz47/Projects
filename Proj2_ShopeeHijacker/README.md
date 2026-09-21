# Proj2: Shopee Hijacker

A script that attaches Playwright to an already-open, manually authenticated Chrome window (via the Chrome DevTools Protocol) and passively listens for Shopee's search API responses while paging through search results, instead of sending its own scripted requests for the data. A second script loads the resulting CSV into a local SQLite database.

Architecture diagram: [docs/architecture-diagram.md](./docs/architecture-diagram.md).

## What it does

`shopee_hijacker.py`:

1. Prompts for a search keyword and a page count.
2. Connects to a running Chrome instance at `http://localhost:9222` via `connect_over_cdp`, and uses the first browser context's first tab (`browser.contexts[0].pages[0]`). Chrome has to already be running in remote-debugging mode with Shopee open and logged in; the script does not launch or log in to a browser itself.
3. Registers a `response` listener that matches any network response whose URL contains `search_items` or `/api/v4/search/search`, calls `response.json()`, and reads `items` from it. For each item it pulls `name`, `price` (divided by 100000, see note below), `historical_sold`, and `sold`, and labels them Title, Price (PHP), Exact Lifetime Sold, and Monthly Sold.
4. Loops `page=0` through `page=max_pages-1`, navigating to `https://shopee.ph/search?keyword=...&page=N` and waiting (15 second timeout) for a matching `/api/v4/search/search` response before moving to the next page. A per-page failure is caught and printed; the loop continues to the next page rather than stopping.
5. After each page load it does one scroll (`page.mouse.wheel(0, 2000)`) and a 1-second wait, presumably to trigger any lazy-loaded secondary calls. Nothing is captured or checked specifically from that scroll.
6. Deduplicates the collected rows by Title with pandas and writes `shopee_<keyword>_<max_pages>_pages.csv`.

`Shopee_csv_to_sql.py`: reads a CSV (the filename is hardcoded to `shopee_mechanical_keyboard_3_pages.csv`, not the dynamic name `shopee_hijacker.py` actually produces for a different keyword or page count) and loads it into `market_intelligence.db`, table `shopee_products`, with `if_exists='replace'`. Each run replaces the whole table; it does not append or keep history, even though a comment in the script mentions append as an option.

Price note: the code assumes Shopee's raw price integer is in hundred-thousandths of the listed currency unit (`price = raw_price / 100000`). That is what the code does; it has not been checked against a live Shopee page as part of this review.

## What's in this folder as evidence

- `shopee_mechanical_keyboard_3_pages.csv`: 161 product rows, columns Title, Price (PHP), Exact Lifetime Sold, Monthly Sold. Example rows: "Zeus G-61 Wired 61-Key RGB Mechanical Gaming Keyboard, Type-C, Blue Switch, Portable Design", 598.0 PHP, 10000 lifetime sold, 7000 monthly sold; "AULA F3261 61 Keys Mechanical Keyboard with Hot Swappable Switches, Wired Type-C", 919.0 PHP, 20000 lifetime sold, 171 monthly sold.
- `market_intelligence.db`: one table, `shopee_products`, same 4 columns, 161 rows, matching the CSV row for row (expected, since the loader does a straight replace-load of that exact CSV).

Both files are a one-time capture from a past run. They show the pipeline produced real output at some point; they are not a live or repeatable proof that it still works today.

## What's not verified here

- No test suite and no CI in this folder. Nothing runs automatically to catch a broken selector, a changed API path, or a change in Shopee's response schema.
- The committed CSV and DB are a point-in-time capture (no run date or log is kept anywhere in this folder, so the capture date is unknown). That is evidence of a past successful run, not proof the target site's DOM or API still matches today.
- The "zero-request footprint" idea (avoiding a "suspicious request volume" flag) is a design intent that follows from listening to responses instead of issuing requests. Nothing in this folder logs or measures request volume, detection, or account safety, so it has not actually been measured.
- The `historical_sold` -> "Exact Lifetime Sold" and `sold` -> "Monthly Sold" labels are the script author's interpretation of Shopee's internal field names, not confirmed against any Shopee documentation (Shopee does not publish this API).
- Both scripts swallow exceptions broadly (a bare `except Exception: pass` inside the response handler, and a generic `except Exception as e` around the whole hijack call that just prints a message). A partial or malformed capture would not necessarily be obvious from the console output alone.

## Known limits

- Filename mismatch between the two scripts: `shopee_hijacker.py` names its CSV after the keyword and page count, but `Shopee_csv_to_sql.py` has one filename hardcoded, so the loader only works unmodified for the exact keyword/page combination it was last edited for.
- Assumes `browser.contexts[0].pages[0]` is the right tab; with more than one context or tab open in the debug Chrome window, it can attach to the wrong one.
- Depends on Shopee continuing to expose `/api/v4/search/search`, which is an unofficial, internal endpoint that can change without notice.
- Requires manual setup every run: launching Chrome with `--remote-debugging-port=9222` and being logged into Shopee before starting the script.

## Setup

1. Close all Chrome windows, then launch with remote debugging enabled:
   - Windows: `chrome.exe --remote-debugging-port=9222`
   - macOS: `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --remote-debugging-port=9222`
2. Log into Shopee manually in that window.
3. `pip install playwright pandas`
4. Run `py shopee_hijacker.py` and enter a keyword and page count when prompted.
5. Optional: edit `csv_filename` in `Shopee_csv_to_sql.py` to match the CSV just produced, then run it to load the data into `market_intelligence.db`.

## Disclaimer

For educational use and technical demonstration of a CDP-based data pipeline. Follow the target site's terms of service and robots.txt. The author is not responsible for misuse.
