"""Tests for hook_wiring.py -- the tracked, restorable hook wiring.

Same in-process PASS/FAIL harness as test_playbook_evict.py. Every test points
CLAUDE_STATE_DIR at a throwaway directory, so the real ~/.claude/settings.json
is never read and never written by this file.

The load-bearing property is NON-DESTRUCTION. --apply exists to run against a
settings.json that may hold the only copy of live API keys, so the tests that
matter most are the ones proving it preserves unrelated keys and refuses rather
than guesses when the file it is about to rewrite cannot be parsed.
"""

import io
import json
import os
import shutil
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")

import hook_wiring as hw

r = []


def check(label, ok, why=""):
    r.append(bool(ok))
    print("%-4s %s" % ("PASS" if ok else "FAIL", label))
    if not ok and why:
        print("       " + why)


WIRING = {
    "SessionStart": [{"hooks": [{"type": "command", "command": "py inject_state.py"}]}],
    "PreToolUse": [
        {"matcher": "Bash", "hooks": [{"type": "command", "command": "py gate.py"}]},
        {"matcher": "mcp__obsidian__vault_write",
         "hooks": [{"type": "command", "command": "py vault_gate.py"}]},
    ],
}


class Sandbox(object):
    """A throwaway ~/.claude. Restores the env var on exit."""

    def __enter__(self):
        self.root = tempfile.mkdtemp(prefix="hookwiring-")
        os.makedirs(os.path.join(self.root, "hooks"))
        self.prev = os.environ.get("CLAUDE_STATE_DIR")
        os.environ["CLAUDE_STATE_DIR"] = self.root
        return self

    def __exit__(self, *exc):
        if self.prev is None:
            os.environ.pop("CLAUDE_STATE_DIR", None)
        else:
            os.environ["CLAUDE_STATE_DIR"] = self.prev
        shutil.rmtree(self.root, ignore_errors=True)

    def write(self, name, obj):
        with io.open(os.path.join(self.root, name), "w", encoding="utf-8") as fh:
            json.dump(obj, fh)

    def write_raw(self, name, text):
        with io.open(os.path.join(self.root, name), "w", encoding="utf-8") as fh:
            fh.write(text)

    def read(self, name):
        with io.open(os.path.join(self.root, name), encoding="utf-8") as fh:
            return json.load(fh)


TRACKED = os.path.join("hooks", "wiring.json")

# -- diff -------------------------------------------------------------------

with Sandbox() as sb:
    sb.write("settings.json", {"hooks": WIRING})
    sb.write(TRACKED, WIRING)
    check("identical wiring reports no drift",
          hw.diff(hw.live_hooks(), hw.tracked_hooks()) == [])

with Sandbox() as sb:
    reordered = {"SessionStart": WIRING["SessionStart"],
                 "PreToolUse": list(reversed(WIRING["PreToolUse"]))}
    sb.write("settings.json", {"hooks": reordered})
    sb.write(TRACKED, WIRING)
    check("reordering entries within an event is not drift",
          hw.diff(hw.live_hooks(), hw.tracked_hooks()) == [],
          "an order-sensitive check cries wolf, and a report that cries wolf "
          "stops being read")

with Sandbox() as sb:
    sb.write("settings.json", {"hooks": {"SessionStart": WIRING["SessionStart"]}})
    sb.write(TRACKED, WIRING)
    lines = hw.diff(hw.live_hooks(), hw.tracked_hooks())
    check("a tracked hook missing from live is reported",
          any("TRACKED but not live" in l and "vault_gate.py" in l for l in lines),
          repr(lines))

with Sandbox() as sb:
    extra = json.loads(json.dumps(WIRING))
    extra["Stop"] = [{"hooks": [{"type": "command", "command": "py done_gate.py"}]}]
    sb.write("settings.json", {"hooks": extra})
    sb.write(TRACKED, WIRING)
    lines = hw.diff(hw.live_hooks(), hw.tracked_hooks())
    check("a live hook missing from the tracked copy is reported",
          any("live but NOT TRACKED" in l and "done_gate.py" in l for l in lines),
          "this is the rot direction: wiring changed on purpose, never captured")

with Sandbox() as sb:
    sb.write("settings.json", {"permissions": {"allow": []}})
    sb.write(TRACKED, WIRING)
    lines = hw.diff(hw.live_hooks(), hw.tracked_hooks())
    check("no hooks block at all names the remedy",
          len(lines) == 1 and "--apply" in lines[0], repr(lines))

with Sandbox() as sb:
    sb.write("settings.json", {"hooks": WIRING})
    check("a missing wiring.json is reported, not treated as agreement",
          hw.diff(hw.live_hooks(), hw.tracked_hooks()) != [])

# -- apply: the clone case --------------------------------------------------

with Sandbox() as sb:
    sb.write(TRACKED, WIRING)
    ok, msg = hw.apply_wiring()
    check("apply creates settings.json when it does not exist at all", ok, msg)
    check("the created file carries the tracked wiring",
          sb.read("settings.json").get("hooks") == WIRING)

with Sandbox() as sb:
    sb.write("settings.json", {"permissions": {"allow": ["Bash(curl -H key: LIVE)"]},
                               "model": "opus", "hooks": {}})
    sb.write(TRACKED, WIRING)
    ok, _ = hw.apply_wiring()
    after = sb.read("settings.json")
    check("apply preserves every unrelated settings key",
          ok and after["model"] == "opus"
          and after["permissions"]["allow"] == ["Bash(curl -H key: LIVE)"],
          "apply must never be a route to losing the API keys it sits next to")
    check("apply replaces the hooks block", after["hooks"] == WIRING)

with Sandbox() as sb:
    sb.write("settings.json", {"model": "opus"})
    sb.write(TRACKED, WIRING)
    hw.apply_wiring()
    backups = [f for f in os.listdir(sb.root) if f.startswith("settings.json.bak-")]
    check("apply backs the previous settings.json up first", len(backups) == 1,
          repr(backups))

with Sandbox() as sb:
    sb.write_raw("settings.json", "{not valid json")
    sb.write(TRACKED, WIRING)
    ok, msg = hw.apply_wiring()
    check("apply REFUSES an unparseable settings.json rather than overwriting it",
          not ok and "refusing" in msg,
          "the permission rules inside it exist nowhere else; guessing destroys them")
    check("the unparseable file is left byte-identical",
          io.open(os.path.join(sb.root, "settings.json"),
                  encoding="utf-8").read() == "{not valid json")

with Sandbox() as sb:
    sb.write("settings.json", {"model": "opus"})
    ok, msg = hw.apply_wiring()
    check("apply refuses when there is no tracked wiring to apply",
          not ok and "refusing" in msg)

# -- capture ----------------------------------------------------------------

with Sandbox() as sb:
    sb.write("settings.json", {"hooks": WIRING})
    ok, _ = hw.capture_wiring()
    check("capture writes live wiring to the tracked file",
          ok and sb.read(TRACKED) == WIRING)

with Sandbox() as sb:
    sb.write("settings.json", {"permissions": {}})
    ok, msg = hw.capture_wiring()
    check("capture refuses when live has no hooks block", not ok,
          "capturing nothing would erase the tracked copy, which is the whole asset")

# -- round trip -------------------------------------------------------------

with Sandbox() as sb:
    sb.write("settings.json", {"hooks": WIRING, "model": "opus"})
    hw.capture_wiring()
    os.remove(os.path.join(sb.root, "settings.json"))
    hw.apply_wiring()
    check("capture then apply restores wiring onto a wiped settings.json",
          sb.read("settings.json").get("hooks") == WIRING)
    check("a restored-from-nothing settings.json reports no drift",
          hw.diff(hw.live_hooks(), hw.tracked_hooks()) == [])

print("\n%d/%d passed" % (sum(r), len(r)))
sys.exit(0 if all(r) else 1)
