"""Tests for vault_caps.py -- the single home for every vault document cap.

Design: ~/.claude/docs/specs/2026-08-21-vault-caps-backend-design.md (D5).

Unlike test_vault_gate.py and test_inject_state.py these run in-process. There
is nothing to isolate: vault_caps touches no filesystem, no env, no network. It
answers two questions about a (path, text) pair and nothing else.
"""

import sys

sys.stdout.reconfigure(encoding="utf-8")

import vault_caps as vc

r = []


def check(label, ok, why=""):
    r.append(bool(ok))
    print("%-4s %s" % ("PASS" if ok else "FAIL", label))
    if not ok and why:
        print("       " + why)


def lines(n, width=6):
    """n lines, no trailing newline, so splitlines() and wc -l agree."""
    return "\n".join("x" * width for _ in range(n))


# ---------------------------------------------------------------- classify

check("Map suffix classifies as map",
      vc.classify("50_Carreer/Dev_Sessions/project-b_Map.md") == "map")
check("current_state suffix classifies as state",
      vc.classify("50_Carreer/Dev_Sessions/project-b_current_state.md") == "state")
check("Playbook suffix classifies as playbook",
      vc.classify("50_Carreer/Dev_Sessions/project-b_Playbook.md") == "playbook")
check("a dated session log classifies as note",
      vc.classify("50_Carreer/Dev_Sessions/2026-08-21-project-b.md") == "note")
check("a guardrail note classifies as note",
      vc.classify("50_Carreer/Dev_Sessions/Guardrails/project-b/x.md") == "note")

check("classification is case-insensitive",
      vc.classify("50_carreer/dev_sessions/Demo_MAP.md") == "map")
check("backslash paths classify the same",
      vc.classify(r"50_Carreer\Dev_Sessions\demo_Map.md") == "map")
check("a project name containing 'map' is not a Map",
      vc.classify("50_Carreer/Dev_Sessions/roadmap_current_state.md") == "state")
check("empty path classifies as note, never crashes",
      vc.classify("") == "note")
check("None path classifies as note, never crashes",
      vc.classify(None) == "note")

# An archive slice is a VERBATIM copy of a doc that was at or over cap. Capping
# it would block the very step that brings the live doc back under cap -- the
# archive write would fail, and D7's eviction could never complete.
check("a Map archived under State_Archive is uncapped",
      vc.classify(
          "50_Carreer/Dev_Sessions/State_Archive/project-b/project-b_Map.md"
      ) == "note",
      "archives are verbatim copies; capping one blocks eviction itself")
check("a state snapshot under State_Archive is uncapped",
      vc.classify(
          "50_Carreer/Dev_Sessions/State_Archive/project-b/2026-08-21-2026.md"
      ) == "note")
check("a Memory mirror is uncapped",
      vc.classify("50_Carreer/Dev_Sessions/Memory/project-b/project/x.md") == "note")


# ----------------------------------------------------------------- measure

check("measure counts lines the way wc -l does",
      vc.measure("a\nb\nc\n")[0] == 3,
      "a trailing newline must not invent a phantom last line")
check("measure counts an unterminated last line",
      vc.measure("a\nb\nc")[0] == 3)
check("measure counts real utf-8 bytes, not characters",
      vc.measure("—")[1] == 3,
      "an em dash is 1 char but 3 bytes; a byte cap must mean bytes")
check("measure of empty text is zero lines",
      vc.measure("")[0] == 0)


# -------------------------------------------------------------------- caps

check("map cap is 150 lines", vc.cap_for("x_Map.md").lines == 150)
check("state cap is 150 lines", vc.cap_for("x_current_state.md").lines == 150)
check("playbook cap is 400 lines", vc.cap_for("x_Playbook.md").lines == 400)
check("playbook cap is 40000 bytes", vc.cap_for("x_Playbook.md").max_bytes == 40000)
check("a note has no line cap", vc.cap_for("x.md").lines is None)

check("map and state are enforced by BLOCKING",
      vc.cap_for("x_Map.md").action == "block"
      and vc.cap_for("x_current_state.md").action == "block")
check("a playbook is only ever NAGGED",
      vc.cap_for("x_Playbook.md").action == "nag",
      "refusing a one-line lesson punishes the wrong action")


# --------------------------------------------------------------- over_cap

M = "50_Carreer/Dev_Sessions/demo_Map.md"
P = "50_Carreer/Dev_Sessions/demo_Playbook.md"

check("a map at exactly the cap is allowed", vc.over_cap(M, lines(150)) is None)
check("a map one line over the cap is reported", vc.over_cap(M, lines(151)))
check("the report names both the measure and the cap",
      "151" in vc.over_cap(M, lines(151)) and "150" in vc.over_cap(M, lines(151)),
      "'too big' is not actionable; the numbers are")
check("a map over the byte cap is reported even when short",
      vc.over_cap(M, "x" * 12001))
check("a note is never over cap", vc.over_cap("50_Carreer/Dev_Sessions/log.md",
                                              lines(5000)) is None)

check("a playbook at 400 lines is allowed", vc.over_cap(P, lines(400)) is None)
check("a playbook at 401 lines is reported", vc.over_cap(P, lines(401)))
check("a playbook under 400 lines but over 40000 bytes is reported",
      vc.over_cap(P, lines(100, width=500)),
      "400 lines OR 40000 bytes, whichever trips first")


# ----------------------------------------------------------- over_refusal

# The measured reason this exists: project-b_Map.md is 153 lines and
# project-c_Map.md is 158, both already partitioned and both believed
# compliant. Blocking a write is cheap and recoverable; refusing to inject
# silently costs a cold session the Map it came for.
check("a map over cap but under the refusal threshold still injects",
      vc.over_cap(M, lines(153)) and vc.over_refusal(M, lines(153)) is None,
      "153 lines: over cap, must NOT be refused")
check("project-c' 158-line Map still injects",
      vc.over_refusal(M, lines(158)) is None)
check("a map at the refusal threshold still injects",
      vc.over_refusal(M, lines(200)) is None)
check("a map past the refusal threshold is refused",
      vc.over_refusal(M, lines(201)))
check("the refusal names the measure and the threshold",
      "201" in vc.over_refusal(M, lines(201))
      and "200" in vc.over_refusal(M, lines(201)))
check("a map over the byte cap is refused, not merely reported",
      vc.over_refusal(M, "x" * 12001))
check("a note is never refused", vc.over_refusal("50_Carreer/Dev_Sessions/l.md",
                                                 lines(5000)) is None)
check("a playbook is never refused, however fat",
      vc.over_refusal(P, lines(5000)) is None,
      "nothing injects Playbooks; a refusal threshold would be a dead number")


# ------------------------------------------------------- one number, once

check("every declared kind has a cap entry",
      set(vc.CAPS) == {"map", "state", "playbook", "note"})
check("the eviction target is 75% of the playbook cap, both dimensions",
      vc.evict_target(P) == (300, 30_000))
check("the eviction target is DERIVED, never a second declared number",
      vc.evict_target(P) == (int(vc.CAPS["playbook"].lines * vc.EVICT_TO),
                             int(vc.CAPS["playbook"].max_bytes * vc.EVICT_TO)),
      "raise the cap and the target must follow it, or this module has drifted "
      "from itself")
check("an uncapped kind targets infinity, not None",
      vc.evict_target("50_Carreer/Dev_Sessions/log.md") == (float("inf"),
                                                            float("inf")),
      "every caller compares against both numbers; a None makes each one "
      "invent its own 'no limit'")

check("the index budget lives here too, not in inject_state",
      isinstance(vc.INDEX_MAX_BYTES, int) and vc.INDEX_MAX_BYTES > 0)

print("\n%d/%d passed" % (sum(r), len(r)))
sys.exit(0 if all(r) else 1)
