#!/usr/bin/env python
"""hook_wiring.py - the hook wiring, tracked in git and restorable.

WHY THIS EXISTS
  ~/.claude/settings.json is gitignored on purpose: its `permissions.allow`
  rules carry live API keys (Brevo, Google). But settings.json is ALSO the only
  place the hook wiring lives -- which events fire, which matchers, which
  scripts. So the hooks themselves are version-controlled while the thing that
  makes them RUN is not.

  Rebuild ~/.claude from a clone and every gate silently stops running. No
  error, no missing file, no failed import: the hooks are all present on disk
  and simply never invoked. That is the worst shape a failure can take, and it
  is exactly the shape this whole hook suite exists to prevent elsewhere.

  So: `wiring.json` holds the `hooks` block verbatim and IS tracked. It is
  secret-free -- verified 2026-08-22, every key pattern in settings.json sits
  inside `permissions.allow` and none outside it -- so no sanitiser stands
  between the live value and the tracked one. A sanitiser would be one more
  thing that can silently do nothing.

SCOPE: THIS MACHINE
  Paths stay literal (C:/Users/<you>/...). Templating them for a machine
  that may never exist buys nothing and adds a resolution step that can fail.
  Restoring onto a different user path is a rewrite of wiring.json, by hand,
  once -- not a feature.

THREE DIRECTIONS, DELIBERATELY NAMED
  --check    live vs tracked, report, exit 1 on drift. Never writes.
  --apply    tracked -> live. The clone/restore direction.
  --capture  live -> tracked. Run after changing wiring on purpose.

  --apply and --capture are not inverses to be guessed between. Picking the
  wrong one silently destroys whichever side was correct, so neither is the
  default and running with no flag does --check.

Tests: test_hook_wiring.py
"""

import datetime
import io
import json
import os
import shutil
import sys

# The env var exists so tests never touch the real ~/.claude. Production leaves
# it unset. Same contract as vault_gate.py's CLAUDE_STATE_DIR.
def claude_dir():
    return os.environ.get("CLAUDE_STATE_DIR") or os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))


def settings_path():
    return os.path.join(claude_dir(), "settings.json")


def wiring_path():
    return os.path.join(claude_dir(), "hooks", "wiring.json")


def load_json(path):
    """Return the parsed object, or None if absent/unreadable.

    Absent and corrupt collapse to the same answer on purpose: both mean "this
    side cannot be trusted as a source", and every caller here treats them the
    same way.
    """
    try:
        with io.open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (IOError, OSError, ValueError):
        return None


def live_hooks():
    settings = load_json(settings_path())
    if not isinstance(settings, dict):
        return None
    return settings.get("hooks")


def tracked_hooks():
    return load_json(wiring_path())


def _commands(entries):
    """Flatten one event's entries to (matcher, command) pairs.

    Compared as a SET, not a list: two orderings of the same three PreToolUse
    hooks are the same wiring, and reporting that as drift would train the
    reader to ignore the report.
    """
    out = set()
    for entry in entries or []:
        matcher = entry.get("matcher", "")
        for hook in entry.get("hooks", []):
            out.add((matcher, hook.get("command", "")))
    return out


def _label(matcher, command):
    # Long inline PowerShell would drown the report; the script name is what
    # identifies a hook to a human anyway.
    short = command if len(command) <= 70 else command[:67] + "..."
    return "[%s] %s" % (matcher or "*", short)


def diff(live, tracked):
    """Human-readable drift lines. Empty list means live matches tracked."""
    if tracked is None:
        return ["wiring.json is missing or unparseable - nothing to compare against"]
    if live is None:
        return ["settings.json has NO hooks block - every gate is silently inactive; "
                "run: py %s --apply" % os.path.join(claude_dir(), "hooks",
                                                    "hook_wiring.py")]
    lines = []
    for event in sorted(set(live) | set(tracked)):
        only_live = _commands(live.get(event)) - _commands(tracked.get(event))
        only_tracked = _commands(tracked.get(event)) - _commands(live.get(event))
        for matcher, command in sorted(only_tracked):
            lines.append("%s: TRACKED but not live - %s"
                         % (event, _label(matcher, command)))
        for matcher, command in sorted(only_live):
            lines.append("%s: live but NOT TRACKED - %s"
                         % (event, _label(matcher, command)))
    return lines


def _backup(path):
    """Timestamped, so it never clobbers the standing settings.json.bak rollback."""
    if not os.path.isfile(path):
        return None
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = "%s.bak-%s" % (path, stamp)
    shutil.copy2(path, dest)
    return dest


def _write_json(path, obj):
    """Write via a temp file in the same directory, then replace.

    settings.json is 35 KB of live configuration including every permission
    rule. A half-written one is a broken session, so the truncating window is
    kept off the real path entirely.
    """
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)


def apply_wiring():
    """tracked -> live. Returns (ok, message). Every other settings key survives."""
    tracked = tracked_hooks()
    if tracked is None:
        return False, "wiring.json is missing or unparseable - refusing to apply"
    settings = load_json(settings_path())
    if settings is None:
        if os.path.isfile(settings_path()):
            # Present but unparseable. Overwriting would destroy the permission
            # rules and the API keys inside them, which exist nowhere else.
            return False, ("settings.json exists but is not valid JSON - refusing "
                           "to overwrite it; fix or move it first")
        settings = {}                      # the true clone case: create it
    backup = _backup(settings_path())
    settings["hooks"] = tracked
    _write_json(settings_path(), settings)
    return True, "wiring applied to %s%s" % (
        settings_path(), " (backup: %s)" % os.path.basename(backup) if backup else "")


def capture_wiring():
    """live -> tracked. Returns (ok, message)."""
    live = live_hooks()
    if live is None:
        return False, "settings.json has no hooks block - nothing to capture"
    _write_json(wiring_path(), live)
    return True, "wiring captured to %s" % wiring_path()


def main(argv):
    mode = argv[1] if len(argv) > 1 else "--check"
    if mode == "--apply":
        ok, message = apply_wiring()
    elif mode == "--capture":
        ok, message = capture_wiring()
    elif mode == "--check":
        lines = diff(live_hooks(), tracked_hooks())
        if not lines:
            print("hook wiring: live matches tracked")
            return 0
        print("hook wiring DRIFT:")
        for line in lines:
            print("  " + line)
        return 1
    else:
        print("usage: hook_wiring.py [--check|--apply|--capture]")
        return 2
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv))
