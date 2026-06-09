"""Offline validation of the DEMO-CV signal (--demo_holdout + --*_signal demo_cv): the engineered
type-1 proxy for example-driven tasks — split the shown demos into fit/check, execute the candidate
solve() on the WITHHELD pair, and read a generalization estimate with ZERO gold. ZERO claude spend
(cv_check runs python subprocesses only). Run: python3 eval/test_demo_cv.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))            # eval/
import prequential as P                                                     # noqa: E402
from envs import arc                                                        # noqa: E402

RESULTS = []


def check(name, cond):
    RESULTS.append(bool(cond))
    print(("ok   " if cond else "FAIL ") + name)


def mk_task():
    """Rule = mirror each row. 2 fit demos + (after holdout) 1 cv demo."""
    demos = [([[1, 2]], [[2, 1]]), ([[3, 4]], [[4, 3]]), ([[5, 6]], [[6, 5]])]
    return {"id": "t1", "demos": [list(d) for d in demos],
            "question": arc._render_demos(demos),
            "tests": [([[7, 8]], [[8, 7]])], "family": "", "skill": "mirror"}


GENERAL = "```python\ndef solve(grid):\n    return [list(reversed(r)) for r in grid]\n```"
# Memorizes the FIT demos; echoes any unseen input -> consistent-on-shown, fails the withheld pair.
OVERFIT = ("```python\nMEMO = {((1, 2),): [[2, 1]], ((3, 4),): [[4, 3]]}\n"
           "def solve(grid):\n    key = tuple(tuple(r) for r in grid)\n"
           "    return MEMO.get(key, [list(r) for r in grid])\n```")
CRASH = "```python\ndef solve(grid):\n    raise ValueError('boom')\n```"

# ---- apply_demo_holdout: split + leak-proof question re-render ----
t = mk_task()
n_split, n_kept = arc.apply_demo_holdout([t], 1)
check("holdout: task split", n_split == 1 and n_kept == 0)
check("holdout: 2 fit demos remain", len(t["demos"]) == 2)
check("holdout: 1 cv demo moved", len(t["cv_demos"]) == 1 and t["cv_demos"][0][0] == [[5, 6]])
check("holdout: question re-rendered without the withheld pair",
      "5 6" not in t["question"] and "1 2" in t["question"])
check("holdout: gold tests untouched", t["tests"] == [([[7, 8]], [[8, 7]])])
t2 = {"id": "t2", "demos": [([[1]], [[1]])], "question": "q", "tests": []}
n_split, n_kept = arc.apply_demo_holdout([t2], 1)
check("holdout: 1-demo task kept whole (>=1 fit must remain)",
      n_split == 0 and n_kept == 1 and "cv_demos" not in t2)

# ---- cv_check: the discriminating case (consistent-on-shown != generalizes) ----
ok_shown, _ = arc.try_run(t, OVERFIT)
ok_cv, fb_cv = arc.cv_check(t, OVERFIT)
check("OVERFIT passes try_run (consistent on SHOWN demos)", ok_shown is True)
check("OVERFIT fails cv_check (withheld demo catches it)", ok_cv is False)
check("cv_check failure feedback names the WITHHELD pair", "WITHHELD" in fb_cv)
check("GENERAL passes cv_check", arc.cv_check(t, GENERAL)[0] is True)
check("crash -> cv_check False", arc.cv_check(t, CRASH)[0] is False)
check("no code -> cv_check None", arc.cv_check(t, "just words") == (None, ""))
check("no cv_demos -> cv_check None", arc.cv_check(t2, GENERAL) == (None, ""))

# ---- prequential.cv_verdict: availability + shape ----
v = P.cv_verdict(arc, t, OVERFIT)
check("cv_verdict: dict with ok=False + signature", v["ok"] is False and v["signature"] == "demo_cv_fail")
check("cv_verdict: ok=True clean signature", P.cv_verdict(arc, t, GENERAL) == {"ok": True, "signature": "", "feedback": ""})
check("cv_verdict: no cv_demos -> None", P.cv_verdict(arc, t2, GENERAL) is None)
check("cv_verdict: no-code abstains -> None", P.cv_verdict(arc, t, "just words") is None)


class NoCvEnv:
    pass


class RaisingEnv:
    def cv_check(self, task, attempt):
        raise RuntimeError("boom")


check("cv_verdict: env without cv_check -> None", P.cv_verdict(NoCvEnv(), t, GENERAL) is None)
check("cv_verdict: cv_check raising -> None", P.cv_verdict(RaisingEnv(), t, GENERAL) is None)

# ---- make_judge('demo_cv'): gate routing + conservatism ----
j = P.make_judge("demo_cv", arc, None)
check("demo_cv judge: generalizing solve -> True", j(t, GENERAL) is True)
check("demo_cv judge: overfit solve -> False", j(t, OVERFIT) is False)
check("demo_cv judge: UNAVAILABLE (no cv_demos) -> False (conservative)", j(t2, GENERAL) is False)

# ---- reflect evidence built from the cv verdict carries the why-it-failed, no gold ----
d = P.reffree_evidence_dict(t, OVERFIT, {"predicted_answer": "x"}, v)
check("cv evidence: outcome carries the withheld-demo feedback", "WITHHELD" in d["outcome"])
check("cv evidence: no gold/diagnosis fields", "gold" not in d and "diagnosis" not in d)

print("\n%d/%d passed" % (sum(RESULTS), len(RESULTS)))
sys.exit(0 if all(RESULTS) else 1)
