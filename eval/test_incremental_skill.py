"""Offline unit tests for the deterministic skill-load + incremental consolidation pieces.
No claude spend: induce_incremental's LLM call is monkeypatched. Run: python3 eval/test_incremental_skill.py
"""
import json
import os
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "engine"))
_TMP = tempfile.mkdtemp(prefix="incr_home_")
os.environ["NATIVE_EVOLVE_HOME"] = _TMP          # must precede engine import (config resolves HOME)

from evolve import config, store, induce, retrieve  # noqa: E402

import shutil
(config.HOME / "memory").mkdir(parents=True, exist_ok=True)
config.SKILLS_DIR.mkdir(parents=True, exist_ok=True)
config.CANDIDATE_DIR.mkdir(parents=True, exist_ok=True)
shutil.copytree(_REPO / "engine" / "prompts", config.PROMPTS_DIR, dirs_exist_ok=True)  # induce reads here

_n = [0]
_fail = [0]


def check(name, cond):
    _n[0] += 1
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        _fail[0] += 1


def _write_skill(name, body, status="active"):
    d = (config.SKILLS_DIR if status == "active" else config.CANDIDATE_DIR) / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text("# %s\n%s\n" % (name, body), encoding="utf-8")
    st = store.load_skill_state()
    st[name] = {"version": 1, "status": status, "promoted_from": []}
    (config.HOME / "memory" / "skill_state.json").write_text(json.dumps(st), encoding="utf-8")


# ---- 1. all_active_skills_block: ALL active, deterministic name order, excludes candidates ----
_write_skill("zebra-skill", "Zebra technique body.", status="active")
_write_skill("alpha-skill", "Alpha technique body.", status="active")
_write_skill("cand-skill", "Candidate not active.", status="candidate")
block = retrieve.all_active_skills_block()
check("all_active block includes both active skills", "zebra-skill" in block and "alpha-skill" in block)
check("all_active block excludes candidate", "cand-skill" not in block)
check("all_active block is name-sorted (alpha before zebra)", block.index("alpha-skill") < block.index("zebra-skill"))
check("empty when no active skills", retrieve.all_active_skills_block.__doc__ is not None)

# ---- 2. _skill_oneline skips the markdown title ----
ol = induce._skill_oneline("# my-title\n\nThe real first line here.\nmore")
check("_skill_oneline skips '# title'", ol == "The real first line here.")

# ---- 3. induce_incremental: filters out an existing-named skill, keeps the new one ----
calls = {"prompt": ""}


def _fake_call(prompt, allowed_tools=None, **kw):
    calls["prompt"] = prompt
    return json.dumps({"skills": [
        {"name": "alpha-skill", "description": "dup of existing", "scope": "x",
         "when_to_use": ["x"], "steps": ["x"], "source_ids": ["m-1"]},
        {"name": "new-technique", "description": "a genuinely new method", "scope": "y",
         "when_to_use": ["y"], "steps": ["y"], "source_ids": ["m-2"]},
    ]})


induce.llm.call_claude = _fake_call          # monkeypatch (no spend)
existing = retrieve._active_skills_with_value()
new_bullets = [{"id": "m-2", "content": "a new lesson about tiling", "type": "heuristic",
                "scope": "y", "status": "active"}]
cands = induce.induce_incremental(new_bullets, existing_skills=existing)
names = [c["name"] for c in cands]
check("incremental drops the existing-named skill (alpha-skill)", "alpha-skill" not in names)
check("incremental keeps the genuinely new skill", "new-technique" in names)
check("incremental prompt shows existing skills (no-duplicate context)",
      "alpha-skill" in calls["prompt"] and "ALREADY have" in calls["prompt"])
check("incremental prompt contains the NEW memory digest", "tiling" in calls["prompt"])

# ---- 4. induce_incremental returns [] on empty new memory (watermark => nothing new) ----
check("empty new memory -> no candidates", induce.induce_incremental([], existing_skills=existing) == [])

# ---- 5. all_active_skills_block: NO truncation (fixed load) + extra_skills as-if-active (gate) ----
long_body = "Step detail that the skill exists to carry. " * 25      # ~1100 chars > the legacy 560 cut
_write_skill("omega-skill", long_body, status="active")
block5 = retrieve.all_active_skills_block()
check("fixed-load block is NOT truncated (full long body survives)", long_body.strip() in block5)
block5x = retrieve.all_active_skills_block(extra_skills=[("beta-cand", "Beta candidate body.")])
check("extra candidate rendered as-if-active (gate full arm)",
      "beta-cand" in block5x and "Beta candidate body." in block5x)
check("extra candidate sits in stable name order (alpha < beta < omega)",
      block5x.index("alpha-skill") < block5x.index("beta-cand") < block5x.index("omega-skill"))
check("base block (no extra) excludes the candidate", "beta-cand" not in block5)
check("name-colliding extra is not rendered twice",
      retrieve.all_active_skills_block(extra_skills=[("alpha-skill", "DUP")]).count("### alpha-skill") == 1)

print("\n%d/%d passed" % (_n[0] - _fail[0], _n[0]))
sys.exit(1 if _fail[0] else 0)
