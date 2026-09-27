# Shopee Search Capture

Captures Shopee search results from your own logged-in Chrome. It attaches to the browser over the Chrome DevTools Protocol, opens its own tab, pages through a search, and reads the product data out of the search API responses the page loads anyway, so it sends no scripted requests of its own. Each run is appended to SQLite with its timestamp and written to a CSV.

Architecture diagram: [docs/architecture-diagram.md](./docs/architecture-diagram.md).

## How it works

`py shopee_capture.py "mechanical keyboard" --pages 3`

1. **Attach** (`shopee_capture.py`): connects to Chrome at `http://localhost:9222` and opens a new tab in your logged-in session. It never touches your other tabs, and closes its own when done.
2. **Page and listen**: for each page (`page=0`, `page=1`, ...) it navigates to the search URL and waits up to 15 seconds for the page's `/api/v4/search/search` response. A page that doesn't answer is skipped and counted. If Shopee sends the tab to its login page, the run stops and says so.
3. **Parse** (`shopee.py`): reads each item's shop ID, item ID, title, price, lifetime sold and monthly sold, and builds the product URL. Shopee sends prices as integers in 1/100000 of a peso. Items without IDs, and responses that aren't readable JSON, are counted as failures and reported at the end rather than silently dropped.
4. **Dedupe**: one row per (shop ID, item ID). Deduping on title, as the first version did, merged different products that share a name.
5. **Store** (`storage.py`): one `capture_runs` row (keyword, pages requested and answered, item and failure counts, start and finish time) plus its `products`, written in a single transaction, so a failed save leaves no half run. Runs are appended, never replaced, so the same item's price and sales can be compared across days:

```sql
select r.started_at, p.price_php, p.monthly_sold
from products p join capture_runs r on r.id = p.run_id
where p.shopid = ? and p.itemid = ?
order by r.started_at;
```

The CSV (default `runs/<keyword>_<timestamp>.csv`) holds the same columns for the current run. The exit code is 1 when nothing was captured, and then nothing is saved.

## Setup

1. Close all Chrome windows, then start Chrome with remote debugging:
   - Windows: `chrome.exe --remote-debugging-port=9222`
   - macOS: `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --remote-debugging-port=9222`
2. Log in to shopee.ph in that window.
3. `pip install -r requirements.txt`
4. `py shopee_capture.py "<keyword>" --pages 3` (options: `--db`, `--csv`, `--cdp`)

## Tests

```bash
python -m pytest tests -q
```

No browser or network needed; they run in CI. They cover parsing (nested and flat item shapes, price scaling, items without IDs, empty pages), dedupe on item ID when titles collide, the response listener ignoring non-search calls and counting unreadable ones, run history across two runs, the one-transaction save, CSV quoting, and the CLI's exit codes.

## Evidence and limits

- `shopee_mechanical_keyboard_3_pages.csv` is a capture from the first version of this script: 161 products for "mechanical keyboard" over 3 pages (Title, Price (PHP), Exact Lifetime Sold, Monthly Sold). It predates the current columns, so it has no item IDs, and its capture date wasn't recorded.
- The current version is tested offline against the response shapes above. It hasn't yet been run against live Shopee.
- `/api/v4/search/search` is Shopee's internal, undocumented endpoint and can change without notice. The field meanings (`historical_sold` as lifetime sold, `sold` as monthly sold) are read from the data, not from Shopee documentation.
- The low request footprint follows from the design (it only reads responses to page loads a person would make). Detection and account safety haven't been measured.

## Disclaimer

For educational use and technical demonstration of a CDP-based data pipeline. Follow the target site's terms of service and robots.txt. The author is not responsible for misuse.
