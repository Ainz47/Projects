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
IF = "n8n-nodes-base.if"
SHEETS = "n8n-nodes-base.googleSheets"
WHATSAPP = "n8n-nodes-base.whatsApp"
EXPECTED_TYPES = {"ghl-lead-router.workflow.json": {WEBHOOK, HTTP, SET, IF, SHEETS, WHATSAPP}}
SECRET_PATTERNS = {
    "google_api_key": r"AIza[0-9A-Za-z_-]{20,}",
    "bearer_token": r"Bearer [A-Za-z0-9._-]{20,}",
    "email_address": r"[A-Za-z0-9._%+-]+@(?!example\.com\b)[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "windows_user_path": r"[A-Za-z]:\\+Users",
    "phone_number": r"\+\d{10,}",
    "google_doc_id": r"/d/[A-Za-z0-9_-]{25,}",
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

    def test_the_merge_step_leads_into_the_write_back_chain(self):
        wf = load("ghl-lead-router.workflow.json")
        conn = wf["connections"]
        self.assertEqual(
            [e["node"] for e in conn["Merge qualification onto lead"]["main"][0]],
            ["Write score/reason/reply to GHL"],
        )
        self.assertEqual(
            [e["node"] for e in conn["Write score/reason/reply to GHL"]["main"][0]],
            ["Add tier tag"],
        )
        self.assertEqual(
            [e["node"] for e in conn["Add tier tag"]["main"][0]], ["Is hot?", "Append lead log"],
        )

    def test_the_tier_branch_moves_the_opportunity_to_the_matching_stage(self):
        wf = load("ghl-lead-router.workflow.json")
        conn = wf["connections"]
        self.assertEqual([e["node"] for e in conn["Is hot?"]["main"][0]], ["Move to Hot stage", "WhatsApp hot lead alert"])
        self.assertEqual([e["node"] for e in conn["Is hot?"]["main"][1]], ["Is warm?"])
        self.assertEqual([e["node"] for e in conn["Is warm?"]["main"][0]], ["Move to Warm stage"])
        self.assertEqual([e["node"] for e in conn["Is warm?"]["main"][1]], ["Move to Cold stage"])

    def test_ghl_write_back_nodes_use_the_shared_templated_auth_credential(self):
        # httpTemplatedCustomAuth, not plain httpHeaderAuth: n8n rejects creating
        # a new plain generic credential on this node (confirmed live via n8n-mcp
        # validation against all 5 of these nodes).
        nodes = {n["name"]: n for n in load("ghl-lead-router.workflow.json")["nodes"]}
        for name in ["Write score/reason/reply to GHL", "Add tier tag", "Move to Hot stage", "Move to Warm stage", "Move to Cold stage"]:
            node = nodes[name]
            self.assertEqual(node["parameters"]["genericAuthType"], "httpTemplatedCustomAuth")
            self.assertEqual(node["credentials"]["httpTemplatedCustomAuth"]["name"], "GHL Private Integration Token")
            self.assertEqual(node["credentials"]["httpTemplatedCustomAuth"]["id"], build_exports.PLACEHOLDER_ID)
            self.assertEqual(node["parameters"]["headerParameters"]["parameters"], [{"name": "Version", "value": "2021-07-28"}])

    def test_the_custom_field_ids_and_pipeline_stage_ids_are_left_blank_for_the_owner_to_fill_in(self):
        nodes = {n["name"]: n for n in load("ghl-lead-router.workflow.json")["nodes"]}
        fields_body = nodes["Write score/reason/reply to GHL"]["parameters"]["jsonBody"]
        self.assertEqual(fields_body.count("id: ''"), 3)
        for name in ["Move to Hot stage", "Move to Warm stage", "Move to Cold stage"]:
            self.assertIn("pipelineStageId: ''", nodes[name]["parameters"]["jsonBody"])


class CrossProjectLinks(unittest.TestCase):
    """Proj20 shares its local n8n instance with Proj16/Proj19 (see README's
    Cross-project links section): a LeadLog tab in the same spreadsheet Proj19
    writes StockLog to, the same shared error-alert workflow, and a hot-lead
    WhatsApp alert reusing Proj16's channel."""

    def test_the_workflow_uses_the_shared_error_alert_workflow(self):
        wf = load("ghl-lead-router.workflow.json")
        self.assertEqual(wf["settings"]["errorWorkflow"], build_exports.SHARED_ERROR_WORKFLOW_ID)

    def test_the_leadlog_sheet_name_is_set_but_the_spreadsheet_id_is_left_blank(self):
        # Same convention as Proj16's sheets_node(): the document ID names a real
        # account's spreadsheet, so it's filled in at import time, never committed.
        nodes = {n["name"]: n for n in load("ghl-lead-router.workflow.json")["nodes"]}
        params = nodes["Append lead log"]["parameters"]
        self.assertEqual(params["documentId"]["value"], "")
        self.assertEqual(params["sheetName"]["value"], "LeadLog")

    def test_the_leadlog_columns_match_proj16s_leads_sheet_shape(self):
        nodes = {n["name"]: n for n in load("ghl-lead-router.workflow.json")["nodes"]}
        columns = nodes["Append lead log"]["parameters"]["columns"]["value"]
        expected = {"timestamp", "name", "email", "company", "message", "budget",
                    "timeline", "status", "tier", "score", "reason", "suggested_reply"}
        self.assertEqual(set(columns), expected)

    def test_the_whatsapp_alert_reuses_proj16s_credential_name(self):
        nodes = {n["name"]: n for n in load("ghl-lead-router.workflow.json")["nodes"]}
        node = nodes["WhatsApp hot lead alert"]
        self.assertEqual(node["credentials"]["whatsAppApi"]["name"], "WhatsApp account")
        self.assertEqual(node["credentials"]["whatsAppApi"]["id"], build_exports.PLACEHOLDER_ID)


class NoSecrets(unittest.TestCase):
    def test_exports_contain_no_secret_shaped_strings(self):
        text = (ROOT / "ghl-lead-router.workflow.json").read_text(encoding="utf-8")
        for label, pattern in SECRET_PATTERNS.items():
            self.assertIsNone(re.search(pattern, text), label)

    def test_the_patterns_catch_the_shapes_they_claim_to(self):
        samples = {
            "google_api_key": "AIza" + "A" * 35,
            "email_address": "someone@" + "gmail.com",
            "phone_number": "+63" + "9171234567",
            "google_doc_id": "/d/" + "x" * 40,
        }
        for label, sample in samples.items():
            self.assertIsNotNone(re.search(SECRET_PATTERNS[label], sample), label)


class GeneratorSync(unittest.TestCase):
    def test_file_on_disk_equals_what_the_generator_builds(self):
        built = build_exports.build()
        for name, text in built.items():
            self.assertEqual((ROOT / name).read_text(encoding="utf-8"), text, name)


if __name__ == "__main__":
    unittest.main()
