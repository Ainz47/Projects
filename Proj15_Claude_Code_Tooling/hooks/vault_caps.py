#!/usr/bin/env python
"""vault_caps.py — every vault document cap, in one place, with one classifier.

WHY THIS EXISTS
  Two checks that can disagree, will. Before this module the Map cap was
  written down in three places that had already drifted apart:

    - the /map skill and the partition spec say "~150 lines"
    - inject_state.py refused at 200 lines / 12,000 bytes
    - nothing at all enforced it at write time, which is why
      project-b_current_state.md was written at 171 lines against its own
      150-line cap on 2026-08-21, by an agent that had read the cap minutes
      earlier

  Same lesson as greeting_for() being shared by the render gate and the push:
  the number lives once, and both callers import it.

CAP vs REFUSAL — why map and state carry two line numbers, not one
  They are different actions with different costs, so they get different
  thresholds:

    - CAP (150) is what a write-time block enforces. Blocking a write is cheap
      and fully recoverable: the author trims and writes again.
    - REFUSE_AT (200) is what inject_state uses before dropping a Map from a
      cold session's context. That is not recoverable in the moment -- the
      session simply never learns what the Map said.

  Collapsing them to a single hard 150 was measured on 2026-08-21 and rejected:
  it would have refused project-b_Map.md (153 lines) and project-c_Map.md
  (158), both already partitioned and both believed compliant. A cap that
  punishes the docs which complied with it teaches people to ignore it.

  Bytes get one number per kind. The headroom problem was only ever about
  lines, and inventing a second byte number nobody asked for is how three
  places became three different numbers in the first place.

ENFORCEMENT DIFFERS BY HOW EACH DOC GROWS
  Map and current_state are written WHOLESALE, so the size is knowable before
  the write lands -- they are blocked. A Playbook grows by vault_append, one
  bullet at a time, so its size is only visible on disk afterwards; it is
  NAGGED and never blocked. Refusing a one-line lesson because the file is
  already fat punishes the wrong action and teaches people to stop logging
  lessons at all.

Design: ~/.claude/docs/specs/2026-08-21-vault-caps-backend-design.md (D5)
Tests:  test_vault_caps.py
"""

import collections

Cap = collections.namedtuple("Cap", "kind lines refuse_lines max_bytes action")

CAPS = {
    # kind        lines  refuse_lines  max_bytes  action
    "map":      Cap("map",      150,  200,  12_000, "block"),
    "state":    Cap("state",    150,  200,  20_000, "block"),
    "playbook": Cap("playbook", 400, None,  40_000, "nag"),
    "note":     Cap("note",    None, None,    None, None),
}

# Not a document cap: the budget the GENERATED guardrail index gets inside a
# session-start push. It lives here anyway so that no size number is left
# hiding in a hook. The index yields first under budget pressure, because it is
# the one section that degrades gracefully -- a truncated index still names
# most rules, whereas half a Map is worse than no Map.
INDEX_MAX_BYTES = 12_000

# Eviction takes an over-cap doc to a FRACTION of its cap, not to the cap.
# Stopping at the cap means the very next appended lesson trips it again, and a
# nag that fires every session is one nobody reads -- the doc keeps growing and
# the signal is gone. A ratio rather than a fourth pair of numbers, so the cap
# stays the only place a size is declared: raise the playbook cap and the
# eviction target follows it, which is the whole reason this module exists.
EVICT_TO = 0.75

# Suffix -> kind. Checked against the BASENAME, so a project called `roadmap`
# does not become a Map.
_SUFFIXES = (
    ("_current_state.md", "state"),
    ("_playbook.md", "playbook"),
    ("_map.md", "map"),
)

# Paths whose contents are verbatim copies of some other doc. They are never
# capped: an archive slice is written precisely BECAUSE the live doc was at or
# over its cap, so capping the copy would block the eviction that brings the
# original back under. Memory mirrors are a different schema entirely.
_UNCAPPED_DIRS = ("state_archive/", "memory/")


def _norm(path):
    return (path or "").replace("\\", "/").lower()


def classify(path):
    """Map a vault path to its document kind: map/state/playbook/note.

    `note` is the catch-all AND the uncapped kind, so anything unrecognised
    fails open. A gate that blocks a doc it does not understand would be a new
    way to wedge a session, which is the one thing these hooks must not do.
    """
    p = _norm(path)
    if any(d in p for d in _UNCAPPED_DIRS):
        return "note"
    base = p.rsplit("/", 1)[-1]
    for suffix, kind in _SUFFIXES:
        if base.endswith(suffix):
            return kind
    return "note"


def cap_for(path):
    return CAPS[classify(path)]


def measure(text):
    """Return (lines, bytes) for a document body.

    splitlines(), not count("\\n") + 1: every file in this vault ends with a
    trailing newline, and the naive form counts a phantom empty last line, so a
    150-line file measures 151 and trips its own cap by exactly one. Bytes are
    real utf-8 bytes, not characters -- an em dash is one character and three
    bytes, and a cap denominated in bytes has to mean bytes.
    """
    text = text or ""
    return len(text.splitlines()), len(text.encode("utf-8"))


def _exceeds(cap, text, line_limit, limit_name):
    """Shared body for over_cap/over_refusal. Returns a reason, or None.

    `limit_name` keeps the message honest: 200 lines is the map REFUSAL
    THRESHOLD, not the map cap, and reporting it as the cap would teach the
    reader the wrong number -- the exact drift this module exists to end.
    """
    n_lines, n_bytes = measure(text)
    if line_limit is not None and n_lines > line_limit:
        return "%d lines, over the %s %s of %d" % (
            n_lines, cap.kind, limit_name, line_limit)
    if cap.max_bytes is not None and n_bytes > cap.max_bytes:
        return "%d bytes, over the %s byte cap of %d" % (
            n_bytes, cap.kind, cap.max_bytes)
    return None


def over_cap(path, text):
    """Reason this doc is over its DECLARED cap, or None.

    The measure and the limit are both named on purpose. "Too big" is not
    actionable; "171 lines, over the state cap of 150" tells the author exactly
    how much to cut.
    """
    cap = cap_for(path)
    if cap.lines is None and cap.max_bytes is None:
        return None
    return _exceeds(cap, text, cap.lines, "cap")


def evict_target(path):
    """(lines, bytes) an over-cap doc of this kind must be brought DOWN to.

    Returns the cap's own numbers scaled by EVICT_TO. A kind with no limit in
    that dimension returns a practical infinity rather than None, because every
    caller compares against both numbers and a None would make each one invent
    its own "no limit" -- three places again.
    """
    cap = cap_for(path)
    inf = float("inf")
    return (inf if cap.lines is None else int(cap.lines * EVICT_TO),
            inf if cap.max_bytes is None else int(cap.max_bytes * EVICT_TO))


def over_refusal(path, text):
    """Reason this doc is too big to INJECT into a cold session, or None.

    Only kinds that are injected have a refusal threshold. A Playbook is never
    injected, so giving it one would be a dead number -- and dead numbers are
    what this module exists to stop.
    """
    cap = cap_for(path)
    if cap.action != "block":
        return None
    return _exceeds(cap, text, cap.refuse_lines, "refusal threshold")
