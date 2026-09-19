---
name: project-map
description: Update the durable project reference doc - a capped pointer index of objectives, status, architecture and guardrail entry points - when the project's actual shape changes. Use when the user runs /map, when a new objective/pipeline stage/major-initiative-status/data-location/guardrail is established or changed, when a new project starts, or when folding an old *_Project_Objectives.md into the new format. Always ends with a plain-text summary of the change.
---

# Project Map

Maintain the one durable "what is this project" doc per project, separate
from session handoff and narrative history. This is an in-place edit, not a
wholesale rewrite - most invocations touch one section, not the whole file.

**The Map is a CAPPED POINTER INDEX**, the same contract `current_state.md`
already runs on. It says where things live and who owns them; it does not hold
the things themselves. The cap is declared once, in
`~/.claude/hooks/vault_caps.py` (`CAPS["map"]`), and enforced at write time by
`vault_gate.py` — never restate the number here, or the two drift and the
skill's copy is the one that gets believed. Set by D1/D2 of
`~/.claude/docs/specs/2026-08-20-vault-doc-partition-design.md`, which is
GLOBAL - every project in `50_Carreer/Dev_Sessions/`, not one pilot.

**NOT in the Map, on purpose.** Each has a home. Writing them here is the
exact failure that grew one Map to 100,072 chars, past the read limit, with
superseded claims sitting next to the corrections that killed them:

| Content | Belongs in |
|---|---|
| Counts, sizes, "as of today" figures | the project's generated status artifact (`STATUS.md` and friends), pointed at from the Map |
| A lesson learned the hard way, war stories | `<ProjectName>_Playbook.md` |
| Session progress, blockers, parked work | `<ProjectName>_current_state.md` (via `/checkpoint`) |
| A guardrail's BODY | one atomic note in `Guardrails/<ProjectName>/<slug>.md` |
| Narrative debugging detail | the dated `YYYY-MM-DD-<ProjectName>.md` log |

## When to run this (unprompted, not just on /map)

Run it whenever something about the project's actual shape changes:
- A new objective, client, or scope decision is established or changed.
- A pipeline stage/automation/integration is added, wired up, paused, or removed.
- A major initiative's status shifts (planned -> in progress -> done -> blocked).
- A new key data location or script replaces/supersedes an old one.
- A new constraint or guardrail is discovered (do-not-touch resource, credit
  limit, external dependency). This writes an ATOMIC NOTE (step 6) - it
  touches the Map only if it opens a topic area the entry table lacks.
- The user explicitly runs `/map`.

Do NOT run it for: routine session progress (that's `current_state.md` via
`/checkpoint`), narrative debugging detail (that's the dated session logs),
or anything that doesn't change how someone would describe the project a
week from now.

## Steps

1. `<ProjectName>` = basename of the current working directory.
2. Vault target: `50_Carreer/Dev_Sessions/<ProjectName>_Map.md`.
3. `mcp__obsidian__vault_read` the target.
   - If it doesn't exist yet: this is a new project's first Map. Check for a
     legacy `50_Carreer/Dev_Sessions/<ProjectName>_Project_Objectives.md` -
     if one exists, fold its content into the new Map's Objectives section
     (don't keep maintaining the old file separately after this). Build the
     Map fresh using the template below.
   - If it exists: read it in full before editing. Locate the section(s)
     that the current change actually touches.
4. Edit **only the affected section(s)** - this is a targeted update, not a
   regeneration of the whole file. Use `mcp__obsidian__vault_patch` with
   `targetType: heading` when possible to replace just that section; fall
   back to a full `vault_write` only if the structure itself needs to change.
5. Template (sections, in order):

   # <ProjectName> - Project Map
   (Living reference doc. Updated only when the project's actual shape changes -
   not a session log. For in-flight session handoff see `<ProjectName>_current_state.md`.
   For narrative history see the dated `YYYY-MM-DD-<ProjectName>.md` logs.)

   **CAPPED and ENFORCED at write time by `vault_gate.py`; the limit itself
   lives in `~/.claude/hooks/vault_caps.py`. This is a POINTER INDEX.**
   Restate the NOT-HERE list here, in the file, so the next editor meets the
   contract before adding to it. Follow it with a "You want X -> read Y"
   routing table. Do NOT write a line count into the Map header — the gate
   reports the real one when it blocks, and a hand-copied number in a file
   nobody re-checks is exactly how the cap drifted into three values before.

   ## Objectives
   Client, primary goal, agreed scope, out-of-scope decisions, deliverable
   format. Stable - rarely changes after the project's first Map.

   ## Current Status
   Where each answer is generated, NOT the answer. One line per major
   initiative: its state, and the artifact or note that proves it. No
   figures - point at the script that regenerates them. Session-level
   detail belongs in current_state.md.

   ## How It's Built
   High-level architecture/pipeline overview, key script and data locations.
   Point into the project's own CLAUDE.md or docs for detail rather than
   duplicating it - this section should stay short even as the project grows.

   ## Constraints & Guardrails
   Bodies live in `Guardrails/<ProjectName>/`, one rule per note. This
   section is a table of ENTRY POINTS BY AREA linking `[[slug]]`, plus a
   pointer to the repo's `.claude/guardrails.json` if one exists. Never
   inline a rule body. Do not list every note either: the per-note index is
   GENERATED at session start by `~/.claude/hooks/inject_state.py` (rule
   names plus a tag manifest, never descriptions or bodies). Never
   hand-maintain that list - hand-maintained status docs are exactly what
   this partition was built to retire.

   ## Tags
   Project-specific tag vocabulary extending `_Tag_Dictionary.md`, one row
   per tag with its meaning. Resolved 2026-08-21: each Map keeps its own
   extension, and guardrail notes draw from both.

6. **A new guardrail does NOT get written into the Map.** Create
   `50_Carreer/Dev_Sessions/Guardrails/<ProjectName>/<slug>.md` via
   `mcp__obsidian__vault_write`. `<slug>` is kebab-case and names the rule
   itself (`never-clamp-a-difference`, `status-md-is-the-only-supply-number`).
   Frontmatter:

   ```
   ---
   tags:
     - guardrail
     - <topic tag from _Tag_Dictionary.md or the Map's ## Tags>
   status: live
   description: <one line, the rule itself, readable standing alone>
   supersedes: []
   ---
   ```

   Body: the rule, why it exists, and the evidence - date, commit, measured
   number - that settled it. Link related rules with `[[slug]]`.
   - **Superseding an existing rule:** set the old note's `status: superseded`
     and name what replaced it; put the old wording in the NEW note's
     `supersedes` list. Never edit a body in place to say the opposite.
     Adjacency as the only signal of which claim won is the rot the
     partition exists to kill.
   - **A decision NOT to do something gets `closed` in its tags.** Those
     notes are injected IN FULL at every session start. That is the whole
     point: a cold session must be told a track is dead before it reads the
     leftover worktree, scraper or branch on disk as live work.
   - Touch the Map only if the rule opens a NEW topic area its entry table
     doesn't already cover.
7. If this is a brand-new project's first Map, also update
   `50_Carreer/Dev_Sessions/_Projects_Index.md` (`mcp__obsidian__vault_read`
   then edit): add a row `| <ProjectName> | <one-line status> | [Map](<ProjectName>_Map.md) |`.
   If an existing "No Map yet" row exists for this project, replace it rather
   than adding a duplicate row.
8. If an existing project's status changed enough that its Index row is
   stale, update that row too.
9. **Always finish with a plain-text summary to the user** - which
   section(s) changed, which notes were created or superseded, and the
   one-line reason. This is not optional; do it every time, even for a small
   edit. Do not skip it because the change seems minor.

## Rules

- In-place edits over full rewrites. The Map should read as continuously
  maintained, not re-generated each time.
- **Cap breach: evict, don't truncate.** If an edit would push the Map over its
  cap, move a section's content to its proper home (the NOT-HERE table above)
  and leave a pointer. A Map cut at an arbitrary point reads as complete when it
  isn't. You do not need to know the number in advance: `vault_gate.py` blocks
  the write and names both the measured size and the limit.
- **No number in the Map that a script can generate.** Name the script and
  its output file instead. Counts go stale silently and have been acted on
  while wrong.
- Keep "How It's Built" pointing at the project's own docs rather than
  duplicating them - the Map will rot if it tries to be the architecture
  reference too.
- Never fabricate a status you haven't verified this session - if unsure
  whether an initiative is still accurate, say so in the summary rather than
  guessing.
- **Partitioning a fat legacy Map:** archive the pre-split file first with
  `mcp__obsidian__vault_copy` to
  `State_Archive/<ProjectName>_Map_pre-partition_<YYYY-MM-DD>.md` - never
  retype it, never `vault_move`. Then triage every evicted entry into
  exactly one of three verdicts (spec D3): LIVE INVARIANT -> atomic note;
  HISTORICAL LESSON -> Playbook; SUPERSEDED -> archived, NOT migrated.
  A mechanical split is rejected: it reproduces dead claims as confident
  notes. Do not delegate this triage to a subagent.
- All vault writes via the Obsidian MCP tool only, per global Obsidian
  Logging rules. After a batch of note writes, run a `search_query` on
  `tags.length == 0` - reading back a field you just wrote does not prove
  Obsidian parsed it.
