"""Lighthouse scores from the local Lighthouse CLI (npx lighthouse@12), using Playwright's Chromium.

  py lighthouse.py before / /product/ /about/      -> appends rows to lighthouse/scores.csv
  py lighthouse.py after  / /product/ /about/

Mobile = Lighthouse default (Moto G emulation, simulated slow 4G); desktop = --preset=desktop.
One row per page x strategy, written as soon as it finishes. The PageSpeed Insights API was the
first choice but its keyless daily quota is shared and was exhausted (429), so this runs locally.
Local scores depend on this machine and connection: compare before/after from the same run setup.
"""
import csv
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

SITE = "https://framelake.s6-tastewp.com"
CATS = ["performance", "accessibility", "best-practices", "seo"]
OUT = Path(__file__).parent / "lighthouse" / "scores.csv"
OUT.parent.mkdir(exist_ok=True)
FIELDS = ["when", "label", "path", "strategy", *CATS, "lcp_s", "cls", "tbt_ms"]

with sync_playwright() as p:
    chrome = p.chromium.executable_path
env = {**os.environ, "CHROME_PATH": chrome}
NPX = shutil.which("npx")  # npx.cmd on Windows; resolved so no shell is needed

label, *paths = sys.argv[1:]
new = not OUT.exists()
with OUT.open("a", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=FIELDS)
    if new:
        w.writeheader()
    for path in paths:
        for strategy in ("mobile", "desktop"):
            cmd = [NPX, "-y", "lighthouse@12", SITE + path, "--output=json", "--output-path=stdout", "--quiet",
                   "--chrome-flags=--headless=new", "--only-categories=" + ",".join(CATS)]
            if strategy == "desktop":
                cmd.append("--preset=desktop")
            res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env, timeout=300)
            try:
                lh = json.loads(res.stdout)
            except json.JSONDecodeError:
                print(path, strategy, "FAILED", res.stderr[-400:])
                continue
            audits = lh["audits"]
            if "numericValue" not in audits["largest-contentful-paint"]:  # page never loaded, e.g. Git Bash mangled "/" into a Windows path (run with MSYS_NO_PATHCONV=1)
                print(path, strategy, "NO METRICS, skipped:", lh.get("runtimeError") or audits["largest-contentful-paint"].get("errorMessage"))
                continue
            row = {"when": datetime.now().isoformat(timespec="minutes"), "label": label, "path": path, "strategy": strategy,
                   **{c: round((lh["categories"][c]["score"] or 0) * 100) for c in CATS},
                   "lcp_s": round(audits["largest-contentful-paint"]["numericValue"] / 1000, 2),
                   "cls": round(audits["cumulative-layout-shift"]["numericValue"], 3),
                   "tbt_ms": round(audits["total-blocking-time"]["numericValue"])}
            w.writerow(row)
            f.flush()
            print(row)
