#!/usr/bin/env python3
"""Phase-0 orchestrator: run methods x seeds, aggregate the prequential curve.

Prequential accuracy at task i = mean EM over tasks 1..i (test-then-train), then
averaged across seeds. Also reports cumulative cost (the C2 x-axis).

Usage:
  python3 eval/run.py --tasks eval/data/searchqa_val.jsonl --n 10 \
      --methods no_memory,ours_full --seeds 0 --outdir eval/out/smoke
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys

CODE_DIR = pathlib.Path(__file__).resolve().parents[1]


def run_one(tasks, n, method, seed, outdir, train_n=12, env_name="searchqa"):
    home = pathlib.Path(outdir) / "runs" / ("%s_seed%d" % (method, seed)) / "home"
    home.mkdir(parents=True, exist_ok=True)
    out = pathlib.Path(outdir) / "runs" / ("%s_seed%d" % (method, seed)) / "tasks.jsonl"
    env = dict(os.environ)
    env.setdefault("NATIVE_EVOLVE_CLAUDE_BIN", os.environ.get("NATIVE_EVOLVE_CLAUDE_BIN", "claude"))
    cmd = [
        sys.executable, str(CODE_DIR / "eval" / "prequential.py"),
        "--tasks", tasks, "--env", env_name, "--n", str(n), "--method", method,
        "--seed", str(seed), "--train_n", str(train_n),
        "--home", str(home), "--out", str(out),
    ]
    subprocess.run(cmd, env=env, check=True)
    return [json.loads(l) for l in out.read_text().splitlines() if l.strip()]


def running_mean(vals):
    out, s = [], 0.0
    for i, v in enumerate(vals):
        s += v
        out.append(s / (i + 1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--env", default="searchqa")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--methods", default="no_memory,ours_full")
    ap.add_argument("--seeds", default="0")
    ap.add_argument("--outdir", default="eval/out/smoke")
    ap.add_argument("--train_n", type=int, default=12,
                    help="external_optimizer: # disjoint offline training tasks")
    ap.add_argument("--workers", type=int, default=1,
                    help="parallel (method,seed) RUNS. Each run is internally sequential "
                         "(prequential online learning); seeds/methods are independent so "
                         "they parallelize safely. Cap to respect API rate limits.")
    args = ap.parse_args()

    methods = [m.strip() for m in args.methods.split(",") if m.strip()]
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    pathlib.Path(args.outdir).mkdir(parents=True, exist_ok=True)

    # results[method][seed] = list of per-task rows
    jobs = [(m, s) for m in methods for s in seeds]
    results = {m: {} for m in methods}
    if args.workers <= 1:
        for m, s in jobs:
            results[m][s] = run_one(args.tasks, args.n, m, s, args.outdir, args.train_n, args.env)
    else:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
            fut = {ex.submit(run_one, args.tasks, args.n, m, s, args.outdir, args.train_n, args.env): (m, s)
                   for m, s in jobs}
            for f in concurrent.futures.as_completed(fut):
                m, s = fut[f]
                results[m][s] = f.result()

    # aggregate prequential accuracy + cost, averaged across seeds
    curve_path = pathlib.Path(args.outdir) / "curve.csv"
    summary = {}
    with curve_path.open("w", encoding="utf-8") as f:
        f.write("method,task_idx,preq_em,preq_f1,cum_cost_usd,n_bullets\n")
        for m in methods:
            per_seed_em, per_seed_f1, per_seed_cost, per_seed_bul = [], [], [], []
            for s in seeds:
                rows = results[m][s]
                per_seed_em.append(running_mean([r["em"] for r in rows]))
                per_seed_f1.append(running_mean([r["f1"] for r in rows]))
                per_seed_cost.append([r["cum_cost_usd"] for r in rows])
                per_seed_bul.append([r["n_bullets"] for r in rows])
            n = min(len(x) for x in per_seed_em)
            for i in range(n):
                em = sum(es[i] for es in per_seed_em) / len(seeds)
                f1 = sum(es[i] for es in per_seed_f1) / len(seeds)
                cost = sum(es[i] for es in per_seed_cost) / len(seeds)
                bul = sum(es[i] for es in per_seed_bul) / len(seeds)
                f.write("%s,%d,%.4f,%.4f,%.6f,%.2f\n" % (m, i, em, f1, cost, bul))
            # first-half vs second-half raw EM (learning signal within the stream)
            def half_means(seed_idx):
                ems = [r["em"] for r in results[m][seeds[seed_idx]]]
                mid = max(1, len(ems) // 2)
                first = sum(ems[:mid]) / mid
                second = sum(ems[mid:]) / max(1, len(ems) - mid)
                return first, second
            firsts = [half_means(i)[0] for i in range(len(seeds))]
            seconds = [half_means(i)[1] for i in range(len(seeds))]
            summary[m] = {
                "final_preq_em": round(sum(es[-1] for es in per_seed_em) / len(seeds), 4),
                "final_preq_f1": round(sum(es[-1] for es in per_seed_f1) / len(seeds), 4),
                "first_half_em": round(sum(firsts) / len(seeds), 4),
                "second_half_em": round(sum(seconds) / len(seeds), 4),
                "total_cost_usd": round(sum(cs[-1] for cs in per_seed_cost) / len(seeds), 4),
                "final_bullets": round(sum(bs[-1] for bs in per_seed_bul) / len(seeds), 2),
            }

    (pathlib.Path(args.outdir) / "summary.json").write_text(json.dumps(summary, indent=2))
    print("\n==================== PHASE-0 SUMMARY ====================")
    print("tasks=%d  methods=%s  seeds=%s" % (args.n, methods, seeds))
    print("%-12s %8s %8s %9s %9s %10s %8s"
          % ("method", "preqEM", "preqF1", "1stHalf", "2ndHalf", "cost_usd", "bullets"))
    for m in methods:
        s = summary[m]
        print("%-12s %8.3f %8.3f %9.3f %9.3f %10.4f %8.1f"
              % (m, s["final_preq_em"], s["final_preq_f1"], s["first_half_em"],
                 s["second_half_em"], s["total_cost_usd"], s["final_bullets"]))
    print("curve -> %s" % curve_path)
    print("========================================================\n")


if __name__ == "__main__":
    main()
