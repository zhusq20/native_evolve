#!/usr/bin/env python3
"""Offline validation of the BBH env (eval/envs/bbh.py) on REAL data rows. Zero claude spend.
Run: python3 eval/test_bbh_env.py"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from envs import bbh  # noqa: E402

DATA = pathlib.Path(__file__).resolve().parent / "data" / "bbh"
passed = 0


def check(name, cond):
    global passed
    print(("PASS " if cond else "FAIL ") + name)
    assert cond, name
    passed += 1


# load every fetched family; confirm shape
fams = {}
for f in sorted(DATA.glob("*.jsonl")):
    t = bbh.load_tasks(str(f))
    fams[f.stem] = t
    check("load %s (n>=200, has question+answer+family)" % f.stem,
          len(t) >= 200 and all(x.get("question") and x.get("answer") and x.get("family") for x in t[:5]))

# --- MC family: correct '(X)' scores 1, a different letter scores 0, extraction robust ---
mc = fams["logical_deduction_five_objects"]
ex = mc[0]
gold = ex["answer"]                                            # e.g. '(A)'
check("MC gold looks like (X)", bbh._MC_GOLD.match(gold) is not None)
check("MC correct -> em=1", bbh.score(ex, "Reasoning...\nAnswer: %s" % gold)["em"] == 1.0)
wrong = "(B)" if gold != "(B)" else "(C)"
check("MC wrong letter -> em=0", bbh.score(ex, "Answer: %s" % wrong)["em"] == 0.0)
check("MC extracts last paren even with noise", bbh.score(ex, "maybe (Z) ... Answer: %s here" % gold)["em"] == 1.0)

# --- free-form families: exact (normalized) match scores 1, perturbation scores 0 ---
for fam in ("word_sorting", "dyck_languages", "multistep_arithmetic_two"):
    ex = fams[fam][0]
    g = ex["answer"]
    check("%s correct (exact) -> em=1" % fam, bbh.score(ex, "work...\nAnswer: %s" % g)["em"] == 1.0)
    check("%s case/space-insensitive -> em=1" % fam,
          bbh.score(ex, "Answer:   %s  " % g.upper())["em"] == 1.0)
    check("%s clearly wrong -> em=0" % fam, bbh.score(ex, "Answer: definitely_not_the_answer_xyz")["em"] == 0.0)

# numeric tolerance: '24' vs '24.0' vs ' 24 '
num = {"family": "multistep_arithmetic_two", "question": "q", "answer": "24"}
check("numeric 24 == 24.0", bbh.score(num, "Answer: 24.0")["em"] == 1.0)
check("numeric 24 != 25", bbh.score(num, "Answer: 25")["em"] == 0.0)

# --- verify (reference-free, format-only) ---
check("verify ok when Answer present", bbh.verify(ex, "blah\nAnswer: foo")["ok"] is True)
check("verify rejects no-answer", bbh.verify(ex, "I think it is foo")["ok"] is False)
check("verify rejects empty answer", bbh.verify(ex, "Answer:   ")["ok"] is False)

# --- evidence is gold-grounded + family-procedural (for skill induction) ---
evd = bbh.evidence(mc[0], "Answer: %s" % wrong, bbh.score(mc[0], "Answer: %s" % wrong))
check("evidence FAIL names the family + asks for transferable procedure",
      evd["outcome"] == "FAIL" and "procedure" in evd["diagnosis"].lower()
      and mc[0]["family"] in evd["diagnosis"])

# verify() never reads gold (provably reference-free): a trap-gold task still verifies on format alone
trap = {"family": "x", "question": "q", "answer": "TOTALLY-WRONG-GOLD"}
check("verify ignores gold (format-only)", bbh.verify(trap, "Answer: anything")["ok"] is True)

print("\n%d/%d checks passed" % (passed, passed))
