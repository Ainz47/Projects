"""Tests for playbook_evict.py -- the D7 eviction split.

Design: ~/.claude/docs/specs/2026-08-21-vault-caps-backend-design.md (D7).

In-process like test_vault_caps.py. Eviction touches no filesystem and no env:
it answers one question about one string. The CLI half that reads and writes
files is deliberately thin for exactly that reason.

The load-bearing property is CONSERVATION. Eviction moves entries; it never
edits, summarises or drops one. Every test below that counts entries or
compares text is guarding that, because the failure mode of a "tidy up the fat
doc" routine is silent loss, and a lessons ledger is the one file where a
silently lost line is never noticed.
"""

import sys

sys.stdout.reconfigure(encoding="utf-8")

import playbook_evict as pe

r = []


def check(label, ok, why=""):
    r.append(bool(ok))
    print("%-4s %s" % ("PASS" if ok else "FAIL", label))
    if not ok and why:
        print("       " + why)


PREAMBLE = """---
tags:
  - lesson
---

# demo - Playbook

Running lessons ledger.

---

"""


def doc(entries_by_section, preamble=PREAMBLE):
    """Build a playbook. entries_by_section: [(heading, [entry line, ...])]."""
    out = [preamble]
    for heading, entries in entries_by_section:
        out.append("## %s\n\n" % heading)
        for e in entries:
            out.append(e.rstrip("\n") + "\n\n")
    return "".join(out)


def bullet(date, text="lesson", pad=0):
    return "- %s: %s%s" % (date, text, " x" * pad)


SIMPLE = doc([
    ("DO", [bullet("2026-08-20", "newest do"),
            bullet("2026-08-10", "oldest do")]),
    ("DON'T", [bullet("2026-08-15", "middle dont")]),
])


# ------------------------------------------------------------------ parsing

pre, blocks = pe.parse(SIMPLE)
check("the preamble is everything above the first section heading",
      pre == PREAMBLE)
check("every canonical section becomes a block", [b.heading for b in blocks] ==
      ["## DO", "## DON'T"])
check("entries are found under their own heading",
      [len(b.entries) for b in blocks] == [2, 1])
check("an entry keeps its raw text", blocks[0].entries[0].text.startswith(
    "- 2026-08-20: newest do"))

check("empty content parses to nothing and never crashes",
      pe.parse("") == ("", []))
check("None content parses to nothing and never crashes",
      pe.parse(None) == ("", []))
check("a playbook with no sections keeps its whole body as preamble",
      pe.parse("# title\n\nprose only\n")[0] == "# title\n\nprose only\n")


# --------------------------------------------------------------- entry dates

check("a colon-form date parses", pe.entry_date("- 2026-08-13: lesson")
      == "2026-08-13")
check("a parenthesised date parses", pe.entry_date("- (2026-08-20) DO a thing")
      == "2026-08-20")
check("a bare date followed by a section word parses",
      pe.entry_date("- 2026-08-19 DON'T: cap the length") == "2026-08-19")
check("a date with a trailing parenthetical parses",
      pe.entry_date("- 2026-08-21 (migrated from the Map): a thing")
      == "2026-08-21")
check("an undated entry has no date", pe.entry_date("- just a lesson") is None)
check("a date later in the line is NOT read as the entry's date",
      pe.entry_date("- a lesson about the 2026-08-19 incident") is None,
      "only a LEADING date dates an entry; a mention is not a filing date")


# ------------------------------------------------------- undated inheritance

UNDATED = doc([
    ("DO", [bullet("2026-08-20", "newest"),
            "- undated, filed next to the 08-20 entry",
            bullet("2026-08-01", "oldest")]),
])
_, ublocks = pe.parse(UNDATED)
dates = pe.effective_dates(ublocks)
check("an undated entry inherits the date of the entry above it",
      dates[1] == "2026-08-20",
      "got %r" % (dates[1],))
check("dated entries keep their own date",
      (dates[0], dates[2]) == ("2026-08-20", "2026-08-01"))

LEADING_UNDATED = doc([("DO", ["- undated first", bullet("2026-08-05")])])
_, lblocks = pe.parse(LEADING_UNDATED)
check("an undated entry with nothing above it inherits from BELOW",
      pe.effective_dates(lblocks)[0] == "2026-08-05",
      "inheriting from context beats an arbitrary rank in either direction")


# ----------------------------------------------------------- the split itself

kept, archived, moved = pe.plan_eviction(SIMPLE, 10_000, 10_000_000)
check("a doc already under target is returned byte-for-byte unchanged",
      kept == SIMPLE, "eviction must be a no-op when nothing is over")
check("an under-target doc archives nothing", archived == "" and moved == [])

kept, archived, moved = pe.plan_eviction(SIMPLE, 0, 0)
check("an unreachable target still leaves every heading standing",
      "## DO" in kept and "## DON'T" in kept,
      "D9's appender targets headings that must exist")
check("an unreachable target evicts every entry but stops there",
      len(moved) == 3 and not any(
          t in kept for t in ("newest do", "oldest do", "middle dont")))

# One entry has to go, and it must be the oldest one in the DOCUMENT, not the
# last one in the file -- sections are newest-first, so file order is not age
# order once there is more than one section.
target_bytes = len(SIMPLE.encode("utf-8")) - 10
kept, archived, moved = pe.plan_eviction(SIMPLE, 10_000, target_bytes)
check("the oldest entry is the one that moves",
      len(moved) == 1 and "oldest do" in moved[0].text,
      "moved: %r" % ([m.text for m in moved],))
check("the newest entries stay", "newest do" in kept and "middle dont" in kept)
check("the evicted entry is gone from the live doc",
      "oldest do" not in kept)
check("the evicted entry is in the archive VERBATIM",
      "- 2026-08-10: oldest do" in archived)
check("the archive files it under the heading it came from",
      archived.index("## DO") < archived.index("oldest do"))
check("a section that lost every entry is NOT written to the archive",
      "## DON'T" not in archived,
      "the archive is a record of what moved, not a copy of the structure")

check("eviction stops as soon as the doc is under target, not one entry later",
      len(pe.plan_eviction(SIMPLE, 10_000, target_bytes)[2]) == 1)


# ------------------------------------------------------------- conservation

BIG = doc([
    ("DO", [bullet("2026-08-%02d" % d, "do %d" % d, pad=40)
            for d in (21, 19, 17, 15, 13, 11, 9, 7, 5, 3)]),
    ("DON'T", [bullet("2026-08-%02d" % d, "dont %d" % d, pad=40)
               for d in (20, 18, 16, 14, 12, 10, 8, 6, 4, 2)]),
    ("WORKS", []),
    ("FAILED", [bullet("2026-07-30", "ancient", pad=40)]),
])
_, all_blocks = pe.parse(BIG)
n_before = sum(len(b.entries) for b in all_blocks)
kept, archived, moved = pe.plan_eviction(BIG, 10_000, 2_000)

_, kept_blocks = pe.parse(kept)
n_after = sum(len(b.entries) for b in kept_blocks)
check("no entry is lost: kept + moved == original",
      n_after + len(moved) == n_before,
      "%d + %d != %d" % (n_after, len(moved), n_before))
check("the eviction reaches its target",
      len(kept.encode("utf-8")) <= 2_000,
      "%d bytes" % len(kept.encode("utf-8")))
check("the very oldest entry in the doc goes first",
      "ancient" in moved[0].text)
check("what moved is exactly what left, in the same words",
      all(m.text.strip() in archived for m in moved))
check("an empty section survives with its heading",
      "## WORKS" in kept)
check("a section emptied BY the eviction keeps its heading too",
      all(h in kept for h in ("## DO", "## DON'T", "## FAILED")))

# What lands on disk is kept PLUS the archive pointer. A loop that measures
# only `kept` promises a target it does not deliver -- the first real eviction
# landed at 30,017 bytes against 30,000, and the 17 was the pointer.
def _wrap(text, n):
    return text + "-" * 400


w_kept, _, w_moved = pe.plan_eviction(BIG, 10_000, 2_000, wrap=_wrap)
check("what the caller will ADD counts toward the target",
      len(_wrap(w_kept, len(w_moved)).encode("utf-8")) <= 2_000,
      "%d bytes with the addition" % len(_wrap(w_kept, len(w_moved)).encode("utf-8")))
check("the addition is measured, never returned",
      "-" * 400 not in w_kept,
      "wrap describes what the caller does next; it must not do it for them")
check("accounting for the addition evicts more, not less",
      len(w_moved) > len(pe.plan_eviction(BIG, 10_000, 2_000)[2]))

check("the line target can trigger eviction on its own",
      len(pe.plan_eviction(BIG, 12, 10_000_000)[2]) > 0,
      "a doc can be line-fat and byte-thin; either trips the cap")


# --------------------------------------------- duplicates are NOT consolidated

DUPES = doc([
    ("DO", [bullet("2026-08-20", "first do")]),
    ("DON'T", [bullet("2026-08-19", "a dont")]),
    ("DO", [bullet("2026-08-18", "second do")]),
])
kept, _, _ = pe.plan_eviction(DUPES, 10_000, 10_000_000)
check("a duplicate heading is left exactly where it was",
      len([l for l in kept.splitlines() if l.strip() == "## DO"]) == 2,
      "consolidating duplicates is audit work and out of D7's scope")


# ------------------------------------------------------------- the pointer

pointed = pe.with_archive_pointer(SIMPLE, "State_Archive/demo/Playbook_2026-08-22.md", 7)
check("the pointer names the archive slice",
      "State_Archive/demo/Playbook_2026-08-22.md" in pointed)
check("the pointer says how many entries moved", "7" in pointed)
check("the pointer sits in the preamble, above the first section",
      pointed.index("State_Archive/demo") < pointed.index("## DO"),
      "a reader hits it before the entries, or it is not a pointer")
check("the pointer leaves the frontmatter at byte 0",
      pointed.startswith("---\ntags:"),
      "Obsidian parses frontmatter ONLY at byte 0 -- D8's whole lesson")
check("a second eviction does not stack a second pointer block",
      pe.with_archive_pointer(pointed, "State_Archive/demo/Playbook_2026-08-23.md",
                              3).count(pe.POINTER_MARK) == 1)
check("the second pointer still names both slices",
      "Playbook_2026-08-22.md" in pe.with_archive_pointer(
          pointed, "State_Archive/demo/Playbook_2026-08-23.md", 3)
      and "Playbook_2026-08-23.md" in pe.with_archive_pointer(
          pointed, "State_Archive/demo/Playbook_2026-08-23.md", 3),
      "an archive that stops being reachable is a deletion with extra steps")


# ------------------------------------------------------- nested subheadings
#
# Every dated "## Added YYYY-MM-DD (session N, ...)" block in the live project-a
# and project-b playbooks nests its own "### DO" / "### WORKS" / "### FAILED"
# subheadings, each followed by that subsection's bullets. No fixture above
# builds that shape, which is exactly why a real bug here (every entry in the
# section rendered AFTER every nested heading, regardless of which subsection
# it belonged to) shipped undetected through six live project-a sessions.

NESTED = (
    PREAMBLE
    + "## Added 2026-08-27 (session 6)\n\n"
    "### DO\n\n"
    + bullet("2026-08-27", "do lesson") + "\n\n"
    "### WORKS\n\n"
    + bullet("2026-08-27", "works lesson") + "\n\n"
    "### FAILED\n\n"
    + bullet("2026-08-27", "failed lesson") + "\n\n"
)

check("a doc with nested subheadings round-trips byte-for-byte when nothing moves",
      pe.plan_eviction(NESTED, 10_000, 10_000_000)[0] == NESTED,
      "a nested ### heading must not be hoisted in front of every entry in "
      "its ## section")

_, nested_blocks = pe.parse(NESTED)
nested_kept = pe.plan_eviction(NESTED, 10_000, 10_000_000)[0]
do_pos = nested_kept.index("### DO")
works_pos = nested_kept.index("### WORKS")
failed_pos = nested_kept.index("### FAILED")
do_lesson_pos = nested_kept.index("do lesson")
works_lesson_pos = nested_kept.index("works lesson")
failed_lesson_pos = nested_kept.index("failed lesson")
check("each entry stays directly under ITS OWN nested subheading, not the last one",
      do_pos < do_lesson_pos < works_pos < works_lesson_pos < failed_pos < failed_lesson_pos,
      "got DO@%d do-lesson@%d WORKS@%d works-lesson@%d FAILED@%d failed-lesson@%d"
      % (do_pos, do_lesson_pos, works_pos, works_lesson_pos, failed_pos, failed_lesson_pos))


# ---------------------------------------------------------------- destinations

check("the archive path is derived from the playbook path",
      pe.archive_path("50_Carreer/Dev_Sessions/project-b_Playbook.md",
                      "2026-08-22")
      == "50_Carreer/Dev_Sessions/State_Archive/project-b/Playbook_2026-08-22.md")
check("a backslash playbook path still derives a forward-slash archive path",
      "\\" not in pe.archive_path(
          r"50_Carreer\Dev_Sessions\demo_Playbook.md", "2026-08-22"))
check("the derived archive path is itself uncapped",
      __import__("vault_caps").classify(
          pe.archive_path("50_Carreer/Dev_Sessions/x_Playbook.md", "2026-08-22")
      ) == "note",
      "if the archive were capped, eviction could never write its own output")

check("the archive slice carries provenance, not just entries",
      "project-b_Playbook.md" in pe.archive_document(
          "50_Carreer/Dev_Sessions/project-b_Playbook.md", "2026-08-22",
          "## DO\n\n- 2026-01-01: x\n"))


print("\n%d/%d passed" % (sum(r), len(r)))
sys.exit(0 if all(r) else 1)
