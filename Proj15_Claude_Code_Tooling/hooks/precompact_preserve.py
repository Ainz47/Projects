import json
import sys


def main():
    try:
        sys.stdin.read()
    except Exception:
        pass
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreCompact",
            "additionalContext": (
                "When summarizing this session, preserve verbatim: the current task and its "
                "exact next step, every decision made this session and why, full paths of all "
                "files being created or modified, exact commands/IDs needed to resume, and any "
                "pending user instructions."
            )
        }
    }))


if __name__ == "__main__":
    main()
    sys.exit(0)
