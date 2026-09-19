import atexit
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid

sys.stdout.reconfigure(encoding="utf-8")
HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vault_gate.py")

TAGGED = "---\ntags:\n  - lesson\n---\n# Note\nbody"
UNTAGGED = "# Note\nbody"

# A path that does NOT exist on disk, so the hook falls back to transcript
# content. Using a real note here would be wrong: the hook now judges the file
# as it stands NOW, so a note that has since been tagged correctly passes.
GHOST = "50_Carreer/Dev_Sessions/2026-08-15-ghost-not-on-disk.md"
# A note the TEST controls, written into a throwaway vault root. The disk
# check's regression case -- written untagged, tagged afterwards by a
# vault_patch this hook does not watch -- used to pin a real note in the live
# vault to get at this code path.
ON_DISK = "50_Carreer/Dev_Sessions/2026-08-21-disk-check.md"


def temp_vault(files):
    """A throwaway vault root, so disk-check cases stop pinning real notes.

    The hook judges a note as it stands on disk NOW, not as it was first
    written. Proving that needs a file the test controls. Before
    CLAUDE_VAULT_ROOT existed the only available lever was a real note in the
    live vault, which meant the fixture would rot silently the day that note
    was archived -- a test that passes for the wrong reason.
    """
    root = tempfile.mkdtemp(prefix="vaultgate-")
    atexit.register(shutil.rmtree, root, True)
    for rel, content in files.items():
        full = os.path.join(root, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with io.open(full, "w", encoding="utf-8") as f:
            f.write(content)
    return root

# Every Stop-path run writes a nag-once sentinel. Until CLAUDE_STATE_DIR
# existed these landed in the REAL ~/.claude -- 419 of them had piled up by
# 2026-08-22, and the suite itself was the largest contributor, adding roughly
# one per Stop test per run. Tests must not litter the directory they are
# testing the hygiene of.
SENTINELS = tempfile.mkdtemp(prefix="vaultgate-sentinels-")
atexit.register(shutil.rmtree, SENTINELS, True)


def tool_use(name, inp):
    return {"message": {"content": [{"type": "tool_use", "name": name, "input": inp}]}}


def run(records, label, expect_block, expect_contains=None, vault=None):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    payload = {
        "session_id": uuid.uuid4().hex,   # fresh id so the sentinel never suppresses
        "transcript_path": path,
        "cwd": os.getcwd(),
    }
    env = dict(os.environ)
    if vault:
        env["CLAUDE_VAULT_ROOT"] = vault
    else:
        env.pop("CLAUDE_VAULT_ROOT", None)
    env["CLAUDE_STATE_DIR"] = SENTINELS
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                       capture_output=True, text=True, env=env)
    os.unlink(path)
    out = (p.stdout or "").strip()
    blocked = '"decision": "block"' in out
    # Search the DECODED reason as well as the raw stdout. The reason is
    # JSON-encoded, so any assertion containing a double quote -- like the
    # vault_patch target form ["<H1>", "DO"] -- is on the wire as \" and can
    # never match the raw text. Asserting on the wire encoding instead of the
    # payload is how a test starts checking the transport.
    try:
        reason = json.loads(out).get("reason", "")
    except ValueError:
        reason = ""
    ok = blocked == expect_block
    if ok and expect_contains:
        ok = expect_contains in out or expect_contains in reason
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        print(f"        expected block={expect_block} got={blocked}")
        print(f"        stdout: {out[:300]}")
        print(f"        stderr: {(p.stderr or '')[:300]}")
    return ok


W = "mcp__obsidian__vault_write"
r = []

r.append(run([tool_use(W, {"path": GHOST, "content": UNTAGGED})],
             "untagged session note -> BLOCK", True, "[missing]"))

r.append(run([tool_use(W, {"path": GHOST, "content": TAGGED})],
             "tagged session note -> pass", False))

# Disk beats transcript in BOTH directions -- it is one code path, but only
# the forgiving half was reachable before CLAUDE_VAULT_ROOT existed. The
# strict half matters more: a note written tagged and then broken on disk is
# exactly the shape of the 2026-08-21 root-prepend failure.
r.append(run([tool_use(W, {"path": ON_DISK, "content": UNTAGGED})],
             "written untagged, tagged on disk since -> pass (disk wins)", False,
             vault=temp_vault({ON_DISK: TAGGED})))

r.append(run([tool_use(W, {"path": ON_DISK, "content": TAGGED})],
             "written tagged, untagged on disk now -> BLOCK (disk wins both ways)",
             True, "[missing]", vault=temp_vault({ON_DISK: UNTAGGED})))

# Vault unreachable: degrade to judging the transcript, never to passing
# everything. A gate that silently stops gating is worse than no gate.
r.append(run([tool_use(W, {"path": ON_DISK, "content": UNTAGGED})],
             "note absent from vault -> BLOCK on transcript (fallback)", True,
             "[missing]", vault=temp_vault({})))

r.append(run([tool_use(W, {"path": ON_DISK, "content": TAGGED})],
             "note absent from vault, written tagged -> pass (fallback)", False,
             vault=temp_vault({})))

r.append(run([tool_use(W, {
    "path": "50_Carreer/Dev_Sessions/State_Archive/project-b/2026-08-15-1745.md",
    "content": UNTAGGED})],
    "State_Archive verbatim copy, untagged -> pass (excluded)", False))

r.append(run([tool_use(W, {
    "path": "50_Carreer/Dev_Sessions/Memory/project-b/project/x.md",
    "content": "---\nname: x\n---\nbody"})],
    "Memory mirror, different schema -> pass (excluded)", False))

r.append(run([tool_use(W, {"path": "50_Carreer/Dev_Sessions/_Tag_Dictionary.md",
                           "content": UNTAGGED})],
             "_Tag_Dictionary itself -> pass (excluded)", False))

r.append(run([tool_use(W, {"path": GHOST, "content": TAGGED}),
              tool_use("Bash", {"command": "git commit -m x"})],
             "commits + tagged note, no Map -> BLOCK (map reminder)", True,
             "never updated"))

r.append(run([tool_use(W, {"path": GHOST, "content": TAGGED}),
              tool_use(W, {"path": "50_Carreer/Dev_Sessions/project-b_Map.md",
                           "content": TAGGED}),
              tool_use("Bash", {"command": "git commit -m x"})],
             "commits + tagged note + Map written -> pass", False))

r.append(run([], "empty transcript -> pass", False))

r.append(run([tool_use("Bash", {"command": "git commit -m x"})],
             "commits but no vault writes -> pass (no note to gate)", False))

r.append(run([tool_use(W, {"path": "projects/somewhere-else.md",
                           "content": UNTAGGED})],
             "note outside Dev_Sessions -> pass (out of scope)", False))

# The 2026-08-15 incident: vault_patch handed a `value` array serialises tags
# as a quoted string. Obsidian never indexes it, so the convention is enforced
# in letter while silently not working -- worse than no tags, because it looks
# done. Presence alone was NOT a sufficient check.
MISTYPED = "---\ntags: '[\"status-change\", \"supply\"]'\n---\nbody"
DOUBLE_Q = '---\ntags: "[a, b]"\n---\nbody'
BARE = "---\ntags: supply\n---\nbody"
FLOW = "---\ntags: [supply, bug]\n---\nbody"

r.append(run([tool_use(W, {"path": GHOST, "content": MISTYPED})],
             "tags as single-quoted string -> BLOCK (mistyped)", True, "mistyped"))
r.append(run([tool_use(W, {"path": GHOST, "content": DOUBLE_Q})],
             "tags as double-quoted string -> BLOCK (mistyped)", True, "mistyped"))
r.append(run([tool_use(W, {"path": GHOST, "content": BARE})],
             "tags as bare scalar -> BLOCK (mistyped)", True, "mistyped"))
r.append(run([tool_use(W, {"path": GHOST, "content": FLOW})],
             "tags as unquoted flow list -> pass", False))

# D8: frontmatter must begin at BYTE 0. Obsidian ignores a block that starts on
# line 2, so the note passes `cat`, vault_patch returns OK, and no tag query
# ever returns it. Three real Playbooks failed exactly this way on 2026-08-21 --
# PersonalWorkflow, UndineJewelry and ProjPitchAstorga -- each because the file
# already began with a blank line and the root-prepend landed underneath it.
# Reporting that as `missing` sends the author to add tags that are already
# there, so it gets its own state.
OFFSET = '\n---\ntags:\n  - lesson\n---\n# Note\nbody'
OFFSET_WS = '  \n\n---\ntags:\n  - lesson\n---\n# Note\nbody'

r.append(run([tool_use(W, {"path": GHOST, "content": OFFSET})],
             "frontmatter on line 2 -> BLOCK as [offset], not [missing]", True,
             "[offset]"))

r.append(run([tool_use(W, {"path": GHOST, "content": OFFSET_WS})],
             "frontmatter after blank lines -> BLOCK as [offset]", True, "[offset]"))

r.append(run([tool_use(W, {"path": GHOST, "content": OFFSET})],
             "the offset message names byte 0, so the fix is obvious", True,
             "byte 0"))

r.append(run([tool_use(W, {"path": GHOST, "content": TAGGED})],
             "frontmatter at byte 0 -> pass (unchanged)", False))

r.append(run([tool_use(W, {"path": ON_DISK, "content": TAGGED})],
             "written at byte 0, offset on disk now -> BLOCK", True, "[offset]",
             vault=temp_vault({ON_DISK: OFFSET})))

# ── D6: write-time cap enforcement (PreToolUse) ──────────────────────────────
# Map and current_state are written WHOLESALE, so the size is knowable before
# the write lands. That makes a block cheap and fully recoverable -- the author
# trims and writes again -- which is why these are refused at the door instead
# of nagged about afterwards. The honour system was measured and failed:
# project-b_current_state.md was written at 171 lines against its own
# 150-line cap on 2026-08-21, by an agent that had read that cap minutes
# earlier.


def run_pre(tool_name, tool_input, label, expect_block, expect_contains=None):
    """Drive the PreToolUse half of the hook.

    Different payload shape AND a different block mechanism from the Stop half:
    PreToolUse blocks with exit 2 and the reason on STDERR, where Stop prints a
    block decision on stdout and exits 0. Asserting the wrong one would let a
    gate that silently stopped blocking still pass its own tests.
    """
    payload = {
        "session_id": uuid.uuid4().hex,
        "tool_name": tool_name,
        "tool_input": tool_input,
        "cwd": os.getcwd(),
    }
    env = dict(os.environ)
    env.pop("CLAUDE_VAULT_ROOT", None)
    env["CLAUDE_STATE_DIR"] = SENTINELS
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                       capture_output=True, text=True, env=env)
    err = (p.stderr or "").strip()
    blocked = p.returncode == 2
    ok = blocked == expect_block
    if ok and expect_contains:
        ok = expect_contains in err
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        print(f"        expected block={expect_block} got={blocked} rc={p.returncode}")
        print(f"        stderr: {err[:400]}")
        print(f"        stdout: {(p.stdout or '')[:200]}")
    return ok


def doc(lines):
    """A tagged document of EXACTLY `lines` lines, so only the cap is in play.

    Tagged on purpose: an untagged body would be a second reason to complain,
    and a test that can pass for either reason proves neither.
    """
    head = "---\ntags:\n  - lesson\n---\n"
    return head + "\n".join("body line %d" % i for i in range(lines - head.count("\n")))


MAP = "50_Carreer/Dev_Sessions/project-b_Map.md"
STATE = "50_Carreer/Dev_Sessions/project-b_current_state.md"
PLAYBOOK = "50_Carreer/Dev_Sessions/project-b_Playbook.md"
ARCHIVE = "50_Carreer/Dev_Sessions/State_Archive/project-b/Map_2026-08-21.md"
LOG = "50_Carreer/Dev_Sessions/2026-08-22-project-b.md"

# The measurement itself is vault_caps' job and is tested there. What these
# assert is that the gate consults it, on the right kinds, at the right moment.
r.append(run_pre(W, {"path": MAP, "content": doc(151)},
                 "Map at 151 lines -> BLOCK", True, "over the map cap of 150"))

r.append(run_pre(W, {"path": MAP, "content": doc(150)},
                 "Map at exactly 150 lines -> pass (the cap is inclusive)", False))

r.append(run_pre(W, {"path": STATE, "content": doc(171)},
                 "current_state at 171 lines, the real 2026-08-21 write -> BLOCK",
                 True, "over the state cap of 150"))

r.append(run_pre(W, {"path": STATE, "content": doc(150)},
                 "current_state at exactly 150 lines -> pass", False))

# Bytes are the other half of the cap and trip independently of lines: 44 long
# lines are a small document by line count and a large one to load.
r.append(run_pre(W, {"path": MAP,
                     "content": "---\ntags:\n  - lesson\n---\n"
                                + "\n".join(["x" * 400] * 40)},
                 "Map at 44 lines but ~16k bytes -> BLOCK on bytes", True,
                 "over the map byte cap of 12000"))

# A block that only says "too big" is not actionable. The whole point of the
# partition is that every evicted kind of content has somewhere to go.
r.append(run_pre(W, {"path": MAP, "content": doc(200)},
                 "the Map block names where the content should go instead", True,
                 "Guardrails/"))

r.append(run_pre(W, {"path": STATE, "content": doc(200)},
                 "the state block names State_Archive as the destination", True,
                 "State_Archive/"))

# A Playbook grows by vault_append, one bullet at a time. Refusing a one-line
# lesson because the file is already fat punishes the wrong action and teaches
# people to stop logging lessons -- so it is nagged on Stop, never blocked here.
r.append(run_pre(W, {"path": PLAYBOOK, "content": doc(500)},
                 "Playbook over cap -> pass (nagged on Stop, never blocked)", False))

# An archive slice is written precisely BECAUSE the live doc was over cap.
# Capping the copy would block the eviction that brings the original back under.
r.append(run_pre(W, {"path": ARCHIVE, "content": doc(400)},
                 "State_Archive slice over cap -> pass (else eviction is impossible)",
                 False))

r.append(run_pre(W, {"path": LOG, "content": doc(400)},
                 "dated session log at any size -> pass (notes are uncapped)", False))

r.append(run_pre(W, {"path": "projects/elsewhere/roadmap.md", "content": doc(400)},
                 "a file called roadmap.md -> pass (suffix match, not substring)",
                 False))

r.append(run_pre("Bash", {"command": "echo " + "x" * 30000},
                 "a huge Bash command -> pass (only vault_write is capped)", False))

r.append(run_pre("mcp__obsidian__vault_append", {"path": MAP, "content": doc(400)},
                 "vault_append to a Map -> pass (size on disk is not knowable here)",
                 False))

# The gate must fail OPEN on anything it does not understand. A hook that
# wedges a session is a worse outcome than a doc that slipped past its cap.
r.append(run_pre(W, {"path": MAP},
                 "vault_write with no content key -> pass (never wedge)", False))

r.append(run_pre(W, {},
                 "vault_write with empty tool_input -> pass (never wedge)", False))

# ── D9: duplicate canonical Playbook sections ────────────────────────────────
# vault_patch heading targets address from the TOP-LEVEL HEADING DOWN.
# `target: ["DO"]` fails with `could not resolve heading target` on a Playbook
# that has an H1, and the natural fallback -- append a fresh `## DO` -- is the
# mechanism behind 109 duplicate sections in project-a. The gate reports the damage
# from disk; the appending instruction states the target form so it stops being
# created in the first place.
#
# Measured on the live vault 2026-08-22, and both facts shape these cases:
#   - 3 of 7 Playbooks have NO H1 (PersonalWorkflow, ProjPitchAstorga,
#     UndineJewelry -- the same three D8 caught with offset frontmatter, same
#     root cause: a file that begins with a blank line). For those the correct
#     target is the bare ["DO"], so a message that only ever names the H1 form
#     sends the author hunting for a heading that does not exist.
#   - The dominant duplicate shape is a DATED PARENTHETICAL, not a bare repeat:
#     `## DON'T (2026-08-05, tooling session)` and six more like it. Matching
#     the literal string `## DO` would miss most of the real corpus.

PB_H1 = "---\ntags:\n  - lesson\n---\n# project-b - Playbook\n"


def pb(*headings, **kw):
    """A Playbook with one bullet under each heading given, H1 optional."""
    head = PB_H1 if kw.get("h1", True) else "---\ntags:\n  - lesson\n---\n"
    return head + "".join("\n## %s\n- a lesson\n" % h for h in headings)


CANON = ("DO", "DON'T", "WORKS", "FAILED")
CLEAN = pb(*CANON)
DUPED = pb(*(CANON + ("DO",)))
DATED = pb(*(CANON + ("DO (2026-08-17)",)))
NO_H1 = pb(*(CANON + ("DO",)), h1=False)

APPEND = "mcp__obsidian__vault_append"
PATCH = "mcp__obsidian__vault_patch"

r.append(run([tool_use(APPEND, {"path": PLAYBOOK, "content": "- x"})],
             "Playbook with `## DO` twice -> BLOCK (duplicate section)", True,
             "duplicate", vault=temp_vault({PLAYBOOK: DUPED})))

r.append(run([tool_use(APPEND, {"path": PLAYBOOK, "content": "- x"})],
             "Playbook with one of each heading -> pass", False,
             vault=temp_vault({PLAYBOOK: CLEAN})))

# `## DO (2026-08-17)` is not a second literal `## DO`, but it is the SAME
# failure: a fresh section appended because the target would not resolve.
# Seven variants of it are sitting in the live vault right now.
r.append(run([tool_use(APPEND, {"path": PLAYBOOK, "content": "- x"})],
             "`## DO (2026-08-17)` counts as a second DO -> BLOCK", True,
             "duplicate", vault=temp_vault({PLAYBOOK: DATED})))

# The report is only useful if it says how to append CORRECTLY next time.
r.append(run([tool_use(APPEND, {"path": PLAYBOOK, "content": "- x"})],
             "the report states the H1-down target form", True,
             '"DO"]', vault=temp_vault({PLAYBOOK: DUPED})))

r.append(run([tool_use(APPEND, {"path": PLAYBOOK, "content": "- x"})],
             "the report says a failed resolve means GO FIND the heading", True,
             "never append a new section", vault=temp_vault({PLAYBOOK: DUPED})))

# A Playbook with no H1 takes the bare ["DO"]. Naming only the H1 form there
# sends the author looking for a heading the file does not have -- which is
# how the wrong target got used in the first place.
r.append(run([tool_use(APPEND, {"path": PLAYBOOK, "content": "- x"})],
             "no H1 in the file -> the report names the bare target instead",
             True, "has no H1", vault=temp_vault({PLAYBOOK: NO_H1})))

# vault_append is how a Playbook actually grows, but a patch or a wholesale
# rewrite can duplicate a section just as easily.
r.append(run([tool_use(PATCH, {"path": PLAYBOOK, "content": "- x"})],
             "vault_patch to a Playbook is watched too -> BLOCK", True,
             "duplicate", vault=temp_vault({PLAYBOOK: DUPED})))

r.append(run([tool_use(W, {"path": PLAYBOOK, "content": DUPED})],
             "vault_write to a Playbook is watched too -> BLOCK", True,
             "duplicate", vault=temp_vault({PLAYBOOK: DUPED})))

# Scope: only what the session TOUCHED. Nagging every session about every
# Playbook in the vault is unactionable noise in a project that owns none of
# them -- the same rule the tag and Map checks already follow.
r.append(run([tool_use(APPEND, {"path": LOG, "content": "- x"})],
             "duplicated Playbook the session never touched -> pass (scope)",
             False, vault=temp_vault({PLAYBOOK: DUPED, LOG: TAGGED})))

# This is a DISK check. An append's content is a fragment, so judging the
# fragment would be meaningless, and guessing from an unreadable vault is how
# a gate starts reporting things that are not true.
r.append(run([tool_use(APPEND, {"path": PLAYBOOK, "content": "- x"})],
             "Playbook absent from disk -> pass (never guess from a fragment)",
             False, vault=temp_vault({})))

# ------------------------------------------------- D7: the over-cap Playbook

# FAT is a clean Playbook -- one of each heading -- that is simply too big. It
# has to be clean, or a pass/fail here could be the duplicate check firing.
FAT_ENTRIES = ["- 2026-08-%02d: lesson %d %s" % (i % 28 + 1, i, "x" * 300)
               for i in range(160)]
FAT = CLEAN + chr(10).join(FAT_ENTRIES) + chr(10)

r.append(run([tool_use(APPEND, {"path": PLAYBOOK, "content": "- x"})],
             "Playbook over its byte cap -> reported on Stop", True,
             "over the playbook byte cap", vault=temp_vault({PLAYBOOK: FAT})))

# The nag exists to be acted on. "Too big" hands the reader the same decision
# that produced a 123KB Playbook, and the cheapest guess is to delete something.
r.append(run([tool_use(APPEND, {"path": PLAYBOOK, "content": "- x"})],
             "the nag names the State_Archive destination", True,
             "State_Archive/project-b/Playbook_", vault=temp_vault({PLAYBOOK: FAT})))

r.append(run([tool_use(APPEND, {"path": PLAYBOOK, "content": "- x"})],
             "the nag names the 75%-of-cap target, not the cap", True,
             "30000 bytes", vault=temp_vault({PLAYBOOK: FAT})))

r.append(run([tool_use(APPEND, {"path": PLAYBOOK, "content": "- x"})],
             "the nag names the tool that plans the split", True,
             "playbook_evict.py", vault=temp_vault({PLAYBOOK: FAT})))

r.append(run([tool_use(APPEND, {"path": PLAYBOOK, "content": "- x"})],
             "the nag says oldest-first and verbatim, so nobody triages", True,
             "oldest first, moved whole", vault=temp_vault({PLAYBOOK: FAT})))

# The append itself is never refused. A cap that punishes writing a lesson
# down is a cap that stops lessons being written down.
r.append(run_pre(APPEND, {"path": PLAYBOOK, "content": "- a new lesson"},
                 "appending to an over-cap Playbook -> never blocked", False))

r.append(run([tool_use(APPEND, {"path": PLAYBOOK, "content": "- x"})],
             "a Playbook under cap -> no size nag", False,
             vault=temp_vault({PLAYBOOK: CLEAN})))

# Same scope rule as every other check here: only what the session touched.
r.append(run([tool_use(APPEND, {"path": LOG, "content": "- x"})],
             "an over-cap Playbook the session never touched -> pass (scope)",
             False, vault=temp_vault({PLAYBOOK: FAT, LOG: TAGGED})))

# A dated log has no cap. Only the three partitioned kinds do, and inventing
# one here would be a fourth number nobody declared.
r.append(run([tool_use(APPEND, {"path": LOG, "content": "- x"})],
             "a fat dated log -> pass (notes are uncapped)", False,
             vault=temp_vault({LOG: TAGGED + "x" * 60000})))


# Only Playbooks carry the four canonical sections. A dated log is free to
# repeat any heading it likes.
r.append(run([tool_use(APPEND, {"path": LOG, "content": "- x"})],
             "duplicate `## DO` in a dated log -> pass (not a Playbook)", False,
             vault=temp_vault({LOG: DUPED})))

_p = subprocess.run([sys.executable, HOOK], input="not json at all",
                    capture_output=True, text=True)
_ok = _p.returncode == 0
print(f"[{'PASS' if _ok else 'FAIL'}] malformed payload -> exit 0 (a broken gate "
      f"must never wedge a session)")
if not _ok:
    print(f"        rc={_p.returncode} stderr: {(_p.stderr or '')[:200]}")
r.append(_ok)



# ---------- GAP A: a Map or state grown by patch/append is nagged on Stop ----
#
# PreToolUse blocks only vault_write, because a wholesale write is the one
# moment the final size is knowable. That is correct, tested above, and
# unchanged here. The Stop half was supposed to catch the other two paths the
# way it already does for Playbooks -- but its size loop walked `playbooks`
# alone, so a Map or current_state grown by vault_patch or vault_append was
# measured in NEITHER place. skills/project-map/SKILL.md prescribes "In-place
# edits over full rewrites", so the documented normal path for /map was
# precisely the unwatched one, and project-a_Map.md reached 1,328 lines while
# everyone believed it was capped.

BIG_MAP = doc(151)
BIG_STATE = doc(151)
OK_MAP = doc(140)

r.append(run([tool_use(PATCH, {"path": MAP, "content": "- x"})],
             "vault_patch to an over-cap Map -> reported on Stop", True,
             "over the map cap", vault=temp_vault({MAP: BIG_MAP})))

r.append(run([tool_use(APPEND, {"path": STATE, "content": "- x"})],
             "vault_append to an over-cap current_state -> reported on Stop",
             True, "over the state cap", vault=temp_vault({STATE: BIG_STATE})))

# The nag has to be actionable, to the same standard as the Playbook one: a
# bare "too big" hands the reader the same guess that produced a 1,328-line
# Map, and the cheapest guess is to delete something that mattered.
r.append(run([tool_use(PATCH, {"path": MAP, "content": "- x"})],
             "the Map nag names where the content should GO", True,
             "POINTER INDEX", vault=temp_vault({MAP: BIG_MAP})))

r.append(run([tool_use(PATCH, {"path": MAP, "content": "- x"})],
             "a Map under cap touched by patch -> no nag", False,
             vault=temp_vault({MAP: OK_MAP})))

# Scope rule, the same one every other check here obeys: only what the session
# actually touched. An over-cap Map nobody edited is not this session's problem
# to fix, and nagging about it teaches people to ignore the nag.
r.append(run([tool_use(APPEND, {"path": PLAYBOOK, "content": "- x"})],
             "an over-cap Map the session never touched -> no nag", False,
             vault=temp_vault({MAP: BIG_MAP, PLAYBOOK: CLEAN})))

# The write-time contract is unchanged: a patch is never BLOCKED at the door,
# because its payload is a fragment and the resulting size is not knowable
# there. Nagging afterwards is the whole point of doing this on Stop.
r.append(run_pre(PATCH, {"path": MAP, "content": doc(400)},
                 "vault_patch to a Map -> still never blocked at the door",
                 False))


# ---------- a crash that says so, and sentinel hygiene ----------------------
#
# Two faults found by inspection on 2026-08-22. Neither was reachable by the
# suite as it stood, which is the point: run() asserts on the block decision
# alone, so a crashed hook and a clean pass were the SAME observable event.

import time


def run_raw(payload, label, check, vault=None, state_dir=None):
    """Run the hook and hand the whole CompletedProcess to `check`.

    run() hides stderr and the exit code because every test before these
    cared only about the block decision. Telling a CRASHED hook from a clean
    one needs both, so this exists rather than bending run() into a helper
    with two jobs and an ambiguous return.
    """
    env = dict(os.environ)
    for key, value in (("CLAUDE_VAULT_ROOT", vault),
                       ("CLAUDE_STATE_DIR", state_dir)):
        if value:
            env[key] = value
        else:
            env.pop(key, None)
    p = subprocess.run([sys.executable, HOOK], input=payload,
                       capture_output=True, text=True, env=env)
    ok = bool(check(p))
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        print(f"        rc={p.returncode}")
        print(f"        stdout: {(p.stdout or '')[:200]}")
        print(f"        stderr: {(p.stderr or '')[:300]}")
    return ok


# -- the bare `except Exception: sys.exit(0)` contract --
#
# The contract itself is RIGHT and stays: a wedged session is worse than a
# missed nag. What was wrong is that it was SILENT. A crash and a clean pass
# produced identical output, which is how a NameError survived two runs on
# 2026-08-22 before anyone noticed. Exit 0 still; just say what happened.

r.append(run_raw("not json at all",
                 "a crashed hook still exits 0 (contract unchanged)",
                 lambda p: p.returncode == 0))

r.append(run_raw("not json at all",
                 "a crashed hook SAYS SO instead of dying silently",
                 lambda p: "vault-gate" in (p.stderr or "")
                 and "internal error" in (p.stderr or "").lower()))

# The type alone ("ValueError") does not locate anything. The traceback is
# what turns "the gate stopped working" into a line number.
r.append(run_raw("not json at all",
                 "the crash report carries the traceback, not just the type",
                 lambda p: "Traceback" in (p.stderr or "")))

# The mirror case, and the one that gives the marker its meaning: if a clean
# run also chattered on stderr, the assertions above would prove nothing.
r.append(run_raw(json.dumps({"session_id": "clean-run", "transcript_path": ""}),
                 "a clean pass exits 0 with NOTHING on stderr",
                 lambda p: p.returncode == 0 and not (p.stderr or "").strip()))


# -- sentinel hygiene --
#
# The nag-once sentinel is written per session and never removed. 367 had
# accumulated in ~/.claude by 2026-08-22. Harmless one at a time, unbounded in
# aggregate, and they litter the directory a human opens to edit settings.

def sentinel_dir(files):
    """A throwaway state dir. `files` maps filename -> age in days."""
    d = tempfile.mkdtemp(prefix="vaultgate-state-")
    atexit.register(shutil.rmtree, d, True)
    now = time.time()
    for name, age_days in files.items():
        full = os.path.join(d, name)
        io.open(full, "w").close()
        stamp = now - age_days * 86400
        os.utime(full, (stamp, stamp))
    return d


SDIR = sentinel_dir({".vault_gate_ancient": 400,
                     ".vault_gate_recent": 1,
                     "settings.json": 400})
SWEEP = json.dumps({"session_id": "sweeper", "transcript_path": ""})

r.append(run_raw(SWEEP, "a stale sentinel is swept",
                 lambda p: not os.path.exists(
                     os.path.join(SDIR, ".vault_gate_ancient")),
                 state_dir=SDIR))

# The sweep must not re-arm the nag for a session still in flight, so recent
# sentinels are left exactly where they are.
r.append(run_raw(SWEEP, "a fresh sentinel survives the sweep",
                 lambda p: os.path.exists(
                     os.path.join(SDIR, ".vault_gate_recent")),
                 state_dir=SDIR))

# A sweep loose enough to delete settings.json would be a far worse bug than
# the litter it cleans. Prefix match, never a glob over the whole directory.
r.append(run_raw(SWEEP, "the sweep never touches a non-sentinel file",
                 lambda p: os.path.exists(os.path.join(SDIR, "settings.json")),
                 state_dir=SDIR))
print(f"\n{sum(r)}/{len(r)} passed")
sys.exit(0 if all(r) else 1)
