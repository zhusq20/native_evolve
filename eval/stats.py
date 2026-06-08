#!/usr/bin/env python3
"""Paired significance for two methods' per-task correctness — the P0 stats gap.

Reads the per-task `em` (0/1) from two methods' `tasks.jsonl` files, pairs rows by task `id`
(within each matched seed file), pools the matched pairs across seeds, and reports:
  - McNemar's EXACT test (two-sided binomial on the discordant pairs) — the right paired test for
    two binary classifiers on the SAME items (it conditions on the discordant cells b,c).
  - a paired BOOTSTRAP 95% CI on the EM difference (resample matched pairs with replacement).

Pure stdlib (math.comb + random) — no scipy/numpy — so it runs on the 3.9 dev box. Zero claude spend.

Usage:
  python3 eval/stats.py \
      --a results/<exp>/runs/ours_full_seed0/tasks.jsonl results/<exp>/runs/ours_full_seed1/tasks.jsonl \
      --b results/<exp>/runs/no_memory_seed0/tasks.jsonl results/<exp>/runs/no_memory_seed1/tasks.jsonl \
      [--label-a ours_full --label-b no_memory] [--boot 10000] [--seed 0]
  python3 eval/stats.py --self-test     # synthetic-data sanity check, no files needed

`--a`/`--b` take matched lists (i-th A file is paired with the i-th B file — same seed/split). Rows
are matched by `id`; tasks missing from either side of a pair are dropped (with a stderr note).
"""
import argparse
import json
import math
import random
import sys
from typing import Dict, List, Tuple


def _load_em_by_id(path):
    # type: (str) -> Dict[str, int]
    out = {}  # type: Dict[str, int]
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            tid = str(row.get("id", row.get("idx")))
            out[tid] = 1 if float(row.get("em", 0.0)) >= 1.0 else 0
    return out


def pair_files(a_paths, b_paths):
    # type: (List[str], List[str]) -> List[Tuple[int, int]]
    """Return matched (em_a, em_b) pairs pooled across the matched file lists."""
    if len(a_paths) != len(b_paths):
        raise ValueError("--a and --b must have the SAME number of files (matched seeds): "
                         "%d vs %d" % (len(a_paths), len(b_paths)))
    pairs = []  # type: List[Tuple[int, int]]
    for ap, bp in zip(a_paths, b_paths):
        ea, eb = _load_em_by_id(ap), _load_em_by_id(bp)
        common = ea.keys() & eb.keys()
        dropped = (ea.keys() | eb.keys()) - common
        if dropped:
            sys.stderr.write("note: %d task id(s) unmatched between %s and %s — dropped\n"
                             % (len(dropped), ap, bp))
        for tid in sorted(common):
            pairs.append((ea[tid], eb[tid]))
    return pairs


def mcnemar_exact(pairs):
    # type: (List[Tuple[int, int]]) -> Dict[str, float]
    """Exact two-sided McNemar. b = A-right/B-wrong, c = A-wrong/B-right; under H0 b~Binom(b+c,.5)."""
    b = sum(1 for x, y in pairs if x == 1 and y == 0)
    c = sum(1 for x, y in pairs if x == 0 and y == 1)
    n = b + c
    if n == 0:
        return {"b": 0, "c": 0, "p_value": 1.0}
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) * (0.5 ** n)
    p = min(1.0, 2.0 * tail)
    return {"b": float(b), "c": float(c), "p_value": p}


def bootstrap_diff_ci(pairs, n_boot=10000, seed=0, alpha=0.05):
    # type: (List[Tuple[int, int]], int, int, float) -> Dict[str, float]
    """Paired bootstrap CI on mean(em_a - em_b). Resample matched pairs with replacement."""
    n = len(pairs)
    if n == 0:
        return {"mean_a": 0.0, "mean_b": 0.0, "diff": 0.0, "ci_lo": 0.0, "ci_hi": 0.0}
    rng = random.Random(seed)
    mean_a = sum(x for x, _ in pairs) / n
    mean_b = sum(y for _, y in pairs) / n
    diffs = []
    for _ in range(n_boot):
        s = 0
        for _ in range(n):
            x, y = pairs[rng.randrange(n)]
            s += x - y
        diffs.append(s / n)
    diffs.sort()
    lo = diffs[int((alpha / 2) * n_boot)]
    hi = diffs[min(n_boot - 1, int((1 - alpha / 2) * n_boot))]
    return {"mean_a": mean_a, "mean_b": mean_b, "diff": mean_a - mean_b, "ci_lo": lo, "ci_hi": hi}


def report(pairs, label_a="A", label_b="B", n_boot=10000, seed=0):
    # type: (List[Tuple[int, int]], str, str, int, int) -> Dict
    mc = mcnemar_exact(pairs)
    bs = bootstrap_diff_ci(pairs, n_boot=n_boot, seed=seed)
    sig = "***" if mc["p_value"] < 0.001 else "**" if mc["p_value"] < 0.01 \
        else "*" if mc["p_value"] < 0.05 else "ns"
    print("n_paired=%d   %s EM=%.3f   %s EM=%.3f" % (len(pairs), label_a, bs["mean_a"], label_b, bs["mean_b"]))
    print("  diff(%s-%s) = %+.3f   95%% bootstrap CI [%+.3f, %+.3f]"
          % (label_a, label_b, bs["diff"], bs["ci_lo"], bs["ci_hi"]))
    print("  McNemar exact: b(%s+/%s-)=%d  c(%s-/%s+)=%d  p=%.4g  [%s]"
          % (label_a, label_b, int(mc["b"]), label_a, label_b, int(mc["c"]), mc["p_value"], sig))
    return {"label_a": label_a, "label_b": label_b, "n": len(pairs), **mc, **bs}


def _self_test():
    # A strictly dominates B (every B-correct is A-correct, plus A rescues 8 more) -> p should be tiny.
    pairs = [(1, 1)] * 20 + [(1, 0)] * 8 + [(0, 0)] * 12
    r = mcnemar_exact(pairs)
    assert r["b"] == 8 and r["c"] == 0, r
    assert r["p_value"] < 0.01, r           # 8 vs 0 discordant -> 2*0.5^8 = 0.0078
    bs = bootstrap_diff_ci(pairs, n_boot=2000, seed=1)
    assert bs["diff"] > 0 and bs["ci_lo"] > 0, bs   # CI excludes 0 -> significant lift
    # No difference -> not significant, CI straddles 0.
    pairs2 = [(1, 1)] * 10 + [(1, 0)] * 5 + [(0, 1)] * 5 + [(0, 0)] * 10
    r2 = mcnemar_exact(pairs2)
    assert r2["p_value"] == 1.0, r2          # b==c -> symmetric -> p=1
    bs2 = bootstrap_diff_ci(pairs2, n_boot=2000, seed=1)
    assert bs2["ci_lo"] < 0 < bs2["ci_hi"], bs2
    # Empty / all-concordant guards.
    assert mcnemar_exact([])["p_value"] == 1.0
    assert mcnemar_exact([(1, 1), (0, 0)])["p_value"] == 1.0
    print("stats.py self-test: OK (McNemar exact + paired bootstrap CI)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--a", nargs="+", help="method-A tasks.jsonl file(s), one per seed/split")
    ap.add_argument("--b", nargs="+", help="method-B tasks.jsonl file(s), matched 1:1 with --a")
    ap.add_argument("--label-a", default="A")
    ap.add_argument("--label-b", default="B")
    ap.add_argument("--boot", type=int, default=10000, help="bootstrap resamples")
    ap.add_argument("--seed", type=int, default=0, help="bootstrap RNG seed")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        _self_test()
        return
    if not args.a or not args.b:
        ap.error("provide --a and --b (matched tasks.jsonl lists), or --self-test")
    pairs = pair_files(args.a, args.b)
    report(pairs, args.label_a, args.label_b, n_boot=args.boot, seed=args.seed)


if __name__ == "__main__":
    main()
