"""PreToolUse gate: stop a project's delivery commands while open flags block them.

Global hook, per-project behavior. Reads the tool call JSON from stdin and the
project's .claude/flags.json (located via CLAUDE_PROJECT_DIR, falling back to
the payload cwd). Projects opt in by declaring "delivery_commands" (a list of
regex patterns) in flags.json; projects without a flags.json or without that
key are ignored entirely.

- any 'open' flag whose 'blocks' patterns match the command -> permission
  decision 'deny' listing the flags and their fix commands (deny, not ask:
  auto permission mode silently auto-approves 'ask' decisions)
- otherwise, if dormant flags exist (blocked/parked) -> one-line reminder
Non-delivery commands pass through silently.
"""
import json
import os
import re
import sys
from pathlib import Path


def _debug(msg):
    try:
        with open(Path(__file__).parent / "delivery_gate_debug.log", "a", encoding="utf-8") as fh:
            fh.write(msg + "\n")
    except Exception:
        pass


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not command:
        return

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    flags_file = Path(project_dir) / ".claude" / "flags.json"
    if not flags_file.is_file():
        return
    try:
        data = json.loads(flags_file.read_text(encoding="utf-8"))
        delivery_patterns = data.get("delivery_commands", [])
        flags = data.get("flags", [])
    except Exception as e:
        print(json.dumps({"systemMessage": f"[delivery-gate] could not read {flags_file}: {e}"}))
        return

    if not any(re.search(p, command) for p in delivery_patterns):
        return

    blocking = [
        f for f in flags
        if f.get("status") == "open"
        and any(pat in command for pat in f.get("blocks", []))
    ]
    if blocking:
        _debug(f"decision: deny ({', '.join(f['id'] for f in blocking)})")
        lines = ["[delivery-gate] Open flags block this delivery command:"]
        for f in blocking:
            lines.append(f"- {f['id']}: {f['desc']}")
            lines.append(f"  fix: {f.get('fix', 'no fix command recorded')}")
        lines.append("Fix the flag(s), or have the user set status to 'waived' in .claude/flags.json, then re-run.")
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "\n".join(lines),
            }
        }))
        return

    dormant = [f["id"] for f in flags if f.get("status") in ("blocked", "parked")]
    if dormant:
        print(json.dumps({
            "systemMessage": "[delivery-gate] dormant flags (not blocking): " + ", ".join(dormant)
        }))


if __name__ == "__main__":
    main()
