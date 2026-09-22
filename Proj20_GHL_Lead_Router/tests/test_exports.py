import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import build_exports  # noqa: E402

WEBHOOK = "n8n-nodes-base.webhook"
HTTP = "n8n-nodes-base.httpRequest"
SET = "n8n-nodes-base.set"
EXPECTED_TYPES = {"ghl-lead-router.workflow.json": {WEBHOOK, HTTP, SET}}
SECRET_PATTERNS = {
    "google_api_key": r"AIza[0-9A-Za-z_-]{20,}",
    "bearer_token": r"Bearer [A-Za-z0-9._-]{20,}",
    "email_address": r"[A-Za-z0-9._%+-]+@(?!example\.com\b)[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "windows_user_path": r"[A-Za-z]:\\+Users",
}


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


class ExportStructure(unittest.TestCase):
    def test_exports_parse_and_contain_the_expected_node_types(self):
        for name, expected in EXPECTED_TYPES.items():
            wf = load(name)
            self.assertTrue(wf["nodes"], name)
            self.assertTrue(expected <= {n["type"] for n in wf["nodes"]}, name)

    def test_every_connection_points_at_an_existing_node(self):
        for name in EXPECTED_TYPES:
            wf = load(name)
            names = {n["name"] for n in wf["nodes"]}
            for source, conn in wf["connections"].items():
                self.assertIn(source, names, name)
                for port in conn["main"]:
                    for edge in port:
                        self.assertIn(edge["node"], names, name)

    def test_workflow_ships_inactive(self):
        self.assertIs(load("ghl-lead-router.workflow.json")["active"], False)

    def test_the_backend_url_is_left_blank_for_the_owner_to_fill_in(self):
        nodes = {n["name"]: n for n in load("ghl-lead-router.workflow.json")["nodes"]}
        self.assertEqual(nodes["Call backend /qualify"]["parameters"]["url"], "")

    def test_the_webhook_and_http_node_are_wired_into_the_merge_step(self):
        wf = load("ghl-lead-router.workflow.json")
        conn = wf["connections"]
        self.assertEqual(
            [e["node"] for e in conn["GHL lead webhook"]["main"][0]], ["Call backend /qualify"],
        )
        self.assertEqual(
            [e["node"] for e in conn["Call backend /qualify"]["main"][0]], ["Merge qualification onto lead"],
        )


class NoSecrets(unittest.TestCase):
    def test_exports_contain_no_secret_shaped_strings(self):
        text = (ROOT / "ghl-lead-router.workflow.json").read_text(encoding="utf-8")
        for label, pattern in SECRET_PATTERNS.items():
            self.assertIsNone(re.search(pattern, text), label)


class GeneratorSync(unittest.TestCase):
    def test_file_on_disk_equals_what_the_generator_builds(self):
        built = build_exports.build()
        for name, text in built.items():
            self.assertEqual((ROOT / name).read_text(encoding="utf-8"), text, name)


if __name__ == "__main__":
    unittest.main()
