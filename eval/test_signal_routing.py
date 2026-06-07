"""Offline validation of the reference-free vs GOLD oracle SIGNAL routing (A1 gate / A2 credit /
A3 reflect). ZERO claude spend — fakes for self_verify and env.score. Confirms the system's
credit/gate/reflect can run GOLD-FREE (reffree) and that reference-free reflection evidence carries
NO gold. Run: python3 eval/test_signal_routing.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))            # eval/
import prequential as P                                                     # noqa: E402
import envs as envs_pkg                                                     # noqa: E402

RESULTS = []


def check(name, cond):
    RESULTS.append(bool(cond))
    print(("ok   " if cond else "FAIL ") + name)


# ---- fakes (no claude) ----
class FakeEnv:
    def score(self, task, resp):                       # GOLD: correct iff "right" in the answer
        return {"em": 1.0 if "right" in (resp or "") else 0.0, "f1": 0.0,
                "sub_em": 0.0, "predicted_answer": resp or ""}


def sv(task, resp, env):                               # REFERENCE-FREE verdict: ok iff "clean"
    if "nocheck" in (resp or ""):
        return None                                    # nothing checkable -> signal unavailable
    ok = "clean" in (resp or "")
    return {"ok": ok, "signature": "" if ok else "constraint", "feedback": "" if ok else "fix X"}


def sv_raises(task, resp, env):
    raise RuntimeError("boom")


env = FakeEnv()
t = {"question": "Q"}

# ---- A1: make_judge routes oracle (gold) vs reffree (self_verify) ----
oj = P.make_judge("oracle", env, sv)
rj = P.make_judge("reffree", env, sv)
check("oracle judge: gold-correct -> True", oj(t, "right") is True)
check("oracle judge: gold-wrong  -> False", oj(t, "wrong") is False)
check("reffree judge: self-clean -> True", rj(t, "clean") is True)
check("reffree judge: self-dirty -> False", rj(t, "dirty") is False)
check("reffree judge: UNAVAILABLE -> False (conservative; gate can't activate on a missing signal)",
      rj(t, "nocheck") is False)
# the two signals are INDEPENDENT (the whole point: deploy can't see gold)
check("independent: gold-right + self-dirty -> oracle True, reffree False",
      oj(t, "right") is True and rj(t, "right") is False)
check("independent: gold-wrong + self-clean -> oracle False, reffree True",
      oj(t, "clean wrong") is False and rj(t, "clean wrong") is True)

# ---- A2: reffree_ok / reffree_verdict (the credit/episode-success signal) ----
check("reffree_ok clean -> True", P.reffree_ok(sv, t, "clean", env) is True)
check("reffree_ok dirty -> False", P.reffree_ok(sv, t, "dirty", env) is False)
check("reffree_ok unavailable -> None (caller falls back to gold for the label)",
      P.reffree_ok(sv, t, "nocheck", env) is None)
check("reffree_ok on verifier exception -> None (fail-safe)",
      P.reffree_ok(sv_raises, t, "x", env) is None)

# ---- A3: reffree_evidence_dict carries NO gold ----
# gold says WRONG (no "right") but the reffree verdict says ok -> evidence must reflect the reffree view
ev = {"predicted_answer": "clean answer", "em": 0.0}
d_ok = P.reffree_evidence_dict(t, "clean answer", ev, {"ok": True, "feedback": ""})
rendered = envs_pkg.render_evidence(d_ok)
check("reffree evidence has outcome/task/predicted",
      all(k in d_ok for k in ("outcome", "task", "predicted")))
check("reffree evidence has NO gold/diagnosis keys (no gold leak)",
      "gold" not in d_ok and "diagnosis" not in d_ok)
check("rendered reffree evidence shows a self-check, NOT a REFERENCE ANSWER",
      "self-check" in rendered and "REFERENCE ANSWER" not in rendered)
d_fail = P.reffree_evidence_dict(t, "bad", {"predicted_answer": "bad"},
                                 {"ok": False, "feedback": "missing constraint X"})
check("reffree evidence (FAILED) carries the reference-free feedback",
      "missing constraint X" in d_fail["outcome"])
d_rep = P.reffree_evidence_dict(
    t, "x", {"predicted_answer": "x", "_repair_trace": [{"signature": "exec", "feedback": "crash"}]},
    {"ok": True, "feedback": ""})
check("reffree evidence includes the (reference-free) repair history when present",
      "repair" in d_rep and "crash" in d_rep["repair"])

# ---- oracle reflect path still builds gold evidence via collect_evidence/render (unchanged) ----
check("oracle judge unaffected by verifier exception (uses gold only)",
      P.make_judge("oracle", env, sv_raises)(t, "right") is True)

# ---- gate/inference ALIGNMENT: paired_ab uses solve_fn + per-task skill_block, base-THEN-skill ----
import os as _os                                                            # noqa: E402
import tempfile as _tmp                                                     # noqa: E402
_os.environ.setdefault("NATIVE_EVOLVE_HOME", _tmp.mkdtemp())
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "engine"))
from evolve import verify as V                                             # noqa: E402
from evolve import retrieve as R                                           # noqa: E402

_seen = []


def _fake_solve(task, mem):                            # records the mem block the gate built
    _seen.append(mem)
    return "clean" if "SKILL-" in mem else "dirty"     # skill present -> self-verify-clean answer


_rows = V.paired_ab(
    skill_block=lambda t: "SKILL-%s" % t["id"],        # per-task CALLABLE skill block (like inference)
    base_block_fn=lambda t: "BASE",
    tasks=[{"id": "a", "question": "q"}],
    env=FakeEnv(), workers=1,
    judge=lambda task, resp: "clean" in resp,          # reference-free-style judge
    solve_fn=_fake_solve)                              # the REAL solve path stand-in
check("paired_ab routes through solve_fn (no bare single-shot claude)", len(_seen) == 2)
check("paired_ab base arm = base only", "BASE" in _seen)
check("paired_ab full arm = base THEN skill (matches inject() order)",
      any(m.startswith("BASE") and m.rstrip().endswith("SKILL-a") for m in _seen))
check("paired_ab full arm (skill present) -> full_em=1", _rows[0]["full_em"] == 1)
check("paired_ab base arm (no skill) -> base_em=0", _rows[0]["base_em"] == 0)

# the gate renders CANDIDATE skills with the SAME function inference uses for ACTIVE skills
_sk = [{"name": "s1", "md": "---\ndescription: alpha helper\n---\nbody one " + "x" * 1000, "value": 0},
       {"name": "s2", "md": "---\ndescription: beta helper\n---\nbody two", "value": 0}]
_blk = R.render_skills_block(_sk, "alpha", k=1)
check("render_skills_block respects k (top-1 by relevance)", "s1" in _blk and "s2" not in _blk)
check("render_skills_block truncates long body (560 cap + ellipsis)", "…" in _blk)
check("render_skills_block uses the inference header (same framing as skills_block)",
      "Verified skills promoted" in _blk)

n_ok = sum(RESULTS)
print("\n%d/%d checks passed" % (n_ok, len(RESULTS)))
sys.exit(0 if all(RESULTS) else 1)
