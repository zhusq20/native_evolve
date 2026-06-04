# Evaluation protocols — prequential vs frozen-deployment

Two complementary protocols in `eval/prequential.py`, selected by `--protocol`. They answer
different questions; keep both. Grounded in SkillOpt's train/val/test manifest convention.

## Why two protocols
- **prequential** (online, default): one shuffled stream, each task TESTED with the memory built
  from tasks `1..i-1` then TRAINED on. Measures *continuous online adaptation* — the learning
  curve. Where **C1** lives (does two-tier memory+skill beat single-tier ACE as memory
  accumulates?). Caveat: a task can be tested right after a near-duplicate, so the headline mixes
  genuine reuse with *local adaptation*.
- **frozen** (SkillOpt-style): **acquire** on a train split (online learning) → **gate** skill
  edits on a val/selection split → **FREEZE** memory+skills → report the headline on a held-out
  **test** split with no further learning. Measures *reuse / transfer*, not local adaptation —
  the fair arena for **C2** (online-acquired `ours` vs offline-acquired `external` on the SAME
  held-out test, compared at equal deployment cost).

## The three splits (SkillOpt roles)
| split | flag | role | SB size |
|---|---|---|---|
| **train** | `--train_n` | rollout evidence the method LEARNS on (frozen acquisition stream; also the external optimizer's offline-training set) | 80 |
| **val / selection** | `--verify_n` | held-out tasks for the accept/reject **skill-edit gate** (`verify.lift_over_base`) | 40 |
| **test** | `--test_n` | frozen held-out **headline** (0 = all remaining after train+val) | 280 |

SkillOpt's manifest is a consistent **~20% / 10% / 70%** across datasets (SearchQA 400/200/1400,
SpreadsheetBench 80/40/280, DocVQA 107/53/374, OfficeQA 50/24/172, LiveMathBench 35/18/124,
ALFWorld 39/18/134). Mirror the ratio for new datasets; mirror the exact sizes where we share a
dataset (SB) for head-to-head comparability.

**Reproducibility rule:** cite the *released split manifest*, not paper-body prose. (SkillOpt's
text says ALFWorld 39/140/134 but the manifest says 39/18/134 — the manifest is the reproducible
split; the 140 is a likely typo.)

## Splitter (`stratified_split`)
Seeded, disjoint, EXACT sizes. With `--stratify_key` set (and present on every task) it interleaves
strata in proportion so every split preserves the family mix (SB `instruction_type`, HotpotQA
`type`); with `--stratify_key ""` it is a plain seeded shuffle, **byte-identical to the previous
slicing** so existing prequential results reproduce. Different seeds → different (still stratified)
partitions, giving robustness across random splits rather than one fixed split.

## What changed in the engine
- `--protocol {prequential,frozen}`, `--test_n`, `--stratify_key` added; **`--verify_n` default
  6 → 18** (6 haiku tasks, SE≈0.2, can't resolve a real skill lift from noise — session-4's
  "gate rubber-stamps" was partly under-power; SkillOpt uses 18–40).
- Per-task work factored into `process(task, idx, learn, phase)`; `learn=False` = pure frozen
  inference (no record/credit/reflect/consolidate). `acquire(stream, phase)` is the shared online
  loop. Each row now carries a `phase` field (`eval` | `acquire` | `test`).
- Frozen flow: methods that learn online (`episodic/ours_mem/ours_full/ace`) run `acquire(train)`;
  `external_optimizer` pays its cost up front in `train_external(train)`; `no_memory` does nothing.
  `ours_full` runs one **final gated consolidation** on val before freezing (set `--induce_every 0`
  to make that the *only* consolidation — cheaper and the cleanest single selection pass).
  Then ALL methods deploy on the frozen test split. Acquisition trace saved to `*_acquire.jsonl`.

## Throughput & robustness
The frozen **deploy** phase (held-out test, ~70% of all calls) is embarrassingly parallel — the
store is frozen, every test task is independent. So all NO-WRITES work fans out concurrently;
only online-learning phases stay sequential (the prequential dependency is real).
- **`--max_concurrency`** (run.py, default 16, set up to ~64): target peak concurrent `claude`
  requests across the launch. The runner derives `deploy_workers = max_concurrency // workers`
  and passes it down; it prints the effective peak.
- **What runs concurrently:** frozen test deploy (all methods); `no_memory`/`external_optimizer`
  in prequential (they never write); the **consolidation gate** A/B on val (`verify.lift_over_base`);
  the **external optimizer's train rollouts**. **What stays sequential:** acquisition for
  `episodic/ours_mem/ours_full/ace` (each task's memory depends on the previous).
- **Order-stable despite out-of-order completion:** parallel deploy collects each call's own cost,
  then reconstructs `cum_cost` in task order from the up-front acquisition cost — so the curve is
  deterministic. Ledger appends are mutex-guarded; SB code-exec uses a unique tempdir per task.
- **Robust retries** (`llm.call_claude`): transient failures — non-zero exit, timeout, empty
  stdout — retry with exponential backoff + jitter. Tunable via env `NATIVE_EVOLVE_MAX_RETRIES`
  (default 5) and `NATIVE_EVOLVE_RETRY_BASE` seconds (default 2.0). A call that still fails after
  all retries raises; the deploy worker catches it, scores it as a miss, and the fan-out continues.

### Serving mode — parallelizing the LEARNING phase too (`--acquire_mode serving`)
The "online learning is sequential" constraint is a property of the strict **measurement**, not of
the system. A real serving deployment never blocks request N+1 on N's reflection — it serves
concurrently against the live store and learns in the background. `--acquire_mode serving` runs the
learning phase that way:
- **Serve** path (user-facing): retrieve from the LIVE store + generate, fanned out at
  `deploy_workers`. Each served task records `n_bullets` = memory visible **at serve time** (the
  staleness signal).
- **Learn** path (background): each served task enqueues an async job on a `learn_workers` pool.
  The expensive reflect (claude) runs in parallel; only the cheap deterministic store write
  (`curate.merge`/`credit`, `episodic.record`) is serialized under `store.STORE_LOCK` and written
  atomically — so concurrent serve-time reads never tear and learners never lose updates.
- **Drain barrier:** all background learning is awaited before FREEZE, so the frozen store is fully
  committed. (`sequential` stays the default for the clean prequential curve.)

Why it's measurement-safe for **frozen** mode: the headline depends only on the *final committed*
store, and curation is near order-independent (episodic append + counter sums are commutative; only
dedup tie-breaking varies), so serving acquisition ≈ sequential acquisition at the headline while
running fully in parallel. For **prequential** mode, serving turns the curve into a realistic
*serving curve* (accuracy vs memory-visible-at-serve and throughput, not vs strict index).

Engine-level benefit: making `store` writes atomic + `STORE_LOCK`-guarded also hardens a REAL
Claude Code deployment, where concurrent Stop-hook reflections would otherwise race on the store.
Validated (no-claude): 30 concurrent `curate.merge` adds → 30 bullets (no lost updates), all lines
valid JSON, 4 readers churning vs a writer → 0 torn reads.

Validated (hotpotqa frozen, deploy_workers=8): 2 methods × (8 acquire + 24 deploy) in 84s wall,
out-of-order completion, `cum_cost` monotonic and idx-ordered, acquisition cost folded into the
first deploy row.

## Cost model (frozen)
Acquisition cost (train rollouts/reflection + val gating, or external's offline training) is paid
**up front** and shows in the first test row's `cum_cost_usd`; deployment is **1 call/task,
identical across methods**. So C2's "lower total cost" = **acquisition cost** (deployment is
equal). Frozen test is cheap (no reflection) → a large held-out test is affordable and the
expensive online reflection is confined to the small ~20% train split.

## Commands
```bash
# SpreadsheetBench — EXACT SkillOpt replication (80/40/280, stratified by instruction_type)
SB=eval/data/spreadsheet/spreadsheetbench_verified_400/dataset.json
python3 eval/run.py --tasks "$SB" --env spreadsheetbench \
  --protocol frozen --train_n 80 --verify_n 40 --test_n 280 \
  --stratify_key instruction_type --induce_every 0 \
  --methods no_memory,episodic,ours_mem,ours_full,ace,external_optimizer \
  --seeds 0,1,2 --workers 1 --max_concurrency 64 --outdir results/sb_frozen
# workers=1 keeps runs sequential so each run's deploy gets the full 64-wide fan-out;
# raise --workers to overlap the sequential ACQUISITION phases of different methods
# (peak concurrency stays ~max_concurrency = workers x deploy_workers).

# HotpotQA — family-structured, own split at the 20/10/70 ratio, stratified by type
python3 eval/fetch.py --env hotpotqa --n 520 --out eval/data/hotpotqa_val.jsonl   # bigger pool
python3 eval/run.py --tasks eval/data/hotpotqa_val.jsonl --env hotpotqa \
  --protocol frozen --train_n 104 --verify_n 52 --test_n 150 \
  --stratify_key type --induce_every 0 \
  --methods no_memory,episodic,ours_full,external_optimizer --seeds 0,1,2 --workers 4 \
  --outdir results/hotpot_frozen
```
`--test_n` controls test size independent of train/val: keep train/val at SkillOpt sizes (that's
the evidence the method learns from) and subsample test only to bound cost (it just sets CI width).
The headline (`summary.json` `final_preq_em`) is the frozen-test EM; report per-`type`/`instruction_type`.
