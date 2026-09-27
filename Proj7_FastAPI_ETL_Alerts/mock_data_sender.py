"""Plays one store-day against a running server: sales, labor, then the labor webhook again (a re-delivery).
Expect one alert, not two. Writes what happened to a JSON report.

    py mock_data_sender.py [--base-url http://127.0.0.1:8000] [--store Store_104] [--date 2026-02-24] [--report runs/demo.json]
"""
import argparse
import json
import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv


def main(argv=None) -> int:
    load_dotenv()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--store", default="Store_104")
    ap.add_argument("--date", default="2026-02-24")
    ap.add_argument("--report", default="runs/demo.json")
    args = ap.parse_args(argv)

    headers = {"X-Webhook-Secret": os.getenv("WEBHOOK_SECRET", "")}
    sales = {"store_id": args.store, "date": args.date, "gross_sales": 5000.00}
    labor = {"store_id": args.store, "date": args.date, "labor_hours": 75.0, "labor_cost": 1500.00}  # 30% of sales
    steps = [("POS sends sales", "sales", sales), ("Scheduler sends labor", "labor", labor),
             ("Scheduler re-sends labor", "labor", labor)]

    report = {"steps": []}
    with httpx.Client(base_url=args.base_url, timeout=15) as client:
        report["health"] = client.get("/health").json()
        for label, path, body in steps:
            r = client.post(f"/webhook/{path}", json=body, headers=headers)
            print(f"{label}: HTTP {r.status_code}")
            report["steps"].append({"step": label, "status": r.status_code})
            time.sleep(2)  # background processing runs after each 202
        row = client.get(f"/metrics/{args.store}/{args.date}", headers=headers)
        report["row"] = row.json()
    print(json.dumps(report["row"], indent=2))

    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    ok = all(s["status"] == 202 for s in report["steps"]) and row.status_code == 200
    print(("OK" if ok else "FAILED") + f". Report: {args.report}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
