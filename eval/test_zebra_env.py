#!/usr/bin/env python3
"""Offline validation of the ZebraLogic env (eval/envs/zebra.py) on REAL solutions. Zero spend.
Run: python3 eval/test_zebra_env.py"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from envs import zebra  # noqa: E402

DATA = pathlib.Path(__file__).resolve().parent / "data" / "zebra_val.jsonl"
passed = 0


def check(name, cond):
    global passed
    print(("PASS " if cond else "FAIL ") + name)
    assert cond, name
    passed += 1


def gold_response(task, wrap_prose=True, fence=False):
    """Build a perfect model answer (JSON grid) from the gold solution."""
    header, rows = task["sol_header"], task["sol_rows"]
    attrs = header[1:]
    grid = {}
    for r in rows:
        grid["House %s" % r[0]] = {a: r[j] for j, a in enumerate(attrs, start=1)}
    js = json.dumps(grid)
    if fence:
        js = "```json\n%s\n```" % js
    return ("Let me reason about the clues...\nFinal answer:\n" + js) if wrap_prose else js


tasks = zebra.load_tasks(str(DATA))
check("loaded >=150 puzzles", len(tasks) >= 150)
check("has families across sizes", len({t["family"] for t in tasks}) >= 8)

# pick a small (2x2) and a larger (5x5 if present) puzzle
small = next(t for t in tasks if t["size"] == "2*2")
big = next((t for t in tasks if t["size"] in ("5*5", "5*4", "4*5")), tasks[-1])

for t, tag in ((small, small["size"]), (big, big["size"])):
    # perfect grid (with prose) -> EM=1, f1=1
    r = zebra.score(t, gold_response(t, wrap_prose=True))
    check("%s perfect grid -> EM=1, f1=1" % tag, r["em"] == 1.0 and r["f1"] == 1.0)
    # fenced perfect grid -> EM=1
    check("%s fenced perfect -> EM=1" % tag, zebra.score(t, gold_response(t, fence=True))["em"] == 1.0)
    # verify ok on a complete grid
    check("%s verify ok on full grid" % tag, zebra.verify(t, gold_response(t))["ok"] is True)

# perturb ONE cell -> EM=0 but f1>0 (most cells still right)
obj = zebra._outer_json(gold_response(big))
firsthouse = "House %s" % big["sol_rows"][0][0]
some_attr = big["sol_header"][1]
obj[firsthouse][some_attr] = "DEFINITELY_WRONG_VALUE_XYZ"
bad = "answer: " + json.dumps(obj)
rb = zebra.score(big, bad)
check("one wrong cell -> EM=0", rb["em"] == 0.0)
check("one wrong cell -> f1>0 (partial credit)", 0.0 < rb["f1"] < 1.0)

# malformed (no JSON) -> EM=0 + verify rejects
check("no-json -> EM=0", zebra.score(big, "I think house 1 is Bob and house 2 is Eric")["em"] == 0.0)
check("no-json -> verify no-json-grid", zebra.verify(big, "no json here")["signature"] == "no-json-grid")

# incomplete grid -> verify flags it
partial = {"House 1": {a: "x" for a in big["sol_header"][1:]}}
check("incomplete grid -> verify incomplete", zebra.verify(big, json.dumps(partial))["signature"] == "incomplete-grid")

# verify reads NO gold: format-only (trap task with bogus solution still verifies on shape)
check("verify ignores gold", zebra.verify(small, gold_response(small))["ok"] is True)

# evidence FAIL teaches the constraint-propagation procedure
evd = zebra.evidence(big, "wrong", {"em": 0.0, "_cells": "1/9"})
check("evidence FAIL teaches propagation procedure",
      evd["outcome"] == "FAIL" and "eliminate" in evd["diagnosis"].lower())

print("\n%d/%d checks passed" % (passed, passed))
