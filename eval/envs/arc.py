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

SCORING is OFFICIAL-faithful, the GENERATOR is custom — keep the two straight (the
"reuse official scoring, don't reimplement" discipline; see docs/findings_synthesis.md):
  * score() delegates the exact-match comparison + per-task score to `arc_lib.scoring`, which
    re-expresses the official ARC-AGI kernel (fchollet/ARC-AGI README + arc-prize/model_baseline):
    grid equality is a plain list-of-lists `==` (dims + every cell, NO cell-level partial credit),
    a test pair is solved iff any attempt matches (pass@k; k=1 here -- one synthesized program ->
    one deterministic output per pair), and the per-task score is the FRACTION of pairs solved.
    score() exposes `em` (strict: all pairs solved = the README task-solved binary), `arc_task_score`
    (the official fractional score), and a NON-official cell-`f1` diagnostic (labeled as ours).
  * the GENERATOR (arc_gen.py) is necessarily self-implemented: paper5 ("ARC-AGI Stream") released
    NO code, and real ARC-AGI is not family/skill-labeled (our gate experiment needs that structure).
    -> ARC is a CONTROLLED DIAGNOSTIC env, not an external-leaderboard comparability headline.

Data: eval/data/arc_val.jsonl (tracked; rows carry family/skill/demos/tests). Re-generate:
  python3 eval/fetch.py --env arc --n 60        (see fetch.py / docs/PROGRESS.md "Data")
"""
import json
import pathlib
import re
import subprocess
import sys

try:
    from .arc_lib import scoring as arc_scoring
except ImportError:  # direct (non-package) import
    from arc_lib import scoring as arc_scoring

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
    if task.get("family"):
        # SYNTHETIC generator: the select-objects-onto-a-blank-grid story IS how arc_gen builds
        # every task, so stating it is a true (and useful) prior.
        rule_line = (
            "Every example below is produced from the INPUT grid by ONE fixed hidden rule: it selects "
            "some of the connected colored objects and applies a fixed transformation to each, drawing "
            "the result on a blank grid (unselected objects disappear).\n\n"
        )
    else:
        # REAL / DIVERSE ARC (family=""): no generative schema may be assumed. The synthetic story is
        # FALSE for most real puzzles (symmetry completion, scaling, color mapping, ...) — asserting it
        # would mislead EVERY arm, including no_memory (same false-premise hazard evidence() guards).
        rule_line = (
            "Every example below is produced from the INPUT grid by ONE fixed hidden rule that "
            "transforms the input grid into the output grid. The rule can be anything consistent "
            "across the examples (e.g. moving/recoloring/duplicating objects, completing a symmetry "
            "or pattern, scaling, cropping, overlaying); the output grid's size may differ from the "
            "input's.\n\n"
        )
    body = (
        "You are solving an ARC-style abstraction puzzle by PROGRAM SYNTHESIS.\n"
        "A grid is a list of rows of integers 0-9 (0 = black background; 1-9 are colored cells).\n"
        + rule_line +
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
    """GOLD signal: run solve on the HELD-OUT test inputs and score the official ARC-AGI way.

    The exact-match comparison + the per-pair / per-task scoring are delegated to
    ``arc_lib.scoring`` (faithful to fchollet's ARC-AGI README + arc-prize's reference scorer)
    so our grid correctness matches the published convention, not an ad-hoc check:
      * ``em``            = arc_lib ``all_solved`` — the README's strict "correct for *all*
                            test inputs" task-solved binary (1.0 iff every held-out pair is
                            an exact grid match). This is the headline metric our runs report.
      * ``arc_task_score``= arc_lib ``fraction`` (task_score / num_pairs) — the OFFICIAL
                            arc-prize per-task score (partial credit across the held-out pairs;
                            with n_tests=2 it is 0 / 0.5 / 1.0). pass@1 by construction (one
                            synthesized program -> one deterministic output per pair).
      * ``f1``            = mean held-out CELL accuracy — a NON-official diagnostic (ARC gives
                            NO cell-level partial credit). Kept for continuity/granularity, but
                            it is OURS, not part of the ARC metric. Use ``arc_task_score`` when
                            you want an ARC-faithful sub-EM.
    """
    code = _extract_code(response)
    tests = task.get("tests", [])
    ins = [t[0] for t in tests]
    golds = [t[1] for t in tests]
    outs, err = _run_solve(code, ins) if (code and ins) else (None, "no code / no tests")
    # one attempt per pair (pass@1); a crash/timeout -> no outputs -> None per pair (never matches)
    preds = outs if outs is not None else [None] * len(golds)
    ts = arc_scoring.task_score([[p] for p in preds], golds)          # official kernel
    accs = [_cell_acc(p, g) for p, g in zip(preds, golds)] if outs is not None else []
    em = 1.0 if ts["all_solved"] else 0.0
    f1 = round(sum(accs) / len(accs), 4) if accs else 0.0
    npass = ts["n_solved"]
    return {"em": em, "f1": f1, "sub_em": em, "arc_task_score": ts["fraction"],
            "predicted_answer": "(python solve)",
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


# ------------------------------------------------------------- demo-CV (REFFREE held-out check)
def apply_demo_holdout(tasks, n):
    """Harness-side demo cross-validation split (--demo_holdout n): move the LAST n demonstration
    pairs of each task from the prompt-visible task["demos"] (fit half) to task["cv_demos"] (check
    half, NEVER shown to the agent), and RE-RENDER task["question"] from the fit demos only — the
    jsonl ships a pre-rendered question embedding ALL demos, so without the re-render the held-out
    pair would leak through the prompt, retrieval, and episodic memory. Tasks with fewer than n+1
    demos are kept whole (>=1 fit demo must remain; cv signal unavailable there). In-place;
    returns (n_split, n_kept_whole). task["tests"] (gold) is untouched."""
    split = kept = 0
    for t in tasks:
        demos = t.get("demos") or []
        if len(demos) >= n + 1:
            t["cv_demos"] = demos[-n:]
            t["demos"] = demos[:-n]
            t["question"] = _render_demos(t["demos"])
            split += 1
        else:
            kept += 1
    return split, kept


def cv_check(task, attempt):
    """REFERENCE-FREE *held-out-demo* execution check (the demo-CV signal): run the candidate
    solve() on task["cv_demos"] — demonstration pairs the harness WITHHELD from the prompt
    (apply_demo_holdout). try_run's consistency-on-SHOWN-demos is necessary but 'consistent !=
    generalizes' (type-2 blind spot); passing a WITHHELD pair is a true generalization estimate —
    and still reads ZERO gold (cv demos are task-input data any deployment has). Returns
    (ok, feedback) like try_run: True / False(+why) / None (no code, or no cv_demos)."""
    code = _extract_code(attempt or "")
    if not code or "def solve" not in code:
        return None, ""
    cv = task.get("cv_demos") or []
    if not cv:
        return None, ""
    ins = [d[0] for d in cv]
    golds = [d[1] for d in cv]
    outs, err = _run_solve(code, ins)
    if outs is None:
        return False, ("Your solve() failed to run on a WITHHELD demonstration input:\n" + err)
    for i, (pred, gold) in enumerate(zip(outs, golds), 1):
        if pred != gold:
            cells = sum(len(r) for r in gold) or 1
            return False, ("Your solve() FAILS a demonstration pair that was WITHHELD from the "
                           "prompt (%d/%d cells correct): the rule you inferred fits the shown "
                           "examples but does NOT generalize. Re-examine what distinguishes your "
                           "rule from the true one."
                           % (int(_cell_acc(pred, gold) * cells), cells))
    return True, ""


# --------------------------------------------------------------------------- reflection
def evidence(task, response, ev):
    correct = ev["em"] == 1.0
    fam = task.get("family", "")
    reason = ev.get("_reason", "")[:200]
    if fam:
        # SYNTHETIC generator: tasks DO share a per-family latent procedure -> record it for the family.
        task_line = ("ARC [family=%s skill=%s]: infer the grid-transformation rule and write solve(grid)."
                     % (fam, task.get("skill", "")))
        diagnosis = "" if correct else (
            "solve() failed on held-out grids (%s). Tasks in the '%s' family ALL share one latent "
            "procedure: extract the connected colored objects (4-connectivity flood fill), SELECT "
            "the objects this family targets, apply the per-object transformation, and redraw on a "
            "blank grid. Record this object-extraction + selection PROCEDURE for the family, not "
            "this single grid's answer." % (reason, fam))
    else:
        # REAL / DIVERSE ARC: NO families -- every puzzle is unique. Do NOT claim a shared procedure
        # (that false premise collapses the memory into one over-general skill). Ask for TWO things:
        # (a) this task's SPECIFIC rule, AND (b) any GENERAL, REUSABLE technique that would help a
        # DIFFERENT puzzle -- those recurring techniques are what consolidate into multiple skills even
        # though the tasks are NOT the same family.
        task_line = "ARC puzzle (standalone, no shared family): infer this grid's rule and write solve(grid)."
        diagnosis = "" if correct else (
            "solve() failed on held-out grids (%s). This is a UNIQUE puzzle with its OWN rule -- there is "
            "NO shared family procedure to assume. Record BOTH: (1) the SPECIFIC transformation THIS task "
            "needs (which objects/cells, what operation, how the output grid is constructed); and (2) any "
            "GENERAL, TRANSFERABLE technique or sub-procedure it taught you that would help solve OTHER, "
            "DIFFERENT ARC puzzles -- e.g. extracting connected components, detecting symmetry/reflection, "
            "finding a repeating tile, mapping colors, cropping to the active region, or always running "
            "solve() on the shown examples before finalizing. Frame the lesson as a reusable METHOD, not "
            "this grid's answer." % reason)
    return {
        "outcome": "PASS" if correct else "FAIL",
        "task": task_line,
        "predicted": "held-out tests passed: %s" % ev.get("_tests", "?"),
        "gold": "exact grid reproduction on held-out inputs",
        "diagnosis": diagnosis,
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
