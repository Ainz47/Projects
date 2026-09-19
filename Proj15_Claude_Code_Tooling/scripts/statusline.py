#!/usr/bin/env python3
"""Claude Code status line: model | project | live context size with zone warnings.

Zones: OK (<200K) / USAGE-BUDGET (>=200K). Not a $/token cost cliff -- Claude
4.6+/5-generation models bill the full 1M context at a flat per-token rate.
The zone flags Pro/Max 5-hour usage-window pressure instead: Anthropic states
usage-limit consumption is "influenced by message length", and every turn
re-sends/cache-reads the full accumulated context, so a long-running
conversation draws down that window faster per turn than the same work split
across periodic /clear resets. Mirrors the single 200K threshold in
hooks/checkpoint_reminder.py -- keep both in sync if either changes.
Registered in settings.json under statusLine; receives session JSON on stdin each render.
"""
import json
import os
import sys

TAIL_BYTES = 262_144

GREEN, RED, DIM, RESET = "\x1b[32m", "\x1b[31m", "\x1b[2m", "\x1b[0m"


def latest_context_tokens(transcript_path):
    try:
        with open(transcript_path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - TAIL_BYTES))
            tail = f.read().decode("utf-8", errors="replace")
        for line in reversed(tail.splitlines()):
            if '"usage"' not in line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            usage = (entry.get("message") or {}).get("usage")
            if not isinstance(usage, dict):
                continue
            return (usage.get("input_tokens", 0)
                    + usage.get("cache_creation_input_tokens", 0)
                    + usage.get("cache_read_input_tokens", 0))
    except OSError:
        pass
    return 0


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        print("ctx: ?")
        return

    model = ((data.get("model") or {}).get("display_name")
             or (data.get("model") or {}).get("id") or "?")
    cwd = ((data.get("workspace") or {}).get("current_dir")
           or data.get("cwd") or "")
    project = os.path.basename(os.path.normpath(cwd)) if cwd else "?"

    tokens = latest_context_tokens(data.get("transcript_path") or "")
    if tokens >= 200_000:
        zone = f"{RED}USAGE-BUDGET{RESET}"
    else:
        zone = f"{GREEN}OK{RESET}"
    ctx = f"{tokens / 1000:.0f}K" if tokens else "~0K"

    print(f"{DIM}{model} | {project} |{RESET} ctx {ctx} {zone}")


if __name__ == "__main__":
    main()
