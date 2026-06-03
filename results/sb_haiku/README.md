# sb_haiku — SpreadsheetBench, 4 methods, 2 seeds

**Setup.** Env = SpreadsheetBench (instruction → Python/openpyxl codegen → execute → official
cell-level comparison vs golden xlsx). Target = `claude` with `NATIVE_EVOLVE_MODEL=haiku`. Stream
n=16, seeds {0,1}. Prequential test-then-train. This is **SkillOpt's home benchmark**.
**Why this env:** diverse procedural tasks (many distinct spreadsheet operations) with mid-range
base accuracy (~0.38 — real headroom, no floor/ceiling). This is the regime that should FAVOR
*accumulating multiple distinct skills* over one frozen global skill.

## Results
| method | EM | per-seed | 1st half | 2nd half | Δhalf | cost $ | EM/$ | bullets |
|---|---|---|---|---|---|---|---|---|
| no_memory | 0.375 | 0.38 / 0.38 | 0.312 | 0.438 | +0.125 | 0.591 | 0.63 | 0 |
| external_optimizer | 0.375 | 0.38 / 0.38 | 0.375 | 0.375 | +0.000 | 0.936 | 0.40 | 0 |
| ace | 0.375 | 0.44 / 0.31 | 0.312 | 0.438 | +0.125 | 0.981 | 0.38 | ~40 |
| **ours_full** | **0.500** | 0.56 / 0.44 | 0.438 | 0.562 | +0.125 | 1.047 | 0.48 | ~40 |

**Takeaways.**
1. **ours is the ONLY method that beats no_memory** (0.500 vs 0.375 = +12.5 pts), and it wins on
   **both** seeds (0.56 / 0.44 vs ~0.375 for everyone else). **C2 (native online > external offline) is supported in this regime.**
2. **external offline gives ZERO net gain** (0.375 = no_memory) while costing 1.6× more → it is
   *strictly dominated*. One frozen global skill can't cover the diverse operations.
3. **ace also gives zero net gain** despite accumulating ~40 bullets — dumping the whole flat
   playbook into context doesn't help; **ours's top-k retrieval over the same memory does** (0.500 vs 0.375).
   That's the C1 signal: *how* memory is structured/injected matters, not just having it.

## Figures

### fig_final_bars.svg — *the bottom line (clearest figure for this experiment)*
Final EM as bars; black dots = the two seeds; under each bar: total cost and EM/$.
- **Read:** bar height = accuracy; dots = per-seed spread.
- **Shows here:** three bars tied at **0.375** (no_memory, external, ace) and **one taller bar at
  0.500** (ours). ours's two seed-dots (0.56, 0.44) **both sit above** the 0.375 line → the win isn't
  a single-seed fluke. external/ace cost more for no gain (lower EM/$).

### fig_learning_curve.svg — *EM over the stream*
Prequential EM vs task index (0–15), line per method, band = min/max across seeds.
- **Read:** flat = no learning; rising = learning; right-edge gap = final difference.
- **Shows here:** `ours` ends clearly highest. **Caveat:** at n=16 the curves are noisy and even
  `no_memory` drifts up half-to-half (just task-ordering luck), so don't over-read the *slope* —
  the trustworthy signal is the **final gap** (ours above the pack).

### fig_acc_vs_cost.svg — *accuracy per dollar*
EM vs cumulative USD (incl. external's offline training, paid before task 0).
- **Read:** up-and-left is better.
- **Shows here:** `external` and `ace` spend more than `no_memory` for the **same** accuracy (they
  move right, not up). `ours` is the only one that moves **up** — it buys real accuracy with its
  extra spend (EM/$ 0.48 vs external 0.40, ace 0.38).

## Data files
- **`curve.csv`** — seed-averaged series: `method, task_idx, preq_em, preq_f1, cum_cost_usd, n_bullets`.
- **`summary.json`** — authoritative final aggregate for all 4 methods (recomputed from `runs/`):
  per method `em, em_per_seed, first_half, second_half, cost_usd, bullets`. Matches the table above.
- **`runs/<method>_seed<k>/tasks.jsonl`** — raw per-task: `idx, id, em (1=all cells match), f1, ...,
  n_bullets, cum_cost_usd`. EM here = official SpreadsheetBench all-cells-correct.
- (`runs/<...>/home/` — isolated per-run memory/ledger; gitignored.)

## Caveats specific to this experiment
- **The promotion gate never fired** (0 skills in any run): with helpful≥5/uses≥5 thresholds and
  only 16 tasks, no bullet matured. So `ours` here = **memory + retrieval only**; the headline
  *memory→skill* mechanism is **untested**. The #1 next experiment is a longer stream to fire it.
- n=16, 2 seeds → signal, not significance. Bump seeds + n and add CIs before claiming.

## Reproduce
```bash
export NATIVE_EVOLVE_MODEL=haiku
python3 eval/run.py --tasks eval/data/spreadsheet/spreadsheetbench_verified_400/dataset.json \
  --env spreadsheetbench --n 16 \
  --methods no_memory,external_optimizer,ace,ours_full --seeds 0,1 --workers 4 --outdir results/sb_haiku
python3 eval/plot.py results/sb_haiku --title "SpreadsheetBench"
```
(SpreadsheetBench data is gitignored — re-fetch per `docs/PROGRESS.md` → "Data".)
