"""Pure planning logic for the calendar sync.

No I/O lives here on purpose. build_events turns reference data into the event
set that *should* exist; diff_events compares that against what does exist.
Keeping both pure is what makes the idempotency property directly testable.
"""
import datetime
import zoneinfo

DOW = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# Monday and Wednesday are written as branch A, the class-attending version.
# It is the more constrained day, so a spare reminder costs less than a missing one.
DEFAULT_BRANCH = "A"


def schedule_key(date_str, block_id):
    """The idempotency key carried on every event as a private property."""
    return f"{date_str}:{block_id}"


def blocks_for(template, dow, branch):
    """Return the active block list for a weekday, resolving MW branching."""
    day = template["days"][dow]
    if day.get("branching"):
        return day["branches"][branch or DEFAULT_BRANCH]
    return day["blocks"]


def _tombstone(entry):
    """A snapshot entry whose id the template no longer has.

    It keeps its interval so the day is still a partition, and resolves inert:
    no calendar event, no attribute, no task. The JS twin is in src/schedule.js.
    """
    return {
        "id": entry["id"],
        "label": "Removed",
        "detail": "",
        "attribute": None,
        "start": entry["start"],
        "end": entry["end"],
        "hours": entry["hours"],
        "kind": "fixed",
        "taskId": None,
        "campaignSlot": False,
        "streakId": None,
        "calendar": {"event": False, "remindMinutes": 10},
        "tombstone": True,
    }


def resolve_blocks(template, dow, branch, day_doc):
    """The block list a date actually ran, folding in any per-date override.

    The override is a structural snapshot: times and the block set are frozen
    on the day document, while label, detail, attribute, taskId, streakId,
    campaignSlot and calendar keep resolving live from the template by block
    id. Ids are globally unique, so the lookup spans every list rather than
    just this weekday's, and an override taken before a branch flip still
    resolves. blocks_for is left alone: the vault note's Template section is a
    picture of the weekly pattern and wants exactly that.
    """
    entries = (day_doc or {}).get("blocksOverride")
    if not entries:
        return blocks_for(template, dow, branch)

    by_id = {}
    for day in template["days"].values():
        lists = day["branches"].values() if day.get("branching") else [day["blocks"]]
        for blocks in lists:
            for block in blocks:
                by_id[block["id"]] = block

    out = []
    for entry in entries:
        base = entry.get("fields") or by_id.get(entry["id"])
        if base is None:
            out.append(_tombstone(entry))
            continue
        block = dict(base)
        block.update({
            "id": entry["id"], "start": entry["start"],
            "end": entry["end"], "hours": entry["hours"],
        })
        out.append(block)
    return out


def build_events(template, day_docs, start_date, days_ahead, timezone):
    """Build the desired Google Calendar event bodies for the window.

    day_docs maps "YYYY-MM-DD" to that day's CouchDB document. A missing
    document, or one whose branch is null, leaves a branching day on branch A.
    """
    default_remind = template["calendar"]["defaultRemindMinutes"]
    events = []

    for offset in range(days_ahead):
        date = start_date + datetime.timedelta(days=offset)
        date_str = date.isoformat()
        dow = DOW[date.weekday()]
        branch = (day_docs.get(date_str) or {}).get("branch")

        for block in resolve_blocks(template, dow, branch, day_docs.get(date_str)):
            calendar = block.get("calendar") or {}
            if not calendar.get("event"):
                continue
            minutes = calendar.get("remindMinutes", default_remind)
            events.append({
                "summary": block["label"],
                "description": block.get("detail") or "",
                "start": {
                    "dateTime": f"{date_str}T{block['start']}:00",
                    "timeZone": timezone,
                },
                "end": {
                    "dateTime": f"{date_str}T{block['end']}:00",
                    "timeZone": timezone,
                },
                "reminders": {
                    "useDefault": False,
                    "overrides": [{"method": "popup", "minutes": minutes}],
                },
                "extendedProperties": {
                    "private": {"scheduleKey": schedule_key(date_str, block["id"])}
                },
            })

    events.sort(key=lambda e: e["extendedProperties"]["private"]["scheduleKey"])
    return events


def key_of(event):
    """Read the scheduleKey off an event, or None if it is not one of ours."""
    private = (event.get("extendedProperties") or {}).get("private") or {}
    return private.get("scheduleKey")


def _instant(bound):
    """Normalise a start/end block to the instant it denotes.

    The API does not echo back what we send. We write a naive local time plus
    a timeZone; Google stores that and returns the same moment with the zone's
    UTC offset appended, so "07:30:00" comes back as "07:30:00+08:00". Comparing
    those strings marks every event as changed on every run. Comparing the
    instants they denote does not, while still catching a genuine reschedule.
    """
    if not bound:
        return None
    zone = bound.get("timeZone")
    raw = bound.get("dateTime")
    if raw is None:
        # All-day events carry `date` instead. We never write these, but an
        # existing one must compare as different rather than blow up.
        return ("date", bound.get("date"), zone)
    moment = datetime.datetime.fromisoformat(raw)
    if moment.tzinfo is None and zone:
        moment = moment.replace(tzinfo=zoneinfo.ZoneInfo(zone))
    return ("dateTime", moment, zone)


def _comparable(event):
    """The fields we own, normalised so only real edits register as changes.

    Anything else on an existing event (id, etag, iCalUID, created, updated,
    organizer...) is Google's and must not trigger an update.
    """
    return {
        "summary": event.get("summary"),
        # Google omits description entirely rather than storing "", so a
        # detail-less block would otherwise differ forever.
        "description": event.get("description") or "",
        "start": _instant(event.get("start")),
        "end": _instant(event.get("end")),
        "reminders": event.get("reminders"),
    }


def diff_events(desired, existing):
    """Compare the desired event set against what the calendar already holds.

    Matching is by scheduleKey alone, which is what makes repeated runs safe:
    an event is identified by the day and block it represents, never by its
    Google id. Events without a scheduleKey were not written by us and are
    ignored entirely, so a hand-made entry on the Schedule calendar survives.
    """
    desired_by_key = {key_of(e): e for e in desired}
    existing_by_key = {}
    for event in existing:
        key = key_of(event)
        if key is not None:
            existing_by_key[key] = event

    to_create = [
        desired_by_key[k] for k in sorted(desired_by_key.keys() - existing_by_key.keys())
    ]
    to_delete = [
        existing_by_key[k]["id"]
        for k in sorted(existing_by_key.keys() - desired_by_key.keys())
    ]
    to_update = []
    for key in sorted(desired_by_key.keys() & existing_by_key.keys()):
        want, have = desired_by_key[key], existing_by_key[key]
        if _comparable(want) != _comparable(have):
            to_update.append((have["id"], want))

    return to_create, to_update, to_delete
