#!/usr/bin/env python
"""vault_gate.py — Stop hook. Prevents documentation drift in the Obsidian vault.

WHY THIS EXISTS
  Two conventions were written down and then never applied, because applying
  them depended on the agent remembering unprompted:
    - `_Tag_Dictionary.md` was created ~2026-08-13 defining a controlled tag
      vocabulary for frontmatter. As of 2026-08-15 it had been applied to ZERO
      session notes written since.
    - `/map` was flagged as needed on 2026-08-15, said out loud, then skipped
      at session end.
  Meanwhile `done_gate.py` — the one convention wired into a hook — has never
  been skipped, because the harness enforces it rather than the agent's memory.
  This hook applies that same mechanism to the vault.

WHAT IT CHECKS (both only fire when the session actually did the thing)
  1. TAGS: any vault_write to 50_Carreer/Dev_Sessions/ must include YAML
     frontmatter with a `tags:` key. Blocks if not.
  2. MAP: if the session made git commits (a real change in project shape) and
     wrote a session note but never touched <Project>_Map.md, remind to /map.
  3. PLAYBOOK SECTIONS: if the session appended to a <Project>_Playbook.md,
     report it carrying the same canonical section twice. Read from DISK, not
     from the transcript -- an append's content is one bullet, so the file's
     real shape is only ever visible on disk.
  4. PLAYBOOK SIZE: same disk read, same scope. Over its cap it is REPORTED
     with its archive destination, never blocked -- see the caps module on why
     size enforcement splits by how a document grows.

  Plus one PreToolUse check, not a Stop check: an over-cap Map or current_state
  write is refused before it lands (check_write_size).

DELIBERATE EXCLUSIONS — writing these without tags is CORRECT, not a violation:
  - State_Archive/**  : verbatim copies of previous snapshots. The archive step
                        must reproduce the outgoing file byte-for-byte; adding
                        frontmatter it never had would corrupt the archive.
  - Memory/**         : auto-memory mirrors use a different frontmatter schema
                        (name/description/metadata.type), not `tags:`.
  - _Tag_Dictionary, _Projects_Index : index/reference files, not notes.

Nags once per session via a sentinel, same as done_gate.py, so a blocked stop
never turns into a loop.

Tests: test_vault_gate.py, which redirects the vault with CLAUDE_VAULT_ROOT.
"""
import collections
import datetime
import json
import os
import re
import sys
import time
import traceback

import playbook_evict
import vault_caps

# CLAUDE_VAULT_ROOT exists so the tests can point this hook at a throwaway
# vault. Production leaves it unset. Without it the only way to exercise
# current_file_has_tags() -- the check that reads the note as it stands on disk
# NOW -- was to pin a real note as a fixture, so the strict half of that check
# (written tagged, broken on disk since) had no test at all.
VAULT_ROOT = os.environ.get("CLAUDE_VAULT_ROOT") or os.path.join(
    os.path.expanduser("~"), "Documents", "Vault"
)

# Where the nag-once sentinels live. Env-overridable for exactly the reason
# CLAUDE_VAULT_ROOT is: a path derived from __file__ can only be exercised by
# writing into the real ~/.claude, so nothing ever watched this directory --
# which is how 367 sentinels accumulated there unnoticed by 2026-08-22.
STATE_DIR = os.environ.get("CLAUDE_STATE_DIR") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
SENTINEL_PREFIX = ".vault_gate_"
# How long a sentinel is kept: long enough that no session in flight is ever
# re-armed, short enough that the directory stays bounded. Deliberately NOT in
# vault_caps.py -- that module owns document SIZES, and putting an unrelated
# number there to look tidy would make "one cap per kind" mean less, not more.
SENTINEL_TTL_DAYS = 7

VAULT_NOTE_DIR = "50_carreer/dev_sessions"
EXCLUDED = ("state_archive/", "memory/", "_tag_dictionary", "_projects_index")
WRITE_TOOLS = ("mcp__obsidian__vault_write",)
# EVERY tool that can change a vault document, not just the wholesale write.
# A Playbook grows by append and patch far more often than by write, so
# watching vault_write alone would watch the RAREST of the three paths that
# create a duplicate section -- and the same is true of size: a Map is
# maintained by in-place edits (skills/project-map/SKILL.md prescribes exactly
# that), so the write-time block sees the one path authors are told NOT to
# take. The Stop half watches all three.
VAULT_EDIT_TOOLS = WRITE_TOOLS + ("mcp__obsidian__vault_append",
                                  "mcp__obsidian__vault_patch")


def norm(p):
    return (p or "").replace("\\", "/").lower()


def is_gated_note(path):
    p = norm(path)
    if VAULT_NOTE_DIR not in p:
        return False
    return not any(x in p for x in EXCLUDED)


def tags_state(content):
    """Classify a note's `tags:` frontmatter: 'ok', 'missing', 'mistyped' or 'offset'.

    'mistyped' exists because of a real incident on 2026-08-15. Writing tags
    via vault_patch with a `value` array serialises them as a QUOTED STRING:

        tags: '["status-change", "supply", "decision"]'

    vault_read returns that value happily, so it looks correct -- but Obsidian
    never parses it as tags, the metadata cache stays empty, and a search on
    tags.length > 0 finds nothing. The convention is then enforced in letter
    while silently not working, which is worse than no tags at all: it looks
    done. Presence alone is NOT a sufficient check.

    Valid: a block list (`tags:` then `  - item` lines) or an unquoted flow
    list (`tags: [a, b]`). Invalid: any quoted scalar.
    """
    if not content:
        return "missing"
    if not content.startswith("---"):
        # Obsidian parses frontmatter ONLY at byte 0. A block starting on
        # line 2 is ignored outright, so the note reads correctly under
        # `cat`, vault_patch reports OK, and no tag query ever returns it.
        # The old code did content.lstrip().startswith("---") and called
        # that `ok` -- the convention enforced in letter while silently not
        # working, which is the exact failure `mistyped` was written to
        # catch, reappearing one line above it. `offset` is its own state
        # because reporting it as `missing` sends the author off to add
        # tags that are already sitting right there.
        return "offset" if content.lstrip().startswith("---") else "missing"
    body = content[3:]
    end = body.find("\n---")
    if end == -1:
        return "missing"
    fm = body[:end]

    m = re.search(r"^\s*tags\s*:(.*)$", fm, re.MULTILINE)
    if not m:
        return "missing"

    rest = m.group(1).strip()
    if rest.startswith(("'", '"')):
        return "mistyped"          # a quoted scalar -- the 08-15 bug
    if rest.startswith("["):
        return "ok" if rest.rstrip().endswith("]") else "mistyped"
    if rest:
        return "mistyped"          # a bare scalar, e.g. `tags: supply`
    # Nothing on the line: expect a block list beneath it.
    after = fm[m.end():]
    return "ok" if re.search(r"^\s*-\s+\S", after, re.MULTILINE) else "missing"


def has_tags_frontmatter(content):
    return tags_state(content) == "ok"


def current_file_has_tags(vault_rel_path):
    """Check the note as it stands on disk NOW, not as first written.

    The transcript records the content of the original write forever, but a
    note is often tagged in a follow-up `vault_patch` (a different tool this
    hook does not watch). Judging on transcript content alone would flag a
    problem that has already been fixed -- and a gate that cannot see a fix
    teaches people to dismiss it, which is exactly how the done_gate's
    authority would erode. Falls back to the transcript when the file cannot
    be read, so a moved vault degrades to the old behaviour rather than
    silently passing everything.
    """
    full = os.path.join(VAULT_ROOT, vault_rel_path.replace("/", os.sep))
    if not os.path.exists(full):
        return None  # unknown; caller falls back to the written content
    try:
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            return tags_state(f.read(4096))
    except OSError:
        return None


# The four sections every Playbook is built from -- `kickoff` creates them empty
# and every lesson is appended under one of them. A Playbook holding two of any
# one of these has been appended to WRONGLY, not richly.
CANONICAL_SECTIONS = ("DO", "DON'T", "WORKS", "FAILED")

_H1 = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_H2 = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
# A trailing parenthetical is stripped before matching, because the duplicates
# in the live vault are overwhelmingly DATED rather than bare: seven distinct
# `## DON'T (2026-08-05, tooling session)`-shaped headings on 2026-08-22 against
# a handful of plain repeats. Matching the literal string `## DO` would report
# the minority and call the file clean.
_TRAILING_PAREN = re.compile(r"\s*\([^()]*\)\s*$")


def canonical_section(heading):
    """Normalise an H2's text to one of CANONICAL_SECTIONS, or None."""
    name = _TRAILING_PAREN.sub("", (heading or "").strip()).strip().upper()
    return name if name in CANONICAL_SECTIONS else None


def duplicate_sections(content):
    """Canonical section names appearing more than once, in canonical order."""
    counts = collections.Counter(
        c for c in (canonical_section(m.group(1))
                    for m in _H2.finditer(content or "")) if c
    )
    return [n for n in CANONICAL_SECTIONS if counts[n] > 1]


def first_h1(content):
    """The text of the document's first H1, or None if it has none.

    Not decoration. `vault_patch` addresses a heading target from the top-level
    heading DOWN, so whether an H1 exists decides whether the correct target is
    ["<H1 text>", "DO"] or the bare ["DO"]. Three of the seven Playbooks in the
    vault on 2026-08-22 had no H1 at all -- the same three D8 caught with offset
    frontmatter, and for the same underlying reason: the file begins with a
    blank line. Naming only the H1 form to those sends the author hunting for a
    heading that does not exist, which is how the wrong target gets used.
    """
    m = _H1.search(content or "")
    return m.group(1) if m else None


def read_vault_file(vault_rel_path):
    """Whole file from the vault, or None if it cannot be read."""
    full = os.path.join(VAULT_ROOT, vault_rel_path.replace("/", os.sep))
    try:
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def playbook_section_report(path, content, dupes):
    """Name the duplicated sections AND the target form that stops them.

    "You have duplicates" is not actionable -- the author's next move is to
    guess, and the guess that made them is appending another section. The
    report therefore carries the exact target string for THIS file.
    """
    name = os.path.basename(path.replace(chr(92), "/"))
    h1 = first_h1(content)
    if h1:
        target = '["%s", "DO"]' % h1
        where = "Its H1 is `# %s`." % h1
    else:
        target = '["DO"]'
        where = ("This file has no H1, so a section IS the top level -- the "
                 "bare form above is correct here.")
    return (
        "[vault-gate] %s carries a duplicate canonical section: %s.\n"
        "  Each of ## DO / ## DON'T / ## WORKS / ## FAILED must appear exactly once.\n"
        "  A duplicate is not untidiness -- it is the FOOTPRINT of a failed heading\n"
        "  resolve. vault_patch addresses a heading target from the top-level heading\n"
        "  DOWN, so a bare target fails on a doc that has an H1, and the natural\n"
        "  fallback is appending a fresh `## DO`. That is the mechanism behind 109\n"
        "  duplicate sections in project-a_Playbook.md.\n"
        "  Correct target for this file: %s\n"
        "  %s\n"
        "  If a target does not resolve, GO FIND the real heading and retry --\n"
        "  never append a new section. Consolidating pre-existing duplicates is\n"
        "  audit work and out of scope: fix your own append, say so, and finish."
        % (name, ", ".join("## " + d for d in dupes), target, where)
    )


def playbook_size_report(path, over_reason, today=None):
    """Name the archive destination and the target, not just the excess.

    Deliberately a REPORT and never a block. The append that tips a Playbook
    over its cap is the one action in this file that is always correct -- it is
    a lesson being written down. Refusing it punishes the logging and leaves the
    bloat, which is how a ledger stops being kept at all.

    The destination is computed rather than described because a nag that ends
    at "it's too big" hands the reader the same decision that produced a 123KB
    Playbook: they guess, and the cheapest guess is to delete something.
    """
    date = today or datetime.date.today().isoformat()
    name = os.path.basename(path.replace(chr(92), "/"))
    t_lines, t_bytes = vault_caps.evict_target(path)
    return (
        "[vault-gate] %s is %s.\n"
        "  This is a report, not a refusal — the append that got you here was the\n"
        "  right action. Evict the OLDEST entries, VERBATIM, into:\n"
        "      %s\n"
        "  until the live file is at or under %d lines / %d bytes (75%% of cap;\n"
        "  stopping AT the cap means the next lesson logged re-trips this).\n"
        "  Plan the split — it writes nothing:\n"
        "      py ~/.claude/hooks/playbook_evict.py \"%s\" --stage <scratch dir>\n"
        "  then push both documents with the Obsidian MCP (vault_write; the\n"
        "  slice is a subset, so vault_copy cannot make it).\n"
        "  No triage and no summarising: oldest first, moved whole, sections keep\n"
        "  their headings even when emptied. Nothing is deleted, and the live file\n"
        "  keeps a pointer to the slice."
        % (name, over_reason, playbook_evict.archive_path(path, date),
           t_lines, t_bytes, path.replace(chr(92), "/"))
    )


def scan_transcript(path):
    """Walk the session transcript for the facts the two checks need."""
    untagged, tagged, map_written, committed = [], False, False, False
    playbooks, capped = [], []
    if not path or not os.path.exists(path):
        return untagged, tagged, map_written, committed, playbooks, capped

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            msg = rec.get("message") or {}
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                name = block.get("name", "")
                inp = block.get("input") or {}

                if name == "Bash" and "git commit" in (inp.get("command") or ""):
                    committed = True

                # Checked BEFORE the WRITE_TOOLS gate: append and patch are
                # not write tools, and they are how a Playbook actually grows.
                if name in VAULT_EDIT_TOOLS:
                    kind = vault_caps.classify(inp.get("path", ""))
                    if kind == "playbook":
                        playbooks.append(inp.get("path", ""))
                    # A Map or current_state grown by patch or append is not
                    # measurable at the door either -- its payload is a
                    # fragment, not the finished document -- so it is measured
                    # here, from disk, exactly like a Playbook. Without this
                    # the ONLY watched path was the wholesale write, while
                    # skills/project-map/SKILL.md prescribes "In-place edits
                    # over full rewrites": following the skill correctly was
                    # what evaded the cap.
                    elif vault_caps.CAPS[kind].action == "block":
                        capped.append(inp.get("path", ""))

                if name not in WRITE_TOOLS:
                    continue
                target = inp.get("path", "")
                if "_map.md" in norm(target):
                    map_written = True
                if not is_gated_note(target):
                    continue
                state = current_file_has_tags(target)
                if state is None:
                    state = tags_state(inp.get("content", ""))
                if state == "ok":
                    tagged = True
                else:
                    untagged.append((target, state))

    return untagged, tagged, map_written, committed, playbooks, capped


# Where over-cap content actually GOES. A block that only says "too big" is not
# actionable -- the author's next move is to guess, and guessing is what put a
# 171-line body in a 150-line current_state on 2026-08-21. Each kind names its
# own destinations because they genuinely differ: a Map sheds RULES, a state
# file sheds HISTORY, and telling either one to "trim" invites deletion of the
# thing that mattered.
DESTINATIONS = {
    "map": (
        "A Map is a POINTER INDEX. MOVE this content, do not delete it:\n"
        "  - a rule or constraint  -> Guardrails/<Project>/<slug>.md, one rule per note\n"
        "  - a lesson learned      -> <Project>_Playbook.md\n"
        "  - counts, supply, status-> the repo's own STATUS.md / CLAUDE.md\n"
        "  - the pre-split copy    -> State_Archive/<Project>/ via vault_copy"
    ),
    "state": (
        "A current_state file is a HANDOFF, not a history. MOVE this content:\n"
        "  - the outgoing snapshot -> State_Archive/<Project>/ via vault_copy\n"
        "                             (copy it; never retype it, never vault_move)\n"
        "  - closed / parked tracks-> Guardrails/<Project>/<slug>.md, tagged `closed`\n"
        "  - what happened when    -> the dated YYYY-MM-DD-<Project>.md log"
    ),
}


def check_write_size(tool_name, tool_input):
    """PreToolUse: refuse an over-cap Map or current_state BEFORE it lands.

    Only vault_write, and only the kinds vault_caps marks `block`. A wholesale
    write is the one moment the document's final size is knowable, which is
    what makes refusing it fair: the author trims and writes again, losing
    nothing. vault_append adds a single bullet to a file whose size lives on
    disk, so blocking there would punish the lesson rather than the bloat --
    that path is nagged by the Stop half of this hook instead.

    Returns a reason string, or None to allow. Anything unmeasurable returns
    None: a gate that cannot read the payload must let it through, never guess.
    """
    if tool_name not in WRITE_TOOLS:
        return None
    path = tool_input.get("path") or ""
    content = tool_input.get("content")
    if not isinstance(content, str):
        return None
    if vault_caps.cap_for(path).action != "block":
        return None
    reason = vault_caps.over_cap(path, content)
    if not reason:
        return None
    return (
        "[vault-gate] Refusing this write: %s is %s.\n\n%s\n\n"
        "The caps live in ~/.claude/hooks/vault_caps.py. Re-write it under the "
        "cap -- do not raise the number, and do not truncate the tail to fit."
        % (os.path.basename(path.replace("\\", "/")), reason,
           DESTINATIONS[vault_caps.classify(path)])
    )


def sweep_sentinels(now=None):
    """Delete nag-once sentinels past their TTL.

    Prefix match on the BASENAME, never a glob over the directory: this runs
    inside ~/.claude, where a sweep loose enough to catch settings.json would
    be a far worse bug than the litter it cleans. Every failure is swallowed
    for the same reason the sentinel write is best-effort -- housekeeping must
    never become the thing that wedges a session.
    """
    cutoff = (time.time() if now is None else now) - SENTINEL_TTL_DAYS * 86400
    try:
        names = os.listdir(STATE_DIR)
    except OSError:
        return
    for name in names:
        if not name.startswith(SENTINEL_PREFIX):
            continue
        full = os.path.join(STATE_DIR, name)
        try:
            if os.path.getmtime(full) < cutoff:
                os.remove(full)
        except OSError:
            pass


def capped_size_report(path, reason):
    """Stop-side nag for a Map or current_state that grew past its cap.

    Shares DESTINATIONS with the write-time block on purpose: the author gets
    the same instruction in the same words whichever path they took to get
    here. Only the verb differs -- by the time this runs the write has already
    landed, so it reports where the other one refuses.
    """
    return (
        "[vault-gate] %s is %s.\n\nIt grew by an IN-PLACE EDIT, which the "
        "write-time block never sees: a patch or append payload is a fragment, "
        "not the finished document, so the real size only exists on disk.\n\n"
        "%s\n\nThe caps live in ~/.claude/hooks/vault_caps.py -- do not raise "
        "the number, and do not truncate the tail to fit."
        % (os.path.basename(path.replace("\\", "/")), reason,
           DESTINATIONS[vault_caps.classify(path)])
    )


def block(reason):
    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(0)


def main():
    payload = json.load(sys.stdin)

    # One script, two events. PreToolUse payloads carry `tool_name`; Stop
    # payloads never do, so the shape is the dispatch. Both halves live here on
    # purpose -- they enforce the same conventions, and splitting them is how
    # one cap ended up written down in three places that had already drifted.
    if "tool_name" in payload:
        reason = check_write_size(payload.get("tool_name", ""),
                                  payload.get("tool_input") or {})
        if reason:
            # PreToolUse blocks with exit 2 + stderr. The Stop half's
            # {"decision": "block"} on stdout is a DIFFERENT mechanism and is
            # silently ignored here -- using it would look like a working gate
            # that never actually stopped anything.
            sys.stderr.write(reason + "\n")
            sys.exit(2)
        sys.exit(0)

    if payload.get("stop_hook_active"):
        sys.exit(0)  # already inside a stop-hook continuation; never double-block

    session_id = payload.get("session_id", "unknown")
    sweep_sentinels()
    sentinel = os.path.join(STATE_DIR, SENTINEL_PREFIX + session_id[:16])
    if os.path.exists(sentinel):
        sys.exit(0)  # nag once per session

    untagged, tagged, map_written, committed, playbooks, capped = scan_transcript(
        payload.get("transcript_path", "")
    )

    problems = []
    if untagged:
        listed = "\n".join(
            f"    - [{state}] {p}" for p, state in dict.fromkeys(untagged)
        )
        msg = (
            "[vault-gate] Session note(s) with unusable frontmatter tags:\n"
            f"{listed}\n"
            "  Use the controlled vocabulary in "
            "50_Carreer/Dev_Sessions/_Tag_Dictionary.md (and the project Map's "
            "own `## Tags` section). If no existing tag fits, add it to a "
            "dictionary FIRST, in the same turn."
        )
        if any(state == "offset" for _, state in untagged):
            msg += ('\n  [offset] means the `tags:` block IS there and is written\n  correctly, but it does not start at byte 0 of the file -- and\n  Obsidian parses frontmatter ONLY at byte 0. Anything below a\n  leading blank line is body text to it. Do NOT add tags: move the\n  block you already have to the very top, then confirm with a\n  search_query on tags.length > 0. Three Playbooks failed exactly\n  this way on 2026-08-21 -- the patch returned OK and `cat` looked\n  right.')
        if any(state == "mistyped" for _, state in untagged):
            msg += (
                "\n  [mistyped] means a `tags:` key exists but Obsidian will "
                "NOT index it -- typically a quoted string like\n"
                "      tags: '[\"a\", \"b\"]'\n"
                "  which is what vault_patch produces when handed a `value` "
                "array. Write the YAML list literally in a vault_write:\n"
                "      tags:\n        - a\n        - b\n"
                "  Then confirm with a search_query on tags.length > 0 -- "
                "vault_read returning your value does NOT prove Obsidian "
                "parsed it."
            )
        problems.append(msg)
    if committed and (untagged or tagged) and not map_written:
        problems.append(
            "[vault-gate] This session made git commits and wrote session "
            "notes, but never updated <Project>_Map.md. If the project's actual "
            "shape changed (new/changed objective, pipeline stage wired or "
            "paused, status shift, new data location, new guardrail), run /map. "
            "If nothing structural changed, say so explicitly and finish."
        )

    # Disk, never the transcript: an append's content is a single bullet, so
    # the only place the file's real shape exists is on disk. Unreadable means
    # SKIP -- a gate that guesses starts reporting things that are not true.
    for pb_path in dict.fromkeys(playbooks):
        content = read_vault_file(pb_path)
        if content is None:
            continue
        dupes = duplicate_sections(content)
        if dupes:
            problems.append(playbook_section_report(pb_path, content, dupes))
        # Size is measured from the same disk read, for the same reason: an
        # append's payload is one bullet, so the file's real size exists
        # nowhere else. Reported separately from the duplicate check because
        # they are independent faults -- a clean Playbook can still be fat.
        over = vault_caps.over_cap(pb_path, content)
        if over:
            problems.append(playbook_size_report(pb_path, over))

    # The same disk read, for the kinds that ARE blocked at the door. The
    # block only ever sees a wholesale vault_write, so a Map or current_state
    # edited in place reaches disk unmeasured. Reported here, never refused --
    # the write has already happened, and refusing it retroactively would only
    # strand the author with no way to comply.
    for doc_path in dict.fromkeys(capped):
        content = read_vault_file(doc_path)
        if content is None:
            continue
        over = vault_caps.over_cap(doc_path, content)
        if over:
            problems.append(capped_size_report(doc_path, over))

    if not problems:
        sys.exit(0)

    try:
        open(sentinel, "w").close()
    except OSError:
        pass  # sentinel is best-effort; a failed write must not block the user

    block("\n\n".join(problems) + "\n\nFix these, or state why they do not "
          "apply, then finish.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # The contract is unchanged and stays: a broken gate must NEVER wedge
        # a session, so the exit code is still 0. What changes is that it no
        # longer does so SILENTLY. A crash and a clean pass used to be the
        # same observable event, which is how a NameError ran unnoticed for
        # two sessions on 2026-08-22. stderr is advisory here -- Claude Code
        # reads a block from the exit code and stdout, never from this.
        # SystemExit is not an Exception, so ordinary sys.exit(0) paths and
        # the exit(2) block never reach here.
        try:
            sys.stderr.write(
                "[vault-gate] internal error -- the gate did NOT run. This is "
                "a bug in the hook itself, not a problem with your write; "
                "nothing was blocked.\n")
            traceback.print_exc(file=sys.stderr)
        except Exception:
            pass  # even the report must not be able to raise
        sys.exit(0)
