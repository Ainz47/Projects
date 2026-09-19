import datetime
import json
import sys
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from calendar_plan import build_events, blocks_for, resolve_blocks, schedule_key  # noqa: E402

TEMPLATE = json.loads(
    (ROOT / "src" / "data" / "schedule-template.json").read_text(encoding="utf-8")
)
MONDAY = datetime.date(2026, 8, 17)
TZ = "Asia/Manila"


def keys(events):
    return [e["extendedProperties"]["private"]["scheduleKey"] for e in events]


class TestBuildEvents(unittest.TestCase):
    def test_only_calendar_event_blocks_are_included(self):
        events = build_events(TEMPLATE, {}, MONDAY, 1, TZ)
        # Monday branch A has 11 blocks but only 6 marked calendar.event
        self.assertEqual(len(events), 6)

    def test_branching_day_defaults_to_branch_a(self):
        events = build_events(TEMPLATE, {}, MONDAY, 1, TZ)
        self.assertTrue(all("mon-a-" in k for k in keys(events)))

    def test_day_document_branch_b_overrides_the_default(self):
        day_docs = {"2026-08-17": {"date": "2026-08-17", "branch": "B"}}
        events = build_events(TEMPLATE, day_docs, MONDAY, 1, TZ)
        self.assertEqual(len(events), 5)
        self.assertTrue(all("mon-b-" in k for k in keys(events)))

    def test_null_branch_falls_back_to_branch_a(self):
        day_docs = {"2026-08-17": {"date": "2026-08-17", "branch": None}}
        events = build_events(TEMPLATE, day_docs, MONDAY, 1, TZ)
        self.assertTrue(all("mon-a-" in k for k in keys(events)))

    def test_schedule_key_format(self):
        self.assertEqual(schedule_key("2026-08-17", "mon-a-class"),
                         "2026-08-17:mon-a-class")

    def test_departure_block_keeps_its_thirty_minute_reminder(self):
        events = build_events(TEMPLATE, {}, MONDAY, 1, TZ)
        depart = next(e for e in events
                      if e["extendedProperties"]["private"]["scheduleKey"]
                      .endswith("mon-a-depart"))
        self.assertEqual(
            depart["reminders"]["overrides"], [{"method": "popup", "minutes": 30}]
        )

    def test_block_without_remind_minutes_uses_the_template_default(self):
        events = build_events(TEMPLATE, {}, MONDAY, 1, TZ)
        default = TEMPLATE["calendar"]["defaultRemindMinutes"]
        klass = next(e for e in events
                     if e["extendedProperties"]["private"]["scheduleKey"]
                     .endswith("mon-a-class"))
        self.assertEqual(
            klass["reminders"]["overrides"], [{"method": "popup", "minutes": default}]
        )

    def test_start_and_end_carry_the_timezone_and_local_time(self):
        events = build_events(TEMPLATE, {}, MONDAY, 1, TZ)
        first = min(events, key=lambda e: e["start"]["dateTime"])
        self.assertEqual(first["start"]["timeZone"], TZ)
        self.assertTrue(first["start"]["dateTime"].startswith("2026-08-17T"))
        self.assertEqual(len(first["start"]["dateTime"]), 19)

    def test_window_spans_days_ahead_and_uses_each_days_own_template(self):
        events = build_events(TEMPLATE, {}, MONDAY, 7, TZ)
        # mon A 6, tue 5, wed A 6, thu 5, fri 5, sat 5, sun 4
        self.assertEqual(len(events), 36)
        dates = {k.split(":")[0] for k in keys(events)}
        self.assertEqual(len(dates), 7)

    def test_output_is_deterministic(self):
        first = build_events(TEMPLATE, {}, MONDAY, 7, TZ)
        second = build_events(TEMPLATE, {}, MONDAY, 7, TZ)
        self.assertEqual(first, second)


from calendar_plan import diff_events, key_of  # noqa: E402


def as_stored(event, event_id):
    """Render one event body the way the API hands it back.

    Google does not echo the request. Verified against the live API on
    2026-08-11: it canonicalises every dateTime by appending the zone's UTC
    offset, and it drops description entirely rather than storing "". A double
    that echoes the body verbatim hides both, which is exactly what happened.
    """
    stored = json.loads(json.dumps(event))
    stored["id"] = event_id
    stored["etag"] = '"abc"'              # Google adds fields we must ignore
    for bound in ("start", "end"):
        moment = datetime.datetime.fromisoformat(stored[bound]["dateTime"])
        moment = moment.replace(tzinfo=ZoneInfo(stored[bound]["timeZone"]))
        stored[bound]["dateTime"] = moment.isoformat()
    if not stored.get("description"):
        stored.pop("description", None)
    return stored


def as_existing(events, start_id=1):
    """Turn desired bodies into what the API would hand back, with ids."""
    return [as_stored(event, f"gcal{n}")
            for n, event in enumerate(events, start=start_id)]


def apply_diff(existing, creates, updates, deletes):
    """Simulate the API applying a diff, so we can re-diff the result."""
    surviving = [e for e in existing if e["id"] not in deletes]
    by_id = {e["id"]: e for e in surviving}
    for event_id, body in updates:
        by_id[event_id] = as_stored(body, event_id)
    result = list(by_id.values())
    return result + as_existing(creates, start_id=900)


class TestDiffEvents(unittest.TestCase):
    def test_everything_is_created_against_an_empty_calendar(self):
        desired = build_events(TEMPLATE, {}, MONDAY, 1, TZ)
        creates, updates, deletes = diff_events(desired, [])
        self.assertEqual(len(creates), 6)
        self.assertEqual(updates, [])
        self.assertEqual(deletes, [])

    def test_running_twice_changes_nothing(self):
        desired = build_events(TEMPLATE, {}, MONDAY, 7, TZ)
        creates, updates, deletes = diff_events(desired, [])
        applied = apply_diff([], creates, updates, deletes)
        creates2, updates2, deletes2 = diff_events(desired, applied)
        self.assertEqual(creates2, [])
        self.assertEqual(updates2, [])
        self.assertEqual(deletes2, [])

    def test_changed_time_produces_an_update_not_a_duplicate(self):
        desired = build_events(TEMPLATE, {}, MONDAY, 1, TZ)
        existing = as_existing(desired)
        existing[0]["start"]["dateTime"] = "2026-08-17T23:59:00"
        creates, updates, deletes = diff_events(desired, existing)
        self.assertEqual(creates, [])
        self.assertEqual(deletes, [])
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0][0], existing[0]["id"])

    def test_branch_flip_deletes_the_a_events_and_writes_the_b_set(self):
        branch_a = build_events(TEMPLATE, {}, MONDAY, 1, TZ)
        existing = as_existing(branch_a)
        day_docs = {"2026-08-17": {"date": "2026-08-17", "branch": "B"}}
        branch_b = build_events(TEMPLATE, day_docs, MONDAY, 1, TZ)

        creates, updates, deletes = diff_events(branch_b, existing)
        self.assertEqual(len(deletes), 6)
        self.assertEqual(len(creates), 5)
        self.assertTrue(all("mon-b-" in key_of(c) for c in creates))

    def test_branch_flip_then_rerun_is_stable(self):
        branch_a = build_events(TEMPLATE, {}, MONDAY, 1, TZ)
        existing = as_existing(branch_a)
        day_docs = {"2026-08-17": {"date": "2026-08-17", "branch": "B"}}
        branch_b = build_events(TEMPLATE, day_docs, MONDAY, 1, TZ)

        applied = apply_diff(existing, *diff_events(branch_b, existing))
        creates, updates, deletes = diff_events(branch_b, applied)
        self.assertEqual((creates, updates, deletes), ([], [], []))

    def test_foreign_events_without_a_schedule_key_are_left_alone(self):
        desired = build_events(TEMPLATE, {}, MONDAY, 1, TZ)
        existing = as_existing(desired)
        existing.append({"id": "handmade", "summary": "Dentist"})
        creates, updates, deletes = diff_events(desired, existing)
        self.assertEqual((creates, updates, deletes), ([], [], []))

    def test_key_of_returns_none_for_a_foreign_event(self):
        self.assertIsNone(key_of({"id": "handmade", "summary": "Dentist"}))

    def test_offset_form_of_the_same_instant_is_not_a_change(self):
        """Google returns 07:30+08:00 for the 07:30 Asia/Manila we sent."""
        desired = build_events(TEMPLATE, {}, MONDAY, 1, TZ)
        existing = as_existing(desired)
        self.assertTrue(existing[0]["start"]["dateTime"].endswith("+08:00"))
        creates, updates, deletes = diff_events(desired, existing)
        self.assertEqual((creates, updates, deletes), ([], [], []))

    def test_dropped_empty_description_is_not_a_change(self):
        """Google omits description rather than storing an empty string."""
        desired = build_events(TEMPLATE, {}, MONDAY, 1, TZ)
        existing = as_existing(desired)
        blank = [e for e in existing if "description" not in e]
        self.assertTrue(blank, "expected at least one detail-less block")
        creates, updates, deletes = diff_events(desired, existing)
        self.assertEqual(updates, [])

    def test_a_real_description_change_is_still_an_update(self):
        """Normalising the empty case must not blind us to a genuine edit."""
        desired = build_events(TEMPLATE, {}, MONDAY, 1, TZ)
        existing = as_existing(desired)
        target = next(e for e in existing if e.get("description"))
        target["description"] = "stale text"
        creates, updates, deletes = diff_events(desired, existing)
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0][0], target["id"])

    def test_stale_day_outside_the_window_is_deleted(self):
        stale = build_events(TEMPLATE, {}, datetime.date(2026, 8, 10), 1, TZ)
        existing = as_existing(stale)
        desired = build_events(TEMPLATE, {}, MONDAY, 1, TZ)
        creates, updates, deletes = diff_events(desired, existing)
        self.assertEqual(len(deletes), len(stale))
        self.assertEqual(len(creates), 6)


if __name__ == "__main__":
    unittest.main()


def snapshot(blocks, **moves):
    """The structural half of a block list, as a day document carries it."""
    out = []
    for b in blocks:
        entry = {"id": b["id"], "start": b["start"], "end": b["end"],
                 "hours": b["hours"], "fields": None}
        entry.update(moves.get(b["id"], {}))
        out.append(entry)
    return out


TUESDAY = datetime.date(2026, 8, 18)


class TestResolveBlocks(unittest.TestCase):
    def test_no_override_is_the_template_list(self):
        self.assertEqual(
            resolve_blocks(TEMPLATE, "tue", None, None),
            blocks_for(TEMPLATE, "tue", None),
        )
        self.assertEqual(
            resolve_blocks(TEMPLATE, "tue", None, {"date": "2026-08-18"}),
            blocks_for(TEMPLATE, "tue", None),
        )

    def test_override_moves_the_times_and_keeps_the_fields_live(self):
        base = blocks_for(TEMPLATE, "tue", None)
        entries = snapshot(
            base,
            **{"tue-client1": {"end": "11:00", "hours": 3.5},
               "tue-talk": {"start": "11:00", "hours": 0.5}},
        )
        resolved = resolve_blocks(TEMPLATE, "tue", None, {"blocksOverride": entries})
        by_id = {b["id"]: b for b in resolved}
        self.assertEqual(by_id["tue-client1"]["end"], "11:00")
        self.assertEqual(by_id["tue-client1"]["label"], "Client Work (CORE)")
        self.assertEqual(by_id["tue-talk"]["start"], "11:00")

    def test_a_snapshotted_id_the_template_lost_becomes_an_inert_tombstone(self):
        entries = snapshot(blocks_for(TEMPLATE, "tue", None))
        entries.append({"id": "tue-gone", "start": "22:00", "end": "22:30",
                        "hours": 0.5, "fields": None})
        resolved = resolve_blocks(TEMPLATE, "tue", None, {"blocksOverride": entries})
        dead = [b for b in resolved if b["id"] == "tue-gone"][0]
        self.assertFalse(dead["calendar"]["event"])
        self.assertIsNone(dead["attribute"])


class TestOverriddenDays(unittest.TestCase):
    def test_an_overridden_date_shifts_only_its_own_events(self):
        base = blocks_for(TEMPLATE, "tue", None)
        entries = snapshot(
            base,
            **{"tue-client1": {"end": "11:00", "hours": 3.5},
               "tue-talk": {"start": "11:00", "hours": 0.5}},
        )
        day_docs = {"2026-08-18": {"date": "2026-08-18", "branch": None,
                                   "blocksOverride": entries}}
        events = build_events(TEMPLATE, day_docs, TUESDAY, 2, TZ)
        by_key = {e["extendedProperties"]["private"]["scheduleKey"]: e for e in events}
        self.assertEqual(
            by_key["2026-08-18:tue-client1"]["end"]["dateTime"], "2026-08-18T11:00:00")
        # Wednesday, the day after, is untouched by the override.
        self.assertTrue(any(k.startswith("2026-08-19:wed-a-") for k in by_key))

    def test_a_one_off_block_becomes_an_event_under_its_own_key(self):
        base = blocks_for(TEMPLATE, "tue", None)
        entries = snapshot(base, **{"tue-lunch": {"start": "12:00", "hours": 0.5}})
        entries.insert(4, {
            "id": "2026-08-18-dentist", "start": "11:30", "end": "12:00", "hours": 0.5,
            "fields": {
                "label": "Dentist", "detail": "Molar.", "attribute": "lifeskills",
                "kind": "fixed", "taskId": None, "campaignSlot": False, "streakId": None,
                "calendar": {"event": True, "remindMinutes": 30},
            },
        })
        day_docs = {"2026-08-18": {"date": "2026-08-18", "blocksOverride": entries}}
        events = build_events(TEMPLATE, day_docs, TUESDAY, 1, TZ)
        keyed = {e["extendedProperties"]["private"]["scheduleKey"]: e for e in events}
        self.assertIn(schedule_key("2026-08-18", "2026-08-18-dentist"), keyed)
        dentist = keyed[schedule_key("2026-08-18", "2026-08-18-dentist")]
        self.assertEqual(dentist["summary"], "Dentist")
        self.assertEqual(dentist["reminders"]["overrides"][0]["minutes"], 30)
