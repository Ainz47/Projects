"""Post the fixtures in leads.json to the local n8n Form Trigger.

Usage: py samples/submit.py [form_url]
The default is the production form of the lead-capture workflow, which only
answers while that workflow is active. Requires: pip install requests
"""
import json
import re
import sys
from pathlib import Path

import requests

DEFAULT_URL = "http://localhost:5678/form/lead-capture"
FIELDS = ["Name", "Email", "Company", "Message", "Budget", "Timeline"]


def main(argv):
    url = argv[0] if argv else DEFAULT_URL
    leads = json.loads((Path(__file__).parent / "leads.json").read_text(encoding="utf-8"))
    page = requests.get(url, timeout=15)
    page.raise_for_status()
    # n8n renders some inputs in the page script, so count distinct field-N names.
    found = set(re.findall(r"field-(\d+)", page.text))
    if found != {str(i) for i in range(len(FIELDS))}:
        print(f"the form has fields {sorted(found)}, expected field-0 to field-{len(FIELDS) - 1}; input names may differ")
        return 1
    for lead in leads:
        # The Form Trigger only accepts multipart/form-data, so send each field as a plain part.
        parts = {f"field-{i}": (None, lead[label]) for i, label in enumerate(FIELDS)}
        response = requests.post(url, files=parts, timeout=60)
        print(f"{lead['label']:<5} expect {lead['expect_tier']:<9} HTTP {response.status_code}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
