"""ZebraLogic environment — logic-grid (Einstein) puzzles: the HARD + reuse-structured + symbolic
regime we were hunting for.

Every puzzle is solved by the SAME procedure (constraint propagation / elimination over a grid),
so it is maximally reuse-structured — ideal for skill formation (the induced skill IS the solving
method). Difficulty scales cleanly with grid `size` (N houses x M attributes), giving a headroom
gradient (`family = sz{N}x{M}`). Deterministic puzzle-level EM (ALL cells correct, the standard
ZebraLogic metric) + cell-accuracy F1. Text-only, no gold leakage in verify.

Data: eval/data/zebra_val.jsonl (rows: id, size, family, question/puzzle, sol_header, sol_rows).
Source: WildEval/ZebraLogic grid_mode (has filled solutions). Re-fetch: see docs/PROGRESS.md "Data".
"""
import json
import pathlib
import re

NAME = "zebra"


def load_tasks(path):
    p = pathlib.Path(path)
    files = sorted(p.glob("*.jsonl")) if p.is_dir() else [p]
    out = []
    for fp in files:
        for line in fp.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            r["question"] = r.get("question", r.get("puzzle", ""))
            out.append(r)
    return out


def _attrs(task):
    return list(task.get("sol_header", [])[1:])          # drop the leading "House" column


def build_prompt(task, mem):
    attrs = _attrs(task)
    n = len(task.get("sol_rows", []))
    fmt = '{"House 1": {%s}, ... , "House %d": {...}}' % (
        ", ".join('"%s": "<value>"' % a for a in attrs), n)
    body = (
        "Solve this logic-grid puzzle. There are %d houses (1..%d); assign each house a unique value "
        "for every attribute (%s). Reason step by step using the clues, then give your FINAL answer as "
        "a single JSON object on the last line, EXACTLY this shape:\n%s\nUse the exact attribute names "
        "and the exact value spellings used in the puzzle.\n\n# Puzzle\n%s"
        % (n, n, ", ".join(attrs), fmt, task.get("question", ""))
    )
    return (mem + "\n\n" + body) if mem else body


def _norm(s):
    return re.sub(r"\s+", " ", str(s).strip().lower()).strip(".")


def _all_json_dicts(text):
    """Every balanced {...} substring that parses to a dict (tolerant of prose/fences)."""
    out = []
    for st in (m.start() for m in re.finditer(r"\{", text or "")):
        depth = 0
        for i in range(st, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        o = json.loads(text[st:i + 1])
                        if isinstance(o, dict):
                            out.append(o)
                    except Exception:
                        pass
                    break
    return out


def _outer_json(text):
    """The grid object = the parseable dict with the most HOUSE-like keys (House N / N)."""
    cand = _all_json_dicts(text or "")
    if not cand:
        return None

    def house_score(d):
        return sum(1 for k in d if re.match(r"(?i)house\s*\d+$|^\s*\d+\s*$", str(k)))
    cand.sort(key=lambda d: (house_score(d), len(d)), reverse=True)
    return cand[0]


def _house_key(d, i):
    """Find house i's attribute dict under tolerant keys (House 1 / house1 / 1 / '1')."""
    for k in ("House %d" % i, "house %d" % i, "House%d" % i, str(i), i):
        if isinstance(d, dict) and k in d and isinstance(d[k], dict):
            return d[k]
    return None


def score(task, response):
    header, rows = task.get("sol_header", []), task.get("sol_rows", [])
    attrs = header[1:]
    n = len(rows)
    obj = _outer_json(response or "")
    total = n * len(attrs)
    correct = 0
    if obj:
        # tolerant attribute lookup (case-insensitive keys)
        for i in range(1, n + 1):
            hd = _house_key(obj, i) or {}
            lk = {_norm(k): v for k, v in hd.items()} if isinstance(hd, dict) else {}
            gold_row = rows[i - 1]
            for j, a in enumerate(attrs, start=1):
                pred = lk.get(_norm(a))
                if pred is not None and _norm(pred) == _norm(gold_row[j]):
                    correct += 1
    cell_acc = (correct / total) if total else 0.0
    em = 1.0 if total and correct == total else 0.0
    return {"em": em, "f1": round(cell_acc, 4), "sub_em": em,
            "predicted_answer": "cells %d/%d" % (correct, total),
            "gold_answers": ["full-grid"], "_cells": "%d/%d" % (correct, total),
            "_reason": "" if em else "grid not fully correct (%d/%d cells)" % (correct, total)}


def verify(task, attempt):
    """REFERENCE-FREE format check (reads no gold): did the model emit a parseable grid of the
    right SHAPE (a dict with an entry per house)? Repair fires on malformed/incomplete output."""
    n = len(task.get("sol_rows", []))
    obj = _outer_json(attempt or "")
    if not obj:
        return {"ok": False, "signature": "no-json-grid",
                "feedback": "No parseable JSON solution. End with one JSON object mapping each "
                            '"House i" to its attribute values.'}
    found = sum(1 for i in range(1, n + 1) if _house_key(obj, i) is not None)
    if found < n:
        return {"ok": False, "signature": "incomplete-grid",
                "feedback": "Your JSON only covers %d of %d houses. Give every house 1..%d." % (found, n, n)}
    return {"ok": True, "signature": "", "feedback": ""}


def evidence(task, response, ev):
    correct = ev["em"] == 1.0
    return {
        "outcome": "PASS" if correct else "FAIL",
        "task": "ZebraLogic [%s]: %s" % (task.get("family", ""), task.get("question", "")[:500]),
        "predicted": "cells correct: %s" % ev.get("_cells", "?"),
        "gold": "full grid (%s)" % task.get("size", ""),
        "diagnosis": "" if correct else (
            "Grid not fully correct (%s cells). Every %s logic-grid puzzle is solved by the SAME "
            "method: track a grid of candidates, apply each clue to ELIMINATE options, propagate "
            "forced placements (a value used once is removed elsewhere), and iterate to a unique "
            "fill. Record this constraint-propagation PROCEDURE, not this puzzle's answer."
            % (ev.get("_cells", "?"), task.get("family", ""))),
    }


def summarize(task, response, ev):
    return (
        "USER TASK (ZebraLogic [%s]):\n%s\n\nWAS CORRECT: %s\nCELLS: %s\n\nRESPONSE (truncated):\n%s"
        % (task.get("family", ""), task.get("question", "")[:600], ev["em"] == 1.0,
           ev.get("_cells", "?"), (response or "")[:600])
    )
