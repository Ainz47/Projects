#!/usr/bin/env python3
"""
done_gate.py — Stop hook (verification gate, v1).

If the project's .claude/guardrails.json declares a "verify" command AND source
files changed this session (git dirty) AND the verify command was not observed
running (marker written by guardrails.py PreToolUse hook), block the stop ONCE
with a one-line reminder. Sentinel file prevents nag loops.

Zero cost when: no project config, no verify key, clean tree, or verify already ran.
Fail-open on any internal error.
"""
import fnmatch
import json
import os
import subprocess
import sys

SOURCE_EXTS = (".py", ".js", ".ts", ".tsx", ".go", ".php", ".rb", ".rs",
               ".java", ".c", ".cpp", ".cs", ".sh", ".ps1", ".sql", ".html", ".css")


def is_skipped(path, patterns):
    """Does this changed file fall outside what the verify command covers?

    Optional "verify_skip" in guardrails.json: a list of globs matched against
    BOTH the repo-relative path and the bare filename, so "_*.py" catches
    one-off scripts anywhere in the tree without needing a path prefix.

    The point is to stop demanding a full suite run for edits the suite cannot
    possibly see -- throwaway probes, generated content, email HTML. A gate that
    fires on files it knows nothing about trains people to ignore the gate.
    """
    if not patterns:
        return False
    p = path.replace("\\", "/")
    base = os.path.basename(p)
    return any(fnmatch.fnmatch(p, pat) or fnmatch.fnmatch(base, pat)
               for pat in patterns)


def find_project(cwd):
    d = os.path.abspath(cwd or os.getcwd())
    while True:
        cand = os.path.join(d, ".claude", "guardrails.json")
        if os.path.isfile(cand):
            return cand, d
        parent = os.path.dirname(d)
        if parent == d:
            return None, None
        d = parent


def main():
    payload = json.load(sys.stdin)
    if payload.get("stop_hook_active"):
        sys.exit(0)  # already inside a stop-hook continuation; never double-block

    cwd = payload.get("cwd", "")
    session_id = payload.get("session_id", "unknown")

    cfg_path, root = find_project(cwd)
    if not cfg_path:
        sys.exit(0)
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        sys.exit(0)

    verify_cmd = (cfg.get("verify") or "").strip()
    if not verify_cmd:
        sys.exit(0)

    claude_dir = os.path.join(root, ".claude")

    # Only nag once per session.
    sentinel = os.path.join(claude_dir, f".done_gate_{session_id[:16]}")
    if os.path.exists(sentinel):
        sys.exit(0)

    # Verify already observed this session?
    marker = os.path.join(claude_dir, ".verify_ran")
    if os.path.exists(marker):
        try:
            with open(marker, "r", encoding="utf-8") as f:
                if f.read().strip() == session_id:
                    sys.exit(0)
        except OSError:
            pass

    # Source changes pending?
    try:
        out = subprocess.run(
            ["git", "-C", root, "status", "--porcelain"],
            capture_output=True, text=True, timeout=10,
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        sys.exit(0)
    skip = cfg.get("verify_skip") or []
    dirty_source = []
    for line in out.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip().strip('"')
        if " -> " in path:  # rename: judge the destination, not the source
            path = path.split(" -> ")[-1].strip().strip('"')
        if path.endswith(SOURCE_EXTS) and not is_skipped(path, skip):
            dirty_source.append(path)
    if not dirty_source:
        sys.exit(0)

    # Block once with the reminder.
    try:
        with open(sentinel, "w", encoding="utf-8") as f:
            f.write("nagged")
    except OSError:
        pass
    print(json.dumps({
        "decision": "block",
        "reason": (f"[done-gate] Source files changed but the project's verify "
                   f"command has not run this session (verify: {verify_cmd}). "
                   f"Triggered by: {', '.join(dirty_source[:5])}"
                   f"{' ...' if len(dirty_source) > 5 else ''}. "
                   f"Run it and report the result, or state why verification "
                   f"does not apply, then finish."),
    }))
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)
