#!/usr/bin/env python3
"""Offline validation of the ARC-AGI Stream env (eval/envs/arc.py + arc_gen.py). ZERO spend.
Run: python3 eval/test_arc_env.py

The headline test is SELF-CONSISTENCY: for every (family, skill) the generator must produce a
task that its OWN emitted reference solve() reproduces on all demos AND all held-out tests, via
the env's real subprocess exec runner. That simultaneously proves (a) the generated tasks are
program-solvable, (b) apply_rule (the ground truth) and the reference solver agree, and (c) the
exec/scoring path works. The reffree (try_run) and oracle (score) channels are then probed
directly with correct / crashing / wrong programs.
"""
import json
import pathlib
import sys
import tempfile

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from envs import arc, arc_gen  # noqa: E402
from envs.arc_lib import scoring as arc_scoring  # noqa: E402

passed = 0


def check(name, cond):
    global passed
    print(("PASS " if cond else "FAIL ") + name)
    assert cond, name
    passed += 1


def wrap(code):
    return "Here is my solution:\n```python\n" + code + "\n```\n"


# --------------------------------------------------------------------- generator unit pieces
g = np.array([
    [0, 0, 0, 0, 0],
    [0, 3, 3, 0, 0],
    [0, 3, 3, 0, 0],
    [0, 0, 0, 5, 0],
    [0, 0, 0, 0, 0],
])
objs = arc_gen.extract_objects(g)
check("extract_objects finds 2 components", len(objs) == 2)
check("extract_objects sizes", sorted(o["size"] for o in objs) == [1, 4])
check("extract_objects colors", sorted(o["color"] for o in objs) == [3, 5])

# largest + keep -> only the 2x2 survives
out = arc_gen.apply_rule(g, "largest", "keep", {})
check("largest+keep keeps the 4-cell, drops the 1-cell",
      out.sum() == 12 and (out == 3).sum() == 4 and (out == 5).sum() == 0)

# color_property + recolor -> the color-3 object repainted to 7, color-5 dropped
out = arc_gen.apply_rule(g, "color_property", "recolor", {"target_color": 3, "new_color": 7})
check("color_property+recolor repaints target color, drops others",
      (out == 7).sum() == 4 and (out == 5).sum() == 0 and (out == 3).sum() == 0)

# hollow on a 3x3 solid block erases the single interior cell
solid = np.zeros((5, 5), dtype=int)
solid[1:4, 1:4] = 4
hol = arc_gen.apply_rule(solid, "largest", "hollow", {})
check("hollow erases the interior cell of a 3x3 block", (hol == 4).sum() == 8 and hol[2, 2] == 0)

# --------------------------------------------------------------------- determinism
t_a = arc_gen.gen_task("largest", "recolor", np.random.default_rng(123))
t_b = arc_gen.gen_task("largest", "recolor", np.random.default_rng(123))
check("generator is seed-deterministic", t_a["demos"] == t_b["demos"] and t_a["tests"] == t_b["tests"])
t_c = arc_gen.gen_task("largest", "recolor", np.random.default_rng(124))
check("different seed -> different task", t_a["demos"] != t_c["demos"])

# --------------------------------------------------------------------- SELF-CONSISTENCY (headline)
# Every (family, skill): the emitted reference solver must reproduce all demos + held-out tests via
# the env's real exec runner. Also verifies the held-out tests are NON-trivial (oracle EM is earned).
rng = np.random.default_rng(7)
all_ok = True
for fam in arc_gen.FAMILIES:
    for sk in arc_gen.SKILLS:
        task = arc_gen.gen_task(fam, sk, rng)
        ref = arc_gen.reference_solver_src(fam, sk, task["params"])
        resp = wrap(ref)
        # reference solver passes held-out tests (ORACLE em == 1.0)
        ev = arc.score(task, resp)
        # reference solver passes the shown demos (REFFREE channel)
        ran_ok, fb = arc.try_run(task, resp)
        ok = (ev["em"] == 1.0 and ran_ok is True)
        if not ok:
            all_ok = False
            print("   self-consistency FAIL %s/%s: em=%s reffree=%s err=%s"
                  % (fam, sk, ev["em"], ran_ok, (ev.get("_exec_err") or fb)[:200]))
check("reference solver reproduces ALL 21 (family,skill) tasks (oracle+reffree agree)", all_ok)

# --------------------------------------------------------------------- oracle vs wrong program
task = arc_gen.gen_task("color_property", "keep", np.random.default_rng(42))
good = wrap(arc_gen.reference_solver_src("color_property", "keep", task["params"]))
check("score: correct program -> em 1.0", arc.score(task, good)["em"] == 1.0)

identity = wrap("def solve(grid):\n    return [list(r) for r in grid]")
ev_id = arc.score(task, identity)
check("score: identity program -> em 0.0 (held-out tests are non-trivial)", ev_id["em"] == 0.0)
check("score: identity program -> graded f1 in [0,1)", 0.0 <= ev_id["f1"] < 1.0)

# --------------------------------------------------------------------- official arc_lib kernel
# pair_correct = exact list-of-lists equality (dims + every cell); None never matches.
check("arc_lib.pair_correct: exact match", arc_scoring.pair_correct([[1, 2]], [[1, 2]]) is True)
check("arc_lib.pair_correct: cell mismatch", arc_scoring.pair_correct([[1, 2]], [[1, 3]]) is False)
check("arc_lib.pair_correct: dim mismatch", arc_scoring.pair_correct([[1, 2]], [[1, 2, 3]]) is False)
check("arc_lib.pair_correct: None -> False", arc_scoring.pair_correct(None, [[0]]) is False)
# pass@k: a pair is solved iff ANY attempt matches.
check("arc_lib.pair_solved: pass@2 second attempt right",
      arc_scoring.pair_solved([[[9]], [[0]]], [[0]]) is True)
# task_score: official fraction = solved_pairs / num_pairs; all_solved = strict binary.
ts_half = arc_scoring.task_score([[[[0]]], [[[9]]]], [[[0]], [[0]]])
check("arc_lib.task_score: 1/2 solved -> fraction 0.5", ts_half["fraction"] == 0.5
      and ts_half["n_solved"] == 1 and ts_half["all_solved"] is False)
ts_all = arc_scoring.task_score([[[[0]]], [[[0]]]], [[[0]], [[0]]])
check("arc_lib.task_score: 2/2 solved -> fraction 1.0 + all_solved", ts_all["fraction"] == 1.0
      and ts_all["all_solved"] is True)
check("arc_lib.aggregate: mean*100", arc_scoring.aggregate([1.0, 0.5, 0.0]) == 50.0)

# score() exposes the official fractional arc_task_score, consistent with em (strict all-pairs).
check("score: correct program -> arc_task_score 1.0", arc.score(task, good)["arc_task_score"] == 1.0)
check("score: identity program -> arc_task_score < 1.0 (held-out not all solved)",
      ev_id["arc_task_score"] < 1.0)
check("score: em==1.0 iff arc_task_score==1.0 (strict == all pairs solved)",
      (arc.score(task, good)["em"] == 1.0) == (arc.score(task, good)["arc_task_score"] == 1.0))

# --------------------------------------------------------------------- reffree (try_run) channel
check("try_run: correct program PASSES the demos", arc.try_run(task, good)[0] is True)

crash = wrap("def solve(grid):\n    return grid[10**9]   # IndexError")
ro, fb = arc.try_run(task, crash)
check("try_run: crashing program -> False with feedback", ro is False and "fail" in fb.lower())

wrong = wrap("def solve(grid):\n    return [[0]*len(grid[0]) for _ in grid]")  # all-blank
ro2, fb2 = arc.try_run(task, wrong)
check("try_run: wrong-output program -> False (reproduces no example)", ro2 is False)

ro3, _ = arc.try_run(task, "no code here, just prose")
check("try_run: no code -> None (defer to critique)", ro3 is None)

timeout = wrap("def solve(grid):\n    while True:\n        pass")
ro4, fb4 = arc.try_run(task, timeout)
check("try_run: infinite loop -> False with TIMEOUT", ro4 is False and "TIMEOUT" in fb4)

# --------------------------------------------------------------------- verify (structural)
check("verify: ok on a defined solve", arc.verify(task, good)["ok"] is True)
check("verify: not ok on prose only", arc.verify(task, "just text")["ok"] is False)
check("verify: not ok when solve missing", arc.verify(task, wrap("def foo():\n    return 1"))["ok"] is False)

# --------------------------------------------------------------------- prompt / evidence
prompt = arc.build_prompt(task, "")
check("build_prompt asks for def solve(grid)", "def solve(grid)" in prompt)
check("build_prompt renders the examples", "Example 1" in prompt and "INPUT:" in prompt)
prompt_mem = arc.build_prompt(task, "MEMORY-BLOCK")
check("build_prompt prepends memory", prompt_mem.startswith("MEMORY-BLOCK"))

ev_pass = arc.score(task, good)
diag = arc.evidence(task, good, ev_pass)
check("evidence: PASS outcome on correct", diag["outcome"] == "PASS" and diag["diagnosis"] == "")
diag_f = arc.evidence(task, identity, ev_id)
check("evidence: FAIL carries family procedure hint", diag_f["outcome"] == "FAIL"
      and "family" in diag_f["diagnosis"] and "color_property" in diag_f["diagnosis"])

# --------------------------------------------------------------------- load_tasks round-trip
with tempfile.TemporaryDirectory() as td:
    fp = pathlib.Path(td) / "arc.jsonl"
    rows = [arc_gen.gen_task("largest", "keep", np.random.default_rng(i)) for i in range(3)]
    fp.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    loaded = arc.load_tasks(str(fp))
    check("load_tasks round-trips n rows", len(loaded) == 3)
    check("load_tasks builds question text", all(l.get("question") and "Example" in l["question"]
                                                 for l in loaded))

print("\n%d checks passed" % passed)
