# Proj1: SchoolSpring job scraper (Texas City ISD)

A two-stage scraper for one district's job board: Texas City ISD's listings on SchoolSpring (`tcisd.tedk12.com` / `tcisd.schoolspring.com`). It is hardcoded to that one site, not a generic ATS scraper despite what the earlier version of this README implied.

## How it works

1. **Cookie harvest (Playwright).** `harvest_cookies()` launches headless Chromium, loads `https://tcisd.tedk12.com/hire/index.aspx`, waits 5 seconds, and reads back the browser context's cookies into a plain dict. This is the step that gets past the site's WAF (Incapsula/Imperva-style bot check) by using a real browser instead of a raw HTTP client.
2. **Direct API call (requests).** `fast_api_scrape()` takes those cookies and calls `https://api.schoolspring.com/api/Jobs/GetPagedJobsWithSearch` directly with `requests`, `size=1000` (one page, no pagination logic), and fixed `origin`/`referer` headers pointing at `tcisd.schoolspring.com`. The response's `value.jobsList` array becomes a pandas DataFrame and is written to `ultimate_hybrid_jobs.csv`. The `domainName` query param is left blank; scoping to Texas City ISD appears to come from the referer/origin headers and the harvested cookies, not from an explicit district id in the URL.
3. **CSV to SQLite.** After the scrape, the script re-reads `ultimate_hybrid_jobs.csv` with pandas and writes it into `school_data.db` (table `job_leads`, `if_exists='replace'`).

## A real bug in the current script

Step 3 calls `sqlite3.connect(...)` but the file never imports `sqlite3`. Run `Sample_SchoolJobs.py` as-is today and it will scrape successfully, write the CSV, then crash with `NameError: name 'sqlite3' is not defined` before the database step runs. The committed `school_data.db` was not produced by this exact file (it has the same 64 rows as the CSV and looks like a straight `df.to_sql` dump, so it was almost certainly made by an earlier working copy of this code, or with the import added by hand and not saved back). Whoever runs this next needs to add `import sqlite3` at the top before step 3 will work.

Also worth knowing: the CSV-to-SQLite block (lines 63-71) sits at module level, not inside `if __name__ == "__main__":`. Running the file directly is fine because Python executes top to bottom either way, but importing this module from anywhere else would trigger the full scrape and DB write as a side effect.

## What's actually in the data

Verified by reading the committed files directly (not by re-running the scraper):

- `ultimate_hybrid_jobs.csv`: 64 rows, 5 columns: `jobId, employer, title, location, displayDate`.
- `school_data.db`: SQLite, one table `job_leads`, same 64 rows and same 5 columns as the CSV.
- Sample row: `jobId=5532430, employer="Texas City Indep School Dist", title="Warehouse Helper", location="Texas City, Texas", displayDate="2026-02-10T06:00:00"`.

The earlier README claimed the output included `SalaryRange` and `Category` fields. Neither exists in the actual CSV or DB schema. That claim, and the generic "1,000+ records" framing, have been removed.

## What is NOT verified here

- No test suite and no CI. `.github/workflows/tests.yml` runs jobs for Proj14 through Proj19; Proj1 is not in it.
- The committed `.db` and `.csv` are a single point-in-time run (64 rows, one district, whatever dates SchoolSpring was returning when it ran). There's no evidence in this folder of when that run happened, and nothing here confirms the SchoolSpring API still accepts the same request shape today, still allows this cookie-transfer approach past its WAF, or still returns the same field names.
- The `sqlite3` import bug above has not been fixed or re-tested; running the script now will reproduce the crash described above unless that's added first.
- No handling for an empty or failed scrape beyond a printed message; if `fast_api_scrape` doesn't get `jobsList` back, no CSV is written and the later `pd.read_csv` call would fail with `FileNotFoundError` on a first run (it would silently reuse a stale CSV on a later run instead).

## Setup and usage

```bash
pip install playwright pandas requests
playwright install chromium
py Sample_SchoolJobs.py
```

(No `requirements.txt` is committed; the above is inferred from the script's imports. `python` is the Windows Store stub on this machine, use `py`.)

## Files in this folder

| File | What it is |
| --- | --- |
| `Sample_SchoolJobs.py` | The scraper described above |
| `ultimate_hybrid_jobs.csv` | Output of a past run, 64 rows |
| `school_data.db` | SQLite copy of the same 64 rows, table `job_leads` |
