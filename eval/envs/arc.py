"""ARC-AGI Stream environment — program-synthesis over ARC-style few-shot grids.

Borrowed from paper5 ("Useful Memories Become Faulty...", arXiv 2605.12978); the
self-contained task generator lives in `arc_gen.py`. Each task shows the solver K
input->output demonstrations sharing ONE latent (family, skill) rule; the solver writes
`def solve(grid)` (grids are list[list[int]], colors 0-9, 0 = background). Correctness is
DETERMINISTIC + EXECUTABLE: run the program, compare grids cell-for-cell.

This env exists to give the promotion gate a regime it never had (session-15): a PRECISE,
executable reference-free signal (`try_run` runs the program on the SHOWN demos -> exact
match) AND shared-procedure FAMILY structure (a per-family skill transfers to every
instance). Contrast dyck, where the reference-free signal was blind NL self-critique.

Two correctness signals, deliberately distinct:
  - score()   = ORACLE/gold: run solve on HELD-OUT test inputs (unseen) -> generalization EM.
  - try_run() = REFERENCE-FREE: run solve on the K demos shown in the prompt (no gold needed,
                the demos ARE the task) -> the precise self_verify execution channel.
A program that overfits the demos but fails held-out is the realistic reffree<oracle gap;
on ARC program synthesis with several diverse demos the two nearly coincide -> the signal is
genuinely precise (the whole point).

Data: eval/data/arc_val.jsonl (tracked; rows carry family/skill/demos/tests). Re-generate:
  python3 eval/fetch.py --env arc --n 60        (see fetch.py / docs/PROGRESS.md "Data")
"""
import json
import pathlib
import re
import subprocess
import sys

NAME = "arc"

_TIMEOUT = 12                       # seconds per exec batch (guards infinite loops in solve)


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
            r["question"] = r.get("question") or _render_demos(r.get("demos", []))
            out.append(r)
    return out


# --------------------------------------------------------------------------- rendering
def _render_grid(grid):
    return "\n".join(" ".join(str(v) for v in row) for row in grid)


def _render_demos(demos):
    chunks = []
    for i, (gin, gout) in enumerate(demos, 1):
        chunks.append("# Example %d\nINPUT:\n%s\nOUTPUT:\n%s"
                      % (i, _render_grid(gin), _render_grid(gout)))
    return "\n\n".join(chunks)


def build_prompt(task, mem):
    body = (
        "You are solving an ARC-style abstraction puzzle by PROGRAM SYNTHESIS.\n"
        "A grid is a list of rows of integers 0-9 (0 = black background; 1-9 are colored cells).\n"
        "Every example below is produced from the INPUT grid by ONE fixed hidden rule: it selects "
        "some of the connected colored objects and applies a fixed transformation to each, drawing "
        "the result on a blank grid (unselected objects disappear).\n\n"
        "Infer the rule from ALL the examples, then write a Python function with the EXACT signature "
        "`def solve(grid):` that takes a list[list[int]] and returns the transformed list[list[int]]. "
        "Your function must reproduce every example. Use only the Python standard library. Put the "
        "function in ONE ```python code block and nothing else after it.\n\n"
        "# Examples\n%s" % _render_demos(task.get("demos", []))
    )
    return (mem + "\n\n" + body) if mem else body


# --------------------------------------------------------------------------- code exec
def _extract_code(text):
    """First ```python (or bare ```) fenced block; fall back to the whole text."""
    if not text:
        return ""
    m = re.search(r"```(?:python|py)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return text.strip()


_DRIVER = r"""
import json, sys
data = json.load(sys.stdin)
ns = {}
try:
    exec(data["code"], ns)
    solve = ns.get("solve")
    if not callable(solve):
        print(json.dumps({"ok": False, "error": "no callable solve(grid) defined"})); sys.exit(0)
    outs = []
    for g in data["inputs"]:
        r = solve([list(row) for row in g])
        outs.append([[int(x) for x in row] for row in r])
    print(json.dumps({"ok": True, "outputs": outs}))
except Exception as e:
    import traceback
    print(json.dumps({"ok": False, "error": traceback.format_exc()[-1200:]}))
"""


def _run_solve(code, inputs):
    """Execute `code`'s solve() on each input grid in a sandboxed subprocess (timeout-guarded).
    Returns (outputs|None, error_str). outputs is a list of grids aligned with `inputs`."""
    payload = json.dumps({"code": code, "inputs": inputs})
    try:
        proc = subprocess.run([sys.executable, "-c", _DRIVER], input=payload,
                              capture_output=True, text=True, timeout=_TIMEOUT)
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT: solve() did not finish within %ds (likely an infinite loop)." % _TIMEOUT
    if proc.returncode != 0:
        return None, ("subprocess crashed: " + (proc.stderr or "")[-1000:])
    try:
        res = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:
        return None, ("unparseable runner output: " + (proc.stdout or "")[-600:])
    if not res.get("ok"):
        return None, res.get("error", "unknown exec error")
    return res.get("outputs"), ""


def _cell_acc(pred, gold):
    if pred is None or len(pred) != len(gold) or any(len(a) != len(b) for a, b in zip(pred, gold)):
        return 0.0
    tot = sum(len(row) for row in gold) or 1
    ok = sum(1 for a, b in zip(pred, gold) for x, y in zip(a, b) if x == y)
    return ok / tot


# --------------------------------------------------------------------------- scoring (ORACLE)
def score(task, response):
    """GOLD signal: run solve on the HELD-OUT test inputs and require exact match on all of them.
    em = 1.0 iff every held-out test reproduces exactly; f1 = mean held-out cell accuracy."""
    code = _extract_code(response)
    tests = task.get("tests", [])
    ins = [t[0] for t in tests]
    golds = [t[1] for t in tests]
    outs, err = _run_solve(code, ins) if (code and ins) else (None, "no code / no tests")
    accs, exacts = [], []
    if outs is not None:
        for pred, gold in zip(outs, golds):
            accs.append(_cell_acc(pred, gold))
            exacts.append(pred == gold)
    em = 1.0 if (exacts and all(exacts)) else 0.0
    f1 = round(sum(accs) / len(accs), 4) if accs else 0.0
    npass = sum(1 for e in exacts if e)
    return {"em": em, "f1": f1, "sub_em": em, "predicted_answer": "(python solve)",
            "gold_answers": ["%d held-out grids" % len(tests)],
            "_tests": "%d/%d" % (npass, len(tests)), "_exec_err": err,
            "_reason": "" if em else (err or "solve failed %d/%d held-out tests"
                                      % (len(tests) - npass, len(tests)))}


# --------------------------------------------------------------------------- verify (structural)
def verify(task, attempt):
    """REFERENCE-FREE structural check (reads no gold): did the model emit a fenced code block
    that DEFINES solve(grid)? Repair fires on a missing/empty/malformed program. (The semantic
    execution check is try_run, used by self_verify's execution channel.)"""
    code = _extract_code(attempt or "")
    if not code:
        return {"ok": False, "signature": "no-code",
                "feedback": "No code found. Put a `def solve(grid):` in one ```python block."}
    if "def solve" not in code:
        return {"ok": False, "signature": "no-solve",
                "feedback": "Your code does not define `def solve(grid):`. Use that exact signature."}
    return {"ok": True, "signature": "", "feedback": ""}


# --------------------------------------------------------------------------- try_run (REFFREE exec)
def try_run(task, attempt):
    """REFERENCE-FREE execution channel for self_verify: run the candidate solve() on the K
    DEMONSTRATION inputs shown in the prompt and check it reproduces their outputs (the demos are
    part of the task -> no gold needed). Returns (ran_ok, feedback):
      True  -> runs clean AND matches every demo (precise PASS signal),
      False -> crashed or mismatched a demo (feedback carries the traceback / first mismatch),
      None  -> no code to run (let the critique channel decide).
    This is the PRECISE signal that un-blinds the gate (vs dyck's NL self-critique)."""
    code = _extract_code(attempt or "")
    if not code or "def solve" not in code:
        return None, ""
    demos = task.get("demos", [])
    ins = [d[0] for d in demos]
    golds = [d[1] for d in demos]
    outs, err = _run_solve(code, ins)
    if outs is None:
        return False, ("Your solve() failed to run on the examples:\n" + err)
    for i, (pred, gold) in enumerate(zip(outs, golds), 1):
        if pred != gold:
            return False, ("Your solve() does not reproduce example %d (%d/%d cells correct). "
                           "Re-examine the rule and fix it." % (i, int(_cell_acc(pred, gold) *
                           (sum(len(r) for r in gold) or 1)), sum(len(r) for r in gold)))
    return True, ""


# --------------------------------------------------------------------------- reflection
def evidence(task, response, ev):
    correct = ev["em"] == 1.0
    fam = task.get("family", "")
    return {
        "outcome": "PASS" if correct else "FAIL",
        "task": "ARC [family=%s skill=%s]: infer the grid-transformation rule and write solve(grid)."
                % (fam, task.get("skill", "")),
        "predicted": "held-out tests passed: %s" % ev.get("_tests", "?"),
        "gold": "exact grid reproduction on held-out inputs",
        "diagnosis": "" if correct else (
            "solve() failed on held-out grids (%s). Tasks in the '%s' family ALL share one latent "
            "procedure: extract the connected colored objects (4-connectivity flood fill), SELECT "
            "the objects this family targets, apply the per-object transformation, and redraw on a "
            "blank grid. Record this object-extraction + selection PROCEDURE for the family, not "
            "this single grid's answer." % (ev.get("_reason", "")[:200], fam)),
    }


def summarize(task, response, ev):
    return (
        "USER TASK (ARC [family=%s skill=%s], program synthesis):\n%s\n\nWAS CORRECT: %s\n"
        "HELD-OUT: %s\n\nRESPONSE (truncated):\n%s"
        % (task.get("family", ""), task.get("skill", ""), task.get("question", "")[:700],
           ev["em"] == 1.0, ev.get("_tests", "?"), (response or "")[:700])
    )


# --------------------------------------------------------------------------- materializer
def fetch(n, out, seed=0, n_demos=4, n_tests=2, size_range=(12, 17), nobj_range=(3, 6),
          families=None, skills=None):
    """Generate a FAMILY-STRATIFIED pool of n tasks (round-robin over family x skill so every
    latent rule recurs ~n/21 times -> shared-procedure repetition for skill formation) and write
    it as jsonl. Deterministic given `seed`. Re-generate: python3 eval/fetch.py --env arc --n 60.
    The prequential runner does its own acquire/val/test (or prequential) split over this pool.
    `size_range`/`nobj_range`/`n_demos` are difficulty knobs (used by the headroom probe).
    `families`/`skills` (lists) restrict the combo pool -> a FOCUSED stream (e.g. families=
    ['group_by_shape'] for the headroom-family skill-formation run)."""
    import numpy as np
    try:
        from . import arc_gen
    except ImportError:  # direct (non-package) import
        import arc_gen
    rng = np.random.default_rng(seed)
    fams = families or list(arc_gen.FAMILIES)
    sks = skills or list(arc_gen.SKILLS)
    combos = [(f, s) for f in fams for s in sks]
    order = []
    while len(order) < n:
        rng.shuffle(combos)
        order.extend(combos)
    rows = []
    for i in range(n):
        fam, sk = order[i]
        task = arc_gen.gen_task(fam, sk, rng, n_demos=n_demos, n_tests=n_tests,
                                size_range=size_range, nobj_range=nobj_range)
        task["id"] = "arc-%s-%s-%03d" % (fam, sk, i)
        task["question"] = _render_demos(task["demos"])
        rows.append(task)
    outp = pathlib.Path(out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    print("wrote %d ARC tasks -> %s (%d families x %d skills)"
          % (len(rows), out, len(arc_gen.FAMILIES), len(arc_gen.SKILLS)))
