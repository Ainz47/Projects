#!/usr/bin/env python
"""playbook_evict.py — move a Playbook's OLDEST entries into a dated archive.

WHY THIS EXISTS
  A Playbook is the skim-first file for a project: the first thing a cold
  session reads. It grows by append, one lesson at a time, and nothing ever
  takes anything out — so the file that exists to be read first becomes the one
  too big to read. `project-b_Playbook.md` reached 43,951 bytes and
  `project-a_Playbook.md` 123,239 before anything measured them.

  The obvious fixes are all worse:
    - per-entry triage      -> a reading pass on every eviction, and a judgment
                               call about which lessons still matter, made by
                               whoever happens to trip the cap
    - warn but never evict  -> the doc keeps growing past what a session can
                               load; the warning becomes wallpaper
    - truncate on load      -> hides the growth instead of stopping it, and the
                               reader cannot tell what they are not seeing

  So eviction is MECHANICAL: oldest first, verbatim, into a dated slice, with a
  pointer left behind. No entry is edited, summarised or dropped. The only
  decision the code makes is WHICH end of the ledger is old, and it reads that
  off the dates the entries already carry.

WHY 75% AND NOT THE CAP
  Evicting down to the cap itself means the next appended lesson re-trips it,
  and a nag that fires every session is one nobody reads. The target is 75% of
  cap, derived in vault_caps.py -- never a second number written down here.

WHAT THIS MODULE WILL NOT DO
  It does not write to the vault. Every Obsidian write goes through the
  Obsidian MCP (project rule), so this computes the split and stops. The CLI
  writes its two candidate documents to a scratch directory for the caller to
  push. That split is why the whole thing is testable in-process.

Design: ~/.claude/docs/specs/2026-08-21-vault-caps-backend-design.md (D7)
Tests:  test_playbook_evict.py
"""

import collections
import os
import re
import sys

import vault_caps

Entry = collections.namedtuple("Entry", "text index")

_HEADING = re.compile(r"^#{1,6}[ \t]", re.MULTILINE)
_H2 = re.compile(r"^##[ \t]", re.MULTILINE)
_ENTRY_START = re.compile(r"^[-*][ \t]")
# Only a LEADING date dates an entry. Every shape the live Playbooks use is
# here: `- 2026-08-13:`, `- (2026-08-20) DO`, `- 2026-08-19 DON'T:` and
# `- 2026-08-21 (migrated from the Map):`. A date mentioned mid-sentence is a
# fact about the lesson, not a filing date, and reading it as one would
# reorder the ledger by whatever incident a lesson happens to cite.
_LEADING_DATE = re.compile(r"^[ \t]*[-*][ \t]+\(?(\d{4}-\d{2}-\d{2})\)?")

# Sorts after every real date, so an entry nobody can date is evicted LAST.
# Only reachable when a Playbook carries no dates at all; inheritance handles
# every other case.
_UNDATABLE = "9999-12-31"

POINTER_MARK = "<!-- archived-slices -->"


class Block(object):
    """One `## Section` and the entries filed under it.

    `items` is the body as a sequence of ("text", str) and ("entry", Entry)
    pieces IN ORIGINAL DOCUMENT ORDER. A nested subheading (e.g. `### DO`
    inside a dated `## Added ...` section) is a "text" item sitting between
    the entries that surround it, not a blob hoisted to the front -- that
    ordering is what makes reassembly byte-for-byte lossless when nothing is
    evicted, which is the property that makes "eviction never edits anything"
    checkable rather than asserted. Losing it once flattened every nested
    DO/WORKS/FAILED subsection in project-a_Playbook.md into one, silently, on
    every eviction that touched the file -- the bug had no test because no
    existing fixture nested a heading inside a section.
    """

    def __init__(self, heading, items, entries):
        self.heading = heading          # e.g. "## DO"
        self.heading_line = heading + "\n"
        self.items = items
        self.entries = entries

    def render(self, dropped=()):
        out = [self.heading_line]
        for kind, value in self.items:
            if kind == "entry":
                if value.index not in dropped:
                    out.append(value.text)
            else:
                out.append(value)
        return "".join(out)


def parse(content):
    """Split a Playbook into (preamble, [Block, ...]).

    The preamble is everything above the first `## ` heading: frontmatter, H1,
    the ledger's own explanation. It is never evicted -- it is not a lesson,
    and losing the frontmatter would cost the file its tags, which is D8's
    failure with extra steps.
    """
    content = content or ""
    m = _H2.search(content)
    if not m:
        return content, []

    preamble = content[:m.start()]
    blocks, counter = [], [0]

    starts = [x.start() for x in _H2.finditer(content)] + [len(content)]
    for i in range(len(starts) - 1):
        chunk = content[starts[i]:starts[i + 1]]
        head, _, rest = chunk.partition("\n")
        blocks.append(Block(head, *_split_entries(rest, counter)))
    return preamble, blocks


def _split_entries(body, counter):
    """(items, [Entry]) for one section body, in original document order.

    An entry runs from its bullet to the next bullet or heading, INCLUDING the
    blank lines that follow it. Trailing whitespace belongs to the entry above
    it so that removing an entry removes its separator too -- otherwise every
    eviction leaves a widening gap where a lesson used to be.

    A nested heading (e.g. `### DO` inside a dated section) closes whatever
    entry was open and becomes a "text" item IN PLACE, between the entries on
    either side of it -- not pulled out to a separate front-loaded bucket.
    Flattening it that way was the bug: every entry in the section ended up
    rendered after every nested heading, regardless of which subsection it
    actually belonged to.
    """
    lines = body.splitlines(True)
    items, entries, current = [], [], None

    def _flush():
        if current is not None:
            e = Entry("".join(current), counter[0])
            entries.append(e)
            items.append(("entry", e))
            counter[0] += 1

    for line in lines:
        if _ENTRY_START.match(line):
            _flush()
            current = [line]
            continue
        if _HEADING.match(line):
            _flush()
            current = None
            items.append(("text", line))
            continue
        if current is None:
            items.append(("text", line))
        else:
            current.append(line)
    _flush()
    return items, entries


def entry_date(text):
    """The date an entry was filed under, or None."""
    m = _LEADING_DATE.match((text or "").lstrip("\n"))
    return m.group(1) if m else None


def effective_dates(blocks):
    """A date for every entry, in document order, inheriting where absent.

    An undated entry takes the date of the entry it was filed NEXT TO -- the
    one above it, or failing that the one below. That is a fact about where it
    sits, not a guess about its content, and it is the only ranking that does
    not either evict undated lessons first (punishing the entries we know least
    about) or pin them in place forever (rewarding a missing date).
    """
    dates = [entry_date(e.text) for b in blocks for e in b.entries]
    last = None
    for i, d in enumerate(dates):
        if d is None:
            dates[i] = last
        else:
            last = d
    nxt = None
    for i in range(len(dates) - 1, -1, -1):
        if dates[i] is None:
            dates[i] = nxt
        else:
            nxt = dates[i]
    return dates


def _under(text, target_lines, target_bytes):
    n_lines, n_bytes = vault_caps.measure(text)
    return n_lines <= target_lines and n_bytes <= target_bytes


def plan_eviction(content, target_lines, target_bytes, wrap=None):
    """(kept, archived, moved) — the split, computed, not applied.

    `moved` is in EVICTION order (oldest first), because that is the order a
    reader of the report cares about. `archived` keeps document order under
    each heading, because that is the order a reader of the archive cares
    about. They are deliberately different.

    `wrap(text, n_moved)` is anything the caller will ADD to the live doc
    afterwards -- in practice the archive pointer. It is applied before
    measuring, never to the returned text, because a loop that measures
    something other than what will be written does not actually guarantee its
    target. Measured, not theoretical: the first real eviction landed the file
    at 30,017 bytes against a 30,000 target, the pointer being the 17.
    """
    content = content or ""
    preamble, blocks = parse(content)
    if not blocks or _under(content, target_lines, target_bytes):
        return content, "", []
    if wrap is None:
        def wrap(text, n_moved):
            return text

    entries = [e for b in blocks for e in b.entries]
    dates = effective_dates(blocks)

    # Ascending date, then LAST-in-file first. Sections are written newest
    # first, so within one date the entry further down the file is the older
    # of the two -- and when a Playbook carries no dates at all, this degrades
    # to plain bottom-up eviction, which is the same convention.
    order = sorted(range(len(entries)),
                   key=lambda i: (dates[i] or _UNDATABLE, -entries[i].index))

    dropped, moved = set(), []
    for i in order:
        dropped.add(entries[i].index)
        moved.append(entries[i])
        if _under(wrap(_render(preamble, blocks, dropped), len(moved)),
                  target_lines, target_bytes):
            break

    return (_render(preamble, blocks, dropped),
            _archive_body(blocks, dropped), moved)


def _render(preamble, blocks, dropped):
    """Reassemble the live doc. Headings survive even when emptied.

    A `## DO` that loses every entry KEEPS its heading: D9's appender targets
    headings from the H1 down, and a target that does not resolve is exactly
    what produces a duplicate section. Eviction must not manufacture the
    failure the neighbouring check exists to report.
    """
    return preamble + "".join(b.render(dropped) for b in blocks)


def _archive_body(blocks, dropped):
    """The evicted entries, under the headings they came from.

    Sections that lost nothing are omitted. The archive is a record of what
    moved, not a second copy of the document's shape.
    """
    out = []
    for b in blocks:
        taken = [e for e in b.entries if e.index in dropped]
        if not taken:
            continue
        out.append(b.heading_line + "\n" + "".join(e.text for e in taken))
    return "".join(out)


def archive_path(playbook_path, date):
    """Where a slice of this Playbook belongs.

    `State_Archive/**` is tag-exempt in vault_gate and uncapped in vault_caps,
    both on purpose: a slice is written precisely BECAUSE the live doc was over
    cap, so capping the slice would block the step that brings it back under.
    """
    p = (playbook_path or "").replace("\\", "/")
    parent, base = p.rsplit("/", 1) if "/" in p else ("", p)
    project = re.sub(r"_playbook\.md$", "", base, flags=re.IGNORECASE)
    parts = [x for x in (parent, "State_Archive", project) if x]
    return "/".join(parts) + "/Playbook_%s.md" % date


def archive_document(playbook_path, date, body):
    """The slice as it is written: provenance line, then the entries verbatim.

    The header is the only text this module authors. Without it a slice read
    cold is a pile of bullets with no way back to the doc it came from, and an
    archive nobody can trace is indistinguishable from a deletion.
    """
    name = os.path.basename((playbook_path or "").replace("\\", "/"))
    return (
        "# %s — archived %s\n\n"
        "Oldest entries evicted from `%s` on %s to bring it back under its cap.\n"
        "Entries are VERBATIM and in their original sections. Nothing here was\n"
        "judged obsolete — it was judged OLD. If a lesson here still bites, move\n"
        "it back to the live Playbook rather than rewriting it from memory.\n\n"
        "---\n\n%s" % (name, date, name, date, body)
    )


def with_archive_pointer(content, archive_rel_path, n_moved):
    """Leave a pointer to the slice in the live doc's preamble.

    Nothing may read as deleted. The pointer goes ABOVE the first section so a
    reader meets it before the entries, and below the frontmatter so the file
    still starts with `---` at byte 0 -- Obsidian parses frontmatter only
    there, which is the whole of D8.
    """
    content = content or ""
    line = "- `%s` — %d entries\n" % (archive_rel_path, n_moved)

    if POINTER_MARK in content:
        # Append to the block that exists. A second block would be a second
        # place to look, and the point of the pointer is that there is one.
        start = content.index(POINTER_MARK)
        end = content.find("\n\n", start)
        end = len(content) if end == -1 else end
        return content[:end] + "\n" + line.rstrip("\n") + content[end:]

    block = (POINTER_MARK + "\n"
             "**Archived slices** — older entries, moved verbatim, nothing deleted:\n"
             + line + "\n")
    m = _H2.search(content)
    return content[:m.start()] + block + content[m.start():] if m else content + block


# --------------------------------------------------------------------- CLI

def _vault_root():
    return os.environ.get("CLAUDE_VAULT_ROOT") or os.path.join(
        os.path.expanduser("~"), "Documents", "Vault")


def main(argv):
    """Report the split, and optionally stage the two documents for an MCP push.

    Staging rather than writing is not caution, it is the project rule: every
    vault write goes through the Obsidian MCP. A script that wrote the vault
    directly would be the one path where the write gate and the tag gate both
    see nothing.
    """
    if not argv:
        print("usage: playbook_evict.py <vault-relative Playbook path> "
              "[--date YYYY-MM-DD] [--stage DIR]")
        return 2

    rel = argv[0].replace("\\", "/")
    date = argv[argv.index("--date") + 1] if "--date" in argv else None
    if date is None:
        import datetime
        date = datetime.date.today().isoformat()
    stage = argv[argv.index("--stage") + 1] if "--stage" in argv else None

    full = os.path.join(_vault_root(), rel.replace("/", os.sep))
    with open(full, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    t_lines, t_bytes = vault_caps.evict_target(rel)
    before = vault_caps.measure(content)
    arch_rel = archive_path(rel, date)

    # The pointer is part of what lands on disk, so it is part of what the
    # eviction has to fit under -- passed in rather than added afterwards.
    kept, archived, moved = plan_eviction(
        content, t_lines, t_bytes,
        wrap=lambda text, n: with_archive_pointer(text, arch_rel, n))
    if moved:
        kept = with_archive_pointer(kept, arch_rel, len(moved))
    after = vault_caps.measure(kept)

    print("%s\n  before : %d lines / %d bytes" % (rel, before[0], before[1]))
    print("  target : %d lines / %d bytes (75%% of cap)" % (t_lines, t_bytes))
    print("  after  : %d lines / %d bytes" % (after[0], after[1]))
    print("  moved  : %d entries -> %s" % (len(moved), arch_rel))
    for e in moved:
        print("      %s  %s" % (entry_date(e.text) or "  undated ",
                                e.text.strip().splitlines()[0][:96]))

    if stage:
        os.makedirs(stage, exist_ok=True)
        keep_f = os.path.join(stage, os.path.basename(rel))
        arch_f = os.path.join(stage, os.path.basename(arch_rel))
        for path, text in ((keep_f, kept),
                           (arch_f, archive_document(rel, date, archived))):
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(text)
        print("\n  staged for the MCP push:\n    %s\n    %s" % (keep_f, arch_f))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
