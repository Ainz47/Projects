import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import build_exports  # noqa: E402

CODE = "n8n-nodes-base.code"
GEMINI = "@n8n/n8n-nodes-langchain.googleGemini"
SHEETS = "n8n-nodes-base.googleSheets"
WHATSAPP = "n8n-nodes-base.whatsApp"
EXPECTED_TYPES = {
    "lead-capture.workflow.json": {
        "n8n-nodes-base.formTrigger", GEMINI, SHEETS, "n8n-nodes-base.if", WHATSAPP, CODE, "n8n-nodes-base.set",
    },
    "weekly-summary.workflow.json": {
        "n8n-nodes-base.scheduleTrigger", SHEETS, CODE, GEMINI, "n8n-nodes-base.set", WHATSAPP,
    },
    "error-alert.workflow.json": {"n8n-nodes-base.errorTrigger", WHATSAPP},
}
SECRET_PATTERNS = {
    "google_api_key": r"AIza[0-9A-Za-z_-]{20,}",
    "google_oauth_secret": r"GOCSPX-[0-9A-Za-z_-]{10,}",
    "sk_key": r"\bsk-[A-Za-z0-9_-]{20,}",
    "meta_access_token": r"\bEAA[0-9A-Za-z]{20,}",
    "bearer_token": r"Bearer [A-Za-z0-9._-]{20,}",
    "github_token": r"gh[pousr]_[A-Za-z0-9]{20,}",
    "email_address": r"[A-Za-z0-9._%+-]+@(?!example\.com\b)[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "windows_user_path": r"[A-Za-z]:\\+Users",
    "phone_number": r"\+\d{10,}",
    "google_doc_id": r"/d/[A-Za-z0-9_-]{25,}",
}


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def by_name(workflow):
    return {n["name"]: n for n in workflow["nodes"]}


def targets(workflow, source, port):
    outputs = workflow["connections"][source]["main"]
    return [edge["node"] for edge in outputs[port]] if port < len(outputs) else []


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

    def test_node_names_are_unique(self):
        for name in EXPECTED_TYPES:
            names = [n["name"] for n in load(name)["nodes"]]
            self.assertEqual(len(names), len(set(names)), name)

    def test_workflows_ship_inactive_with_no_pinned_data(self):
        for name in EXPECTED_TYPES:
            wf = load(name)
            self.assertIs(wf["active"], False, name)
            self.assertFalse(wf.get("pinData"), name)

    def test_credentials_are_placeholders_and_alert_targets_are_blank(self):
        for name in EXPECTED_TYPES:
            for node in load(name)["nodes"]:
                for cred in node.get("credentials", {}).values():
                    self.assertEqual(cred["id"], build_exports.PLACEHOLDER_ID, name)
                if node["type"] == WHATSAPP:
                    self.assertEqual(node["parameters"]["phoneNumberId"], "")
                    self.assertEqual(node["parameters"]["recipientPhoneNumber"], "")


class LeadCaptureWiring(unittest.TestCase):
    def setUp(self):
        self.wf = load("lead-capture.workflow.json")
        self.nodes = by_name(self.wf)

    def test_invalid_leads_skip_the_llm_and_land_in_the_sheet(self):
        self.assertEqual(targets(self.wf, "Is valid?", 0), ["Gemini qualify"])
        self.assertEqual(targets(self.wf, "Is valid?", 1), ["Mark rejected"])
        self.assertEqual(targets(self.wf, "Mark rejected", 0), ["Append row"])

    def test_parsed_leads_go_to_the_sheet_and_the_hot_check(self):
        self.assertCountEqual(targets(self.wf, "Parse qualification", 0), ["Append row", "Is hot?"])
        self.assertEqual(targets(self.wf, "Is hot?", 0), ["WhatsApp alert"])
        self.assertEqual(targets(self.wf, "Is hot?", 1), [])

    def test_an_llm_failure_does_not_drop_the_lead(self):
        self.assertEqual(self.nodes["Gemini qualify"].get("onError"), "continueRegularOutput")
        self.assertEqual(targets(self.wf, "Gemini qualify", 0), ["Normalize LLM output"])
        self.assertEqual(targets(self.wf, "Normalize LLM output", 0), ["Parse qualification"])

    def test_sheet_append_is_atomic_so_concurrent_leads_are_not_lost(self):
        # Found in a live run: without useAppend, leads arriving together overwrote each other.
        self.assertIs(self.nodes["Append row"]["parameters"]["options"].get("useAppend"), True)

    def test_code_nodes_embed_the_tested_logic(self):
        self.assertIn("function validateLead", self.nodes["Validate lead"]["parameters"]["jsCode"])
        parse = self.nodes["Parse qualification"]["parameters"]["jsCode"]
        self.assertIn("function parseQualification", parse)
        self.assertIn("function acceptedRow", parse)
        self.assertNotIn("module.exports", parse)


class NoSecrets(unittest.TestCase):
    def test_exports_contain_no_secret_shaped_strings(self):
        for name in EXPECTED_TYPES:
            text = (ROOT / name).read_text(encoding="utf-8")
            for label, pattern in SECRET_PATTERNS.items():
                self.assertIsNone(re.search(pattern, text), f"{name}: {label}")

    def test_the_patterns_catch_the_shapes_they_claim_to(self):
        samples = {
            "google_api_key": "AIza" + "A" * 35,
            "sk_key": "sk-" + "a" * 30,
            "meta_access_token": "EAA" + "B" * 30,
            "email_address": "someone@" + "gmail.com",
            "phone_number": "+63" + "9171234567",
            "google_doc_id": "/d/" + "x" * 40,
        }
        for label, sample in samples.items():
            self.assertIsNotNone(re.search(SECRET_PATTERNS[label], sample), label)
        self.assertIsNone(re.search(SECRET_PATTERNS["email_address"], "dana@example.com"))


class GeneratorSync(unittest.TestCase):
    def test_files_on_disk_equal_what_the_generator_builds(self):
        built = build_exports.build()
        self.assertEqual(set(built), set(EXPECTED_TYPES))
        for name, text in built.items():
            self.assertEqual((ROOT / name).read_text(encoding="utf-8"), text, name)


if __name__ == "__main__":
    unittest.main()
