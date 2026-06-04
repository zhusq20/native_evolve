# PROGRESS — native_evolve

Living state of the project. Newest session at the top of the Changelog.
Read `CLAUDE.md` for how-to-work; this file is what's-been-done + what's-next.

---

## Thesis
Internalize an external skill optimizer (SkillOpt/GEPA) into the agent's own online
loop. Reflect → curate (deterministic) → promote-with-gate, via Claude Code hooks.

- **C1** two-tier (memory + gated skill) + top-k retrieval  >  single-tier ACE playbook.
- **C2** native *online* self-evolution  ≥  external *offline* optimizer, at lower total cost.

## Method abstraction (eval/prequential.py, test-then-train / prequential)
For a shuffled task stream, each task is first **evaluated** (test) with the memory built
from tasks `1..i-1`, then **learned from** (train). Cumulative cost is logged per task so
acc-vs-cost is fair. Baselines, all on the same `claude` CLI + same target model:
- `no_memory`        — lower bound.
- `ours_full`        — top-k memory retrieval + reflect + skill promotion (gate).
- `ace`              — single-tier: inject the FULL playbook every task, reflect, NO promotion.
- `external_optimizer` — SkillOpt/GEPA style: offline-train ONE global SKILL.md on a disjoint
                         split (cost paid up front + logged), then FROZEN during eval.

## Status (what works, validated)
- Engine: store / retrieve / curate(deterministic) / reflect(claude) / promote+gate(claude). ✓
- Deployment: Claude Code hooks (UserPromptSubmit→inject memory, Stop→reflect, recursion-guarded). ✓
- Eval harness: prequential runner, 4 baselines, `--workers` parallel across runs, SVG plots. ✓
- Envs: searchqa ✓, spreadsheetbench ✓ (codegen+exec+official cell-compare), hotpotqa ✓
  (distractor multi-hop QA, official EM/F1, bridge/comparison families), gsm8k ✓ (deprecated: too easy).
- Skills visible in `./skills/` with `.claude/skills` symlink. ✓
- Parallelism: across (method,seed) runs only; a single online run is inherently sequential
  (prequential dependency). Confirmed isolated (per-run home/ledger).

## Results so far  (haiku target, n small, 2 seeds — SIGNALS not significance)

### SearchQA (n=24)  — stationary, format-bound QA
| method | EM | cost$ |
|---|---|---|
| no_memory | 0.708 | 0.37 |
| **external/SkillOpt (offline)** | **0.896** | 0.56 |
| ace | 0.812 | 0.65 |
| ours | 0.833 | 0.77 |
→ **External WINS here.** One global format skill, learned offline & cheaply, suffices on a
stationary format-bound distribution. ours learns gradually, pays reflection tax. C2 NOT supported here.

### SpreadsheetBench (n=16)  — diverse procedural codegen (SkillOpt's home turf)
| method | EM | seed0 | seed1 | cost$ | bullets |
|---|---|---|---|---|---|
| no_memory | 0.375 | .375 | .375 | 0.59 | 0 |
| external/SkillOpt (offline) | 0.375 | .375 | .375 | 0.94 | 0 |
| ace | 0.375 | .438 | .312 | 0.98 | ~40 |
| **ours** | **0.500** | **.562** | **.438** | 1.05 | ~40 |
→ **ours WINS on both seeds.** External's single frozen skill gives zero net gain (=no_memory)
on diverse tasks → **C2 supported here**. ours (top-k retrieval) > ACE (dump 40 bullets) → **C1 partly supported**.
- **CRITICAL CAVEAT**: the promotion gate **never fired** (0 skills promoted; helpful≥5 needs a longer
  stream). So at n=16, "ours" = memory + retrieval ONLY; the **skill-promotion tier is UNTESTED**.
- Base accuracy 0.40 = good mid-range (headroom, no floor/ceiling). Figures: `results/sb_haiku/*.svg`.

### SpreadsheetBench — 6-arm "episodic vs consolidated" scout (2026-06-04, n=48, SEED 0 only → signal)
| method | EM | cost$ | note |
|---|---|---|---|
| **episodic (raw past-success exemplars)** | **0.562** | **1.61** | BEST and CHEAPEST |
| ours_full (episodic+distilled+gated skill) | 0.438 | 5.27 | gate REJECTED skills @15/31/47 → = episodic+distilled |
| no_memory | 0.417 | 1.82 | |
| external/SkillOpt (offline) | 0.417 | 2.20 | zero net gain (= no_memory) |
| ace (full-playbook consolidation) | 0.396 | 3.63 | below no_memory |
| ours_mem (distilled top-k retrieval) | 0.375 | 3.20 | WORST — distillation is lossy here |
→ **Raw-trajectory (episodic) reuse wins by +0.15 AND is cheapest; every CONSOLIDATED form
(distilled memory, ACE playbook, offline skill) lands at or BELOW no_memory.** And **distilled
DILUTES even episodic**: ours_full (episodic+distilled) 0.438 < episodic-alone 0.562. The gate
correctly promotes nothing (base 2/6 → +skills 1/6 every checkpoint → graceful degradation). A
clean SB+haiku replication of both memory papers (lossy-abstraction bottleneck; consolidation can
fall below no-memory). **1 seed only → strong signal, not significance.** Figures: `results/sb_headline/`.

**Cross-setting story (now theory-grounded by two memory papers + our data):** the two envs span the
two regimes the literature names —
- **searchqa = shared-latent-procedure** (every task needs the same "exact-format answer extraction"):
  CONSOLIDATION wins (external 0.896 ≫ no_memory 0.708; one format skill *is* the shared procedure).
- **SpreadsheetBench = diverse / no-shared-procedure** (ids confirm no task families): EPISODIC raw
  reuse wins; consolidation is lossy clutter. → **consolidate only where a shared procedure exists.**

## Open questions / NEXT (priority order) — revised 2026-06-04 (session 4)
0. **Add ≥3 seeds to the SB 6-arm scout** to confirm the ordering (episodic ≫ rest at 1 seed,
   but single-seed SB EM has SE≈0.09 — see session-3/4 noise notes).
1. **searchqa 6-arm + acquisition→FROZEN-DEPLOYMENT protocol** — the SHARED-PROCEDURE regime
   where skill *formation* can pay off (external already won searchqa 0.896). The C2 frontier:
   do ONLINE self-formed, gated skills match the OFFLINE external optimizer? Add a frozen phase
   (learn on acquisition → freeze memory/skills → deploy on held-out / context-shifted tasks),
   per the skill-formation benchmark, to measure REUSE not local adaptation. (Code is ~ready;
   `episodic`/`ours_full` already record+gate; just need the freeze/deploy split in prequential.)
2. **Gate (or drop) the distilled tier too** — scout shows ours_full (episodic+distilled) 0.438 <
   episodic-alone 0.562: distilled memory DILUTES episodic. Either gate the distilled tier the
   same way skills are (must beat pure episodic), or make episodic the default backbone.
3. **Significance**: ≥3–5 seeds, mean±CI on whichever env.
4. **Family-structured benchmark**: SB has NO shared-procedure families (ids aren't base-variant;
   97 singletons, only 14 bases with 2 variants). To fairly test skill *formation*, construct or
   find families sharing a latent procedure (the skill-formation benchmark's core construction).
5. **Generalization stressors** (skill-formation benchmark): context shift, adversarial shortcuts,
   multi-skill composition — in the frozen-deployment phase.
6. (Carried) context-budget + poisoning stress; tool-using agent variant (`--add-dir` + Bash).

## Design decisions (and why)
- Reuse SkillOpt's deterministic spreadsheet parts (executor+evaluator, openpyxl-only) →
  copied into `eval/envs/sb_lib/` so the repo is self-contained; faithful to the official benchmark.
- LLM only via `claude -p` (constraint). Curation deterministic (anti context-collapse, ACE).
- Cost accounting via a per-run ledger (`home/ledger.jsonl`); external optimizer's training
  cost is paid before the eval loop so acc-vs-cost is honest.
- Recursion guard for the Stop-hook reflector: `--setting-sources user` + `NATIVE_EVOLVE_REFLECTING=1` + Read-only.

## Data
SpreadsheetBench (gitignored, 38 MB). Re-fetch:
```bash
mkdir -p eval/data/spreadsheet && cd eval/data/spreadsheet
curl -sSL -o sb400.tar.gz \
  "https://huggingface.co/datasets/KAKA22/SpreadsheetBench/resolve/main/spreadsheetbench_verified_400.tar.gz"
tar xzf sb400.tar.gz   # -> spreadsheetbench_verified_400/dataset.json (+ spreadsheet/<id>/)
# task file = .../spreadsheetbench_verified_400/dataset.json
```
SearchQA: `eval/data/searchqa_val.jsonl` (tracked). GSM8K: `python3 eval/fetch.py --env gsm8k --n 40`.

---

## Changelog
### 2026-06-04  (session 5 — dataset feasibility sweep for eval-scope expansion)
Assessed 14 candidate benchmarks (Spreadsheet, OfficeQA, DocVQA, HotpotQA, IFBench, HoVer,
PUPA, AIME-2025, LiveBench-Math, ARC-AGI, WebShop, ScienceWorld, AppWorld, ALFWorld) for
fit with the single-call `claude -p` harness. Full writeup: **`docs/dataset_feasibility.md`**.
- **Decisive filter = harness constraint #1** (one headless `claude -p` call/task, no agent
  loop / tools / vision). It cleanly partitions the field.
- **ADOPT (text + programmatic scoring + real family structure):** ① **HotpotQA-distractor**
  (searchqa-clone, bridge/comparison families → cleanest in-harness C1 skill-formation test,
  low effort); ② **IFBench** (deterministic reference-free verifiers — a scoring modality we
  lack; built-in OOD constraint-generalization stressor); ③ **HoVer-oracle** (num_hops 2/3/4
  family axis → compositional frozen-deployment split). These FILL the project's #1 gap (a
  family-structured benchmark; searchqa/SB/MATH have none).
- **Adopt-with-work / optional:** DocVQA-OCR (ANLS fuzzy-scoring + OCR robustness axis),
  LiveBench-Math (contamination-freshness for C2; overlaps MATH).
- **Defer:** Spreadsheet-912 (volume only, same diverse regime), PUPA (LLM-judge + live API),
  WebShop (BM25-infra heavy, strips its own task).
- **Reject — needs a new multi-turn agent↔env harness (separate initiative):** OfficeQA,
  ScienceWorld, AppWorld, ALFWorld, native WebShop. Priority if ever built: AppWorld → ALFWorld
  → ScienceWorld.
- **Reject — mechanically fit but poor thesis fit:** AIME-2025 (n=30, haiku floors w/o thinking,
  no shared procedure), ARC-AGI (anti-reuse by design, floors).
- **NEXT:** implement HotpotQA then IFBench env files (both ~½ day); 24-task haiku dry-run to
  confirm mid-range before committing seeds; for any adopted env, plan a one-time online warmup
  (nltk/spacy/pyarrow + data fetch) before the offline loop.

**HotpotQA env IMPLEMENTED + dry-run done (this session).** New files: `eval/envs/hotpotqa.py`
(distractor-only, searchqa-shaped, carries `type`/`level`), `eval/scoring_hotpotqa.py` (official
HotpotQA EM/F1 vendored, yes/no-aware), `eval/data/hotpotqa_val.jsonl` (150 tasks, 122 bridge /
28 comparison, all `hard`; fetch via `eval/fetch.py --env hotpotqa --n N` off the HF
datasets-server). Scorer unit-checked; 1-task + 24-task haiku smokes pass; plot.py works.
**24-task dry-run (seed 0, n=24):**
| method | EM | F1 | bridge EM | comparison EM | 1st→2nd half | cost |
|---|---|---|---|---|---|---|
| no_memory | 0.667 | 0.787 | 0.632 (n=19) | 0.800 (n=5) | 0.750→0.583 | $0.41 |
| episodic | 0.667 | 0.816 | 0.579 (n=19) | 1.000 (n=5) | 0.667→0.667 | $0.39 |
→ **Mid-range CONFIRMED, no floor/ceiling** (overall 0.667, like searchqa's 0.708). The flagged
caveat HOLDS: **comparison (yes/no) is near-ceiling/guessable (0.8–1.0, n=5)**; **bridge is the
family with real headroom (~0.60)** and is the majority — so analysis should report per-`type` EM
(or weight bridge), not just flat EM. episodic≈no_memory at n=24 is expected noise (SE≈0.1). Env
ready for the full multi-method × ≥3-seed run; figures in `results/hotpot_dryrun/`.

### 2026-06-04  (session 4 — memory→skill investigation, then episodic-first refactor)
The big one. Started out to "fire the promotion gate" (session-3 NEXT #1); ended up reworking
what a skill IS and which memory form actually transfers. Total spend this session ≈ **$27.5**
(894 `claude` calls), all de-risking + the 1-seed scout — under the old $40 headline budget.

**1. The gate was STRUCTURALLY dead, not stream-starved.** Traced it: `uses` only increments in
   `curate.reinforce`, which only fires on a `reinforce` delta carrying an existing `m-id` — but
   the Reflector is never shown existing ids, AND both envs force answer-only / code-only output
   so the agent can't cite `[id]`. ⇒ `uses` pinned at 0 forever ⇒ gate (`uses≥5 ∧ helpful≥5`)
   unreachable at ANY stream length. (Session-3 NEXT #1 "just run n=48" would have burned ~$40
   and still shown 0 promotions.)
**2. Fixed attribution → deterministic presence/gold credit** (`curate.credit`): the harness
   credits the bullets it actually injected (uses+1; helpful+1 on a pass; no harmful on fail).
   Gate now fires. searchqa smoke: 4 skills promoted; SB pilot (n=32): 17 skills promoted.
**3. But firing the gate exposed the promotion path as NET-HARMFUL** (it had never run end-to-end):
   promoted bullets were marked `promoted` and DRAINED from active memory, and the skills were
   invisible to the target (`cwd`/`setting_sources`/`allowedTools`). Pilot 1st→2nd-half EM
   0.625→0.312 (below no_memory). Confirmed single-seed SB (n=32) is NOISE-dominated (SE≈0.09):
   a "fixed" rerun looked worse purely from `claude` stochasticity, so single-seed A/B can't
   adjudicate mechanism changes.
**4. Reworked skill PRODUCTION → LLM induction** (`induce.py` + `prompts/skill_inducer.md`):
   synthesize 3–7 rich, consolidated, orthogonal skills from clustered memory instead of inflating
   one bullet per skill. Produced genuinely good-looking openpyxl/formula skills.
**5. Counterfactual A/B (`verify.py`): the induced skills DON'T help** — across 2 designs (general
   all-injected; failure-focused + relevance-gated) and 20 held-out task-instances: **0 fixes, 4
   breaks.** Skills never turned a fail→pass and broke working solutions (dilution). The old replay
   gate was a rubber stamp (all `pass_rate` 1.0). "Correct facts ≠ useful skills."
**6. Two memory papers reframed everything** (user-provided): (a) LLM *consolidation* of episodes is
   often faulty even from good experience; utility rises then falls below no-memory; episodic-only
   control stays competitive; gate consolidation explicitly; *consolidate without overwriting the
   evidence*. (b) skill-formation benchmark: raw-trajectory reuse frequently beats distilled skills
   (lossy-abstraction bottleneck); bottleneck is *selective procedural abstraction, not storage*;
   gains unstable under FROZEN DEPLOYMENT; tasks organized into families sharing a latent procedure.
   Our scattered results match both exactly.
**7. Refactored the engine to be episodic-first, non-destructive, explicitly gated:**
   - `episodic.py` — raw `task→solution→outcome` traces, append-only; retrieve a similar past
     SUCCESS as a few-shot exemplar (raw episodes as first-class evidence).
   - `induce.write_skill` — publishes induced skills WITHOUT touching memory (source bullets stay
     active/retrievable: consolidate without overwriting the evidence).
   - `verify.lift_over_base` — the explicit gate: a skill set activates ONLY if it beats the
     episodic+distilled baseline on held-out tasks; else `ours_full` degrades gracefully.
   - `prequential.py` methods now: `no_memory | episodic | ours_mem | ours_full | ace |
     external_optimizer`. ours_full = episodic + distilled + gated skills; consolidation runs
     every `--induce_every` (16) tasks, gated on `--verify_n` (6) held-out tasks. plot.py updated.
   Mechanical smoke passed: gate REJECTs (degrades), memory never drained.
**8. SB 6-arm scout (1 seed, n=48)** — the headline result of this session (table above):
   **episodic 0.562 (best & cheapest) ≫ ours_full 0.438 ≈ no_memory/external 0.417 > ace 0.396 >
   ours_mem 0.375.** Raw reuse wins; every consolidated form ≤ no_memory; distilled even dilutes
   episodic; gate promotes nothing. Clean replication of both papers on SB+haiku.
**9. SB has no task-family structure** (ids 97 singletons / 14 bases w/ 2 variants) ⇒ SB is the
   "diverse / no-shared-procedure" regime; searchqa is the "shared-procedure" regime. The
   cross-setting spine is now theory-grounded (see Results → Cross-setting story).

New/changed files: `engine/evolve/{episodic,induce,verify}.py`, `engine/prompts/skill_inducer.md`,
`engine/evolve/{curate,retrieve}.py` (credit + select_and_block + skills_block), `eval/prequential.py`
(6 methods, episodic record, gated consolidation), `eval/plot.py`, `eval/{diagnose_arms,verify_induced}.py`.

### 2026-06-02  (session 3 — analysis + figures + per-experiment docs)
- Added `fig_final_bars.svg` (final EM + per-seed dots + cost/EM-$ per method) to plot.py; `--title`.
- Documented everything: `results/README.md` (index + cross-setting spine + how-to-read + caveats),
  `results/haiku24/README.md` and `results/sb_haiku/README.md` (one section per figure + per data file).
- Recomputed authoritative `summary.json` (all 4 methods) from `runs/`. Removed throwaway dirs.
- Full stats locked in: SearchQA external 0.896 > ours 0.833; SpreadsheetBench ours 0.500 > rest 0.375.

### 2026-06-02  (session 2 — 3-layer restructure)
- Split repo into layers: **root** = research workspace (docs + `eval/` harness),
  **`engine/`** = object under study (evolve/adapters/prompts/memory/skills/scripts/.claude),
  **`results/`** = experiment outputs (moved from `eval/out`).
- `eval/prequential.py` now imports engine via `ENGINE_DIR`; `prepare_home` copies prompts
  AND seeds replay cases from `engine/memory/replay` → the promotion gate can now fire in experiments.
- Deploy is now `cd engine && claude`. Root has no hooks (research session won't self-trigger reflection).

### 2026-06-02  (session 1 — build + first results)
- Built engine, hooks, prequential harness, 4 baselines, SVG plots, env-pluggable.
- Envs: searchqa, gsm8k (deprecated: ceiling), spreadsheetbench (integrated SkillOpt exec/eval).
- Results: SearchQA (external wins), SpreadsheetBench (ours wins both seeds; gate didn't fire).
- Made skills visible (`./skills/` + `.claude/skills` symlink; `evolve setup`).
- Set up handoff: CLAUDE.md, this file, requirements.txt, .gitignore, git.
- **Next session: do NEXT #1 (longer SpreadsheetBench stream to fire the promotion gate).**
