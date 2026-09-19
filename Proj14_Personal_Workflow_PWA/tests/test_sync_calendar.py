import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from calendar_plan import diff_events, key_of  # noqa: E402
from gcal import paged  # noqa: E402

FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "gcal_events_list.json").read_text(encoding="utf-8")
)


class TestPaging(unittest.TestCase):
    def test_paged_follows_next_page_token_and_collects_every_item(self):
        pages = FIXTURE["pages"]
        calls = []

        def fetch(token):
            calls.append(token)
            return pages[0] if token is None else pages[1]

        items = paged(fetch)
        self.assertEqual(calls, [None, "PAGE2"])
        self.assertEqual(len(items), 3)

    def test_paged_stops_when_no_next_page_token(self):
        def fetch(token):
            return {"items": [{"id": "only"}]}

        self.assertEqual(len(paged(fetch)), 1)


class TestReconcileAgainstRecordedFixture(unittest.TestCase):
    def existing(self):
        return [item for page in FIXTURE["pages"] for item in page["items"]]

    def test_recorded_events_match_their_own_desired_set_exactly(self):
        existing = self.existing()
        desired = [
            {k: v for k, v in e.items() if k not in ("id", "etag")}
            for e in existing
            if key_of(e) is not None
        ]
        creates, updates, deletes = diff_events(desired, existing)
        self.assertEqual((creates, updates, deletes), ([], [], []))

    def test_the_hand_made_event_is_never_deleted(self):
        existing = self.existing()
        creates, updates, deletes = diff_events([], existing)
        self.assertNotIn("handmade", deletes)
        self.assertEqual(sorted(deletes), ["gcal_aaa", "gcal_bbb"])


import datetime  # noqa: E402

from sync_calendar import window_bounds, read_day_docs  # noqa: E402


class FakeCouch:
    """Stands in for CouchDB.request, returning one _all_docs page."""

    def __init__(self, rows):
        self.rows = rows
        self.paths = []

    def request(self, method, path, body=None):
        self.paths.append(path)
        return 200, {"rows": self.rows}


class TestWindowBounds(unittest.TestCase):
    def test_bounds_cover_the_whole_window_in_the_local_offset(self):
        time_min, time_max = window_bounds(
            datetime.date(2026, 8, 17), 7, "Asia/Manila"
        )
        self.assertEqual(time_min, "2026-08-17T00:00:00+08:00")
        self.assertEqual(time_max, "2026-08-24T00:00:00+08:00")


class TestReadDayDocs(unittest.TestCase):
    def test_day_docs_are_keyed_by_date_and_scoped_to_the_window(self):
        rows = [
            {"doc": {"_id": "day:2026-08-17", "date": "2026-08-17", "branch": "B"}},
            {"doc": {"_id": "day:2026-08-18", "date": "2026-08-18", "branch": None}},
        ]
        couch = FakeCouch(rows)
        docs = read_day_docs(couch, "schedule", datetime.date(2026, 8, 17), 7)
        self.assertEqual(docs["2026-08-17"]["branch"], "B")
        self.assertIsNone(docs["2026-08-18"]["branch"])
        self.assertIn("include_docs=true", couch.paths[0])

    def test_rows_without_a_document_are_skipped(self):
        couch = FakeCouch([{"id": "day:2026-08-17", "value": {"deleted": True}}])
        docs = read_day_docs(couch, "schedule", datetime.date(2026, 8, 17), 7)
        self.assertEqual(docs, {})


if __name__ == "__main__":
    unittest.main()
