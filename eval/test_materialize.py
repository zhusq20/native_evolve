"""Offline validation of the NATIVE-retrieval foundation (materialize.py + the PostToolUse hook).
ZERO claude spend. Asserts:
  (1) materialize_into renders active distilled bullets as mem-* skills + past-success episodes as
      ex-* skills; skips deprecated bullets and failed episodes; SKILL.md frontmatter parses; names
      are unique slugs matching their dir.
  (2) description uses `scope` when present, falls back to content; YAML-quoted so a ':' is safe.
  (3) cap keeps the most net-helpful; regeneration clears stale mem-*/ex-* (no dup, no resurrection).
  (4) invoked_to_bullet_ids round-trips mem-<id> -> id and ignores ex-/promoted; match_invoked finds
      a materialized name inside a logged hook event.
  (5) active promoted skills are linked into the catalog.
  (6) the PostToolUse hook logs a Skill invocation (and ignores non-Skill tools).
Run: python3 eval/test_materialize.py
"""
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parent.parent
_TMP_HOME = tempfile.mkdtemp(prefix="mat_home_")
os.environ["NATIVE_EVOLVE_HOME"] = _TMP_HOME       # must precede the engine import (config resolves HOME)
sys.path.insert(0, str(REPO / "engine"))
from evolve import materialize, store, config       # noqa: E402

RESULTS = []
HOOK = REPO / "engine" / "adapters" / "claude_code" / "hook_post_tool_use.py"


def check(name, cond):
    RESULTS.append(bool(cond))
    print(("ok   " if cond else "FAIL ") + name)


def _fm(skills_dir, name):
    """Parse a SKILL.md's frontmatter name+description without a yaml dep."""
    md = (pathlib.Path(skills_dir) / name / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", md, re.S)
    if not m:
        return None, None, md
    fm = m.group(1)
    nm = re.search(r"^name:\s*(.+)$", fm, re.M)
    dm = re.search(r"^description:\s*(.+)$", fm, re.M)
    return (nm.group(1).strip() if nm else None), (dm.group(1).strip() if dm else None), m.group(2)


BULLETS = [
    {"id": "m-0001", "content": "Write the COMPUTED literal, never a formula string.",
     "scope": "spreadsheet cells: when asked for a value", "status": "active", "helpful": 5, "harmful": 0},
    {"id": "m-0002", "content": "Answer with the exact minimal span only.",
     "scope": "", "status": "active", "helpful": 2, "harmful": 0},          # empty scope -> content fallback
    {"id": "m-0003", "content": "Group objects by shape: pick the frequency-mode group.",
     "scope": "ARC: selection by shape family", "status": "active", "helpful": 9, "harmful": 1},
    {"id": "m-0009", "content": "deprecated lesson", "scope": "x", "status": "deprecated",
     "helpful": 0, "harmful": 4},
]
EPS = [
    {"id": "t1", "question": "what year did X happen", "solution": "1969", "passed": True, "signature": ""},
    {"id": "t2", "question": "compute the sum", "solution": "def f(): return 42", "passed": True},
    {"id": "t3", "question": "failed one", "solution": "nope", "passed": False},
]


def test_basic_render():
    d = tempfile.mkdtemp(prefix="cat_")
    man = materialize.materialize_into(d, items=BULLETS, episodes=EPS, include_promoted=False)
    dirs = sorted(os.listdir(d))
    mem = [x for x in dirs if x.startswith("mem-")]
    ex = [x for x in dirs if x.startswith("ex-")]
    check("3 active bullets -> 3 mem skills (deprecated skipped)", mem == ["mem-m-0001", "mem-m-0002", "mem-m-0003"])
    check("2 passed episodes -> 2 ex skills (failed skipped)", len(ex) == 2)
    check("manifest covers all written units", len(man) == 5 and all(e["kind"] in ("mem", "ex") for e in man))
    # frontmatter parses; name matches dir; unique
    names = []
    ok_fm = True
    for nm in mem + ex:
        fnm, desc, _ = _fm(d, nm)
        ok_fm = ok_fm and (fnm == nm) and bool(desc)
        names.append(fnm)
    check("every SKILL.md frontmatter parses, name==dir", ok_fm)
    check("names unique", len(names) == len(set(names)))
    # description: scope when present, content when scope empty
    _, d1, _ = _fm(d, "mem-m-0001")
    _, d2, _ = _fm(d, "mem-m-0002")
    check("scope used as description when present", "spreadsheet cells" in d1)
    check("content fallback when scope empty", "exact minimal span" in d2)
    check("description is YAML-quoted (':' safe)", d1.startswith('"') and d1.endswith('"'))


def test_cap_and_regen():
    d = tempfile.mkdtemp(prefix="cap_")
    materialize.materialize_into(d, items=BULLETS, episodes=[], include_promoted=False, cap=2)
    mem = sorted(x for x in os.listdir(d) if x.startswith("mem-"))
    # net-helpful: m-0003(=8) > m-0001(=5) > m-0002(=2) -> top-2 keeps 0003,0001
    check("cap keeps the most net-helpful", mem == ["mem-m-0001", "mem-m-0003"])
    # regenerate with a different set -> stale cleared, no resurrection of dropped/deprecated
    materialize.materialize_into(d, items=BULLETS[:1], episodes=[], include_promoted=False)
    mem2 = sorted(x for x in os.listdir(d) if x.startswith("mem-"))
    check("regeneration clears stale mem-*", mem2 == ["mem-m-0001"])


def test_attribution():
    n1, _ = materialize.bullet_skill(BULLETS[0])
    nex, _ = materialize.episode_skill(EPS[0], 0)
    check("invoked_to_bullet_ids round-trips mem-<id> -> id",
          materialize.invoked_to_bullet_ids([n1]) == ["m-0001"])
    check("ex-/promoted names are not credited",
          materialize.invoked_to_bullet_ids([nex, "self-verify-and-repair"]) == [])
    logged = json.dumps({"tool": "Skill", "tool_input": {"command": n1}})
    check("match_invoked finds a materialized name in a logged event",
          materialize.match_invoked(logged, [n1, "mem-m-0002"]) == [n1])


def test_promoted_link():
    # create an ACTIVE promoted skill in the (tmp) home + skill_state, then materialize with linking
    sk = config.SKILLS_DIR / "demo-skill"
    sk.mkdir(parents=True, exist_ok=True)
    (sk / "SKILL.md").write_text("---\nname: demo-skill\ndescription: demo\n---\n\nbody\n", encoding="utf-8")
    store.save_skill_state({"demo-skill": {"status": "active", "version": 1}})
    d = tempfile.mkdtemp(prefix="prom_")
    man = materialize.materialize_into(d, items=BULLETS[:1], episodes=[], include_promoted=True)
    check("active promoted skill linked into catalog",
          "demo-skill" in os.listdir(d) and (pathlib.Path(d) / "demo-skill" / "SKILL.md").exists())
    check("promoted appears in manifest", any(e["kind"] == "promoted" and e["name"] == "demo-skill" for e in man))


def test_hook():
    log = os.path.join(tempfile.mkdtemp(prefix="hook_"), ".invoked")
    skill_evt = json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Skill",
                            "tool_input": {"command": "mem-m-0003"}})
    subprocess.run([sys.executable, str(HOOK), log], input=skill_evt, text=True, timeout=30)
    other_evt = json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Bash",
                            "tool_input": {"command": "ls"}})
    subprocess.run([sys.executable, str(HOOK), log], input=other_evt, text=True, timeout=30)
    txt = pathlib.Path(log).read_text(encoding="utf-8") if os.path.exists(log) else ""
    check("hook logs the Skill invocation", "mem-m-0003" in txt)
    check("hook ignores non-Skill tools", txt.count("\n") == 1 and "ls" not in txt)


if __name__ == "__main__":
    test_basic_render()
    test_cap_and_regen()
    test_attribution()
    test_promoted_link()
    test_hook()
    n = len(RESULTS)
    p = sum(RESULTS)
    print("\n%d/%d passed" % (p, n))
    sys.exit(0 if p == n else 1)
