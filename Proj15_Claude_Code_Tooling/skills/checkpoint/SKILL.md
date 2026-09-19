---
name: checkpoint
description: Save the current project/session state to the vault state file via Obsidian MCP. Use when the user runs /checkpoint, when a [usage-budget-warning] fires at 200K tokens, or before /clear or ending a work block.
---

# Checkpoint Session State

Persist a snapshot of the current project state so any future session (or this
session after compaction) can resume cold.

## Steps

1. `<ProjectName>` = basename of the current working directory
   (e.g. `C:\code\project-b` -> `project-b`).
2. Vault target: `50_Carreer/Dev_Sessions/<ProjectName>_current_state.md`.
3. Compose the COMPLETE replacement file (snapshot, not journal). It is CAPPED,
   and `vault_gate.py` BLOCKS an over-cap write at the door — the block message
   names the measured size and the limit. The numbers live in
   `~/.claude/hooks/vault_caps.py` (`CAPS["state"]`) and nowhere else; do not
   restate one here. Template:

   # <ProjectName> - Current State
   Updated: <YYYY-MM-DD HH:mm>

   ## Current Focus
   <the one task in progress right now, and its exact next step>

   ## Last Session
   <3-6 bullets: what was just accomplished>

   ## Decisions Made
   <bullets: decision + one-line why. Carry forward still-relevant older decisions.>

   ## Next Steps
   <ordered list, most immediate first>

   ## Blockers
   <bullets, or "None". BLOCKED = will be retried when the blocker clears.
   Anything that will never be retried goes in Closed / Out of Scope instead.>

   ## Closed / Out of Scope
   <bullets: the track, the one-line reason it is dead, and the date. NEVER
   dropped as stale - see the rule below. A cold session cannot tell a dead
   track from live WIP by looking at the repo, because closed work leaves
   scrapers, branches, worktrees and test files behind exactly like live work
   does. If a closed track has artifacts still on disk, NAME THEM here.>

   ## Key Paths
   <exact file paths, IDs, commands needed to resume cold>

4. Archive the outgoing snapshot, if there is one:
   - `mcp__obsidian__vault_read` the current state file from step 2.
   - If it does not exist (first checkpoint in this project), SKIP to step 5. Not an error.
   - `mcp__obsidian__vault_write` its content VERBATIM to
     `50_Carreer/Dev_Sessions/State_Archive/<ProjectName>/<YYYY-MM-DD-HHmm>.md`,
     where the timestamp is NOW (when archiving), not the snapshot's own `Updated:` line.
   - If that exact path already exists, use `<YYYY-MM-DD-HHmmss>.md` instead. `vault_write`
     overwrites silently, so check rather than assume.
   - COPY, NEVER `vault_move`. A move leaves a window with no `_current_state.md`, and
     `inject_state.py` reads a missing file as "project has no state" and starts cold in
     silence. Absence is not a detectable error, so it must never happen.
   - If the read or the write fails: STOP and report. Do NOT continue to step 5. The old
     state stays live and still true; overwriting it after failing to preserve it is the
     exact loss this step exists to prevent.
5. Write the new snapshot with `mcp__obsidian__vault_write` (path relative to vault root,
   full overwrite).
   - If the Obsidian MCP is unavailable: say so explicitly and STOP.
     NEVER write to the vault with filesystem tools.
6. Confirm: "Checkpointed to `<vault path>`", naming the archive path too when one was written.

## Rules

- Keep only current truth; drop stale content from the previous snapshot.
  Dropping it is safe because step 4 archived it first. Narrative history still belongs in
  the dated Dev_Sessions logs, but this skill no longer depends on those being written.
- **EXCEPTION: closure decisions are never stale.** A track that was
  investigated and ruled out stays in `## Closed / Out of Scope` permanently,
  carried forward at every checkpoint. It reads as finished, which is exactly
  why it gets dropped - and once dropped, the leftover branch/worktree/scraper
  on disk is indistinguishable from work in progress, so the next cold session
  re-proposes it. Record the reason, not just the verdict: "UT: DOPL records
  route CLOSED, R156-1-106 exempts addresses/phones/emails and the request form
  forbids automated lists (2026-08)" survives a cold read; "UT: closed" does
  not.
- NEVER prune, age out, or delete anything under `State_Archive/`. This skill also runs
  unattended when the 120K-token reminder fires, and nothing on that path may delete a file.
- Be specific enough that a fresh session needs no re-discovery: paths, flags,
  IDs, exact commands.
- After a reminder-triggered checkpoint, resume the interrupted task immediately.
