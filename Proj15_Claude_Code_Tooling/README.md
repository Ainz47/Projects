# Claude Code Tooling

The hooks, skills and guardrails I run Claude Code with every day, published with paths and project names stripped. The idea behind all of it: **a rule the agent has to remember will eventually be skipped, so the important ones are enforced by the harness.**

Most of these hooks exist because a convention was written down, then not applied. Each one turns a habit into a gate that runs whether or not the agent remembers.

## The hooks

| Hook | Event | What it enforces |
|---|---|---|
| `guardrails.py` | PreToolUse (every tool) | Deny and ask rules from a per-project `.claude/guardrails.json` plus an optional global one. Pure code, zero token cost unless a rule fires |
| `delivery_gate.py` | PreToolUse (Bash, PowerShell) | Blocks a project's delivery commands (send, push, publish) while any open flag says it must not ship. Returns a hard deny, because auto-approve mode silently accepts an "ask" |
| `vault_gate.py` | PreToolUse (note writes) and Stop | Keeps the notes vault from drifting: tags from a controlled vocabulary, no duplicate Playbook sections, size caps on state and map documents |
| `done_gate.py` | Stop | If the project declares a `verify` command, source changed this session and the command never ran, blocks the stop once with a reminder. Fails open on any internal error |
| `checkpoint_reminder.py` | PostToolUse | One reminder per session, at the context size where a checkpoint plus `/clear` actually saves usage |
| `inject_state.py` | SessionStart | Pushes the project's handoff state, every note tagged `closed` in full, and a generated index of the rest, so a cold session starts knowing what it must not re-propose |
| `precompact_preserve.py` | PreCompact | Tells the summariser what to keep verbatim |
| `hook_wiring.py` + `wiring.json` | (tooling) | Tracks the hook wiring in git and restores it, see below |
| `vault_caps.py`, `playbook_evict.py` | (libraries) | One place for every document cap and one classifier, and a tool that moves a Playbook's oldest entries to a dated archive |

`scripts/statusline.py` is the status line: model, project and live context size, with a warning zone.

## Skills

| Skill | What it does |
|---|---|
| `checkpoint` | Saves the session state to the project's handoff note before switching tools or clearing |
| `kickoff` | Scaffolds or retrofits a project: `CLAUDE.md`, `guardrails.json` with a verify command, an objectives note, optional CI (templates included) |
| `project-map` | Maintains a capped pointer index per project: objectives, status, architecture, guardrails |
| `retro` | Weekly review of the session logs, then proposes updates to instructions and guardrails as a diff to approve |

`example-CLAUDE.md` is a generic version of the global instructions these hooks back up.

## Design notes worth reading

- **Silent failure is the worst failure.** `~/.claude/settings.json` is the only place the hook wiring lives, and it is gitignored because it holds API keys. Rebuild the directory from a clone and every gate stops running with no error. So the wiring is tracked separately in `wiring.json`, `hook_wiring.py --apply` restores it, and `inject_state.py` warns at session start when live and tracked differ.
- **Two checks that can disagree, will.** A document size cap had been written in three places that had drifted apart, and nothing enforced it at write time. `vault_caps.py` now holds every number, and the write-time gate and the read-time refusal both import it.
- **Gates fail open, and say so.** A crashing hook exits 0 so it cannot wedge a session, and it reports its own traceback on stderr instead of dying silently.
- **Deny, not ask.** In auto-approve mode an "ask" decision is approved without a human, so anything that must stop, denies.

## Install

Copy `hooks/` and `skills/` into `~/.claude/`, then edit `hooks/wiring.json`. It uses `<HOME>` as a placeholder for your home directory, so replace that first. Merge the result into your `settings.json` with:

```bash
py ~/.claude/hooks/hook_wiring.py --apply
```

The vault location is `~/Documents/Vault/50_Carreer/Dev_Sessions` by default. Set `CLAUDE_VAULT_STATE_DIR` to point elsewhere.

## Tests

Each file is a self-contained script. Run one, or all:

```bash
cd hooks
py -m pip install -r requirements.txt   # pyyaml, used by inject_state and its tests
for f in test_*.py; do py -X utf8 "$f" || break; done
```

211 checks across five files (wiring 18, session-start injection 26, playbook eviction 50, vault caps 45, vault gate 72). The tests run hooks as real subprocesses against a temporary vault and an isolated state directory, so they never touch a real `~/.claude`.

## Not published

Personal scripts and skills unrelated to the workflow above, plus `settings.json`, `mcp.json` and credentials. The real `CLAUDE.md` holds project and client rules, so `example-CLAUDE.md` stands in for it.
