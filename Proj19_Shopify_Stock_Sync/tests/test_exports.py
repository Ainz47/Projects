import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import build_exports  # noqa: E402

FILE = "order-stock-sync.workflow.json"
SECRET_PATTERNS = {
    "google_api_key": r"AIza[0-9A-Za-z_-]{20,}",
    "google_oauth_secret": r"GOCSPX-[0-9A-Za-z_-]{10,}",
    "sk_key": r"\bsk-[A-Za-z0-9_-]{20,}",
    "bearer_token": r"Bearer [A-Za-z0-9._-]{20,}",
    "github_token": r"gh[pousr]_[A-Za-z0-9]{20,}",
    "github_fine_grained": r"github_pat_[A-Za-z0-9_]{20,}",
    "airtable_token": r"\bpat[A-Za-z0-9]{14}\.[a-f0-9]{32,}",
    "shopify_token": r"\bshp(at|ca|ss)_[a-f0-9]{20,}",
    "email_address": r"[A-Za-z0-9._%+-]+@(?!example\.com\b)[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "windows_user_path": r"[A-Za-z]:\\+Users",
}


def load():
    return json.loads((ROOT / FILE).read_text(encoding="utf-8"))


def by_name(workflow):
    return {n["name"]: n for n in workflow["nodes"]}


def targets(workflow, source, port):
    outputs = workflow["connections"][source]["main"]
    return [edge["node"] for edge in outputs[port]] if port < len(outputs) else []


class ExportTests(unittest.TestCase):
    def test_export_is_in_sync_with_the_generator(self):
        self.assertEqual((ROOT / FILE).read_text(encoding="utf-8"), build_exports.build()[FILE])

    def test_node_types(self):
        types = {n["type"] for n in load()["nodes"]}
        self.assertEqual(types, {
            "n8n-nodes-base.scheduleTrigger", "n8n-nodes-base.code",
            "n8n-nodes-base.httpRequest", "n8n-nodes-base.if",
        })

    def test_wiring(self):
        w = load()
        chain = ["Every 5 minutes", "Plan orders query", "Shopify token", "Shopify orders", "Plan stock lookup", "Any SKUs?"]
        for a, b in zip(chain, chain[1:]):
            self.assertEqual(targets(w, a, 0), [b], f"{a} -> {b}")
        self.assertEqual(targets(w, "Any SKUs?", 0), ["Shopify stock"])
        self.assertEqual(targets(w, "Any SKUs?", 1), ["Advance cursor"])
        for a, b in [("Shopify stock", "Airtable rows"), ("Airtable rows", "Plan updates"), ("Plan updates", "Any updates?")]:
            self.assertEqual(targets(w, a, 0), [b], f"{a} -> {b}")
        self.assertEqual(targets(w, "Any updates?", 0), ["Chunk updates"])
        self.assertEqual(targets(w, "Any updates?", 1), ["Advance cursor"])
        for a, b in [("Chunk updates", "Airtable update"), ("Airtable update", "Dispatch refresh"), ("Dispatch refresh", "Advance cursor")]:
            self.assertEqual(targets(w, a, 0), [b], f"{a} -> {b}")

    def test_the_cursor_is_advanced_last_and_only_there(self):
        w = load()
        self.assertNotIn("Advance cursor", w["connections"])
        for name in by_name(w):
            if name != "Advance cursor":
                self.assertIn(name, w["connections"], f"{name} must lead somewhere")
        # A write is "<something>.cursor =" (the assignment that advances it). A read like
        # "const cursor = ...cursor ?? null" must NOT count: after ".cursor" there is no "="
        # until the next assignment, so the regex only matches an actual write.
        write_pattern = re.compile(r"\.cursor\s*=[^=]")
        cursor_writers = [n["name"] for n in w["nodes"] if write_pattern.search(n.get("parameters", {}).get("jsCode", ""))]
        self.assertEqual(cursor_writers, ["Advance cursor"])

    def test_once_only_nodes(self):
        nodes = by_name(load())
        self.assertTrue(nodes["Dispatch refresh"].get("executeOnce"))
        self.assertTrue(nodes["Advance cursor"].get("executeOnce"))

    def test_http_nodes_use_named_credentials_and_no_inline_secrets(self):
        nodes = by_name(load())
        self.assertIn("httpCustomAuth", nodes["Shopify token"]["credentials"])
        for name in ("Airtable rows", "Airtable update", "Dispatch refresh"):
            self.assertIn("httpHeaderAuth", nodes[name]["credentials"], name)
        text = (ROOT / FILE).read_text(encoding="utf-8")
        self.assertNotIn("client_secret", text)
        self.assertIn("appXXXXXXXXXXXXXX", text)  # the Airtable base id is a placeholder until import

    def test_no_secrets_anywhere_in_the_export(self):
        text = (ROOT / FILE).read_text(encoding="utf-8")
        for label, pattern in SECRET_PATTERNS.items():
            self.assertIsNone(re.search(pattern, text), f"looks like a {label}")

    def test_code_nodes_are_self_contained_and_parse(self):
        node_bin = subprocess.run(["node", "--version"], capture_output=True, text=True)
        if node_bin.returncode != 0:
            self.skipTest("node is not installed")
        for n in load()["nodes"]:
            if n["type"] != "n8n-nodes-base.code":
                continue
            source = n["parameters"]["jsCode"]
            self.assertNotIn("require(", source, n["name"])
            self.assertNotIn("module.exports", source, n["name"])
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "node.js"
                path.write_text(source, encoding="utf-8")
                check = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
                self.assertEqual(check.returncode, 0, f"{n['name']}: {check.stderr}")

    def test_workflow_is_saved_inactive(self):
        self.assertFalse(load()["active"])


if __name__ == "__main__":
    unittest.main()
