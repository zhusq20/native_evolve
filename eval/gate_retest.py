"""Targeted precision-law-FOR-GATING re-test (the discriminating ACTIVATE case).

The clean 1-seed run (results/dyck_gateAB_clean/) induced a NEUTRAL skill, so both gates correctly
rejected — it never tested whether the reffree gate PRESERVES a genuine lift. This loads
session-13's ALREADY-ACTIVATED dyck candidate (`dyck-language-stack-algorithm`, gold rescued=4/broke=2
in that run) on top of its acquired episodic+distilled base, and runs the gate A/B (paired_ab_multi)
with BOTH judges on the SAME val answers. Question: when the GOLD gate would ACTIVATE a beneficial
skill, does the REFFREE (no-gold) gate also activate it?

Repair OFF (design (a): the repair=0 column). Lexical retrieval (as session-13). ZERO new claude
EXCEPT the val A/B solves (~32x2 single-shot + reffree critique calls). Run:
  NATIVE_EVOLVE_CLAUDE_BIN=... NATIVE_EVOLVE_MODEL=haiku python3 eval/gate_retest.py [--dry]
"""
import os
import sys
import json
import pathlib

REPO = pathlib.Path(__file__).resolve().parent.parent
S13_HOME = REPO / "results" / "bbh_skillform" / "dyck_languages" / "runs" / "ours_full_seed0" / "home"
SKILL_MD = S13_HOME / "skills" / "dyck-language-stack-algorithm" / "SKILL.md"
DATA = REPO / "eval" / "data" / "bbh" / "dyck_languages.jsonl"
OUT = REPO / "results" / "dyck_gate_retest.json"
DRY = "--dry" in sys.argv

# engine config reads HOME at import -> point it at session-13's acquired store BEFORE importing evolve
os.environ["NATIVE_EVOLVE_HOME"] = str(S13_HOME)
ledger = REPO / "results" / "dyck_gate_retest_ledger.jsonl"
ledger.write_text("", encoding="utf-8")
os.environ["NATIVE_EVOLVE_LEDGER"] = str(ledger)

sys.path.insert(0, str(REPO / "engine"))
sys.path.insert(0, str(REPO / "eval"))
from evolve import retrieve, episodic, verify, llm  # noqa: E402
import envs as envs_pkg                              # noqa: E402
import self_verify as self_verify_mod               # noqa: E402
import prequential as P                              # noqa: E402  (module-level helpers only)

assert SKILL_MD.exists(), "missing session-13 candidate skill: %s" % SKILL_MD
env = envs_pkg.get_env("bbh")
all_tasks = env.load_tasks(str(DATA))
# SAME split as session-13 (acquire 32 / val 32 / test 96, seed 0, no strata) -> the SAME 32 val tasks
train_tasks, verify_tasks, test_tasks = P.stratified_split(all_tasks, (32, 32, 96), 0, "")


def base_block(t):
    """episodic + distilled (lexical) — the episodic-first base the skill must beat, from S13's store."""
    epi = episodic.exemplar_block(t["question"])
    dis, _ = retrieve.select_and_block(t["question"])
    return "\n\n".join(x for x in (epi, dis) if x)


cand = [{"name": "dyck-language-stack-algorithm", "md": SKILL_MD.read_text(encoding="utf-8"), "value": 0}]
skill_block_fn = lambda t: retrieve.render_skills_block(cand, t["question"], k=3)            # noqa: E731
solve_fn = lambda task, mem: llm.call_claude(env.build_prompt(task, mem), allowed_tools="Read")  # noqa: E731

if DRY:                                              # wiring check, NO claude spend
    t0 = verify_tasks[0]
    bb = base_block(t0)
    sb = skill_block_fn(t0)
    print("DRY: %d val tasks; base_block chars=%d; skill_block chars=%d" % (len(verify_tasks), len(bb), len(sb)))
    print("skill_block head:\n", sb[:300])
    print("base_block head:\n", (bb or "(empty)")[:300])
    sys.exit(0)

judges = {"oracle": P.make_judge("oracle", env, self_verify_mod.self_verify),
          "reffree": P.make_judge("reffree", env, self_verify_mod.self_verify)}
rows = verify.paired_ab_multi(skill_block_fn, base_block, verify_tasks, env, judges,
                              workers=16, solve_fn=solve_fn)
t_or = verify.gate_tally(rows, "oracle", min_n=18, margin=2)
t_rf = verify.gate_tally(rows, "reffree", min_n=18, margin=2)
sig = verify.signal_agreement(rows, "oracle", "reffree")
out = {"candidate": "dyck-language-stack-algorithm", "n_val": len(verify_tasks),
       "oracle": t_or, "reffree": t_rf, "signal_agreement": sig,
       "agree": t_or["activate"] == t_rf["activate"]}
print(json.dumps(out, indent=2))
OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
print("\n-> %s" % OUT)
