import datetime
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from vault_render import GENERATED_MARKER, comparable, render, render_override_line  # noqa: E402

TEMPLATE = json.loads(
    (ROOT / "src" / "data" / "schedule-template.json").read_text(encoding="utf-8")
)
MONDAY = datetime.date(2026, 8, 17)
STAMP = datetime.datetime(2026, 8, 17, 5, 0, 0)


class TestRender(unittest.TestCase):
    def setUp(self):
        self.text = render(TEMPLATE, {}, MONDAY, STAMP)

    def test_renders_non_ascii_template_content_intact(self):
        # The note is UTF-8 in the vault, so non-ASCII block content must
        # survive rather than be forced to ASCII. The production template no
        # longer has a naturally-occurring em dash in it, so inject one into
        # a copy just for this test rather than depending on incidental data.
        template = json.loads(json.dumps(TEMPLATE))
        template["days"]["tue"]["blocks"][0]["detail"] = "Outside — for the light."
        text = render(template, {}, MONDAY, STAMP)
        self.assertIn(chr(0x2014), text)

    def test_carries_the_generated_marker(self):
        self.assertIn(GENERATED_MARKER, self.text)

    def test_has_both_sections(self):
        self.assertIn("## Template", self.text)
        self.assertIn("## This week", self.text)

    def test_template_section_lists_all_seven_days_in_weekday_order(self):
        order = [self.text.index(f"### {name}") for name in
                 ("Monday", "Tuesday", "Wednesday", "Thursday",
                  "Friday", "Saturday", "Sunday")]
        self.assertEqual(order, sorted(order))

    def test_branching_days_show_both_branches(self):
        self.assertIn("#### Branch A", self.text)
        self.assertIn("#### Branch B", self.text)

    def test_a_block_renders_time_label_and_detail(self):
        self.assertIn("`06:00-06:30` **Top Focus** - Quiet time", self.text)

    def test_week_section_has_seven_dated_days(self):
        for offset in range(7):
            day = MONDAY + datetime.timedelta(days=offset)
            self.assertIn(day.isoformat(), self.text)

    def test_week_marks_the_resolved_branch_on_branching_days(self):
        self.assertIn("### Mon 2026-08-17 (Branch A)", self.text)

    def test_day_document_branch_b_is_reflected_in_the_week(self):
        text = render(TEMPLATE, {"2026-08-17": {"date": "2026-08-17", "branch": "B"}},
                      MONDAY, STAMP)
        self.assertIn("### Mon 2026-08-17 (Branch B)", text)

    def test_non_branching_day_has_no_branch_suffix(self):
        self.assertIn("### Tue 2026-08-18\n", self.text)

    def test_render_is_deterministic(self):
        self.assertEqual(self.text, render(TEMPLATE, {}, MONDAY, STAMP))

    def test_override_line_names_only_the_overridden_half(self):
        day = {"date": "2026-08-11", "sleepOverride": "23:15",
               "wakeOverride": None, "blocks": {}, "checks": {}}
        line = render_override_line(day, {"wake": "06:00", "sleep": "22:30"})
        self.assertEqual(line, "- sleep 23:15 (+45)")

    def test_override_line_names_both_when_both_set(self):
        day = {"date": "2026-08-11", "sleepOverride": "23:15",
               "wakeOverride": "07:00", "blocks": {}, "checks": {}}
        line = render_override_line(day, {"wake": "06:00", "sleep": "22:30"})
        self.assertEqual(line, "- sleep 23:15 (+45), wake 07:00 (+60)")

    def test_override_line_is_empty_on_a_clean_day(self):
        day = {"date": "2026-08-11", "sleepOverride": None,
               "wakeOverride": None, "blocks": {}, "checks": {}}
        self.assertEqual(render_override_line(day, {"wake": "06:00", "sleep": "22:30"}), "")

    def test_a_negative_nudge_is_signed(self):
        day = {"date": "2026-08-11", "sleepOverride": "21:45",
               "wakeOverride": None, "blocks": {}, "checks": {}}
        line = render_override_line(day, {"wake": "06:00", "sleep": "22:30"})
        self.assertEqual(line, "- sleep 21:45 (-45)")


class TestComparable(unittest.TestCase):
    def test_timestamp_line_is_excluded(self):
        early = render(TEMPLATE, {}, MONDAY, datetime.datetime(2026, 8, 17, 5, 0))
        late = render(TEMPLATE, {}, MONDAY, datetime.datetime(2026, 8, 17, 23, 59))
        self.assertNotEqual(early, late)
        self.assertEqual(comparable(early), comparable(late))

    def test_a_real_content_change_still_differs(self):
        monday = render(TEMPLATE, {}, MONDAY, STAMP)
        branch_b = render(TEMPLATE, {"2026-08-17": {"branch": "B"}}, MONDAY, STAMP)
        self.assertNotEqual(comparable(monday), comparable(branch_b))


def _todo(text, **kw):
    doc = {
        "_id": f"todo:2026-08-17T09:00:00.000Z:{text[:6]}", "type": "todo",
        "text": text, "note": "", "due": None, "pinned": False,
        "done": False, "doneAt": None,
        "createdAt": "2026-08-17T09:00:00.000Z",
        "updatedAt": "2026-08-17T09:00:00.000Z",
    }
    doc.update(kw)
    return doc


class TestTodosSection(unittest.TestCase):
    def test_section_is_absent_when_there_are_no_todos(self):
        self.assertNotIn("## Todos", render(TEMPLATE, {}, MONDAY, STAMP, todos=[]))

    def test_open_items_render(self):
        text = render(TEMPLATE, {}, MONDAY, STAMP, todos=[_todo("buy milk")])
        self.assertIn("## Todos", text)
        self.assertIn("- [ ] buy milk", text)

    def test_a_due_date_renders_with_the_item(self):
        text = render(TEMPLATE, {}, MONDAY, STAMP,
                      todos=[_todo("email the client", due="2026-08-20")])
        self.assertIn("- [ ] email the client (due 2026-08-20)", text)

    def test_a_pinned_item_is_marked(self):
        text = render(TEMPLATE, {}, MONDAY, STAMP, todos=[_todo("call the bank", pinned=True)])
        self.assertIn("- [ ] **call the bank**", text)

    def test_an_item_completed_this_week_renders_ticked(self):
        text = render(TEMPLATE, {}, MONDAY, STAMP, todos=[
            _todo("fix the sync", done=True, doneAt="2026-08-15T18:00:00.000Z"),
        ])
        self.assertIn("- [x] fix the sync", text)

    def test_an_item_completed_the_previous_week_does_not_render(self):
        text = render(TEMPLATE, {}, MONDAY, STAMP, todos=[
            _todo("old thing", done=True, doneAt="2026-08-01T18:00:00.000Z"),
        ])
        self.assertNotIn("old thing", text)

    def test_an_item_completed_exactly_six_days_ago_still_renders(self):
        text = render(TEMPLATE, {}, MONDAY, STAMP, todos=[
            _todo("edge case", done=True, doneAt="2026-08-11T18:00:00.000Z"),
        ])
        self.assertIn("- [x] edge case", text)

    def test_open_items_come_before_completed_ones(self):
        text = render(TEMPLATE, {}, MONDAY, STAMP, todos=[
            _todo("done thing", done=True, doneAt="2026-08-16T18:00:00.000Z"),
            _todo("open thing"),
        ])
        self.assertLess(text.index("open thing"), text.index("done thing"))

    def test_the_existing_four_argument_call_still_works(self):
        self.assertIn("## Template", render(TEMPLATE, {}, MONDAY, STAMP))


if __name__ == "__main__":
    unittest.main()


class TestOverriddenWeek(unittest.TestCase):
    def test_an_overridden_date_shifts_the_week_but_not_the_template(self):
        tue = TEMPLATE["days"]["tue"]["blocks"]
        entries = []
        for b in tue:
            entry = {"id": b["id"], "start": b["start"], "end": b["end"],
                     "hours": b["hours"], "fields": None}
            if b["id"] == "tue-client1":
                entry.update({"end": "11:00", "hours": 3.5})
            if b["id"] == "tue-talk":
                entry.update({"start": "11:00", "hours": 0.5})
            entries.append(entry)

        day_docs = {"2026-08-18": {"date": "2026-08-18", "blocksOverride": entries}}
        text = render(TEMPLATE, day_docs, MONDAY, STAMP)
        week = text.split("## This week")[1]
        template_section = text.split("## This week")[0]

        self.assertIn("`07:30-11:00` **Client Work (CORE)**", week)
        # The Template section is the weekly pattern and must not move.
        self.assertIn("`07:30-10:30` **Client Work (CORE)**", template_section)
