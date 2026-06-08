"""ARC-AGI scoring KERNEL — faithful to the official Abstraction & Reasoning Corpus
scoring convention, so our grid comparison and per-task score match the published
benchmark instead of an ad-hoc reimplementation.

Provenance (the same vendoring discipline as ``sb_lib`` / ``ifeval_lib``):
  * exact-match comparison + pass@k + the fractional per-task score are lifted from
    arc-prize's reference scorer ``ARCScorer.score_task``
    (https://github.com/arcprize/model_baseline → src/arc_agi_benchmarking/scoring/scoring.py);
  * the criterion itself is fchollet's ARC-AGI README
    (https://github.com/fchollet/ARC-AGI): "Only *exact* solutions (all cells match the
    expected answer) can be said to be correct"; a task is solved only when the solver
    "produce[s] the correct output grid for *all* test inputs".

The official scorer's two load-bearing lines, verbatim, are:

    attempt_data.correct = attempt_data.answer == task.test[pair_index].output   # exact match
    score = task_score / num_pairs if num_pairs > 0 else 0.0                      # fractional

i.e. the comparison is a plain Python list-of-lists ``==`` (dimensions + every cell),
NO partial / cell-level credit; pass@k means a test pair counts as solved if ANY of its
attempts matches; the per-task score is the FRACTION of test pairs solved; the aggregate
is the mean per-task score (×100 for a percentage). This module re-expresses exactly that
kernel over grids passed directly (we already hold the gold grids and run the program
ourselves), rather than vendoring the official ``ARCScorer`` class wholesale — that wrapper
is JSON-submission / file-I/O machinery (``ARCTask`` / ``BenchmarkedTaskResults`` dataclasses,
submission-dir readers) tied to a direct-grid-PREDICTION submission format that does not
apply to our PROGRAM-SYNTHESIS setup. The scoring logic that governs correctness is the kernel
below; importing the file-I/O wrapper would add no faithfulness, only inapplicable plumbing.

Adaptation caveat — pass@1 by construction: in our env the solver emits ONE ``solve(grid)``
program which DETERMINISTICALLY produces one output per test input, so there is exactly one
attempt per pair. ``pass@k`` is preserved structurally (``attempts`` is a list) but is k=1
here; the official benchmark allows pass@2 (ARC-AGI-2) / pass@3 (ARC-AGI-1) for direct-grid
submissions. This is a property of the SOLVING protocol (program synthesis), not the scorer.

A grid is a ``list[list[int]]`` (rows of integers 0-9); ``None`` denotes "no output produced"
(e.g. the program crashed / timed out) and never matches a gold grid.
"""


def pair_correct(answer, gold):
    """One test pair's exact-match verdict — the official ``answer == output`` kernel.

    A plain list-of-lists equality: True iff dimensions AND every cell match. ``answer``
    may be ``None`` (no output produced) -> never correct.
    """
    if answer is None:
        return False
    return answer == gold


def pair_solved(attempts, gold):
    """pass@k for one test pair: True iff ANY attempt exactly matches the gold grid.

    Mirrors the official loop's ``any_attempt_correct``. ``attempts`` is the list of
    candidate output grids for this pair (k=1 in the program-synthesis setup).
    """
    return any(pair_correct(a, gold) for a in attempts)


def task_score(attempts_per_pair, golds):
    """Score one task the official way.

    ``attempts_per_pair[i]`` = the list of attempt grids for held-out test pair ``i``;
    ``golds[i]`` = its gold grid. Returns a dict:
      * ``fraction``   = task_score / num_pairs  (the official per-task score, 0.0-1.0),
      * ``n_solved``   = number of test pairs solved (any attempt exact),
      * ``n_pairs``    = number of held-out test pairs,
      * ``all_solved`` = True iff EVERY test pair is solved (the README's strict
                         "correct for *all* test inputs" task-solved binary),
      * ``per_pair``   = list[bool] of each pair's pass@k verdict.
    """
    n = len(golds)
    per_pair = [pair_solved(attempts_per_pair[i], golds[i]) for i in range(n)]
    n_solved = sum(1 for ok in per_pair if ok)
    return {
        "fraction": (n_solved / n) if n > 0 else 0.0,
        "n_solved": n_solved,
        "n_pairs": n,
        "all_solved": n > 0 and n_solved == n,
        "per_pair": per_pair,
    }


def aggregate(task_fractions):
    """Aggregate per-task ``fraction`` scores into the official benchmark percentage:
    ``mean(task_fractions) * 100`` (``ARCScorer.score_submission``'s
    ``total_score / total_tasks * 100``). Returns 0.0 on an empty set."""
    return (sum(task_fractions) / len(task_fractions) * 100.0) if task_fractions else 0.0
