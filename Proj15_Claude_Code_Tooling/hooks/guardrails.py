#!/usr/bin/env python3
"""
guardrails.py — global PreToolUse hook.

Reads per-project .claude/guardrails.json (walking up from the session cwd)
plus optional global ~/.claude/guardrails.json, and enforces deny/ask rules
against every tool call. Pure code — zero token cost unless a rule fires.

Config schema (both files, all keys optional):
{
  "deny": [ {"match": "text", "regex": false, "tools": ["Bash"], "reason": "why"} ],
  "ask":  [ {"match": "text", "regex": false, "tools": ["*"],    "reason": "why"} ],
  "verify": "shell command string (used by done_gate.py)"
}

Behavior:
  deny match -> exit 2, reason on stderr (tool call blocked, Claude sees reason)
  ask match  -> permissionDecision "ask" JSON on stdout (user confirms in UI)
  otherwise  -> exit 0 silently
Fail-open: any internal error -> exit 0, error appended to guardrails_errors.log.
"""
import json
import os
import re
import sys

HOME = os.path.expanduser("~")
GLOBAL_CONFIG = os.path.join(HOME, ".claude", "guardrails.json")
ERROR_LOG = os.path.join(HOME, ".claude", "hooks", "guardrails_errors.log")

# Built-in ask rules — always active, no config required.
# Kept short to avoid permission fatigue; project configs add the rest.
BUILTIN_ASK = [
    {"match": "git push --force", "tools": ["Bash", "PowerShell"],
     "reason": "Force push rewrites remote history"},
    {"match": "git push -f", "tools": ["Bash", "PowerShell"],
     "reason": "Force push rewrites remote history"},
    {"match": "git reset --hard", "tools": ["Bash", "PowerShell"],
     "reason": "Hard reset discards local changes"},
]


def log_error(msg):
    try:
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except OSError:
        pass


def find_project_config(cwd):
    """Walk up from cwd looking for .claude/guardrails.json."""
    d = os.path.abspath(cwd or os.getcwd())
    while True:
        cand = os.path.join(d, ".claude", "guardrails.json")
        if os.path.isfile(cand):
            return cand, d
        parent = os.path.dirname(d)
        if parent == d:
            return None, None
        d = parent


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        log_error(f"config load failed {path}: {e}")
        return {}


def rule_applies(rule, tool_name):
    tools = rule.get("tools") or ["*"]
    return "*" in tools or tool_name in tools


def rule_matches(rule, haystack):
    match = rule.get("match", "")
    if not match:
        return False
    if rule.get("regex"):
        try:
            return re.search(match, haystack, re.IGNORECASE) is not None
        except re.error:
            log_error(f"bad regex in rule: {match!r}")
            return False
    return match.lower() in haystack


def main():
    payload = json.load(sys.stdin)
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    cwd = payload.get("cwd", "")

    # Serialized, lowercased view of the whole tool input for matching.
    haystack = json.dumps(tool_input, ensure_ascii=False).lower()

    proj_path, proj_root = find_project_config(cwd)
    proj_cfg = load_json(proj_path) if proj_path else {}
    glob_cfg = load_json(GLOBAL_CONFIG) if os.path.isfile(GLOBAL_CONFIG) else {}

    deny_rules = (proj_cfg.get("deny") or []) + (glob_cfg.get("deny") or [])
    ask_rules = (proj_cfg.get("ask") or []) + (glob_cfg.get("ask") or []) + BUILTIN_ASK

    # ── Built-in dynamic checks ──────────────────────────────
    command = ""
    if tool_name in ("Bash", "PowerShell"):
        command = str(tool_input.get("command", "")).lower()
        # rm -rf outside temp/scratchpad areas -> ask
        if ("rm -rf" in command or "rm -fr" in command or
                "remove-item -recurse -force" in command):
            safe = ("scratchpad" in command or "/tmp" in command
                    or "appdata/local/temp" in command
                    or "appdata\\local\\temp" in command)
            if not safe:
                ask_rules = ask_rules + [{
                    "match": "", "tools": [tool_name], "_forced": True,
                    "reason": "Recursive delete outside temp/scratchpad"}]
    if tool_name in ("Write", "Edit"):
        fp = str(tool_input.get("file_path", "")).lower()
        if fp.endswith("guardrails.json"):
            ask_rules = ask_rules + [{
                "match": "", "tools": [tool_name], "_forced": True,
                "reason": "Modifying guardrail rules themselves"}]

    # ── Verify-marker side duty (for done_gate.py) ───────────
    verify_cmd = (proj_cfg.get("verify") or "").strip().lower()
    if verify_cmd and command and verify_cmd in command and proj_root:
        try:
            marker = os.path.join(proj_root, ".claude", ".verify_ran")
            with open(marker, "w", encoding="utf-8") as f:
                f.write(payload.get("session_id", ""))
        except OSError as e:
            log_error(f"verify marker write failed: {e}")

    # ── Deny rules (hard block) ──────────────────────────────
    for rule in deny_rules:
        if rule_applies(rule, tool_name) and rule_matches(rule, haystack):
            reason = rule.get("reason", "matched deny rule")
            print(f"[guardrails] BLOCKED: {reason} "
                  f"(rule: {rule.get('match', '')!r})", file=sys.stderr)
            sys.exit(2)

    # ── Ask rules (user confirmation) ────────────────────────
    for rule in ask_rules:
        forced = rule.get("_forced", False)
        if forced or (rule_applies(rule, tool_name) and rule_matches(rule, haystack)):
            reason = rule.get("reason", "matched ask rule")
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "ask",
                    "permissionDecisionReason": f"[guardrails] {reason}",
                }
            }))
            sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # fail-open: never brick tool calls
        log_error(f"guardrails internal error: {e!r}")
        sys.exit(0)
