#!/usr/bin/env python3
"""Offline validation of the HoVer env (eval/envs/hover.py). Zero claude spend.
Run: python3 eval/test_hover_env.py"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from envs import hover  # noqa: E402

DATA = pathlib.Path(__file__).resolve().parent / "data" / "hover_val.jsonl"
passed = 0


def check(name, cond):
    global passed
    print(("PASS " if cond else "FAIL ") + name)
    assert cond, name
    passed += 1


# load real data
tasks = hover.load_tasks(str(DATA))
check("loaded >=200 claims", len(tasks) >= 200)
check("rows have question+answer+family", all(t["question"] and t["answer"] in ("SUPPORTED", "NOT_SUPPORTED")
                                              and t["family"].startswith("hop") for t in tasks[:10]))

# --- label extraction: the critical 'not supported' must NOT map to SUPPORTED ---
check("'SUPPORTED' -> SUPPORTED", hover._label("SUPPORTED") == "SUPPORTED")
check("'NOT_SUPPORTED' -> NOT_SUPPORTED", hover._label("NOT_SUPPORTED") == "NOT_SUPPORTED")
check("'not supported' -> NOT_SUPPORTED", hover._label("not supported") == "NOT_SUPPORTED")
check("'unsupported' -> NOT_SUPPORTED", hover._label("the claim is unsupported") == "NOT_SUPPORTED")
check("'refuted' -> NOT_SUPPORTED", hover._label("this is refuted") == "NOT_SUPPORTED")
check("'supports' -> SUPPORTED", hover._label("the evidence supports it") == "SUPPORTED")
check("'not sure' does NOT false-trigger -> '' (needs 'not support' adjacency)",
      hover._label("hmm not sure honestly") == "")
check("bare 'no verdict' does NOT trigger NOT_SUPPORTED", hover._label("gave no verdict") == "")

# --- scoring on a real SUPPORTED + a real NOT_SUPPORTED task ---
sup = next(t for t in tasks if t["answer"] == "SUPPORTED")
nsup = next(t for t in tasks if t["answer"] == "NOT_SUPPORTED")
check("SUPPORTED claim, correct verdict -> em=1", hover.score(sup, "reasoning...\nAnswer: SUPPORTED")["em"] == 1.0)
check("SUPPORTED claim, wrong verdict -> em=0", hover.score(sup, "Answer: NOT_SUPPORTED")["em"] == 0.0)
check("NOT_SUPPORTED claim, correct -> em=1", hover.score(nsup, "Answer: NOT_SUPPORTED")["em"] == 1.0)
check("NOT_SUPPORTED claim, 'not supported' phrasing -> em=1",
      hover.score(nsup, "Answer: the claim is not supported")["em"] == 1.0)
check("no verdict -> em=0", hover.score(sup, "I am unsure and gave zzz")["em"] == 0.0)

# --- verify (reference-free) ---
check("verify ok with a verdict", hover.verify(sup, "Answer: SUPPORTED")["ok"] is True)
check("verify rejects no-verdict", hover.verify(sup, "I cannot decide; here are thoughts")["ok"] is False)

# verify reads NO gold: a trap-gold task still verifies on format alone
trap = {"question": "q", "answer": "WRONG-GOLD", "family": "hop2"}
check("verify ignores gold", hover.verify(trap, "Answer: SUPPORTED")["ok"] is True)

# --- evidence is gold-grounded + procedural (decomposition) for skill induction ---
evd = hover.evidence(nsup, "Answer: SUPPORTED", hover.score(nsup, "Answer: SUPPORTED"))
check("evidence FAIL teaches the decomposition procedure",
      evd["outcome"] == "FAIL" and "decompose" in evd["diagnosis"].lower() and nsup["family"] in evd["diagnosis"])

print("\n%d/%d checks passed" % (passed, passed))
