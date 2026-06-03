# results/ — experiment data & figures

One subdir per experiment. Each has 3 figures (`.svg`) + the data of record
(`curve.csv`, `summary.json`, `runs/<method>_seed<k>/tasks.jsonl`) and its own
`README.md` documenting every figure and data file.

| experiment | env | target | n | seeds | doc |
|---|---|---|---|---|---|
| `haiku24/` | SearchQA (stationary, format-bound QA) | claude haiku | 24 | 2 | [haiku24/README.md](haiku24/README.md) |
| `sb_haiku/` | SpreadsheetBench (diverse procedural codegen) | claude haiku | 16 | 2 | [sb_haiku/README.md](sb_haiku/README.md) |

## The four methods (same target model + same harness; only the paradigm differs)
- **no_memory** — vanilla agent, no learning. Lower bound.
- **external_optimizer** — SkillOpt/GEPA style: optimize ONE global skill OFFLINE on a
  disjoint train split (cost paid up front), then FROZEN during eval.
- **ace** — single-tier: grow one itemized playbook, inject it in FULL each task, NO skill promotion.
- **ours_full** — two-tier: top-k memory retrieval + reflect + gated skill promotion (online).

## Protocol — prequential (test-then-train)
Tasks form a fixed-seed stream. Each task is **tested first** (using only memory built from
earlier tasks), **then learned from**. Cumulative cost is logged per task, so accuracy and
cost are measured on the same footing. `external_optimizer` pays its training cost before the
stream begins (counted in cost).

## Headline finding — the paradigm winner is regime-dependent
| | no_memory | external (offline) | ACE | **ours (online 2-tier)** |
|---|---|---|---|---|
| **SearchQA** EM | 0.708 | **0.896** ✅ | 0.812 | 0.833 |
| **SpreadsheetBench** EM | 0.375 | 0.375 | 0.375 | **0.500** ✅ |

- **Stationary, format-bound (SearchQA)** → a single skill learned once offline suffices →
  **external wins**; ours learns fastest within-stream but doesn't overtake at n=24 and costs most.
- **Diverse, procedural (SpreadsheetBench)** → one frozen skill can't cover many distinct
  operations → external & ACE give **zero** net gain; **ours is the only method that helps**.

That contrast is the paper's spine: each paradigm has a regime. See per-experiment READMEs.

## How to read each figure
- **fig_learning_curve.svg** — prequential EM (cumulative-mean accuracy) vs task index.
  Flat = no learning; upward = learning. Shaded band = min/max across seeds.
- **fig_acc_vs_cost.svg** — same EM, but x = cumulative USD (incl. training/reflection).
  Up-and-left is better (more accuracy per dollar). `external` starts shifted right (it
  pre-pays training before task 0).
- **fig_final_bars.svg** — final EM per method; black dots = individual seeds; under each bar:
  total cost and EM/$ (cost efficiency).

## Caveats (apply to all current results)
- **Small scale**: n=16–24, 2 seeds → these are **signals, not significance**. No CIs yet.
- **Within-method 1st→2nd-half deltas are confounded** by task ordering at this n (even
  no_memory "improves" half-to-half on SpreadsheetBench). Trust **between-method** gaps.
- **The promotion gate never fired** (0 skills promoted; needs a longer stream). So `ours`
  here = memory + retrieval only; the skill-promotion tier is **not yet tested**. (Next: longer run.)

Regenerate any figure: `python3 eval/plot.py results/<exp> --title "<Name>"`.
