# NYC DOB Violation Monitor

Applied web automation test project focused on collecting public building-violation records for Bronx and Brooklyn properties.

This project includes:

1. A completed manual test task with 5 violation records.
2. A lightweight Python collector that pulls official NYC DOB violation data.
3. A practical automation design for long-term monitoring, deduplication, and spreadsheet/database logging.

## Project Goal

Build a reliable workflow that can:

1. Search approved public data sources for building violations.
2. Extract the required fields.
3. Clean and standardize the records.
4. Remove duplicates before logging.
5. Push results into Google Sheets or Airtable.
6. Flag incomplete rows for manual review.

## Completed Test Task

Collected 5 building violations from Bronx and Brooklyn properties and attached direct official source links for each extracted record.

Manual result table: [manual_test_results.md](./manual_test_results.md)

Structured sample output: [sample_violations.json](./sample_violations.json)

## Why I Would Automate It This Way

The official NYC DOB Open Data endpoint is the best primary source for this workflow because it exposes structured records and supports reliable monitoring. It is a stronger extraction layer than BIS HTML pages, which may block direct scripted access.

That gives the system:

1. More reliable extraction.
2. Cleaner structured fields.
3. Easier deduplication.
4. Simpler scheduled monitoring.
5. Better long-term maintainability if page layouts change elsewhere.

## Automation Workflow

1. Extract
   Query the official NYC DOB violations endpoint for target boroughs, dates, or monitored BIN lists.

2. Transform
   Normalize address casing, format dates, simplify violation types, and derive a clean status field.

3. Dedupe
   Use a stable unique key such as `bin + violation_number`.

4. Load
   Upsert results into Google Sheets or Airtable with columns for address, violation number, type, issue date, status, source link, and review notes.

5. Review
   Flag rows with missing issue dates, missing types, malformed BIN values, or ambiguous status values.

6. Schedule
   Run daily or weekly with Task Scheduler, GitHub Actions, or a small container job.

## Recommended Stack

1. Python
   Main orchestration and data cleaning.

2. `urllib` or `requests`
   Official API extraction.

3. Playwright
   Optional browser validation if a secondary site needs to be reviewed manually.

4. Google Sheets API or Airtable API
   Final logging target.

5. SQLite or Postgres
   Local dedupe cache and change tracking.

## Files

```text
Proj10_NYC_BIS_Violation_Monitor/
├── Readme.md
├── manual_test_results.md
├── sample_violations.json
└── nyc_bis_violation_collector.py
```

## Run The Collector

```bash
python nyc_bis_violation_collector.py --limit 25
python nyc_bis_violation_collector.py --limit 25 --output latest_violations.json
python nyc_bis_violation_collector.py --limit 25 --format csv --output latest_violations.csv
```

## Notes

1. The script uses the official NYC DOB Open Data endpoint for the extraction layer.
2. Each `source_page_link` points to the exact official API query used for that specific record.
3. This makes the sample easier to audit and avoids relying on blocked BIS deep links.
