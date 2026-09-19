---
name: kickoff
description: Scaffold or retrofit a project with the standard workflow setup - per-project CLAUDE.md, guardrails.json (deny/ask rules + verify command), Obsidian objectives note, and optional CI. Use when starting any new project or bringing an existing one up to standard. Trigger with /kickoff.
---

# /kickoff — Project Scaffold

Bring the current project up to the standard workflow setup. Works for new
projects (scaffold) and existing ones (retrofit — merge, never overwrite).

## Steps

1. **Gather facts** (from the repo itself first; ask the user only what can't be inferred):
   - Project name + one-line purpose
   - Do-not-touch items: IDs, campaigns, prod systems, files owned by others
   - Credit/money-spending operations (APIs, enrichment scripts) → become `ask` rules
   - Destructive domain operations → `ask` or `deny` rules
   - Verify command (test suite or smoke check, e.g. `pytest tests`). If none exists,
     propose a minimal one; a smoke script counts.
   - Key scripts, data directories, environment quirks

2. **Write `.claude/guardrails.json`** from `templates/guardrails.template.json`:
   - Every do-not-touch item → `deny` rule (scope tools to Bash/PowerShell/WebFetch)
   - Every credit-spending or destructive op → `ask` rule
   - Set `verify` to the project's verify command (short distinctive substring)
   - RETROFIT: if the file exists, merge new rules in; never remove existing rules
     without explicit user approval

3. **Write/extend `CLAUDE.md`** using `templates/CLAUDE.md.template` as the section
   checklist. RETROFIT: only add missing sections to an existing CLAUDE.md.

4. **Ignore runtime files**: ensure `.gitignore` covers
   `.claude/.verify_ran` and `.claude/.done_gate_*` (keep `guardrails.json` tracked).

5. **Obsidian objectives note** (via Obsidian MCP only): create
   `50_Carreer/Dev_Sessions/<ProjectName>_Project_Objectives.md` if missing —
   client, primary goal, scope, out-of-scope, pipeline, deliverable format.
   Also create `<ProjectName>_Playbook.md` if missing, with empty sections:
   `## DO`, `## DON'T`, `## WORKS`, `## FAILED` (running lessons ledger —
   session logs append one-line dated lessons here).

6. **CI (optional)**: if a `tests/` dir exists AND the repo has a GitHub remote,
   offer to install `templates/ci-pytest.yml` as `.github/workflows/ci.yml`.

7. **Report**: list every file created/changed and every guardrail rule added.
   Remind the user that new hooks/config take effect from the next session.

## Rules
- Never overwrite an existing CLAUDE.md or guardrails.json wholesale — merge.
- Deny rules are for things that must NEVER happen; ask rules for things that
  need a human yes. When unsure, use ask (deny false-positives are expensive).
- Keep ask rules few — permission fatigue kills guardrails.
