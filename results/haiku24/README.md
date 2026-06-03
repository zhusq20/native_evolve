# haiku24 — SearchQA, 4 methods, 2 seeds

**Setup.** Env = SearchQA (context-grounded trivia QA, exact-match scored). Target = `claude`
with `NATIVE_EVOLVE_MODEL=haiku`. Stream length n=24, seeds {0,1}. Prequential test-then-train.
**Why this env:** stationary, format-bound — the transferable knowledge is mostly *answer-format
discipline*. This is the regime that should FAVOR a one-shot offline optimizer.

## Results
| method | EM | per-seed | 1st half | 2nd half | Δhalf | cost $ | EM/$ | bullets |
|---|---|---|---|---|---|---|---|---|
| no_memory | 0.708 | 0.67 / 0.75 | 0.708 | 0.708 | +0.000 | 0.371 | 1.91 | 0 |
| **external_optimizer** | **0.896** | 0.92 / 0.88 | 0.875 | 0.917 | +0.042 | 0.556 | 1.61 | 0 |
| ace | 0.812 | 0.79 / 0.83 | 0.792 | 0.833 | +0.042 | 0.652 | 1.25 | 6 |
| ours_full | 0.833 | 0.79 / 0.88 | 0.750 | 0.917 | +0.167 | 0.775 | 1.08 | 6 |

**Takeaways.**
1. **External offline optimizer wins (0.896).** One global format skill, learned cheaply off a
   12-task train split then frozen, is the best tool here. **C2 (native ≥ external) is NOT supported in this regime.**
2. **ours has the steepest in-stream learning** (Δhalf +0.167, vs +0.04 for ace/external, 0.00 for
   no_memory) and ties external on the 2nd half (0.917) — but it starts lower (0.750) and never
   overtakes within 24 tasks, while paying the most (lowest EM/$ = 1.08).
3. **ours edges ace (0.833 vs 0.812)** — weak support for two-tier > single-tier (C1), but both lag external.

## Figures

### fig_learning_curve.svg — *does the method learn over the stream?*
Prequential EM (cumulative-mean accuracy) on the y-axis vs task index (0–23) on the x-axis; one
line per method, shaded band = min/max across the 2 seeds.
- **Read:** flat line = no learning; rising line = learning. The gap between lines at the right
  edge = final accuracy difference.
- **Shows here:** `no_memory` is flat (~0.71). `external` sits highest and nearly flat (frozen skill,
  good from task 0). `ours` starts lowest and **climbs the most**, crossing `ace` and converging
  toward `external` by the end — the "learning happens, but too slowly to overtake" story.

### fig_acc_vs_cost.svg — *accuracy per dollar (the C2 axes)*
Same EM on y, but x = cumulative USD (target calls + reflection + any offline training).
- **Read:** up-and-to-the-left is better. A method that reaches the same EM further left is cheaper.
- **Shows here:** `external` reaches high EM at low cost (training is cheap, eval is single-pass).
  `ours` drifts right (every task pays a reflection tax) for less final EM → **external dominates ours on both axes here.**

### fig_final_bars.svg — *the bottom line per method*
Final EM as bars; black dots = the two individual seeds (spread = noise); under each bar: total
cost and EM/$ (cost efficiency).
- **Read:** bar height = accuracy; dots close together = stable across seeds; EM/$ = bang-per-buck.
- **Shows here:** external tallest; ours second; the two seed-dots are close for every method
  (reasonably stable at n=24). EM/$ falls as methods spend more (no_memory 1.91 → ours 1.08).

## Data files
- **`curve.csv`** — seed-averaged time series. Columns: `method, task_idx, preq_em, preq_f1,
  cum_cost_usd, n_bullets`. One row per (method, task index). This is what the curve figures plot.
- **`summary.json`** — authoritative final aggregate for all 4 methods (recomputed from `runs/`):
  per method `em, em_per_seed, first_half, second_half, cost_usd, bullets`. Matches the table above.
- **`runs/<method>_seed<k>/tasks.jsonl`** — raw per-task record (the source of truth). One JSON line
  per task: `idx, id, em, f1, sub_em, pred, n_bullets, cum_cost_usd, cum_output_tokens`.
- (`runs/<...>/home/` — per-run isolated memory/ledger/transcripts; gitignored, regenerable.)

## Reproduce
```bash
export NATIVE_EVOLVE_MODEL=haiku
python3 eval/run.py --tasks eval/data/searchqa_val.jsonl --env searchqa --n 24 \
  --methods no_memory,external_optimizer,ace,ours_full --seeds 0,1 --workers 4 --outdir results/haiku24
python3 eval/plot.py results/haiku24 --title "SearchQA"
```
