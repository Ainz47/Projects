import json
import os
import sys
import tempfile

# (threshold, message template) — each fires once per session, highest matching first
#
# Only one threshold: a checkpoint that isn't followed by /clear doesn't
# shrink the running conversation, so a mid-session-only reminder (the old
# 120K entry) was pure overhead -- tool calls to read/archive/write the vault
# note, no reduction in the per-turn context every subsequent turn still
# drags along. The saving only materializes when a checkpoint is paired with
# an actual /clear, which is what this message asks for.
#
# This is NOT a $/token pricing cliff -- Claude 4.6+/5-generation models
# (what this account runs on) bill the full 1M context window at a flat
# per-token rate, confirmed 2026-08-24 against Anthropic's own pricing docs.
# The real reason to clear here is the separate Pro/Max usage-limit (the
# 5-hour/weekly window), which Anthropic states is "influenced by message
# length" -- every turn re-sends/cache-reads the full accumulated context,
# so a long-running conversation burns that budget faster per turn than an
# equivalent amount of work split across periodic /clear resets, even though
# the dollar cost per token never changes.
THRESHOLDS = [
    (300_000, (
        "[usage-budget-warning] Context is at ~{tokens} tokens (>= 300K). "
        "This does not cost more per token, but it does draw down the Pro/Max "
        "5-hour usage window faster per turn from here on. Tell the user "
        "immediately and recommend checkpointing (/checkpoint) and running "
        "/clear to reset context."
    )),
]
TAIL_BYTES = 262_144  # newest usage entry is near EOF; avoid reading huge transcripts fully


def latest_context_tokens(transcript_path):
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
        if not usage:
            continue
        return (
            usage.get("input_tokens", 0)
            + usage.get("cache_creation_input_tokens", 0)
            + usage.get("cache_read_input_tokens", 0)
        )
    return 0


def main():
    try:
        data = json.load(sys.stdin)
        session_id = data.get("session_id") or "unknown"
        transcript = data.get("transcript_path") or ""
        if not transcript or not os.path.isfile(transcript):
            return
        marker_dir = os.path.join(tempfile.gettempdir(), "claude_checkpoint_markers")
        os.makedirs(marker_dir, exist_ok=True)
        tokens = latest_context_tokens(transcript)
        for threshold, template in THRESHOLDS:
            if tokens < threshold:
                continue
            marker = os.path.join(marker_dir, f"{session_id}.{threshold}.done")
            if os.path.exists(marker):
                break  # already fired once this session
            with open(marker, "w") as f:
                f.write(str(tokens))
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": template.format(tokens=tokens)
                }
            }))
            break
    except Exception:
        pass


if __name__ == "__main__":
    main()
    sys.exit(0)
