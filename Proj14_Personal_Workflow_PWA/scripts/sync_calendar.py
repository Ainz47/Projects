"""Upsert the next week of schedule blocks into the dedicated Google Calendar.

Runs hourly from Task Scheduler. Every event carries a scheduleKey private
property, so a run reconciles rather than duplicates. The calendar is an
output, never a dependency: if this fails the app is unaffected.
"""
import datetime
import sys
import urllib.parse
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))
from couch import CouchDB, CouchError, load_env  # noqa: E402
from calendar_plan import build_events, diff_events  # noqa: E402
from gcal import (  # noqa: E402
    GoogleApiError,
    GoogleAuthError,
    GoogleCalendar,
    access_token,
)

ROOT = Path(__file__).resolve().parent.parent


def window_bounds(start_date, days_ahead, timezone):
    """RFC3339 bounds for the query window, in the schedule's own timezone."""
    zone = ZoneInfo(timezone)
    start = datetime.datetime.combine(start_date, datetime.time.min, tzinfo=zone)
    end = start + datetime.timedelta(days=days_ahead)
    return start.isoformat(), end.isoformat()


def read_day_docs(couch, db_name, start_date, days_ahead):
    """Fetch the day documents overlapping the window, keyed by date string."""
    first = start_date.isoformat()
    last = (start_date + datetime.timedelta(days=days_ahead - 1)).isoformat()
    # Day ids are exactly "day:YYYY-MM-DD" with no suffix, so the plain last
    # date is a correct upper bound under CouchDB's default inclusive_end.
    startkey = urllib.parse.quote(f'"day:{first}"', safe="")
    endkey = urllib.parse.quote(f'"day:{last}"', safe="")
    status, body = couch.request(
        "GET",
        f"/{db_name}/_all_docs?startkey={startkey}&endkey={endkey}&include_docs=true",
    )
    if status != 200:
        raise CouchError(status, body)
    docs = {}
    for row in body.get("rows", []):
        doc = row.get("doc")
        if doc and doc.get("date"):
            docs[doc["date"]] = doc
    return docs


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    env = load_env(ROOT / ".env")
    timezone = env.get("SCHEDULE_TIMEZONE", "Asia/Manila")
    calendar_name = env.get("GOOGLE_CALENDAR_NAME", "Schedule")
    db_name = env.get("COUCHDB_DB", "schedule")

    couch = CouchDB(env["COUCHDB_URL"], env["COUCHDB_USER"], env["COUCHDB_PASSWORD"])
    template = couch.get_doc(db_name, "schedule:v1")
    if template is None:
        print("no schedule:v1 document. Run scripts/seed.py first.")
        return 1

    days_ahead = template["calendar"]["daysAhead"]
    start_date = datetime.datetime.now(ZoneInfo(timezone)).date()

    day_docs = read_day_docs(couch, db_name, start_date, days_ahead)
    desired = build_events(template, day_docs, start_date, days_ahead, timezone)

    token = access_token(
        env["GOOGLE_CLIENT_ID"], env["GOOGLE_CLIENT_SECRET"], env["GOOGLE_REFRESH_TOKEN"]
    )
    api = GoogleCalendar(token)

    calendar_id = api.find_calendar(calendar_name)
    if calendar_id is None:
        calendar_id = api.create_calendar(calendar_name, timezone)
        print(f"created calendar {calendar_name}")

    time_min, time_max = window_bounds(start_date, days_ahead, timezone)
    existing = api.list_events(calendar_id, time_min, time_max)

    # Plan the entire change set before writing anything, so a failure while
    # planning leaves the calendar untouched. Writes themselves are not atomic;
    # a crash mid-apply is safe because the next run reconciles the remainder.
    creates, updates, deletes = diff_events(desired, existing)

    for event_id in deletes:
        api.delete_event(calendar_id, event_id)
    for event_id, body in updates:
        api.update_event(calendar_id, event_id, body)
    for body in creates:
        api.insert_event(calendar_id, body)

    print(
        f"{start_date} +{days_ahead}d: "
        f"{len(creates)} created, {len(updates)} updated, {len(deletes)} deleted, "
        f"{len(desired)} desired"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GoogleAuthError as exc:
        # Distinct exit code: this one needs a human, a retry will never fix it.
        print(f"AUTH FAILURE: {exc}")
        raise SystemExit(2)
    except (GoogleApiError, CouchError) as exc:
        print(f"TRANSIENT FAILURE: {exc}")
        raise SystemExit(1)
