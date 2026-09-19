"""Tests for inject_state.py -- the D4 session-start PUSH hook.

Design: ~/.claude/docs\\specs\\2026-08-21-inject-state-d4-design.md

The hook runs as a real subprocess against a temp vault, matching
test_vault_gate.py's convention. The temp vault is selected with the
CLAUDE_VAULT_STATE_DIR env var, which exists ONLY so these tests can point the
hook somewhere safe -- production leaves it unset and falls back to the real
vault path.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")
HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "inject_state.py")

STATE_HEADER = "## Project state"
CLOSED_HEADER = "## Closed / out of scope"
MAP_HEADER = "## Project map"
INDEX_HEADER = "## Guardrail index"
MAP_REFUSED = "Map NOT injected"
AUDIT_HEADER = "Frontmatter audit"


def note(tags, description, body):
    tag_block = "".join("  - " + t + "\n" for t in tags)
    return (
        "---\ntags:\n" + tag_block + "status: live\n"
        + "description: " + description + "\nsupersedes: []\n---\n\n" + body + "\n"
    )


class Vault:
    """A throwaway Dev_Sessions directory."""

    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix="vaulttest-")
        # The hook also compares the live settings.json with the tracked
        # wiring.json and warns on drift. Give it an isolated state dir where
        # the two agree, so these tests never depend on the machine's own
        # ~/.claude (a fresh clone has no settings.json at all).
        self.state_dir = tempfile.mkdtemp(prefix="claudestate-")
        wiring_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wiring.json")
        os.makedirs(os.path.join(self.state_dir, "hooks"))
        shutil.copy(wiring_src, os.path.join(self.state_dir, "hooks", "wiring.json"))
        with open(wiring_src, encoding="utf-8") as f:
            hooks = json.load(f)
        with open(os.path.join(self.state_dir, "settings.json"), "w", encoding="utf-8") as f:
            json.dump({"hooks": hooks}, f)

    def state(self, project, text):
        self._write(project + "_current_state.md", text)

    def map(self, project, text):
        self._write(project + "_Map.md", text)

    def note(self, project, slug, text):
        d = os.path.join(self.dir, "Guardrails", project)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, slug + ".md"), "w", encoding="utf-8") as f:
            f.write(text)

    def _write(self, name, text):
        with open(os.path.join(self.dir, name), "w", encoding="utf-8") as f:
            f.write(text)

    def run(self, project, stdin=None):
        env = dict(os.environ, CLAUDE_VAULT_STATE_DIR=self.dir,
                   CLAUDE_STATE_DIR=self.state_dir)
        if stdin is None:
            stdin = json.dumps({"cwd": "C:\\fake\\" + project})
        return subprocess.run([sys.executable, HOOK], input=stdin,
                              capture_output=True, text=True,
                              encoding="utf-8", env=env)

    def cleanup(self):
        shutil.rmtree(self.dir, ignore_errors=True)
        shutil.rmtree(self.state_dir, ignore_errors=True)


RESULTS = []


def check(name, condition, detail=""):
    ok = bool(condition)
    RESULTS.append((name, ok))
    line = ("PASS  " if ok else "FAIL  ") + name
    if not ok and detail:
        line += "\n        " + detail
    print(line)


def migrated_vault():
    """A project in the post-partition shape: state + capped Map + notes."""
    v = Vault()
    v.state("demo", "# demo - Current State\nFocus: shipping the hook.\n")
    v.map("demo", "# demo Map\nPointer index.\n")
    v.note("demo", "utah-closed", note(
        ["closed", "scraper"],
        "The UT records route is dead and its worktree looks like live WIP.",
        "# CLOSED: Utah\n\nDO NOT RE-PROPOSE. Artifacts remain on disk.\n"
        "UT SENDING IS STILL LIVE.",
    ))
    v.note("demo", "never-touch-foreign-campaign", note(
        ["guardrail"],
        "A campaign owned by someone else is never writable.",
        "# Never touch it\n\nUNIQUEBODYMARKER placeholder-id.",
    ))
    v.note("demo", "validate-rendered-sentence", note(
        ["guardrail", "enrichment"],
        "Read merge fields back into the real copy line before pushing.",
        "# Validate the rendered sentence\n\nNot a non-blank check.",
    ))
    return v


def main():
    # 1-7: a fully migrated project
    v = migrated_vault()
    out = v.run("demo").stdout

    check("state file is injected", "shipping the hook." in out)

    check("closed note body is injected in full",
          "DO NOT RE-PROPOSE" in out and "UT SENDING IS STILL LIVE" in out,
          "closed bodies are the payload D4 exists for")

    check("non-closed note body is withheld",
          "UNIQUEBODYMARKER" not in out,
          "the index must carry descriptions only, never bodies")

    check("index names every note",
          all(s in out for s in ["utah-closed", "never-touch-foreign-campaign",
                                 "validate-rendered-sentence"]),
          "a rule you have never heard the name of cannot be pulled")

    check("index does not render descriptions",
          "Read merge fields back into the real copy line" not in out,
          "descriptions are the 78% saving -- the slug carries the discovery")

    check("tag manifest lists every tag with its count",
          all(s in out for s in ["guardrail(2)", "enrichment(1)", "closed(1)",
                                 "scraper(1)"]),
          "a session must know which tags exist before it can query one")

    check("under-cap map is injected", "Pointer index." in out and MAP_HEADER in out)

    check("all four sections emitted",
          all(h in out for h in [STATE_HEADER, CLOSED_HEADER, MAP_HEADER, INDEX_HEADER]))

    check("clean vault emits no audit block", AUDIT_HEADER not in out)
    v.cleanup()

    # 8-9: a Map over the LINE cap
    v = migrated_vault()
    v.map("demo", "# Fat Map\n" + "\n".join("line " + str(i) for i in range(400)))
    out = v.run("demo").stdout
    check("over-line-cap map is refused", MAP_REFUSED in out and "line 399" not in out)
    check("refusal names the measured line count", "401" in out,
          "must state the actual size, not just 'too big'")
    check("refused map does not suppress siblings",
          "shipping the hook." in out and "DO NOT RE-PROPOSE" in out
          and INDEX_HEADER in out)
    v.cleanup()

    # 10: a Map over the BYTE cap with an acceptable line count
    v = migrated_vault()
    v.map("demo", "# Fat Map\n" + ("x" * 20000))
    out = v.run("demo").stdout
    check("over-byte-cap map is refused",
          MAP_REFUSED in out and ("x" * 500) not in out)
    v.cleanup()

    # 11: no Guardrails folder
    v = Vault()
    v.state("lonely", "# lonely\nstate body here\n")
    p = v.run("lonely")
    check("missing guardrails folder still injects state",
          "state body here" in p.stdout and p.returncode == 0)
    check("missing guardrails folder emits no index", INDEX_HEADER not in p.stdout)
    v.cleanup()

    # 12-13: frontmatter Obsidian cannot index
    v = migrated_vault()
    v.note("demo", "broken-fm", note(
        ["guardrail"], "greetings lost: 0 across the corpus.", "# Broken\n\nbody"))
    out = v.run("demo").stdout
    check("note with obsidian-breaking yaml is still indexed", "broken-fm" in out)
    check("broken yaml note is named in the audit",
          AUDIT_HEADER in out and "broken-fm" in out.split(AUDIT_HEADER)[-1])
    v.cleanup()

    # 14: the critical one -- a #closed note with broken frontmatter
    v = migrated_vault()
    v.note("demo", "closed-but-broken", note(
        ["closed"], "a colon: breaks this frontmatter.",
        "# CLOSED: something\n\nCLOSEDBROKENBODY must survive."))
    out = v.run("demo").stdout
    check("closed note with broken yaml is still pushed in full",
          "CLOSEDBROKENBODY must survive." in out,
          "strict-only parsing would silently drop this -- the exact D4 failure")
    v.cleanup()

    # 15: a note with no description would render a bare index line
    v = migrated_vault()
    v.note("demo", "no-desc",
           "---\ntags:\n  - guardrail\nstatus: live\n---\n\n# No desc\n\nbody")
    out = v.run("demo").stdout
    check("note missing a description is named in the audit",
          AUDIT_HEADER in out and "no-desc" in out.split(AUDIT_HEADER)[-1])
    v.cleanup()

    # 16: guardrails but no state file
    v = Vault()
    v.note("orphan", "a-rule",
           note(["guardrail"], "A rule with no state file.", "# Rule\n\nbody"))
    p = v.run("orphan")
    check("guardrails without a state file still emit an index",
          INDEX_HEADER in p.stdout and "- a-rule" in p.stdout,
          "the state file must not gate the other sections")
    v.cleanup()

    # 17-19: degenerate inputs
    v = Vault()
    p = v.run("nothing-here")
    check("unknown project emits nothing",
          p.stdout.strip() == "" and p.returncode == 0)
    v.cleanup()

    v = Vault()
    v.state("Online jobs", "# Online jobs\nspaced project body\n")
    check("project name with a space resolves",
          "spaced project body" in v.run("Online jobs").stdout)
    v.cleanup()

    v = Vault()
    p = v.run("demo", stdin="not json at all")
    check("malformed stdin exits zero silently",
          p.returncode == 0 and p.stdout.strip() == "")
    v.cleanup()

    # 20: an index too large for its cap
    v = migrated_vault()
    long_slug = "a-deliberately-long-rule-name-to-exceed-the-index-cap-%03d"
    for i in range(400):
        v.note("demo", long_slug % i,
               note(["guardrail"], "d" * 200, "# Rule\n\nbody"))
    out = v.run("demo").stdout
    check("oversized index is truncated with a shortfall notice",
          "not listed" in out and INDEX_HEADER in out)
    check("truncated index still pushes closed notes in full",
          "DO NOT RE-PROPOSE" in out,
          "closures outrank the index under budget pressure")
    v.cleanup()

    # 21
    v = migrated_vault()
    check("exit code is zero on success", v.run("demo").returncode == 0)
    v.cleanup()

    failed = [r for r in RESULTS if not r[1]]
    print("\n%d/%d passed" % (len(RESULTS) - len(failed), len(RESULTS)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
