"""
NYC DOB violation collector.

This script uses the official NYC DOB Open Data endpoint as the primary
extraction layer and generates a direct source link back to the exact API
query used for each violation record.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


API_ENDPOINT = "https://data.cityofnewyork.us/resource/3h2n-5cm9.json"
SOURCE_FIELDS = (
    "boro, bin, house_number, street, violation_number, issue_date, "
    "violation_type, violation_category, disposition_date, "
    "disposition_comments, description"
)

BORO_LABELS = {
    "1": "Manhattan",
    "2": "Bronx",
    "3": "Brooklyn",
    "4": "Queens",
    "5": "Staten Island",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch NYC DOB violations and generate direct source links."
    )
    parser.add_argument(
        "--boroughs",
        nargs="+",
        default=["2", "3"],
        help="Borough codes to query. Defaults to Bronx (2) and Brooklyn (3).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum number of records to fetch before deduplication.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "csv"),
        default="json",
        help="Output format when --output is provided.",
    )
    parser.add_argument(
        "--output",
        help="Optional output path. If omitted, records are printed to stdout.",
    )
    return parser.parse_args()


def build_query(limit: int, boroughs: Iterable[str]) -> str:
    quoted_boroughs = ",".join(f"'{boro}'" for boro in boroughs)
    return (
        "select "
        "boro, bin, block, lot, house_number, street, violation_number, "
        "issue_date, violation_type_code, violation_type, violation_category, "
        "disposition_date, disposition_comments, description "
        f"where boro in({quoted_boroughs}) "
        "and violation_number is not null "
        "order by issue_date desc "
        f"limit {limit}"
    )


def build_url(limit: int, boroughs: Iterable[str]) -> str:
    return f"{API_ENDPOINT}?{urlencode({'$query': build_query(limit, boroughs)})}"


def fetch_rows(url: str) -> list[dict]:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/135.0.0.0 Safari/537.36"
            )
        },
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.split())


def clean_address(house_number: str | None, street: str | None) -> str:
    parts = [clean_text(house_number), clean_text(street).title()]
    return " ".join(part for part in parts if part)


def clean_violation_type(raw_value: str | None) -> str:
    value = clean_text(raw_value)
    if not value:
        return ""

    first_segment = re.split(r"\s{2,}", raw_value.strip())[0]
    label = first_segment.split("-", 1)[-1] if "-" in first_segment else first_segment
    return clean_text(label).title()


def clean_status(raw_value: str | None) -> str:
    value = clean_text(raw_value)
    if not value:
        return ""
    status = value.rsplit("-", 1)[-1]
    return clean_text(status).title()


def format_date(raw_value: str | None) -> str:
    value = clean_text(raw_value)
    if len(value) == 8 and value.isdigit():
        try:
            return datetime.strptime(value, "%Y%m%d").date().isoformat()
        except ValueError:
            return value
    return value


def build_source_link(bin_value: str, violation_number: str) -> str:
    query = (
        f"select {SOURCE_FIELDS} "
        f"where bin='{bin_value}' and violation_number='{violation_number}' "
        "limit 1"
    )
    return f"{API_ENDPOINT}?$query={quote(query, safe='')}"


def normalize_rows(rows: Iterable[dict]) -> list[dict]:
    normalized: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for row in rows:
        bin_value = clean_text(row.get("bin"))
        violation_number = clean_text(row.get("violation_number"))
        dedupe_key = (bin_value, violation_number)
        if dedupe_key in seen or not bin_value or not violation_number:
            continue
        seen.add(dedupe_key)

        normalized.append(
            {
                "borough": BORO_LABELS.get(
                    clean_text(row.get("boro")),
                    clean_text(row.get("boro")),
                ),
                "bin": bin_value,
                "block": clean_text(row.get("block")),
                "lot": clean_text(row.get("lot")),
                "address": clean_address(row.get("house_number"), row.get("street")),
                "violation_number": violation_number,
                "violation_type": clean_violation_type(row.get("violation_type")),
                "issue_date": format_date(row.get("issue_date")),
                "status": clean_status(row.get("violation_category")),
                "disposition_date": format_date(row.get("disposition_date")),
                "disposition_comments": clean_text(row.get("disposition_comments")),
                "description": clean_text(row.get("description")),
                "source_page_link": build_source_link(bin_value, violation_number),
            }
        )

    return normalized


def write_json(records: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(records, indent=2), encoding="utf-8")


def write_csv(records: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)


def main() -> None:
    args = parse_args()
    url = build_url(limit=args.limit, boroughs=args.boroughs)
    rows = fetch_rows(url)
    records = normalize_rows(rows)

    if args.output:
        output_path = Path(args.output)
        if args.format == "csv":
            write_csv(records, output_path)
        else:
            write_json(records, output_path)
        print(f"Wrote {len(records)} records to {output_path}")
        return

    print(json.dumps(records, indent=2))


if __name__ == "__main__":
    main()
