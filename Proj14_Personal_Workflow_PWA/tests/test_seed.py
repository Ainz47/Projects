"""seed.py must not overwrite checks/tasks the app has since edited, but must
sync everything else (streaks, days, wake/sleep, ...) from the file."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from seed import merge_template, seed_docs  # noqa: E402


class FakeCouch:
    """Records what was written and answers get_doc from a fixed doc map."""

    def __init__(self, docs=None):
        self.docs = dict(docs or {})
        self.written = []

    def get_doc(self, db_name, doc_id):
        return self.docs.get(doc_id)

    def put_doc(self, db_name, doc):
        self.written.append(doc["_id"])
        self.docs[doc["_id"]] = doc
        return {"rev": "10-abc"}


class MergeTemplateTests(unittest.TestCase):
    def test_no_remote_doc_uses_the_file_as_is(self):
        local = {"_id": "schedule:v1", "checks": {"a": {"label": "A"}}}
        self.assertEqual(merge_template(None, local), local)

    def test_app_owned_keys_come_from_remote(self):
        remote = {
            "checks": {"a": {"label": "A", "retiredOn": "2026-08-20"}},
            "tasks": {"t-a": {"label": "A task"}},
            "streaks": {"stale": {"label": "should not appear"}},
        }
        local = {
            "_id": "schedule:v1",
            "checks": {"a": {"label": "A", "retiredOn": None}},
            "tasks": {"t-a": {"label": "A task"}},
            "streaks": {"fresh": {"label": "hand-edited"}},
        }
        merged = merge_template(remote, local)
        self.assertEqual(merged["checks"]["a"]["retiredOn"], "2026-08-20")
        # streaks is structural: the file wins wholesale, remote-only entries drop.
        self.assertEqual(merged["streaks"], {"fresh": {"label": "hand-edited"}})

    def test_ids_new_in_the_file_are_added_to_the_app_owned_keys(self):
        remote = {"checks": {"a": {"label": "A"}}, "tasks": {}}
        local = {
            "_id": "schedule:v1",
            "checks": {"a": {"label": "A (renamed in file)"}, "b": {"label": "B"}},
            "tasks": {},
        }
        merged = merge_template(remote, local)
        # "a" already existed remotely, so the remote copy wins even though the
        # file renamed it - that edit needs --force.
        self.assertEqual(merged["checks"]["a"]["label"], "A")
        # "b" is new, so it comes through untouched.
        self.assertEqual(merged["checks"]["b"]["label"], "B")


class SeedDocsTests(unittest.TestCase):
    def setUp(self):
        self.data = ROOT / "src" / "data"
        self.local_template = json.loads(
            (self.data / "schedule-template.json").read_text(encoding="utf-8")
        )

    def test_writes_everything_into_an_empty_database(self):
        couch = FakeCouch()
        result = seed_docs(couch, "schedule", self.data)
        self.assertEqual([action for _, action in result], ["wrote", "wrote"])
        self.assertIn("schedule:v1", couch.written)

    def test_structural_edits_sync_without_force(self):
        remote = dict(self.local_template)
        remote["streaks"] = {**remote["streaks"], "old-streak": {"label": "gone from file"}}
        couch = FakeCouch(docs={"schedule:v1": remote})
        seed_docs(couch, "schedule", self.data)
        written = couch.docs["schedule:v1"]
        self.assertNotIn("old-streak", written["streaks"])

    def test_checks_and_tasks_are_preserved_from_the_live_doc(self):
        remote = dict(self.local_template)
        first_check_id = next(iter(self.local_template["checks"]))
        remote["checks"] = {
            **remote["checks"],
            first_check_id: {**remote["checks"][first_check_id], "retiredOn": "2026-08-20"},
        }
        couch = FakeCouch(docs={"schedule:v1": remote})
        seed_docs(couch, "schedule", self.data)
        written = couch.docs["schedule:v1"]
        self.assertEqual(written["checks"][first_check_id]["retiredOn"], "2026-08-20")

    def test_force_overwrites_checks_and_tasks_from_the_file(self):
        remote = dict(self.local_template)
        first_check_id = next(iter(self.local_template["checks"]))
        remote["checks"] = {
            **remote["checks"],
            first_check_id: {**remote["checks"][first_check_id], "retiredOn": "2026-08-20"},
        }
        couch = FakeCouch(docs={"schedule:v1": remote})
        seed_docs(couch, "schedule", self.data, force=True)
        written = couch.docs["schedule:v1"]
        self.assertIsNone(written["checks"][first_check_id].get("retiredOn"))

    def test_the_campaign_document_is_still_written_every_time(self):
        couch = FakeCouch(docs={
            "schedule:v1": self.local_template,
            "campaign:talk-demo": {"_id": "campaign:talk-demo"},
        })
        seed_docs(couch, "schedule", self.data)
        self.assertIn("campaign:talk-demo", couch.written)


if __name__ == "__main__":
    unittest.main()
