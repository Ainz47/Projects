"""SessionStart hook: PUSH the closures, index the details.

Implements D4 of the vault doc partition design
(~/.claude/docs/specs/2026-08-20-vault-doc-partition-design.md).

Driving principle: **you can only query for what you know exists.** So a cold
session is handed, without asking:

  1. <Project>_current_state.md        -- what the session is doing
  2. every note tagged `closed`, IN FULL -- what it must NOT re-propose
  3. <Project>_Map.md, if it is within its cap -- where things live
  4. a generated one-line index of every guardrail note -- what rules exist

Bodies of non-closed guardrail notes are deliberately NOT pushed. They are
PULLed on demand by reading Guardrails/<Project>/<slug>.md or by tag query.

Why closures are pushed in full rather than indexed: a closed track is *defined*
by leaving artifacts behind (a dirty worktree, a half-built scraper), so the
repo is the worst possible place to ask "is this in scope". That question has
already been answered wrong once, by a session that had no way to know the
answer had been written down.

Tests: test_inject_state.py
"""

import collections
import json
import os
import re
import sys

import vault_caps

try:
    import yaml
except ImportError:                                    # audit degrades, push does not
    yaml = None

try:
    import hook_wiring
except ImportError:                                    # wiring check degrades, push does not
    hook_wiring = None

sys.stdout.reconfigure(encoding="utf-8")

# The env var exists so the tests can point at a throwaway vault. Production
# leaves it unset.
VAULT_STATE_DIR = os.environ.get("CLAUDE_VAULT_STATE_DIR") or (
    os.path.join(os.path.expanduser("~"), "Documents", "Vault", "50_Carreer", "Dev_Sessions")
)
GUARDRAILS_SUBDIR = "Guardrails"
SPEC = "2026-08-20-vault-doc-partition-design.md"

# Every size number this hook uses lives in vault_caps, so the write-time gate
# and this read-time refusal cannot drift apart. They previously did: the /map
# skill said ~150 lines while this file refused at 200, and nothing reconciled
# them. See vault_caps.py for why map/state carry a cap AND a refusal threshold.
STATE_MAX_BYTES = vault_caps.CAPS["state"].max_bytes
INDEX_MAX_BYTES = vault_caps.INDEX_MAX_BYTES

TAGS_RE = re.compile(r"^tags\s*:(.*)$", re.MULTILINE)
DESC_RE = re.compile(r"^description\s*:(.*)$", re.MULTILINE)
KEY_RE = re.compile(r"^\S[^:]*:")


# ------------------------------------------------------------------ reading

def read_text(path, limit=None):
    """Return file text, or None if it is not there / not readable."""
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read(limit) if limit else f.read()
    except OSError:
        return None


def split_frontmatter(text):
    """Tolerantly split a note into (frontmatter, body).

    Deliberately hand-rolled rather than YAML: a note whose frontmatter Obsidian
    cannot parse must still be delivered, because it may be a `closed` note and
    dropping one of those is the precise failure this hook exists to prevent.
    Fidelity is recovered separately by strict_problem(), which reports the
    divergence instead of acting on it.
    """
    stripped = text.lstrip()
    if not stripped.startswith("---"):
        return "", text
    rest = stripped[3:]
    end = rest.find("\n---")
    if end == -1:
        return "", text
    return rest[:end], rest[end + 4:]


def parse_tags(fm):
    m = TAGS_RE.search(fm)
    if not m:
        return []
    inline = m.group(1).strip()
    if inline.startswith("["):
        return [t.strip().strip("'\"") for t in inline.strip("[]").split(",") if t.strip()]
    if inline:
        return [inline.strip("'\"")]
    tags = []
    for line in fm[m.end():].split("\n")[1:]:
        stripped = line.strip()
        if stripped.startswith("- "):
            tags.append(stripped[2:].strip().strip("'\""))
        elif stripped:
            break
    return tags


def parse_description(fm):
    m = DESC_RE.search(fm)
    if not m:
        return ""
    value = m.group(1).strip()
    for line in fm[m.end():].split("\n")[1:]:      # folded continuation lines
        if not line.strip() or KEY_RE.match(line) or not line[:1].isspace():
            break
        value += " " + line.strip()
    return value.strip().strip("'\"")


def strict_problem(fm):
    """What Obsidian would refuse about this frontmatter, or None.

    A note the hook reads happily but Obsidian indexes with zero tags is
    invisible to every tag query, so it can never be PULLed. That bug ate a
    whole note's tags on 2026-08-21 and was caught only by remembering to run a
    tags.length == 0 query by hand. Reporting it here makes it loud instead.
    """
    if yaml is None:
        return None
    try:
        parsed = yaml.safe_load(fm)
    except Exception as exc:
        return "YAML parse error: " + str(exc).replace("\n", " ")[:90]
    if not isinstance(parsed, dict):
        return "frontmatter is not a mapping"
    if not parsed.get("tags"):
        return "indexed with ZERO tags"
    return None


def load_notes(project):
    """Load Guardrails/<project>/*.md, or None when the project is unpartitioned."""
    folder = os.path.join(VAULT_STATE_DIR, GUARDRAILS_SUBDIR, project)
    if not os.path.isdir(folder):
        return None
    notes = []
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".md"):
            continue
        slug = name[:-3]
        text = read_text(os.path.join(folder, name))
        if text is None:
            notes.append({"slug": slug, "tags": [], "description": "",
                          "body": "", "problem": "file could not be read"})
            continue
        fm, body = split_frontmatter(text)
        description = parse_description(fm)
        if not fm:
            problem = "no frontmatter block"
        else:
            problem = strict_problem(fm)
        if problem is None and not description:
            problem = "no description -- nothing summarises it in a tag query"
        notes.append({"slug": slug, "tags": parse_tags(fm),
                      "description": description, "body": body.strip(),
                      "problem": problem})
    return notes


# ------------------------------------------------------------------ emitting

def emit_state(out, project):
    text = read_text(os.path.join(VAULT_STATE_DIR, project + "_current_state.md"),
                     STATE_MAX_BYTES)
    if not text or not text.strip():
        return
    out.append("## Project state (auto-restored from vault: %s_current_state.md)\n"
               % project)
    out.append(text.rstrip() + "\n")


def emit_closed(out, notes):
    closed = [n for n in notes if "closed" in n["tags"]]
    if not closed:
        return
    out.append("## Closed / out of scope (%d %s, full text)\n"
               % (len(closed), "note" if len(closed) == 1 else "notes"))
    out.append("These tracks are DECIDED. Do not re-propose them, and do not read "
               "leftover\nartifacts on disk as evidence that they are still open.\n")
    for note in closed:
        out.append("### " + note["slug"])
        out.append(note["body"] + "\n")


def emit_map(out, project):
    path = os.path.join(VAULT_STATE_DIR, project + "_Map.md")
    text = read_text(path)
    if not text or not text.strip():
        return
    too_big = vault_caps.over_refusal(path, text)
    if too_big:
        out.append("> [!warning] Map NOT injected")
        out.append("> %s_Map.md is %s." % (project, too_big))
        out.append("> This project has not been partitioned yet. Read it directly "
                   "if you need it,\n> or run the migration (spec: %s).\n" % SPEC)
        return
    out.append("## Project map (%s_Map.md)\n" % project)
    out.append(text.rstrip() + "\n")


def emit_index(out, notes, project):
    """Name every rule, describe none of them, and say which tags exist.

    Descriptions are deliberately dropped. They cost 10,881 chars across
    project-b's 58 notes against 2,150 for the names alone, and the names in
    this vault are already sentences -- `compile-reverts-the-ga-sprinkler-merge`
    fires the "there is a rule about that" reflex on its own, which is the only
    job the index has. The tag manifest is what makes a targeted PULL possible:
    you cannot query a tag you have not been told exists.
    """
    if not notes:
        return
    counts = collections.Counter()
    for note in notes:
        counts.update(note["tags"])

    out.append("## Guardrail index (%d rules, names only — bodies NOT loaded)\n"
               % len(notes))
    if counts:
        out.append("TAGS  " + " ".join(
            "%s(%d)" % (tag, n) for tag, n in
            sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))) + "\n")
    out.append("Pull one rule: `%s/%s/<slug>.md`. Pull a topic: search_query on its "
               "tag.\n" % (GUARDRAILS_SUBDIR, project))

    rows, budget = [], 0
    for note in notes:
        row = "- " + note["slug"]
        if budget + len(row) > INDEX_MAX_BYTES:
            break
        rows.append(row)
        budget += len(row) + 1
    out.extend(rows)
    if len(rows) < len(notes):
        out.append("\n> %d of %d rules not listed (index cap). Query by tag to reach "
                   "them." % (len(notes) - len(rows), len(notes)))
    out.append("")


def emit_audit(out, notes):
    broken = [n for n in notes if n["problem"]]
    if not broken:
        return
    out.append("> [!error] Frontmatter audit — %d %s INVISIBLE to Obsidian tag queries"
               % (len(broken), "note is" if len(broken) == 1 else "notes are"))
    for note in broken:
        out.append("> - %s.md — %s" % (note["slug"], note["problem"]))
    out.append("> These were still delivered above, but no tag query will return "
               "them.\n> Fix the frontmatter.\n")


SECTIONS = (
    ("project state", lambda out, project, notes: emit_state(out, project)),
    ("closed notes", lambda out, project, notes: emit_closed(out, notes)),
    ("project map", lambda out, project, notes: emit_map(out, project)),
    ("guardrail index", lambda out, project, notes: emit_index(out, notes, project)),
    ("frontmatter audit", lambda out, project, notes: emit_audit(out, notes)),
)


def emit_wiring_drift(out):
    """Report hook wiring that has drifted from its tracked copy.

    Warn-only, and deliberately NOT project-scoped: the wiring is a property of
    this machine, so it is emitted before main() decides whether the cwd is even
    a vault-tracked project.

    This cannot catch the total-loss case from inside a session -- if the wiring
    is gone, this hook does not run either. It catches the case that PRODUCES a
    bad restore: wiring edited in settings.json and never captured, so the
    tracked copy quietly goes stale until the day it is relied on.
    """
    if hook_wiring is None:
        return
    lines = hook_wiring.diff(hook_wiring.live_hooks(), hook_wiring.tracked_hooks())
    if not lines:
        return
    out.append("> [!warning] Hook wiring differs from the tracked copy "
               "(hooks/wiring.json)")
    for line in lines:
        out.append("> - " + line)
    out.append("> Intentional change? `py ~/.claude/hooks/hook_wiring.py --capture`"
               "\n> Lost wiring? `py ~/.claude/hooks/hook_wiring.py --apply`\n")


def main():
    out = []
    try:
        emit_wiring_drift(out)
    except Exception as exc:
        out.append("> [!error] inject_state: the hook wiring check failed: %s\n" % exc)

    def flush():
        if out:
            print("\n".join(out))

    try:
        data = json.load(sys.stdin)
        cwd = data.get("cwd") or ""
    except Exception:
        return flush()
    project = os.path.basename(os.path.normpath(cwd)) if cwd else ""
    if not project:
        return flush()

    notes = load_notes(project)
    has_state = os.path.isfile(os.path.join(VAULT_STATE_DIR,
                                            project + "_current_state.md"))
    has_map = os.path.isfile(os.path.join(VAULT_STATE_DIR, project + "_Map.md"))
    if notes is None and not has_state and not has_map:
        return flush()                           # not a vault-tracked project

    for name, emit in SECTIONS:
        try:
            emit(out, project, notes or [])
        except Exception as exc:                 # one bad section must not eat the rest
            out.append("> [!error] inject_state: the %s section failed: %s\n"
                       % (name, exc))
    flush()


if __name__ == "__main__":
    main()
    sys.exit(0)
