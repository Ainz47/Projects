---
name: retro
description: Weekly feedback-loop review - read the recent Obsidian Dev_Sessions logs, extract recurring failures/insights, and propose updates to CLAUDE.md files, guardrails, and memory as an approve-before-apply diff. Trigger with /retro (optionally /retro <days>).
---

# /retro — Close the Feedback Loop

Turn the week's session logs into durable improvements. Manual trigger only;
one pass per invocation. Default window: 7 days (override via argument).

## Steps

1. **Collect** (via Obsidian MCP only): read each active project's
   `<ProjectName>_current_state.md` **FIRST**, then its `<ProjectName>_Playbook.md`,
   then list `50_Carreer/Dev_Sessions/` notes modified in the window and read them.
   If a session-note lesson is missing from the playbook, add it there as part of
   the retro.

   **Order matters and this is the reverse of what it used to say.** The playbook
   is append-only history: a `FAILED` entry stays in it verbatim after the finding
   has been overturned, and it reads as a live verdict. The current-state file is
   where supersessions get recorded. On 2026-08-03/04 the project-b playbook
   still said Utah was "deprioritized, 6.1% match rate, dropped" hours after an
   uncapped sweep had moved it to 9.0% and reopened the line; quoting the playbook
   alone re-closed a decision that had already been reopened. **Treat a playbook
   entry as a dated hypothesis, not a current verdict — confirm against
   current-state or the source artifact before quoting it as settled.**

2. **Extract patterns** — look specifically for:
   - The same bug/failure hit more than once → candidate CLAUDE.md "Known Issues"
     or guardrail rule
   - Manual confirmations that repeat → candidate ask rule, or removal of one
     that only causes fatigue
   - "Key insight" lines never captured in CLAUDE.md or memory
   - Workarounds that should become conventions (e.g. a new API discovery
     replacing an old approach)
   - Stale info: CLAUDE.md/memory statements the logs prove wrong

3. **Propose** — one consolidated list, grouped by target file:
   - `<project>/CLAUDE.md` additions/corrections
   - `.claude/guardrails.json` rule changes
   - Global `~/.claude/CLAUDE.md` behavior-rule changes (rare — only clear repeats)
   - Memory files to add/update/delete
   Show exact before/after text. Do NOT apply anything yet.

4. **Apply on approval** — user picks which items; apply only those. Log the
   retro itself to `50_Carreer/Dev_Sessions/YYYY-MM-DD-retro.md` (what was
   reviewed, what changed, what was rejected).

## Rules
- Never apply without approval — this skill edits the rulebooks.
- Prefer deleting/simplifying over adding; instruction bloat is a failure mode.
- If a proposed change contradicts an existing rule, flag the conflict instead
  of silently overriding it.
