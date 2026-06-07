"""Offline validation of the precision-law-FOR-GATING audit (verify.paired_ab_multi + gate_tally).
ZERO claude spend — a fake solve_fn + fake judges. Asserts:
  (1) base & full are each solved EXACTLY ONCE per task (NOT once per judge) — so both judges score
      the IDENTICAL answers (the whole point: no re-solve noise in a judge-vs-judge comparison);
  (2) gate_tally reproduces rolling_gate's single-round accept rule (powered ∧ beats ∧ not-diluting);
  (3) two judges that disagree on the same answers yield different activate decisions (the audit can
      actually detect a precision gap).
Run: python3 eval/test_gate_audit.py
"""
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "engine"))
from evolve import verify  # noqa: E402

RESULTS = []


def check(name, cond):
    RESULTS.append(bool(cond))
    print(("ok   " if cond else "FAIL ") + name)


# 18 tasks so the n>=min_n power floor is satisfiable. answer = "<id>:<arm>".
TASKS = [{"question": "q%d" % i, "id": i} for i in range(18)]
SOLVE_CALLS = []


def fake_solve(task, mem):
    # arm is encoded by whether the skill block is present in mem; record every call to count solves.
    arm = "full" if "SKILL" in (mem or "") else "base"
    SOLVE_CALLS.append((task["id"], arm))
    return "%d:%s" % (task["id"], arm)


# ORACLE judge (ground truth): with the skill, the first 6 base-failures become passes, nothing breaks.
# Encode: base passes iff id >= 6; full passes iff id >= 0 (skill rescues ids 0..5). -> rescued=6 broke=0.
def oracle_judge(task, resp):
    i = task["id"]
    if resp.endswith(":full"):
        return True                      # skill makes everything pass
    return i >= 6                         # base: ids 0..5 fail, 6..17 pass


# REFFREE judge (imprecise here): format-only — sees EVERY non-empty answer as ok (can't see the
# correctness rescue). -> base_pass=full_pass=18, rescued=0, broke=0 -> no measurable lift.
def reffree_judge(task, resp):
    return bool(resp)


base_block = lambda t: "BASE"
skill_block = lambda t: "SKILL-block"
judges = {"oracle": oracle_judge, "reffree": reffree_judge}

rows = verify.paired_ab_multi(skill_block, base_block, TASKS, env=None, judges=judges,
                              workers=1, solve_fn=fake_solve)

# (1) single-solve: exactly 2 solves per task (one base, one full), NOT 4 (2 per judge).
check("solved base+full exactly ONCE per task (%d == 2*%d)" % (len(SOLVE_CALLS), len(TASKS)),
      len(SOLVE_CALLS) == 2 * len(TASKS))
check("each task solved once as base and once as full",
      sorted(SOLVE_CALLS) == sorted([(t["id"], a) for t in TASKS for a in ("base", "full")]))

# (2) both judges scored the SAME answers (rows carry both judges' verdicts on identical solves).
check("rows carry both judges per task", all("oracle_base" in r and "reffree_full" in r for r in rows))

t_or = verify.gate_tally(rows, "oracle", min_n=18, margin=2)
t_rf = verify.gate_tally(rows, "reffree", min_n=18, margin=2)
print("   oracle:", t_or)
print("   reffree:", t_rf)

# oracle: base passes = ids 6..17 = 12; full passes = 18; rescued = 6 (ids 0..5); broke = 0.
check("oracle base_pass=12", t_or["base_pass"] == 12)
check("oracle full_pass=18", t_or["full_pass"] == 18)
check("oracle rescued=6 broke=0", t_or["rescued"] == 6 and t_or["broke"] == 0)
check("oracle ACTIVATES (powered & beats & not-diluting)", t_or["activate"] is True)

# reffree (format-only): base_pass=full_pass=18 -> lift 0 -> below margin -> REJECT.
check("reffree base_pass==full_pass==18", t_rf["base_pass"] == 18 and t_rf["full_pass"] == 18)
check("reffree rescued=0 broke=0", t_rf["rescued"] == 0 and t_rf["broke"] == 0)
check("reffree REJECTS (no measurable lift)", t_rf["activate"] is False)

# (3) the audit detects the precision gap: the two signals DISAGREE on the same answers.
check("audit detects precision gap (oracle activate != reffree activate)",
      t_or["activate"] != t_rf["activate"])

# (4) gate_tally matches rolling_gate's rule on a hand case: n=20, full-base=3>=margin2, broke<=rescued.
synth = ([{"x_base": 0, "x_full": 1}] * 5 +          # 5 rescued
         [{"x_base": 1, "x_full": 0}] * 2 +          # 2 broke
         [{"x_base": 1, "x_full": 1}] * 13)          # 13 stable pass
ts = verify.gate_tally(synth, "x", min_n=18, margin=2)
# base_pass=15, full_pass=18 -> diff 3>=2 (beats); rescued5 broke2 (not-diluting); n20>=18 (powered)
check("gate_tally rule: powered & beats & not-diluting -> activate",
      ts["activate"] is True and ts["rescued"] == 5 and ts["broke"] == 2 and ts["full_pass"] - ts["base_pass"] == 3)
# flip to diluting: broke>rescued -> reject
synth2 = ([{"x_base": 0, "x_full": 1}] * 2 + [{"x_base": 1, "x_full": 0}] * 5 +
          [{"x_base": 1, "x_full": 1}] * 13)
ts2 = verify.gate_tally(synth2, "x", min_n=18, margin=2)
check("gate_tally rule: diluting (broke>rescued) -> reject", ts2["activate"] is False)

print("\n%d/%d checks passed" % (sum(RESULTS), len(RESULTS)))
sys.exit(0 if all(RESULTS) else 1)
