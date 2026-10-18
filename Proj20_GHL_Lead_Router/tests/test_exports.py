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
            [e["node"] for e in conn["GHL lead webhook"]["main"][0]], ["Read contact before write"],
        )
        self.assertEqual(
            [e["node"] for e in conn["Read contact before write"]["main"][0]], ["Fingerprint inquiry"],
        )
        self.assertEqual(
            [e["node"] for e in conn["Fingerprint inquiry"]["main"][0]], ["New inquiry?"],
        )
        self.assertEqual(
            [e["node"] for e in conn["New inquiry?"]["main"][0]], ["Call backend /qualify"],
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
            ["Has a tier?"],
        )
        self.assertEqual([e["node"] for e in conn["Has a tier?"]["main"][0]], ["Clear other tier tags"])
        self.assertEqual([e["node"] for e in conn["Has a tier?"]["main"][1]], ["Add tier tag"])
        self.assertEqual([e["node"] for e in conn["Clear other tier tags"]["main"][0]], ["Add tier tag"])
        self.assertEqual(
            [e["node"] for e in conn["Add tier tag"]["main"][0]],
            ["Look up opportunity by contact", "Upsert lead log"],
        )
        self.assertEqual(
            [e["node"] for e in conn["Look up opportunity by contact"]["main"][0]], ["Is hot?"],
        )

    def test_the_tier_branch_moves_the_opportunity_to_the_matching_stage(self):
        wf = load("ghl-lead-router.workflow.json")
        conn = wf["connections"]
        self.assertEqual([e["node"] for e in conn["Is hot?"]["main"][0]], ["Move to Hot stage", "First time hot?"])
        self.assertEqual([e["node"] for e in conn["Is hot?"]["main"][1]], ["Is warm?"])
        self.assertEqual([e["node"] for e in conn["Is warm?"]["main"][0]], ["Move to Warm stage"])
        self.assertEqual([e["node"] for e in conn["Is warm?"]["main"][1]], ["Is cold?"])
        self.assertEqual([e["node"] for e in conn["Is cold?"]["main"][0]], ["Move to Cold stage"])
        # a "review" lead (the model failed, not the lead) falls out of Is cold?'s
        # false port with nowhere to go: its opportunity stays in the New stage
        self.assertEqual(len(conn["Is cold?"]["main"]), 1)

    def test_a_review_lead_is_tagged_needs_review_not_with_the_raw_tier(self):
        nodes = {n["name"]: n for n in load("ghl-lead-router.workflow.json")["nodes"]}
        body = nodes["Add tier tag"]["parameters"]["jsonBody"]
        self.assertIn("'review'", body)
        self.assertIn("'needs-review'", body)

    def test_every_http_node_retries_with_a_wait_between_tries(self):
        for n in load("ghl-lead-router.workflow.json")["nodes"]:
            if n["type"] == HTTP:
                self.assertIs(n.get("retryOnFail"), True, n["name"])
                self.assertEqual(n.get("maxTries"), 3, n["name"])
                self.assertGreaterEqual(n.get("waitBetweenTries", 0), 1000, n["name"])

    def test_the_backend_call_reads_the_lead_from_the_webhook_node_by_name(self):
        # It sits behind the fingerprint/replay check, so its $json is the Set
        # node's output, not the webhook body (seen live: exec 114 failed with
        # "JSON Body is not valid JSON" when it still read $json.body).
        body = {n["name"]: n for n in load("ghl-lead-router.workflow.json")["nodes"]}["Call backend /qualify"]["parameters"]["jsonBody"]
        self.assertNotIn("$json", body)
        for field in ["name", "email", "message", "budget", "timeline", "blocker"]:
            self.assertIn(f"$('GHL lead webhook').item.json.body.customData.{field}", body)
        self.assertIn("$('GHL lead webhook').item.json.body.company_name", body)

    def test_the_backend_call_allows_for_a_render_cold_start(self):
        nodes = {n["name"]: n for n in load("ghl-lead-router.workflow.json")["nodes"]}
        self.assertEqual(nodes["Call backend /qualify"]["parameters"]["options"]["timeout"], 60000)

    def test_the_contact_is_read_from_ghl_before_anything_is_written(self):
        nodes = {n["name"]: n for n in load("ghl-lead-router.workflow.json")["nodes"]}
        read = nodes["Read contact before write"]
        self.assertEqual(read["parameters"]["method"], "GET")
        self.assertIn("/contacts/", read["parameters"]["url"])
        # it runs before the model is called, so it reads the id off the webhook
        self.assertIn("GHL lead webhook", read["parameters"]["url"])

    def test_a_replay_of_the_same_inquiry_stops_before_the_model_or_any_write(self):
        # GHL can re-send the same form webhook; re-scoring it could land in a
        # different tier and flip the stage. Same content fingerprint as the
        # one stored on the contact = already routed, so nothing runs.
        wf = load("ghl-lead-router.workflow.json")
        nodes = {n["name"]: n for n in wf["nodes"]}
        new_inquiry = wf["connections"]["New inquiry?"]["main"]
        self.assertEqual(len(new_inquiry), 1)
        cond = nodes["New inquiry?"]["parameters"]["conditions"]["conditions"][0]
        self.assertIn("Read contact before write", cond["leftValue"])
        self.assertIn("customFields", cond["leftValue"])
        self.assertIn("Fingerprint inquiry", cond["rightValue"])
        self.assertEqual(cond["operator"]["operation"], "notEquals")

    def test_the_fingerprint_hashes_the_inquiry_content_from_the_webhook(self):
        nodes = {n["name"]: n for n in load("ghl-lead-router.workflow.json")["nodes"]}
        [assignment] = nodes["Fingerprint inquiry"]["parameters"]["assignments"]["assignments"]
        self.assertEqual(assignment["name"], "lead_hash")
        for field in ["budget", "timeline", "blocker", "message"]:
            self.assertIn(f"customData.{field}", assignment["value"])
        self.assertIn(".hash('sha256')", assignment["value"])

    def test_the_fingerprint_is_stored_only_after_a_stage_move_succeeds(self):
        # Marking done last, like Proj19's cursor: a run that fails midway
        # leaves no fingerprint, so the replay redoes the work. A review lead
        # never reaches it either, so replaying one calls the model again.
        wf = load("ghl-lead-router.workflow.json")
        conn = wf["connections"]
        for name in ["Move to Hot stage", "Move to Warm stage", "Move to Cold stage"]:
            self.assertEqual([e["node"] for e in conn[name]["main"][0]], ["Mark inquiry routed"], name)
        nodes = {n["name"]: n for n in wf["nodes"]}
        mark = nodes["Mark inquiry routed"]
        self.assertEqual(mark["parameters"]["method"], "PUT")
        self.assertIn("Fingerprint inquiry", mark["parameters"]["jsonBody"])
        self.assertEqual(mark["parameters"]["jsonBody"].count("id: ''"), 1)

    def test_a_scored_lead_drops_its_other_tier_tags_so_only_one_tier_drip_fires(self):
        nodes = {n["name"]: n for n in load("ghl-lead-router.workflow.json")["nodes"]}
        clear = nodes["Clear other tier tags"]
        self.assertEqual(clear["parameters"]["method"], "DELETE")
        self.assertIn("/tags", clear["parameters"]["url"])
        body = clear["parameters"]["jsonBody"]
        for tag in ["'hot'", "'warm'", "'cold'", "'needs-review'"]:
            self.assertIn(tag, body)
        self.assertIn("filter", body)
        cond = nodes["Has a tier?"]["parameters"]["conditions"]["conditions"][0]
        self.assertEqual(cond["rightValue"], "review")
        self.assertEqual(cond["operator"]["operation"], "notEquals")

    def test_the_backend_call_sends_its_api_key_from_a_named_credential(self):
        node = {n["name"]: n for n in load("ghl-lead-router.workflow.json")["nodes"]}["Call backend /qualify"]
        self.assertEqual(node["parameters"]["authentication"], "genericCredentialType")
        self.assertEqual(node["parameters"]["genericAuthType"], "httpTemplatedCustomAuth")
        self.assertEqual(node["credentials"]["httpTemplatedCustomAuth"],
                         {"id": build_exports.PLACEHOLDER_ID, "name": "Proj20 qualify API key"})

    def test_the_whatsapp_alert_only_fires_the_first_time_a_contact_turns_hot(self):
        wf = load("ghl-lead-router.workflow.json")
        nodes = {n["name"]: n for n in wf["nodes"]}
        self.assertEqual([e["node"] for e in wf["connections"]["First time hot?"]["main"][0]], ["WhatsApp hot lead alert"])
        cond = nodes["First time hot?"]["parameters"]["conditions"]["conditions"][0]
        self.assertIn("Read contact before write", cond["leftValue"])
        self.assertIn("'hot'", cond["leftValue"])

    def test_the_lead_log_upserts_by_email_so_a_replay_does_not_add_a_second_row(self):
        nodes = {n["name"]: n for n in load("ghl-lead-router.workflow.json")["nodes"]}
        params = nodes["Upsert lead log"]["parameters"]
        self.assertEqual(params["operation"], "appendOrUpdate")
        self.assertEqual(params["columns"]["matchingColumns"], ["email"])

    def test_the_routing_branch_finishes_before_the_lead_log_runs(self):
        # executionOrder v1 runs sibling branches top to bottom by canvas y, and
        # a failed node stops the run. The lead log sits below every routing
        # node, so a Sheets failure can't block a stage move (seen live: an
        # expired Sheets OAuth stopped execution 101 before the opportunity
        # moved); the run still errors, so the shared error workflow alerts.
        wf = load("ghl-lead-router.workflow.json")
        self.assertEqual(wf["settings"]["executionOrder"], "v1")
        nodes = {n["name"]: n for n in wf["nodes"]}
        routing, todo = set(), ["Look up opportunity by contact"]
        while todo:
            name = todo.pop()
            if name not in routing:
                routing.add(name)
                for port in wf["connections"].get(name, {}).get("main", []):
                    todo += [e["node"] for e in port]
        self.assertNotIn("Upsert lead log", routing)
        log_y = nodes["Upsert lead log"]["position"][1]
        for name in routing:
            self.assertGreater(log_y, nodes[name]["position"][1], name)
        self.assertNotIn("onError", nodes["Upsert lead log"])

    def test_ghl_write_back_nodes_use_the_shared_templated_auth_credential(self):
        # httpTemplatedCustomAuth, not plain httpHeaderAuth: n8n rejects creating
        # a new plain generic credential on this node (confirmed live via n8n-mcp
        # validation against all 5 of these nodes).
        nodes = {n["name"]: n for n in load("ghl-lead-router.workflow.json")["nodes"]}
        for name in ["Read contact before write", "Write score/reason/reply to GHL", "Clear other tier tags",
                     "Add tier tag", "Look up opportunity by contact", "Move to Hot stage", "Move to Warm stage",
                     "Move to Cold stage", "Mark inquiry routed"]:
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
        lookup_query = nodes["Look up opportunity by contact"]["parameters"]["queryParameters"]["parameters"]
        location_param = next(p for p in lookup_query if p["name"] == "location_id")
        self.assertEqual(location_param["value"], "")

    def test_the_stage_move_nodes_look_up_the_opportunity_id_instead_of_trusting_the_webhook(self):
        # GHL's own webhook Custom Data sends opportunityId: '' even when the
        # opportunity already exists (confirmed live against the real hot test
        # contact) - the stage-move nodes must resolve the id from the lookup
        # node's own response, not from the webhook-supplied field.
        nodes = {n["name"]: n for n in load("ghl-lead-router.workflow.json")["nodes"]}
        lookup = nodes["Look up opportunity by contact"]
        self.assertEqual(lookup["parameters"]["method"], "GET")
        self.assertEqual(lookup["parameters"]["url"], "https://services.leadconnectorhq.com/opportunities/search")
        contact_param = next(p for p in lookup["parameters"]["queryParameters"]["parameters"] if p["name"] == "contact_id")
        self.assertIn("Merge qualification onto lead", contact_param["value"])
        for name in ["Move to Hot stage", "Move to Warm stage", "Move to Cold stage"]:
            url = nodes[name]["parameters"]["url"]
            self.assertIn("Look up opportunity by contact", url)
            self.assertIn("opportunities[0].id", url)
            self.assertNotIn("Merge qualification onto lead", url)


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
        params = nodes["Upsert lead log"]["parameters"]
        self.assertEqual(params["documentId"]["value"], "")
        self.assertEqual(params["sheetName"]["value"], "LeadLog")

    def test_the_leadlog_columns_match_proj16s_leads_sheet_shape(self):
        nodes = {n["name"]: n for n in load("ghl-lead-router.workflow.json")["nodes"]}
        columns = nodes["Upsert lead log"]["parameters"]["columns"]["value"]
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
