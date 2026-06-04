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
  --seeds 0,1,2 --workers 6 --outdir results/sb_frozen

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
