"""Convert the REAL ARC-AGI-1 dataset (fchollet/ARC-AGI) into the `arc` env's jsonl format.

The `arc` env (eval/envs/arc.py) is data-agnostic: it reads `demos` (the shown
input->output pairs) and `tests` (held-out input->output pairs) off each row and solves by
PROGRAM SYNTHESIS (`def solve(grid)`), scoring with the official ARC-AGI exact-match kernel
(arc_lib/scoring.py). So real ARC tasks drop straight in — we only reshape the JSON.

Key difference from the synthetic generator (arc_gen.py): real ARC tasks are all UNIQUE —
there are NO shared-procedure families. So:
  * family is left EMPTY ("") and skill "" — real ARC has no shared-procedure families, and a
    non-empty family triggers arc.py:evidence()'s family-procedure diagnosis (correct for the
    synthetic generator, FALSE here). Empty family routes evidence() to the per-task (diverse)
    branch. `--stratify_key family` still works (one "" stratum => random split).
  * the BOUNDARY thesis predicts the skill/consolidation tier should add little here (no
    family => no shared latent procedure to abstract); episodic/distilled memory may still
    transfer general ARC strategy. This is the diverse/singleton side of the boundary on a
    REAL benchmark (vs the synthetic family-rich side).

Provenance: fchollet/ARC-AGI (Apache-2.0), data/{training,evaluation}/*.json. Each source
file is {"train": [{"input","output"}...], "test": [{"input","output"}...]}; the task id is
the 8-hex filename stem (kept as our row id => externally referenceable, unlike generated ids).

Usage:
  git clone --depth 1 https://github.com/fchollet/ARC-AGI.git /tmp/ARC-AGI
  python3 eval/fetch_arc_real.py --src /tmp/ARC-AGI/data/training --n 60 \
      --out eval/data/arc_real_train.jsonl
Options:
  --max_cells N   keep only tasks whose every grid has <= N cells (floor/cost control on haiku;
                  0 = no filter). Real ARC grids run 1..900 cells (median ~88).
  --seed K        deterministic shuffle before taking the first n (default 0).
"""
import argparse
import json
import pathlib

try:
    from .envs import arc as arc_env
except ImportError:  # run as a script
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    from envs import arc as arc_env


def _task_max_cells(d):
    m = 0
    for p in d["train"] + d["test"]:
        for g in (p["input"], p["output"]):
            m = max(m, len(g) * (len(g[0]) if g else 0))
    return m


def convert(src, n, out, seed=0, max_cells=0):
    import numpy as np
    src = pathlib.Path(src)
    files = sorted(src.glob("*.json"))
    if not files:
        raise SystemExit("no *.json under %s — clone fchollet/ARC-AGI first" % src)
    rows = []
    for fp in files:
        d = json.loads(fp.read_text(encoding="utf-8"))
        if not d.get("train") or not d.get("test"):
            continue
        if max_cells and _task_max_cells(d) > max_cells:
            continue
        demos = [[p["input"], p["output"]] for p in d["train"]]
        tests = [[p["input"], p["output"]] for p in d["test"]]
        rows.append({
            "id": "arc-real-%s" % fp.stem,
            "family": "",              # real ARC has NO families: leave EMPTY (do not fake "real").
                                       # A non-empty family makes arc.py:evidence() inject a FALSE
                                       # "all tasks in this family share one latent procedure" diagnosis
                                       # (true for the synthetic generator, false for real ARC) -> the
                                       # reflector parrots one idea -> homogeneous memory -> a single
                                       # over-general skill. Empty family routes evidence() to its
                                       # per-task (diverse) branch so each unique puzzle distils its OWN
                                       # specific rule PLUS any transferable technique -> multiple skills.
            "skill": "",
            "params": {},
            "demos": demos,
            "tests": tests,
            "question": arc_env._render_demos(demos),
        })
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(rows))
    rows = [rows[i] for i in idx[:n]] if n and n < len(rows) else [rows[i] for i in idx]
    outp = pathlib.Path(out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    print("wrote %d real ARC-AGI tasks -> %s (from %d files in %s; max_cells=%s)"
          % (len(rows), out, len(files), src, max_cells or "off"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="ARC-AGI data dir (training or evaluation)")
    ap.add_argument("--n", type=int, default=0, help="cap (0 = all)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max_cells", type=int, default=0)
    args = ap.parse_args()
    convert(args.src, args.n, args.out, seed=args.seed, max_cells=args.max_cells)


if __name__ == "__main__":
    main()
