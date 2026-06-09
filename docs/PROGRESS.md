# PROGRESS — native_evolve

Living state of the project. Newest session at the top of the Changelog.
Read `CLAUDE.md` for how-to-work; this file is what's-been-done + what's-next.
**For the consolidated scientific narrative (claims, the precision law + type-1/type-2 taxonomy, the
gate-discipline reframe, the evidence map), read `docs/findings_synthesis.md`.**

---

## Thesis
Internalize an external skill optimizer (SkillOpt/GEPA) into the agent's own online
loop. Reflect → curate (deterministic) → promote-with-gate, via Claude Code hooks.

- **C1** two-tier (memory + gated skill) + top-k retrieval  >  single-tier ACE playbook.
- **C2** native *online* self-evolution  ≥  external *offline* optimizer, at lower total cost.

> **⚠️ PIVOT (session 18, 2026-06-08).** Headline is now **C1 — the memory↔skill BOUNDARY** — studied under
> the OFFLINE **`--protocol frozen`** protocol (train-with-gold → FREEZE → deploy-frozen; oracle signals =
> default). **C2 is SET ASIDE** (train-with-gold+freeze IS the offline-optimizer protocol). The reference-free
> / precision-law / "native verifier" line (sessions 14–17) is DEMOTED to supporting material; verify is no
> longer load-bearing (gold drives train; frozen deploy learns nothing). Boundary thesis: *consolidate
> memory→a gated skill ONLY where a shared latent procedure spans a task FAMILY; else keep episodic memory.*
> See the session-18 changelog entry + `memory/refocus-memory-over-verification.md`.

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
  **Retrieval default = `--memory_mode native` (session 19): every distilled bullet, episode, and
  promoted skill is materialized as a DISCOVERABLE Claude Code skill (`.claude/skills`) and the agent
  NATIVELY selects/invokes what it needs (a few-turn Skill-enabled solve); credit goes to what it
  ACTUALLY invoked (PostToolUse hook). `--memory_mode inject` (+ `--retrieval lexical|agentic`)
  reproduces the pre-session-19 force-injection behavior.** (Pre-19 default was `--retrieval agentic`.)
- Deployment: Claude Code NATIVE (session 19) — SessionStart→`evolve materialize` (memory becomes a
  discoverable skill catalog), Stop→reflect which now ALSO **credits the memory the agent invoked**
  (transcript attribution, reference-free success) + **consolidates via induce+held-out gate**
  (`promote.consolidate_deploy`, the SAME mechanism as the experiment — replaces legacy `promote.run`).
  The live deploy learning loop is thus aligned with the eval loop. Pre-19: UserPromptSubmit force-injected memory. ✓
- Eval harness: prequential runner, 4 baselines, `--workers` parallel across runs, SVG plots. ✓
- Envs: searchqa ✓, spreadsheetbench ✓ (codegen+exec+official cell-compare), hotpotqa ✓
  (distractor multi-hop QA, official EM/F1, bridge/comparison families), gsm8k ✓ (deprecated: too easy).
- Skills visible in `./skills/` with `.claude/skills` symlink. ✓
- Parallelism: across (method,seed) runs only; a single online run is inherently sequential
  (prequential dependency). Confirmed isolated (per-run home/ledger).
- **Session-8 apparatus (cross-benchmark; unit + online validated):** uniform `solve()` = single-shot +
  conditional **repair** (`--repair_turns`) driven by a reference-free verify; gold-grounded
  `env.evidence()` → **trace-grounded reflection** (killed the inverse-skill poison); **signature-keyed
  episodic** + `repair_hint`; **rolling-window** consolidation gate; **dataset-blind `self_verify`**
  (execution + self-critique, auto-routed; `--verify_mode oracle|self|self_exec|self_both`, **default now
  `self_both`** = run BOTH exec + semantic critique, critique advisory on a clean run). New env: **IFBench**
  (reference-free constraint verifiers). ✓

## Results so far  (haiku target, n small, 1–2 seeds — SIGNALS not significance)

### ⭐ CURRENT HEADLINE (session 8, 2026-06-05) — the four-regime TWO-AXIS LEVER MAP (1 seed each, preqEM)
The apparatus carries TWO levers (reference-free **repair** + self-evolving **memory**); a 2×2
(memory × repair) per regime shows WHICH lever a benchmark draws on — governed entirely by `verify`:

| regime | env (n) | repair Δ (fires) | memory Δ (r0) | memory×repair | verify character |
|---|---|---|---|---|---|
| diverse codegen | SB (32) | **+0.34** (13/32) | +0.22 | **SUBSTITUTE** | partial (form) → big blind spot |
| ref-free verifiable | IFBench (24) | +0.13/+0.17 (10/24) | +0.04 | **COMPLEMENT** | COMPLETE (verify==rubric) |
| shared-proc QA | searchqa (24) | ~0 (1–2/24) | **+0.17** | — (repair idle) | weak (format) |
| family multi-hop | HotpotQA (24) | 0 (0–1/24) | +0.04 | — (repair idle) | weak; bridge diverse |

- **Axis 1 — repair fires/helps ∝ verify-VISIBILITY** (crashes/constraints visible → repair; QA semantic
  errors invisible → idle). **Axis 2 — memory & repair STACK vs FIGHT ∝ verify-COMPLETENESS**: complete
  verify (IFBench) → COMPLEMENT; large blind spot (SB) → SUBSTITUTE. The memory↔repair conflict IFF verify
  is incomplete — the conflict IS the blind spot.
- **Deployment-realism — the PRECISION LAW:** a DATASET-BLIND verify recovers the repair win iff its signal
  is PRECISE — execution for code (SB self_exec **0.750** ≈ oracle 0.812), in-prompt constraints for
  instruction-following (IFBench self **0.792** == oracle) — and BACKFIRES when noisy (SB exec+LLM-critique
  **0.375**, below baseline 0.469). Fix = channel-routing `self_verify`. ⇒ **the lever map SURVIVES a
  realistic verifier; repair's value is real, not an oracle artifact.** [**session-9 correction:** the
  0.375 backfire was partly a NON-MONOTONE-LOOP bug; with `monotone_repair` + exec-authoritative critique,
  forced exec+critique recovers to **0.719 ≥ baseline** — a noisy signal now degrades gracefully instead
  of backfiring. The precision law holds in spirit (critique adds no value beyond exec on code) but no
  longer HURTS. See the session-9 changelog.]
- Two robust wins: reference-free repair ~doubles SB gold-free (0.47→0.81); trace-grounded reflection
  flipped SB memory from net-harmful (session-7) to +0.22. **All 1-seed signals — details in the session-8
  changelog.** Raw runs: gitignored `results/_p3_*/`.
- **[session-10 UPDATE] SB flips SUBSTITUTE→COMPLEMENT under the new `self_both`+N3 default** (deployment-
  realistic, NOT oracle): the full 2×2 gives D(mem+repair)=0.750 = best cell, > repair-alone 0.625 and >
  memory-alone 0.625; **memory @ repair-on went −0.09 (session-8 oracle) → +0.125** — memory no longer
  fights repair. 1-seed signal, CONFOUNDED (vs session-8 both verify changed oracle→self_both AND N3 added;
  weaker repair leaves headroom) → needs ≥3 seeds + a (self_both, no-N3) control. See the session-10 changelog.

> The session ≤7 tables below are HISTORICAL (single-shot harness, pre-repair, pre-trace-grounding) and are
> SUPERSEDED by the lever map above; kept for the record.

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

> ⚠️ **RETRACTED (session 7, 2026-06-04).** The "SpreadsheetBench = diverse → consolidation dilutes"
> half is an **ARTIFACT of our single-shot/haiku harness + a trace-blind reflector, NOT a property
> of SB.** SkillOpt doubles SB (~0.4→0.8) with **GPT-5.5 + a 30-turn execute→observe→repair loop**;
> its SB skill *is* a strong shared procedure (a verify-and-repair workflow). Our harness is
> single-shot with no execution feedback (`prequential.py:163`), so that skill is inert; and our
> reflector — fed only a 240-char reason, never the traceback — learned the **inverse** skill
> (≈38% of SB bullets are formula-framed; one induced skill literally says *"write the formula
> string in actual Excel/Sheets on a test cell first"* → openpyxl never evaluates it → grader sees
> `None` → fail), which is why consolidation lands *below* no_memory and episodic (no distilled
> bullets) "wins". **Corrected claim:** our pipeline can't learn SB's shared procedure because it
> lacks the execution loop the procedure is written for, and our trace-blind reflector learns its
> inverse. See session-7 changelog + `docs/` for the full SkillOpt investigation.

## Open questions / NEXT (priority order)
**TOP PRIORITY (session-8 close, 2026-06-05): the cross-benchmark apparatus is BUILT + ONLINE-VALIDATED
across 4 regimes; the two-axis lever map + the precision law are the deliverables (1 seed each — signal).**
Phases 0–2 (repair loop, trace-grounded reflection, signature-episodic, rolling gate) + Phase 3 (the four
2×2s) + the deployment-realism A/B (oracle vs dataset-blind `self_verify`) are all DONE (see Results
headline + session-8 changelog). What's genuinely next:
- **Re-run the full lever map under routed-`self_verify`** (not oracle) → publish the DEPLOYMENT-REALISTIC
  lever map as the headline. (no_memory cells already ≈ oracle; still need the `ours_full` cells.)
- **≥3 seeds** on the 2×2s → turn the magnitudes (SB interference −0.09 ≈1 SE; the memory deltas) from
  signal into significance.
- **Verify-completeness / semantic-memory fix on SB:** make memory learn the SEMANTIC layer (why the VALUE
  is wrong, from gold-grounded evidence) to cover verify's blind spot → test if SB flips SUBSTITUTE→
  COMPLEMENT (the IFBench pattern). This is the highest-insight follow-up. **[session-10: BUILT (N3 semantic
  diff) + first online 2×2 run → SB DID flip to COMPLEMENT under `self_both`+N3 (1 seed, confounded).** Two
  remaining: (a) ≥3 seeds for significance; (b) a **(self_both, no-N3) control** to attribute the flip to N3
  semantic memory vs merely-weaker self_both repair — needs a `--no_semantic_reflect` switch (N3 is currently
  unconditional in the SB env).]
- **`repair_turns` 2–3 on IFBench** (multi-constraint satisfaction is iterative → expect higher yield).
- **Cost honesty:** route `self_verify`'s critique-call cost into the per-task ledger row (currently
  undercounts; ledger total is authoritative).
- Carried: frozen-reuse headline + accuracy-vs-total-cost vs external; complete the 6-method SB headline
  (ace/external) under the new apparatus.

--- earlier list (session 4, partly addressed: frozen protocol + searchqa frozen now DONE) ---
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
- **Repair = a SEPARATE, LABELED lever, kept (not dropped) [decision (a), session 15].** `self_verify` is
  the reference-free OUTCOME SIGNAL (drives credit/gate/reflect = core; also feeds the repair loop). Memory
  claims are read off the repair=0 column (default); repair's effect is reported via the memory × repair 2×2.
  The deploy-faithful memory headline is the AGENTIC harness (native self-correction; `monotone_repair`
  bypassed). Keeps the "learn from your own repair trajectory" sub-story without confounding "memory helps".
  Full discipline: `docs/eval_protocol.md` → "Reporting discipline"; rationale: `memory/self-verify-role-split.md`.
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
### 2026-06-09  (session 21 — REAL ARC-AGI-2 dataset + INCREMENTAL consolidation + DETERMINISTIC skill loading)
The user asked to test on the REAL ARC-AGI dataset (prior runs used the synthetic family-labeled
`arc_gen.py`). Switched to **arcprize/ARC-AGI-2** (user picked v2/v3; v3 is an interactive-game benchmark
that doesn't fit our static input/output-grid program-synthesis env, so v2 — same JSON format as v1 — is
the right choice). Then, driven by a chain of user design questions, redesigned skill formation.

**Data (NEW `eval/fetch_arc_real.py`):** converts fchollet/ARC-AGI(-1) or arcprize/ARC-AGI-2
`{train,test}` JSON → the `arc` env's `demos`/`tests` rows (program synthesis + official scoring; no new
env module — the env is data-agnostic). Committed pools (ARC-AGI-2 training, seed 0): `arc2_train_full.jsonl`
(no size filter, headline) + `arc2_train_small.jsonl` (≤300 cells, floor probe). Re-fetch: `git clone
--depth 1 https://github.com/arcprize/ARC-AGI-2 /tmp/ARC-AGI-2` then `python3 eval/fetch_arc_real.py --src
/tmp/ARC-AGI-2/data/training --out eval/data/arc2_train_full.jsonl --seed 0 --n 90`.
- **Floor probes (haiku, native, Bash-enabled, single-shot-ish):** ≤120-cell ARC-AGI-1 pool **0.75** (too
  easy, ceiling); ARC-AGI-2 ≤300 pool **0.50**; ARC-AGI-2 **no filter** (grids ≤900 cells) **0.55** —
  mid-range, NOT floored (real headroom even at full v2 difficulty; mostly turns=1, genuine haiku ability).

**ROOT-CAUSE FINDING (why family-less data collapsed to ONE over-general skill).** A first family="real"
run built **27 near-duplicate bullets**, all paraphrasing one idea ("the ARC 'real' family shares an
object-extraction procedure") → `induce` correctly merged them into 1 skill. Cause: real ARC has NO
families, but tagging tasks `family="real"` made `arc.py:evidence()` inject a FALSE "tasks in family X ALL
share one latent procedure" diagnosis (true for the synthetic generator, false for real ARC) → the
reflector parroted it. **Fix:** converter sets `family=""`; `evidence()` branches — empty family → per-task
diagnosis asking for (1) THIS task's specific rule AND (2) any TRANSFERABLE technique usable on a DIFFERENT
puzzle; non-empty → keeps the synthetic family-procedure branch. `skill_inducer.md` now tells the inducer
diverse/unrelated tasks yield SEVERAL orthogonal skills, not one.
- **Two user design Qs resolved in code:** (a) "can different-family memory still form skills?" — YES, via
  transferable-technique skills (the fix above). (b) "can different families merge into ONE shared skill?"
  — YES: induction is GLOBAL/pooled over all memory (family is just a `scope` tag, not a partition), so a
  genuine cross-family shared technique can become one skill; the gate validates it.

**INCREMENTAL CONSOLIDATION (`--consolidate_mode incremental`, NEW DEFAULT; `pooled`=legacy).** User Q:
"is showing Claude ALL bullets at once reasonable, or should it be periodic/incremental?" — agreed: pooled-
all doesn't scale (digest cap 120 → silent truncation) and re-induces from scratch each period (near-dup
skills, session-16). New `induce.induce_incremental(new_memory, existing_skills)` + `skill_inducer_incremental.md`:
shows the inducer the EXISTING skills (don't duplicate) + ONLY new memory since the last consolidation
(watermark `_consolidated_bullet_ids` / `_consolidated_ep_n`) → ADD orthogonal skills. Bounded input → scales,
no re-derivation. Gate base = pool bullets + already-active skills → the candidate's MARGINAL value over the library.

**DETERMINISTIC SKILL LOADING (`--skill_load fixed`, NEW DEFAULT; `native`=comparison arm).** User: with a
curated incremental skill set, the harness should FIXEDLY load skills in train/eval/deploy (not rely on
native discovery). Assessed as reasonable: it (i) decouples skill VALUE from skill DISCOVERY (resolves the
recurring "skill tier marginal" ambiguity), and (ii) ALIGNS the gate (already controlled-injection) with
inference — gate accept now predicts what inference sees. `retrieve.all_active_skills_block()` injects EVERY
active skill (user chose "all active", not top-k) into the solve prompt; `native_solve` keeps them OUT of the
catalog under fixed (no double-load); tier-1 bullets stay native. Caveat recorded: doesn't scale past a
handful of skills (then need a deterministic top-k); deploy fixed-load = hook-inject skill text (pre-19 style),
a different mode than native CC skills. `--gate_sample N` bounds multi-skill gate cost (K skills → K·N·2 solves).

**Validation (zero→small spend):** existing suites green (arc 38, materialize 17, gate_audit 16,
deploy_learning 8) + NEW `eval/test_incremental_skill.py` **10/10**. New-path smoke (incremental ×2 rounds +
fixed-load, family-less ARC-AGI-2 train12/test4, ~$3.6): ran CLEAN — watermark advanced (`@5 new_bullets=0`,
`@11 new_bullets=2 existing_skills=0 → induced 1: validate-solve-on-examples` = a transferable technique,
NOT a family procedure), gate kept it candidate (no lift on 4 tiny gate tasks → no false promotion), frozen
test ran. Committed `52224bc`. The pre-existing `engine/skills/self-verify-and-repair/SKILL.md` edit is left
uncommitted (unrelated, pending).

**HEADLINE RESULT (`results/arc2_t48_incr`, family-less ARC-AGI-2, frozen train48/test20, 1 seed, haiku, ~$16.7):**

| arm | test EM (n=20) | F1 | bullets | active skills | cost |
|---|---|---|---|---|---|
| no_memory | **0.400** (8/20) | 0.658 | 0 | 0 | $2.02 |
| ours_full | **0.400** (8/20) | 0.704 | 15 | 1 | $14.63 |

- **The incremental mechanism works end-to-end on REAL data (what the user asked for).** 3 rounds, watermark
  advancing as only-new memory is shown: `@15 new_bullets=9 existing_skills=0 -> induced 1 (validate-solve-on-
  training-before-held-out); gate base=6 ->+skill=6 (resc1/broke1) => candidate`; `@31 new_bullets=4
  existing_skills=0 -> induced 1 (validate-arc-solve-on-training); gate base=6 ->+skill=7 (resc2/broke1) =>
  ACTIVATE`; `@47 new_bullets=2 existing_skills=1 -> induced 0 (already covered)`. Both induced skills are
  TRANSFERABLE TECHNIQUES ("validate your solve on the training examples"), NOT fake family procedures — the
  family="" + per-task evidence() fix delivered, so skills DO form on non-same-family tasks. One ACTIVATED via
  the gate; deterministic fixed-load injected it at test.
- **Scientific read: EM is FLAT (0.40 == 0.40); memory nudged only F1 (+0.046) at 7x the cost.** On diverse,
  family-less ARC-AGI-2 the two-tier memory/skill does NOT beat no_memory on EM — the active "validate your
  solve" skill is a generic technique that flipped no held-out puzzle fail->pass. This is the project's
  recurring **"skill tier marginal"** finding (see [[boundary-result-memory-over-skill]]), now reproduced on a
  REAL benchmark under the new incremental + fixed-load design — and it is the EXPECTED diverse/singleton side
  of the C1 boundary (complement to the synthetic family-rich +0.40 of arc_gbs_pooled_t1). **1 seed -> SIGNAL,
  not significance.**
- **Known imperfection (next fix):** the incremental dedup context (`existing_skills`) counts only ACTIVE
  skills, so `@31` (none active yet) re-induced a near-duplicate of `@15`'s candidate. Pass CANDIDATES into the
  "skills you already have" context too. Also several transient `claude exit 1` retries during acquire/gate
  (one acquire task gave up after 1 retry) — handled, didn't crash; raise max_retries for big-grid solves.
- **NEXT:** (a) >=3 seeds on this config for significance; (b) the `--skill_load native` comparison arm to
  measure discovery loss (value vs discovery, now cleanly separable); (c) candidate-aware incremental dedup;
  (d) optionally a harder-headroom or family-structured real subset where a skill could actually flip EM.

### 2026-06-09  (session 20 — REWORK the promotion gate: CLUSTER-SCOPED within-failure-mode A/B, replacing the global val-split gate)
**Decision (user-driven design):** the promotion gate no longer asks "does this skill generalize to a
held-out val split". It asks the narrower, higher-power question **"within the failure-mode cluster the
skill was induced from, does reading the skill beat not reading it on instance-disjoint gate samples?"**
Rationale: the global val split was both off-distribution (skill rarely fires) and underpowered; testing
on the cluster's OWN samples (instance-disjoint, same signature) gives relevance + power without the
leakage of testing on the exact tasks that wrote the skill. We do NOT require cross-task generalization
— the **frozen test split stays the honest generalization referee**; the gate is just a promotion
heuristic. (This deliberately makes the GATE controlled-injection again, NOT the session-19 native
discovery — inference stays native; only the gate's measurement is controlled.)

**Mechanism (replaces, not adds — per user):**
- `induce.induce_clustered(min_cluster=4)` — cluster raw EPISODES by failure `signature`, deterministic
  id-sorted split into train/gate halves, induce ONE skill per cluster **from the TRAIN half only**
  (verified: gate episodes never enter the inducer prompt → no leakage). Returns
  `{name,md,skill,signature,train_eps,gate_eps}`. Clusters too small to fill both halves are skipped.
- `prequential.consolidate(idx)` rewritten: per cluster, A/B = `solve(task, base)` vs
  `solve(task, base+skill)` on the **gate half**, where `base` = the train-half successes rendered as
  worked examples (`episodic.exemplar_block_from`), held FIXED across both arms (skill text = lone
  variable). Judge = `make_judge(--gate_signal)` (oracle gold by default; gold looked up via new
  `task_by_id` over all_tasks since episodes store only the question). **Accept rule:**
  `(with−without) ≥ --cluster_gate_margin` (default 1) ∧ `broke ≤ rescued`, **no power floor** (clusters
  are small by design). Each cluster decides independently → a skill that fails its own gate degrades to
  a candidate (ours_full never below episodic+distilled).
- Removed: the old global-val gate body, `consolidate_native`, and the now-dead `base_block`. New flags
  `--cluster_min`, `--cluster_gate_margin`. `--gate_min_n/--gate_margin/--gate_audit/--memory_mode`
  no longer touch the gate (memory_mode still drives native inference).

**Status:** code + AST + unit smoke (split arithmetic, no-leakage, empty-safe) PASS. **NOT yet run
end-to-end** — next: an ARC `--protocol frozen` run to confirm the cluster gate fires and activates
skills, then compare forward-stream/test EM vs the old global-gate runs.

**Session 20 cont. — kill the DOUBLE consolidation + clarify the two-tier write boundary (user Q).**
Tracing the frozen acquire→freeze flow with the user surfaced that `consolidate()` was being run TWICE
back-to-back on the identical episode set whenever `train_n % induce_every == 0`: the PERIODIC trigger
(`run_phase:~796` / `batched_learn:~946`, fires when `(idx+1) % induce_every == 0`) lands on the LAST
acquire task `idx=train_n-1`, and then the end-of-acquire FINAL trigger (`prequential.py:~987`, there to
capture tail episodes recorded after the last periodic fire before freezing) re-runs `consolidate(train_n-1)`
on the same `episodic.load()` → identical induce + gate A/B = pure claude waste, and a source of the
near-duplicate-named skills noted in session 16. **Fix:** a closure-level `_consolidated_idx` set + an
early-return guard at the top of `consolidate()` (`prequential.py:403-419`) — each task index consolidates
at most once. Distinct periodic idxs never collide, so only the redundant repeat is suppressed; the FINAL
trigger still runs (and catches tail episodes) whenever `train_n` is NOT a multiple of `induce_every`
(the common case, e.g. the smoke's `induce_every=12 > train_n=8`); `--induce_every 0` skill-OFF is
untouched (never calls consolidate). Compiles; arc env 38/38 green. (Alternative non-code workaround for a
single run: set `induce_every` to a non-divisor of `train_n`, e.g. 17 not 16 — no longer needed.)
- **Clarified the WRITE boundary (the user's "does memory summarization live in consolidate?" question):**
  NO. Two tiers, two writers. **Tier-1 memory (摘要)** = distilled bullets via `reflect`→`curate.merge` +
  raw exemplars via `episodic.record`, written PER TASK in the learning step (`batched_learn` calls
  `reflect.run(..., promote_skills=False)`). **Tier-2 skill** = `consolidate()` ONLY: it reads already-
  accumulated EPISODES, clusters by failure signature, induces a skill, gates it (within-cluster A/B), and
  `induce.write_skill`s it. `consolidate()`'s body makes zero `curate.merge`/episode writes — it is purely
  the tier-1→tier-2 promotion gate, NOT the memory distiller. (Naming caveat: ACE's "consolidation" =
  compress memory; OUR `consolidate()` = gated skill formation.)

**Session 20 cont. — FIRST e2e native frozen run (arc_boundary_t1) → a structural finding → REDESIGN the gate
to POOLED same-data (user), + num_turns instrumentation.** Ran the Tier-1 boundary (no_memory + ours_full,
`--protocol frozen --train_n 16 --verify_n 8 --test_n 12 --induce_every 16 --memory_mode native
--skill_tools "Skill,Read,Write,Edit,Bash" --skill_turns 8 --batch_size 8`, 1 seed, haiku, $3.7 total).
- **Result (null + diagnostic):** no_memory test EM **0.667** (8/12), ours_full **0.667** (F1 0.985 vs 0.958,
  $2.75 vs $0.93, 5 bullets, **0 skills**). EM identical; memory nudged only F1; 1 seed n=12 → noisy.
- **⚠️ STRUCTURAL FINDING — the session-20 cluster gate cannot fire under native mode.** `induce_clustered`
  clusters episodes by failure `signature` (`if sig:` skips empties), but the signature is ONLY populated by
  the harness REPAIR loop (`ev["_repair_signatures"]`), which `--memory_mode native` BYPASSES (native
  self-correction, repair_calls=0). Confirmed in the data: 16 episodes, 5 failed, **every failure signature
  empty** → 0 clusters → 0 candidates. So under the deploy-faithful native headline (and ARC's Type-2 blind
  reffree signal, which wouldn't give a meaningful failure key even WITH repair), the skill tier was
  structurally untestable — independent of n. (The double-consolidation guard was in place + correct but not
  stress-tested: consolidate found no candidates, so no real double-induce to suppress.)
- **REDESIGN (user-driven) — POOLED, SAME-DATA gate replaces the cluster-scoped held-out gate.** Per the user:
  *don't keep a held-out A/B; show Claude ALL un-consolidated memory and let IT decide which lessons to package
  into skills; then A/B on that SAME data — the agent deterministically LOADS the pool memory, and the lone
  variable is whether it ALSO loads the candidate skill.* Rationale: attacks the QUANTITY problem head-on
  (no `>=4 same-signature` threshold, no data spent on a held-out half) instead of working around it.
  `prequential.consolidate()` rewritten (`prequential.py:~408`): `pool` = all active distilled bullets →
  `induce.induce(pool, focus_failures=False)` (Claude decides over the whole pool — the existing whole-pool
  inducer, determinism-rule-safe: reads, never rewrites, gate decides) → gate set = every distinct episode's
  task (NO held-out) → new `_gate_solve(task, mem_text)` runs a CONTROLLED deterministic-injection solve (the
  pool memory in the prompt, NO native catalog, but Bash-enabled so a procedure skill can execute) → accept iff
  `(full−base) ≥ margin ∧ broke ≤ rescued`, no power floor. Design choices flagged for the user: (a) `base`
  loads the distilled BULLETS (a lessons list), NOT raw task→answer exemplars, so re-solving a source task with
  the pool loaded is non-trivial (else base ≈ trivially-pass and the +skill A/B has no room); (b) the gate is
  controlled-injection by design (the actual TEST inference stays native) — same stance as the original
  session-20 gate; (c) cost: the gate is now `(#episode tasks) × 2 × (#candidates)` controlled solves (≈32 at
  n=16), a real bump, parallelized at deploy_workers. The frozen TEST split stays the out-of-sample referee.
  `induce_clustered` kept in induce.py for reference (no longer called by the experiment).
- **num_turns instrumentation:** `llm.call_claude(..., return_meta=True)` now also returns the session's actual
  `num_turns` (the JSON already carried it; we were dropping it); `native_solve` surfaces it and all four task-
  row builders log `num_turns`. So no_memory vs ours_full agent-turn parity is now MEASURABLE per task (the cap
  `--skill_turns` was already global/identical across arms; this measures actual self-paced turns; extra turns'
  cost was already in the ledger). The arc_boundary_t1 run PREDATES this (old code) → re-run needed for turns.
- **Status:** code compiles; arc env 38/38 green; NOT yet billed-run with the pooled gate. NEXT: re-run on a
  FOCUSED `group_by_shape` split (the session-16 regime where a transferable procedure exists and memory gave
  +0.50) on the new code, so the pooled gate, the guard, and num_turns all get exercised at once.
- **Dead-code cleanup (user-spotted): removed `--verify_n` / `verify_tasks`.** Once the gate verifies on the
  TRAIN data (cluster gate since s20, pooled gate now) there is no separate val/selection split — `verify_tasks`
  was split out but consumed nowhere, so `--verify_n` only reserved tasks that sat unused (shrinking the pool).
  Dropped `--verify_n` from `run.py` + `prequential.py`, the frozen split is now `(train, test)` and prequential
  `(eval, train)`, and `stratified_split` is generalized to `len(sizes)` slices (so `gate_retest.py`'s direct
  3-tuple call still works). compiles; arc 38/38; split sanity (2-/3-way, disjoint) green.

**Session 20 cont. — POOLED-gate e2e run on group_by_shape (arc_gbs_pooled_t1): the gate FIRES, +0.40 memory
win, skill tier still marginal.** Re-ran on the FOCUSED `group_by_shape` split (`arc_gbs.jsonl`, the s16
regime; `--train_n 16 --test_n 20 --stratify_key skill --induce_every 16 --memory_mode native --skill_turns 8
--batch_size 8`, 1 seed, haiku, **$11.0 total**) on the new pooled-gate + num_turns code.

| arm | test EM (n=20) | F1 | num_turns | cost |
|---|---|---|---|---|
| no_memory | **0.100** (2/20) | 0.951 | 1.0 (all single-shot) | $2.60 |
| ours_full | **0.500** (10/20) | 0.975 | 1.6 (1–3) | $8.45 |

- **The pooled gate WORKS (the cluster gate couldn't):** `[consolidate pooled @15] skill=arc-family-procedure-
  extraction gate_n=16 base=5 -> +skill=5 (rescued=2 broke=2) => candidate (degrade)`. `induce.induce` proposed
  a skill from the bullets; the A/B ran on ALL 16 source tasks (your no-held-out design); +skill rescued 2 but
  broke 2 → net 0 < margin → correctly STAGED as candidate, not activated. **Guard validated:** a single
  `consolidate @15` line (the redundant final consolidate suppressed).
- **+0.40 EM memory win** (ours_full 0.50 vs no_memory 0.10), replicating the s16 group_by_shape +0.50 on a
  less-noisy n=20. no_memory cratered from 0.667 (mixed families, arc_boundary_t1) to 0.10 here — group_by_shape
  is the hard regime that genuinely NEEDS the object-extraction+grouping procedure haiku lacks, so memory has
  real headroom. 1 seed → strong SIGNAL, not significance.
- **The +0.40 is MEMORY, not the skill tier.** The skill stayed a candidate (never activated) → ours_full's test
  run had NO active skill → it is effectively the skill-OFF arm. So this run's boundary answer: distilled memory
  (12 bullets + episodic, natively discovered) carries +0.40; the skill tier adds 0 (it couldn't beat the raw
  memory even on its own data). The project's recurring story, now reproduced under the pooled same-data gate.
- **num_turns instrumentation confirmed + quantifies the turn gap:** no_memory 1.0 (empty catalog → single-shot),
  ours_full 1.6 (1–3, consults memory). The cap (`--skill_turns 8`) is identical across arms; the ~0.6-turn gap
  is ours_full self-pacing to read memory (cost ledgered). Small relative to the +0.40 EM, so memory CONTENT —
  not extra iteration — is the plausible driver; the instrumentation now lets us control it if needed.
- Results-of-record: `results/arc_gbs_pooled_t1/{summary.json,curve.csv,run.log,runs/*/tasks.jsonl}`.
- **NEXT:** ≥3 seeds on this exact config → significance for the +0.40 memory claim (`eval/stats.py`); separately,
  why the induced skill breaks as many as it rescues (a better procedure draft, or a margin/accept tweak, vs the
  honest read "the bullets already encode the procedure → consolidation adds nothing").

### 2026-06-08  (session 19 — make eval台 == real deploy: BOTH memory AND skill retrieval go through Claude Code's NATIVE mechanism (discoverable .claude/skills, agent selects/invokes); mechanism go/no-go PASS for ~$0.01)
The user asked to align the eval harness with REAL deployment: memory and skill should BOTH be selected
via Claude Code's native skill mechanism (description-gated catalog, agent invokes, body lazy-loaded),
and the deploy UserPromptSubmit force-injection should ALSO become native. This removes a real
confound: pre-19, eval force-INJECTED the top-k skills as text every task (no agent choice, pure
clutter), so "does the skill tier add anything over memory?" was measured under a clumsy injection
method, not deploy-faithful conditions.

**Key reframe (the user's correction, and it was right): native skill discovery does NOT need the
heavyweight per-env `agentic_attempt`.** `claude -p` is already an internal agent loop; SB's
`agentic_attempt` is heavy only because SB's ANSWER is a file (write/run/repair). For native skill
discovery we just lift the artificial 1-turn/`Read`-only restriction on the normal text-answer solve:
install skills in the solve's cwd `.claude/skills`, allow the `Skill` tool, give a few turns,
`--setting-sources project`. Env-agnostic, works on ARC directly, **~1.5–3× single-shot cost (NOT 10–20×)**.

**Built (all 3.9-safe; design decisions locked with the user):**
- `engine/evolve/materialize.py` (NEW, pure Python — no LLM, determinism rule intact): renders the store
  as a discoverable catalog. **Per-bullet mini-skill** (user's choice): each active distilled bullet →
  `mem-<id>/SKILL.md`, `description` = the bullet's existing `scope` field (deterministic, no new LLM
  call), body = content; each past-success episode → `ex-<slug>/SKILL.md`; active promoted skills linked
  in. Caps the catalog by net-helpful (coarse bound, like `select_agentic`'s max_index; agent does the
  fine per-task selection). `invoked_to_bullet_ids` / `match_invoked` reverse-map what the agent invoked
  → bullet ids for credit. `assemble_deploy_catalog` / `link_all_skills` for the deploy side.
- `engine/adapters/claude_code/hook_post_tool_use.py` (NEW): a PostToolUse hook that logs every `Skill`
  invocation to a file → the deterministic bridge that replaces "harness injected id X" with "agent
  INVOKED skill X" (deploy-faithful: credit what was USED, not what was offered).
- `eval/prequential.py`: `--memory_mode native|inject` (DEFAULT native) + `--skill_turns` (4) +
  `--skill_tools` ("Skill,Read"; ARC adds Bash). `native_solve()` builds a per-task sandbox (catalog +
  PostToolUse hook + settings.json), runs the Skill-enabled few-turn solve, reads invocations, credits
  the invoked bullets. ALL solve paths route through it in native mode (uniform across arms; no_memory =
  empty catalog; ace/external still inject their playbook/frozen-skill TEXT = the clean single-tier-dump
  contrast). Credit at all 3 sites (process / serve_and_learn / batched_learn) routed via `_credit_ids`.
- **Gate goes native** (`consolidate_native`): base arm = native_solve with the base catalog, full arm =
  + the candidate skills as DISCOVERABLE (presence, not injected text). Judge = **reffree self_verify
  paired check** (user's lightweight choice), reusing `verify.gate_tally` / `signal_agreement` and a new
  factored-out `verify.rolling_decision` (shared accept rule + rolling state; `rolling_gate` refactored
  onto it, behavior identical — gate_audit test 16/16). Honest precision-law caveat: trust the reffree
  gate only where the signal is precise (ARC exec/demo qualifies).
- **Deploy native** (`engine/scripts/evolve` + `engine/.claude/settings.json` + `install-claude`):
  `evolve setup`/`materialize` assemble `.claude/skills` as a REAL dir (authored-skill symlinks +
  materialized mem-*/ex-*); SessionStart hook runs `evolve materialize` to keep the catalog fresh from
  the store; UserPromptSubmit memory-injection REMOVED (memory is now discoverable skills). `.gitignore`
  already covered `engine/.claude/skills`.

**Validation:**
- **GO/NO-GO smoke (`eval/smoke_native.py`, 1 real claude call, ~$0.014, haiku): PASS.** Headless
  `claude -p --setting-sources project` DISCOVERED a `mem-*` skill from the sandbox catalog, INVOKED it
  (the answer carried a secret knowable only from the skill body), the PostToolUse hook FIRED, and
  attribution mapped it back to bullet `m-0001`. (Skill tool_input key is `"skill"`; the substring-based
  `match_invoked` is schema-robust.) This is the de-risking that native discovery works in headless mode.
- End-to-end native prequential ran clean (searchqa, ours_full, frozen 2-train/1-test, gate off): EM=1.0,
  episodes recorded, no crash through inject→native_solve→credit→reflect→deploy.
- Offline: `eval/test_materialize.py` 17/17 (NEW; materialize render/cap/regen/attribution + hook + deploy
  link), `eval/test_gate_audit.py` 16/16 (verify refactor), `eval/test_arc_env.py` 38 (target env intact).

**NOT yet done (honest):** `consolidate_native` is wired + its pieces individually validated, but not yet
run end-to-end with REAL induction (a billed native-gate run). The Tier-1 boundary experiment is the next
billed step.

**NEXT — the Tier-1 native boundary run on ARC (now deploy-faithful):** `--protocol frozen --env arc
--stratify_key family --memory_mode native --skill_tools Skill,Read,Bash`, arms {no_memory, ours_full,
ours_full skill-OFF (`--induce_every 0`)}. With native retrieval the skill-OFF arm now answers "does the
SKILL tier add anything OVER memory" under the SAME mechanism deployment uses — no injection confound.

**Session 19 cont. — align the LIVE deploy LEARNING loop to the experiment (credit + promotion).** Audit
(user asked "train 和 deploy 对齐了吗") found: the eval's frozen train→test is aligned (both go through one
`native_solve`; the gate's full arm presents the candidate as discoverable exactly as inference would — no
train/inference mismatch). But the REAL interactive deploy (`cd engine && claude`) had two gaps vs the
experiment: (a) it never CREDITED invoked memory (no signal), (b) it promoted via the legacy
`promote.run()` (per-bullet draft + replay-substring gate), not the experiment's induce+held-out-gate.
Closed both:
- **Credit** (`reflect.py`): the Stop-hook reflection now parses the transcript for invoked `Skill` names
  (`_walk_content` extracts the tool_use input), maps `mem-<id>` → bullet ids, and `curate.credit(ids,
  success=...)`. Success is REFERENCE-FREE (no tool error observed in the transcript) — the deploy-available
  analogue of the experiment's reffree credit (a live session has no gold/env). Experiment path
  (summary set, `promote_skills=False`) is untouched — it credits via its own native_solve invoked_ids.
- **Promotion** (`promote.consolidate_deploy`): replaces `promote.run()` in the deploy reflect path.
  Clusters memory via `induce.induce` (NOT one-skill-per-bullet), then GATES candidates against the replay
  cases (the deploy held-out benchmark) with the experiment's SAME accept rule (`verify.rolling_decision`,
  native with/without A/B via `_deploy_catalog_solve` = deploy-faithful catalog). NO replay benchmark → STAGE
  candidates for review (honest; never auto-activate blind). Frequency-gated (`DEPLOY_INDUCE_EVERY`, default
  8 reflections) so a live turn doesn't pay induce+gate. `config.ensure_skill_link` hardened to NO-OP on the
  real-dir native catalog (was: migrate+clobber). `promote.run()` kept as legacy/reference.
- **Validated offline** (`eval/test_deploy_learning.py` 8/8, zero spend): transcript→invoked-skill
  extraction; credit uses+1 always / helpful+1 iff no error; consolidate stages candidates when no replay;
  ensure_skill_link doesn't clobber. Full sweep green (materialize 17/17, gate_audit 16/16, arc 38).
  NOT yet billed-run end-to-end (the induce+gate claude path mirrors the already-validated experiment
  functions + the smoke_native mechanism). **Fundamental, honest residual:** deploy's signal is
  reference-free (no gold/env) and its held-out set is the replay cases (sparse → usually underpowered →
  stages) — the MECHANISM matches the experiment; the SIGNAL/evidence is the deploy-available analogue.

**Session 19 cont. — wire the native flags through run.py + FIX the skill-OFF arm + ready-to-run ARC commands.**
- `run.py` now FORWARDS `--memory_mode` / `--skill_turns` / `--skill_tools` / `--permission_mode` to
  prequential (were prequential-only, so a run.py launch silently used defaults). `--permission_mode`
  (default `bypassPermissions`) is now a real flag wired into `native_solve`'s `claude --permission-mode`
  (was hardcoded). For ARC self-test use `--skill_tools "Skill,Read,Write,Edit,Bash"` (Bash lets the agent
  run its solve() on the shown demos = the precise reference-free check). Tools are a GLOBAL flag → applied
  to ALL arms → no confound.
- **FIX (validity-critical):** the frozen post-acquire `consolidate()` (`prequential.py:~1065`) ran
  UNCONDITIONALLY for ours_full, so `--induce_every 0` was NOT a true skill-OFF arm (it still induced+gated
  once at end-of-acquire). Now gated on `induce_every>0` → `--induce_every 0` = genuine skill-OFF (no
  induction at all; ours_full degrades to episodic+distilled), so the C1 skill-tier isolation is clean.
  Corrects the session-18 memory's "skill-OFF = `--induce_every 0`" claim (it was incomplete).
- **Ready-to-run (signals stay `oracle` = frozen+gold boundary protocol; native = deploy-faithful RETRIEVAL):**
  - *Mechanism smoke (~$1–3, 1 seed, 1 gate):* `run.py --tasks eval/data/arc_val.jsonl --env arc
    --methods no_memory,ours_full --protocol frozen --train_n 8 --verify_n 6 --test_n 6 --stratify_key family
    --induce_every 12 --memory_mode native --skill_tools "Skill,Read,Write,Edit,Bash" --permission_mode
    bypassPermissions --skill_turns 8 --seeds 0 --outdir results/arc_native_smoke --max_concurrency 8`
    (induce_every>train_n → only the end-of-acquire consolidation fires once).
  - *Tier-1 boundary (after smoke; TWO run.py calls — skill-OFF is also method `ours_full`, so a SEPARATE
    outdir to avoid the shared `runs/ours_full_seed0/home`):* arm A+B = `--methods no_memory,ours_full
    --train_n 16 --verify_n 8 --test_n 12 --induce_every 16 --outdir results/arc_boundary_t1`; arm C
    (skill-OFF) = `--methods ours_full --induce_every 0 --outdir results/arc_boundary_t1_skilloff` (same
    env/splits/native flags). Reads: ours_full − skill-OFF = skill-tier marginal value; skill-OFF −
    no_memory = memory's own value. Then ≥3 seeds + `eval/stats.py` for significance.
- **STATUS: ready to run; gated on the user.** Native + deploy-learning code committed (a0155d4, d5b0e5e,
  c0909fd); offline suite green (materialize 17/17, deploy_learning 8/8, gate_audit 16/16, arc 38); mechanism
  go/no-go PASSED ($0.014). Pending user decision: the uncommitted
  `engine/skills/self-verify-and-repair/SKILL.md` (verifier-isolation edit, unrelated to this session; inert
  for the native ARC smoke — that authored skill is excluded from the eval catalog by design).

### 2026-06-08  (session 18 — STRATEGIC PIVOT: refocus on the memory↔skill BOUNDARY (C1) under the OFFLINE frozen+gold protocol; verification line DEMOTED to supporting; zero spend this session)
The user flagged that sessions 14–17 had drifted from the original memory/skill thesis INTO verification
(the reference-free SIGNAL refactor → precision-law → gate audits → session-18's "native agent verifier for
ALL datasets" plan). Two decisions, both the user's, recorded here as the project's new direction.

**Decision 1 — A 为主、B 作支撑.** memory/skill (C1/C2) is the headline; verification = MINIMAL supporting
infra + the precision-law as an explanatory chapter, NOT the contribution. DROPPED the session-18 "native
verifier for ALL datasets / make every env solve agentically" expansion (scope B / Phases 3–4 of
`docs/native_verifier_plan.md`).

**Decision 2 — adopt the OFFLINE protocol; accept the C2 tradeoff.** Headline protocol is now
**`--protocol frozen`: train-with-gold → FREEZE memory+skills → deploy-frozen on held-out test** (the standard
skill-formation setup; measures REUSE not local adaptation). This needs NO new code — `--protocol frozen`
(`--n_train/--n_val/--n_test`, `--stratify_key`) already exists and the signal flags
(`--gate/credit/reflect_signal`) **default to `oracle` (gold)**. CONSEQUENCE the user consciously accepted:
this IS the offline-optimizer protocol, so **C2 (native online reference-free ≥ offline optimizer) is SET
ASIDE** (demoted to a possible side-ablation: gold→reffree / frozen→online "how much is lost"). C1/the
boundary is KEPT and is CLEANER under freeze. **Under frozen+gold, verify is NOT load-bearing** (gold drives
training; frozen deploy learns nothing) → it's an optional knob. This reverses the session-14
`native-design-law` "ONE reference-free online loop" north star → that memory + `docs/signal_and_gold_policy.md`
+ `docs/native_verifier_plan.md` are now marked SUPERSEDED/supporting.

**The boundary thesis (sharpened, = what C1 should claim):** *consolidate memory → a GATED skill ONLY where a
shared latent procedure spans a task FAMILY; keep episodic memory for singleton/diverse tasks; the gate is the
mechanism that enforces this boundary.* Already supported in spirit by prior data (episodic wins on diverse SB;
consolidation wins on shared-procedure searchqa; the +0.50 ARC group_by_shape memory lift). The crux not yet
isolated: does the SKILL tier add anything OVER memory? → needs the **skill-OFF arm** (`--induce_every 0`,
confirmed at `prequential.py:700`) = ours_full minus skill induction (degrades to episodic+distilled).

**Done this session (ZERO claude spend):**
- `eval/stats.py` (NEW) — the P0 stats gap: **paired McNemar exact test + paired bootstrap 95% CI** on per-task
  `em` from two methods' `tasks.jsonl`, matched by id, pooled across seeds. Pure stdlib (3.9-safe). Self-test
  green (`python3 eval/stats.py --self-test`).
- Confirmed the boundary experiment is fully supported by existing flags: `--protocol frozen --env arc
  --stratify_key family` (ARC tasks carry `family`/`skill`, `arc_gen.py:330`); arms {no_memory, episodic,
  ours_mem, ours_full, ace, external_optimizer} are env-agnostic; `--induce_every 0` = skill-OFF.
- Recorded the pivot: PROGRESS banner + this entry; `memory/refocus-memory-over-verification.md` (extended) +
  `native-design-law.md` (demoted) + MEMORY.md; SUPERSEDED headers on the two north-star docs.

**NEXT — the C1/boundary experiment on ARC (frozen+gold), budget-gated tiers:**
- **Tier 1 — smoke (~$15–25, 1 seed):** family-rich split, arms {no_memory, ours_full, ours_full skill-OFF
  (`--induce_every 0`)}. Question: does the SKILL tier add anything OVER episodic+distilled memory? (Isolates
  the boundary; extends the session-16 +0.50 with the missing skill-OFF arm.)
- **Tier 2 — make-or-break (~$40–70):** if Tier 1 shows a skill-tier signal, add the single-tier baselines
  (ace, external_optimizer) + go to ≥3 seeds + significance via `eval/stats.py`.
- **Tier 3:** the singleton/diverse split → draw the OTHER side of the boundary (episodic should win, gate
  should reject) → the full boundary map.
- (Carried, now supporting only) the reference-free / precision-law results stand as an explanatory chapter.

### 2026-06-08  (session 17 — apply "reuse official scoring, don't reimplement" to ARC: align score() with the official ARC-AGI kernel; the GENERATOR stays custom for a documented reason)
The user asked to align ARC's evaluation code with the "original" and reuse it rather than self-implement.
Investigated, then split the env cleanly into a CUSTOM generator (justified) + OFFICIAL-faithful scoring (now vendored).

**Finding 1 — the GENERATOR cannot be reused (custom is the only option).** paper5 ("ARC-AGI Stream", arXiv
2605.12978) ships ONLY a PDF (`papers/paper5/2605.12978v1.pdf`) — no code, no generator. And real ARC-AGI
(fchollet) data is NOT family/skill-labeled, which the entire gate experiment depends on (shared-procedure
families + precise signal). So `arc_gen.py` MUST stay self-implemented — this is the one justified self-implemented
artifact (already flagged in `reuse-not-reimplement-eval.md`). Documented the reason inline in arc_gen.py's docstring.

**Finding 2 — the SCORING has an "original" and now matches it.** Pulled the official ARC-AGI scoring convention
(fchollet/ARC-AGI README + arc-prize/model_baseline `ARCScorer.score_task`). The kernel is tiny and unambiguous:
exact match = plain list-of-lists `pred == gold` (dims + every cell, NO cell-level partial credit); a test pair is
solved iff ANY attempt matches (pass@k); the per-task score is the FRACTION of pairs solved (`task_score/num_pairs`);
aggregate = mean×100. Audit of our old `arc.py:score()`:
  * exact-match comparison (`pred == gold`) was ALREADY identical to official ✓ (no faithfulness bug — unlike the
    pre-vendor ifbench regex stub or sb_lib's value quantization, ARC's comparison has no non-obvious rule to get wrong);
  * we reported a STRICT all-or-nothing `em` + a homemade cell-`f1`, and did NOT expose the official FRACTIONAL
    per-pair task score — the one real divergence.

**Change (additive, recorded results stay comparable):** vendored the official scoring KERNEL into
`eval/envs/arc_lib/scoring.py` (same discipline as `sb_lib/` / `ifeval_lib/`; provenance header + the pass@1
program-synthesis caveat). `arc.py:score()` now delegates the per-pair exact-match + per-task scoring to it and
exposes:
  * `em` = strict all-pairs-solved (the README "correct for *all* test inputs" task-solved binary; VALUE UNCHANGED),
  * `arc_task_score` = the OFFICIAL fractional score (`task_score/num_pairs`; with n_tests=2 → 0/0.5/1.0) — NEW,
  * `f1` = mean cell accuracy, now explicitly LABELED a non-official diagnostic (VALUE UNCHANGED → prior arc_gbs
    cell-F1 numbers remain comparable). I did NOT vendor the official `ARCScorer` class wholesale: its JSON-submission
    file-I/O wrapper (ARCTask/BenchmarkedTaskResults dataclasses, submission-dir readers) is tied to a direct-grid
    PREDICTION format that doesn't apply to our program-synthesis env — only the scoring logic is faithfulness-bearing.

**Honest scope:** because ARC's scorer is trivial, this is mostly PROVENANCE + exposing the official fractional
metric, not a bug fix (our exact-match was already right). The lasting value: the env is now cleanly split — scoring
is official-faithful (vendored, with the fractional metric available), generator is custom-by-necessity (documented).
ARC remains a CONTROLLED DIAGNOSTIC (no external-leaderboard comparability, since the tasks are generated), NOT a
comparability headline. **Tests: `eval/test_arc_env.py` 38/38 (was 27; +11 for arc_lib kernel + arc_task_score),
zero spend.** New: `eval/envs/arc_lib/{__init__,scoring}.py`. Touched: `arc.py` (import + score() + docstring),
`arc_gen.py` (docstring). **NEXT (unchanged):** the ≥3-seed + P0-stats follow-up on the group_by_shape +0.50 memory
win; optionally report `arc_task_score` alongside em in the arc summaries/plots.

### 2026-06-08  (session 16 cont. — METHODOLOGY: vendor the OFFICIAL IFEval verifiers; "reuse official scoring, don't reimplement")
Prompted by the user's audit ("is the self-implemented eval code necessary?"), paid down a faithfulness debt.
The old `ifbench.py` was a stdlib REGEX REIMPLEMENTATION of IFEval — its own docstring admitted "close, not
identical": only 23/25 instruction types, nltk tokenizers regex-approximated (word/sentence counts diverge near
boundaries), and `repeat_prompt`/`end_checker`/`postscript` leniency-divergent. Since em is prompt-level STRICT
(one verifier flips → whole prompt flips), our IFBench em could differ from published IFEval. **NOW vendors
google-research's `instructions{,_registry,_util}.py` VERBATIM into `eval/envs/ifeval_lib/`** (the same discipline
as `sb_lib/` vendoring SkillOpt's executor) and replicates the official strict-check loop
(`build_description(**kwargs)` → re-build with the prompt if the instruction needs it → `check_following`). All 25
types (incl. `language:response_language` via langdetect + `nth_paragraph_first_word`). **TYPE-1 preserved:
`verify()`==`score()` (same `_check_all`) → the reference-free signal == the gold criterion BY CONSTRUCTION.**
Deps added (`requirements.txt`): nltk(+punkt)/langdetect/immutabledict/absl-py. Regenerated `ifbench_val.jsonl`
(full coverage). Tests: `eval/test_ifbench_env.py` 24/24 (+ arc 27/27), zero spend.
**The principle (now explicit): REUSE official scoring (vendor it), never reimplement.** This leaves `arc` as the
ONLY remaining fully-self-implemented env (P5 released no generator + real ARC isn't family-labeled, so custom was
justified — but it carries a "our-ARC-not-standard, no external comparability" caveat; treat ARC as a CONTROLLED
DIAGNOSTIC, not a comparability headline). IFBench is now faithful + type-1 + integrated → the strongest env for
the reference-free/gate claim. NEXT (the arc/ifbench tradeoff): a constraint-FAMILY-focused IFBench frozen
gate_audit (type-1 + shared procedure → the cleanest shot at the positive case on a FAITHFUL env), with ARC kept
for the demo-CV mechanism test + the (custom-env) +0.50 memory datapoint.

### 2026-06-07  (session 16 cont. — MAKE-OR-BREAK group_by_shape gate run → HUGE clean memory win (+0.50 monotone) + a SHARPER precision law: "executable ≠ precise"; the hoped reffree-preserves-activation POSITIVE case did NOT land, for an informative reason)
Ran the billed frozen `group_by_shape` gate_audit run (arc_gbs.jsonl, train24/val18/test18, induce_every12,
no_memory + ours_full, **repair OFF**, lexical, seed0, `--gate_audit`; **$15.6** — ours_full $13.5 ran over the
~$10 estimate: the val A/B at @11 + a double consolidate at @23 added cost).

**RESULT 1 — the biggest CLEAN memory lift in the project (C1):**
| method | test EM | rescued / broke | cell-F1 | cost |
|---|---|---|---|---|
| no_memory | 0.444 (8/18) | — | 0.958 | $2.02 |
| **ours_full** | **0.944 (17/18)** | **9 / 0 (MONOTONE)** | 0.999 | $13.54 |
**+0.50 EM, 9 rescued / 0 broken**, repair off, on a PRECISE-signal family-structured env. The group-by-shape
SELECTION procedure transfers across ALL skills (rescues span border×4, flip×3, keep×1, recolor×1). This is the
"memory helps a lot where a TRANSFERABLE PROCEDURE is genuinely missing" thesis at full strength. **Attribution
caveat:** ours_full at test = 9 distilled bullets + episodic + 1 (thinly) activated skill → the +0.50 is the
COMBINED memory effect, NOT isolated to the skill (no skill-OFF arm; the bullets already encode the procedure).
1 seed, n=18 → strong SIGNAL.

**RESULT 2 — first genuinely-good induced skill, but the activation is NOT robust:** the reflector induced an
excellent group-by-shape procedure skill (`arc-family-procedure-not-hacks`: "extract objects via 4-conn flood
fill → select by family criteria → apply transform per object → redraw on blank grid; do NOT add per-grid
hacks"). The gold **single-round** gate (gate_audit uses `gate_tally`, NOT the accumulated `rolling_gate`)
activated it at @23 (oracle rescued **2/3** base-failures, broke 0, full-base=+2 = exactly margin). BUT the
PRODUCTION accumulated rolling_gate would REJECT: per-round full-base deltas @11/@23a/@23b = +1/+2/−2 →
cumulative ≈ +1 < margin. So **NOT a robust skill activation** (thin favorable single round, n=18, 1 seed — same
caution as session-13). The durable win lives in MEMORY/bullets; the skill tier stays marginal — the consistent
project story, now with a +0.50 memory effect behind it. (Minor harness quirk noted: the inducer drafted 3
near-duplicate skills with different names across checkpoints.)

**RESULT 3 — the key SCIENCE: the precision law sharpens to "EXECUTABLE ≠ PRECISE; the reference-free signal must
test the GOLD CRITERION, not a proxy."** At the activating checkpoint the **reffree gate DISAGREED with oracle**
(AGREE=False: reffree rejected, rescued2/broke3). Across ALL checkpoints **`base_fail_agree` ≈ 0.0–0.33** — the
reffree (pass-the-SHOWN-DEMOS) signal is BLIND to the gold base-failures: a program can reproduce the few demos
yet fail held-out (it overfits the demos). **Few-shot demos UNDERDETERMINE the generalization rule**, so the
deploy-available reference-free check tests CONSISTENCY-WITH-SHOWN-EXAMPLES, not GENERALIZATION (what gold scores).
⇒ being "executable" is necessary but NOT sufficient for a trustworthy no-gold gate; the check must test the SAME
criterion as gold. This UNIFIES dyck (NL self-critique tests "looks plausible," not "is correct") and ARC (demos
test "consistent," not "generalizes") — both reference-free signals are PROXIES → blind. **The hoped POSITIVE case
(a PRECISE reffree gate PRESERVES a gold activation) did NOT materialize — and the reason (proxy-vs-criterion) is
more informative than a trivial confirmation.** Results/figs: `results/arc_gbs_gateAB/` (+ `gate_audit.json`).

**NEXT (this result directly motivates it): make the ARC reffree signal PRECISE-FOR-GENERALIZATION, then re-audit.**
Two deploy-available ways to close the proxy gap WITHOUT gold: (a) more demos (passing K=8 implies the rule far
better than K=4); (b) **demo cross-validation** — split the SHOWN examples into fit/check, score reffree on the
held-back SHOWN examples (still no gold). If a precise-for-generalization reffree signal THEN tracks oracle →
the real positive case. Also: ≥3 seeds + P0 stats on the +0.50 (already monotone → likely robust); a skill-OFF
arm (`--induce_every 0`) to isolate the skill's marginal test contribution from the bullets'.

### 2026-06-07  (session 16 — BUILT the ARC-AGI Stream env: the precise-signal + family-structure regime the gate needs; zero spend, fully validated; + the "can we just turn knobs?" analysis)
The session-15 conclusion was that NO current env has BOTH a PRECISE reference-free signal AND a robustly-
beneficial gate-activating skill (SB precise-but-rejects; dyck activates-but-blind; IFBench precise-but-rejects),
so a clean "reffree gate PRESERVES a gold ACTIVATION" demo needs a new regime. Two threads this session.

**Thread A — analysis the user asked for: can we ACTIVATE skills by expanding n / shrinking the induce
interval, instead of a new benchmark? Answer: NO — those knobs don't touch our binding constraint.** Read the
real gate (`verify.rolling_gate` + `prequential.consolidate`). Activation rule = `powered(n_cum≥18) ∧
beats(full−base≥2 cum) ∧ not_diluting(broke≤rescued cum)`. Two DISTINCT "gate never fires" modes that respond
OPPOSITELY to more n / more rounds: **(A) no candidate drafted** (the old SB n=16 `helpful≥5` caveat) — more
n/shorter interval HELPS; **(B) candidate drafted but the A/B REJECTS it** (dyck/IFBench/SB now) — the skill is
net-NEUTRAL on held-out val, so more n drives (full−base)→its true ~0 making `beats≥2` HARDER, and more rounds
converge the rolling state to reject FASTER (the gate getting correctly conservative; session-13's rescued4/broke2
"activation" re-measured to 4/4). The eval path is firmly Mode B (consolidate induces candidates directly from the
failure digest, no `helpful≥5` step; n already 32≫18). So: **expanding n improves VALIDITY, doesn't create
activations; shrinking the interval gives more but LOWER-evidence candidates + faster-converging rejection** (for
skill QUALITY you'd LENGTHEN the interval). The binding constraint is skill-marginal-value-over-memory + val
headroom (base failures to rescue) = a TASK-REGIME property → needs a regime change, not a knob. (Cheaper middle
path noted: a HARDER SLICE of an existing symbolic env un-saturates word_sorting + makes the procedure necessary.)

**Thread B — benchmark inventory of papers/ + decision.** Inventoried the 6 papers' benchmarks (agent-extracted):
P1 MemOp=SWE-bench Verified; P2 SkillOpt=**SearchQA+SpreadsheetBench**(ours)+DocVQA/LiveMath/OfficeQA/ALFWorld;
P3 CoEvoSkills + P4 MUSE + P6 = **SkillsBench** (the de-facto agent-skill standard, Docker verifier, 87 tasks×11
domains); P5 = **ARC-AGI Stream** + ALFWorld/ScienceWorld/WebShop. Candidates with BOTH a precise/executable signal
AND shared-procedure families: SkillsBench (best but Docker-heavy), **ARC-AGI Stream (lightweight, explicit
family/skill taxonomy, programmatic grid check)**, SWE-bench (heavy). **User chose ARC-AGI Stream.**

**BUILT (self-contained, NO ARC-GEN/Docker/network; pure Py3.9 + numpy; ZERO claude spend):**
- `eval/envs/arc_gen.py` — procedural generator re-derived from P5's Tables 5–6 + App. B.2. Two latent axes:
  **FAMILY** (selection rule: which connected objects participate) × **SKILL** (per-object transform), composited
  on a blank canvas (unselected objects dropped). v1 = **7 skills** {keep, recolor, translate, flip_horizontal,
  border, mark_center, hollow} × **3 families** {color_property, largest, group_by_shape} = 21 latent rules; P5's
  other 3 families {inside_frame, key_marker (conditional), compose_horizontal (2-panel)} DEFERRED to v2. `apply_rule`
  IS the ground truth; `reference_solver_src()` emits a self-contained `solve()` that reproduces it.
- `eval/envs/arc.py` — env conforming to the interface. Task = few-shot **program synthesis** (`def solve(grid)`),
  grids list[list[int]] colors 0–9. **TWO deliberately-distinct signals:** `score()` = ORACLE (run solve on HELD-OUT
  test inputs → exact-match EM + cell-F1); `try_run()` = REFERENCE-FREE (run solve on the SHOWN demos → the PRECISE
  self_verify EXECUTION channel — `self_verify` routes here because the answer carries a code block, so the gate gets
  execution, NOT dyck's blind NL self-critique). Subprocess exec runner (12s timeout, crash/loop-safe). `verify()` =
  ref-free structural (code block defines solve); `evidence/summarize` = per-FAMILY procedure-focused reflection.
  Design: NO helpers provided to the agent (max headroom; the induced skill can teach the extract-objects+select
  procedure).
- `eval/test_arc_env.py` (**27/27, zero spend**) — headline = SELF-CONSISTENCY across ALL 21 (family,skill): the
  emitted reference solver reproduces every demo AND held-out test via the real exec runner (proves tasks are
  program-solvable + generator↔runner agree). Plus oracle-vs-wrong, the 4 try_run cases (pass/crash/wrong/timeout/
  no-code), verify, prompt, evidence, load_tasks.
- `eval/data/arc_val.jsonl` (tracked, 647K, seed 0, 60 tasks balanced over families/skills). Re-gen:
  `python3 eval/fetch.py --env arc --n 60`. Wired via the by-module-name dispatcher (`--env arc`, no registration);
  verified end-to-end through `envs.get_env` (load/prompt/score/try_run/collect_evidence all green).

**HEADROOM PROBE RESULT (no_memory, 3 difficulty tiers x n=12, haiku, repair off, ~$3.3):** healthy STRUCTURED
headroom — NOT the ceiling we feared.
| tier (grid/demos) | no_memory EM | cell-F1 |
|---|---|---|
| easy (10²/5) | 0.667 (8/12) | 0.973 |
| med (13²/4) | 0.750 (9/12) | 0.983 |
| hard (17²/3) | 0.750 (9/12) | 0.986 |
EM is FLAT across tiers (grid size / n_demos are NOT the difficulty lever — the difficulty is RULE INFERENCE, not
grid size). The ~0.70 headroom is **highly CONCENTRATED** (the ideal shape for skill formation, unlike zebra's
scattered near-misses):
- by FAMILY: color_property **0.87**, largest **0.92** (near-ceiling) vs **group_by_shape 0.22 (2/9)** — ALL the
  headroom is here;
- by SKILL: keep/recolor/hollow **1.00**, flip 0.83, vs mark_center/translate **0.67**, **border 0.44** (hardest);
- 7 of 10 failures involve group_by_shape OR border; the group_by_shape failures are NEAR-MISSES (cell-F1 0.87–0.98)
  = "capable but slips on the mode-shape SELECTION procedure" → systematically rescuable by a per-family procedure
  skill (extract objects → normalize shape → pick the frequency-mode group). This is the "transferable procedure is
  genuinely missing" case (session-13 law), NOT zebra's "capable model occasionally errs."
Added difficulty knobs `size_range`/`nobj_range` to `arc_gen.gen_task` + `arc.fetch` (defaults unchanged → the
committed arc_val.jsonl still reproduces). Probe (gitignored): `results/_arc_probe/`.

**NEXT (the make-or-break billed run — GATED on user): a group_by_shape-FOCUSED frozen ours_full vs no_memory with
`--gate_audit`** (the headroom family → an induced "group-by-shape selection" skill has real rescue room; precise
exec reffree signal → the gate should TRACK gold). The precision-law-for-gating POSITIVE case we've never gotten:
does a PRECISE reference-free gate PRESERVE a gold skill ACTIVATION? Then ≥3 seeds + P0 stats (McNemar + bootstrap CI).

### 2026-06-07  (session 15 cont. — VALIDATION EXPERIMENT: clean precision-law-FOR-GATING audit on dyck → mechanism works; 1-seed AGREE-on-reject + a measured reffree precision gap; discriminating ACTIVATE case still pending)
Ran the first billed validation of the session-14 reference-free refactor: the `ours_full` reffree-vs-oracle
GATE A/B (does a no-gold gate make the same accept/reject decision as the gold gate?). **Budget gate honored**
(user chose "smoke then make-or-break ~$22"; spent ~$10.4 total).

**Validity checks BEFORE spending (caught two design traps):**
- The gate A/B only means something on an env where the gate ACTIVATES a skill. Checked session-13 BBH: the
  gate REJECTED on **word_sorting** (lift was from distilled BULLETS, not a skill) and ACTIVATED on
  **dyck_languages** → switched the experiment to **dyck**.
- **Smoke (dyck 16/18/24, oracle vs reffree as two separate runs) exposed an acquisition-noise confound:** the
  two arms acquired DIFFERENT memory purely from claude reflection stochasticity (oracle 1 bullet→0 candidates;
  reffree 7 bullets→2 candidates), so comparing their test EM doesn't isolate the gate signal. Also the gate
  doesn't fire at the smoke scale (oracle induced nothing). Smoke DID validate the reffree gate PATH end-to-end
  (induced 2 cands, ran the reference-free paired A/B, graceful REJECT) + confirmed FREEZE (test wrote nothing:
  episodes.jsonl=16=acquire-only; parallel deploy_workers=12 only safe on a frozen store).

**The fix — `gate_audit` (new, offline-validated ZERO spend, `eval/test_gate_audit.py` 13/13):**
`verify.paired_ab_multi` solves the val base/full A/B ONCE and scores it with BOTH judges (oracle gold +
reffree self_verify) on the IDENTICAL answers → removes the judge-comparison noise; `verify.gate_tally`
replays rolling_gate's single-round accept rule; `prequential --gate_audit` logs both decisions to
`home/gate_audit.json` (live decision still = `--gate_signal`). Threaded through run.py.

**Clean make-or-break result (dyck, ONE acquisition 32/32/96, seed0, repair OFF, lexical, induce_every 0):**
| signal | base_pass | full_pass | rescued | broke | activate |
|---|---|---|---|---|---|
| oracle (gold) | 29/32 | 29/32 | 2 | 2 | **False** |
| reffree (self-critique) | 31/32 | 31/32 | 1 | 1 | **False** |
→ **AGREE=True (both REJECT the induced candidate `dyck-exhaust-stack`).** Deployed test EM **0.927** (skill
kept as candidate → ours_full = episodic + 4 bullets) vs no_memory **0.729** = **+0.198 from MEMORY** (clean,
repair off). Cost $7.93. Results: `results/dyck_gateAB_clean/` (+ `_smoke_{oracle,reffree}/`).

**Interpretation (honest):** (1) the audit MECHANISM works — confound removed, both judges on identical
answers. (2) On this seed the two gates AGREE, but it's the EASY direction: the gold gate ALSO rejected (skill
was neutral, rescued=broke=2), so rejecting is trivially right under either signal. **We did NOT get the
discriminating case** (gold says ACTIVATE → does reffree also activate?) — acquisition stochasticity induced a
NEUTRAL skill this run (session-13's run induced a BENEFICIAL one, rescued=4/broke=2 → ACTIVATE). (3) **A real
reffree PRECISION GAP is visible in the numbers:** reffree judged 31/32 base answers as ok where gold says only
29/32 — it MISSED 2 of the 3 genuine failures (over-lenient self-critique on bracket sequences). Latent here
(skill neutral) but exactly the failure mode that would make a reffree gate UNDER-fire on a beneficial skill =
the precision-law-for-gating boundary.

**TARGETED RE-TEST (the discriminating case; `eval/gate_retest.py`, +$4):** loaded session-13's ALREADY-
ACTIVATED candidate `dyck-language-stack-algorithm` on top of its acquired episodic+distilled base and ran
`paired_ab_multi` (both judges, SAME val answers, repair off, n_val=32):
| signal | base_pass | full_pass | rescued | broke | base_fail | activate |
|---|---|---|---|---|---|---|
| oracle (gold) | 28/32 | 28/32 | 4 | 4 | 4 | False |
| reffree (self-critique) | 32/32 | 31/32 | 0 | 1 | 0 (SATURATED) | False |
**Two findings, both important:**
1. **Precision-law-for-gating CONFIRMED, concretely:** on dyck the reffree self-critique is so LENIENT it
   passed ALL 32 base answers (saturated, base_fail=0) — BLIND to the 4 failures gold catches. Across the
   clean run + retest it over-passed every time (gold-fail 3→reffree-saw-1, then gold-fail 4→reffree-saw-0). A
   gate that sees no failures has NO signal to gate on. ⇒ the reference-free gate is trustworthy ONLY where the
   signal is precise (execution↔code, in-prompt-constraints↔instruction-following); NL self-critique of bracket
   sequences is NOT, so the no-gold gate degrades to blind. `agree=True` (both reject) is COINCIDENTAL — oracle
   rejects because the skill is net-neutral, reffree because it's blind.
2. **The session-13 "first durable gate activation" was a THIN, NON-REPRODUCIBLE margin:** this same skill is
   net-NEUTRAL on re-measurement (gold rescued=4/broke=4) vs session-13's rescued=4/broke=2 → at n=32 the ±2 is
   noise. That activation should NOT be cited as a robust skill win.
**Net:** the session-14 reffree-gate refactor works MECHANICALLY (audit validated), but on an imprecise-signal
env (dyck) a no-gold gate carries no usable signal — the honest precision-law boundary. **To get the POSITIVE
case (reffree PRESERVES a gold lift) we need an env with a PRECISE reffree signal AND a robustly-beneficial
gate-activating skill** — code→execution (but SB's gate rejects: diverse) or IFBench→in-prompt constraints (gate
behavior there untested). That is a NEW experiment to scope, not a dyck seed. Results: `results/dyck_gate_retest.json`.
New harness: `eval/gate_retest.py`.

**IFBENCH PROBE — the COMPLEMENTARY (precise-signal) side (`results/ifbench_gateAB/`, +$3.45).** IFBench's
reference-free signal is precise (in-prompt constraints; session-8 self==oracle). ours_full frozen 24/30/6,
seed0, `--gate_audit`, repair off, lexical. Added `verify.signal_agreement` (per-task judge agreement, incl.
`base_fail_agree` = agreement on the gold base-FAILURES, where a gate's rescue signal lives — a blind judge
scores ~0 there even at high overall agreement). 1 candidate induced (`constraint-satisfaction-in-instruction
-tasks`):
| env | reffree signal | reffree saw gold's base-failures? | base_fail_agree | gate (both signals) |
|---|---|---|---|---|
| dyck | NL self-critique of bracket seq (imprecise) | 0 of 4 (SATURATED, blind; base_pass 32/32 vs gold 28) | 0.00 | reject (coincidental) |
| IFBench | in-prompt constraints (precise) | 2 of 4; NOT saturated (reffree base_fail=8 vs gold 4) | 0.50 | reject (signal-grounded) |
→ **PRECISION-LAW-FOR-GATING, BOTH SIDES (1-seed signal):** where the reference-free signal is PRECISE
(IFBench), the no-gold gate TRACKS gold (sees failures, makes a signal-grounded decision); where it is
IMPRECISE (dyck), it goes BLIND (saturated) and any agreement is coincidental. (IFBench base_fail_agree=0.50 is
2/4 — small n_base_fail; the robust contrast is tracks-vs-blind, not the exact 0.50; ≥3 seeds would tighten it.)

**SECOND ROBUST FINDING across ALL gate tests (dyck×2, IFBench, + earlier word_sorting/SB): the promotion gate
essentially NEVER activates a durable skill.** Every induced candidate is REJECTED on held-out A/B (or, like
session-13 dyck, "activates" on a thin non-reproducible margin). The skills induced are not robustly beneficial;
the system gracefully degrades to memory (episodic+bullets), which is where the actual wins live (dyck ours_full
+0.198 over no_memory @ repair=0; IFBench prior +0.04–0.08). This empirically reinforces the C1 REFRAME (judge
the GATE's discipline, not tier-count — see `memory/lit-critique-strategy.md`): the gate correctly gates skills
OUT. ⇒ a clean "reffree PRESERVES a gold ACTIVATION" demo would need an env with BOTH a precise signal AND a
robustly-beneficial activating skill — none of our current envs has both (SB precise-but-rejects; dyck
activates-but-blind; IFBench precise-but-rejects). Likely needs a constructed code-FAMILY (precise exec signal +
genuine shared procedure). **Total validation spend this session ≈ $17.9.** New: `eval/gate_retest.py`,
`verify.{paired_ab_multi,gate_tally,signal_agreement}`, `prequential/run --gate_audit`,
`eval/test_gate_audit.py` (16/16).

### 2026-06-07  (session 15 — DESIGN DECISION: repair-lever keep-vs-drop → user picked (a) KEEP, strictly ablated + labeled-lever discipline codified)
Resolved the one open design decision flagged in memory (`self-verify-role-split.md` → "OPEN DECISION: the
user must pick"): whether to KEEP the harness repair loop (strictly ablated) or DROP it (signal-only). **The
user picked (a): KEEP repair as a SEPARATE, LABELED lever** — retaining the real-but-separate repair杠杆 + the
"learn from your own repair trajectory" sub-story (rejected (b) = the purest-memory-paper route that drops the
repair lever). The apparatus already SUPPORTED (a) cleanly (default `--repair_turns 0`; `--repair_methods`;
agentic bypasses `monotone_repair`), so this session **codifies the reporting discipline** — no behavior change,
ZERO claude spend.

**The discipline (now enforced across code + docs):**
1. **`self_verify` is the reference-free OUTCOME SIGNAL** (the system's own correctness signal; two roles —
   Role 2 = drives credit/gate/reflect = CORE; Role 1 = feeds the repair loop). The repair loop is NEVER called
   "memory".
2. **Memory claims are ALWAYS read off the repair=0 column** (`--repair_turns 0`, the default → default config
   is already clean).
3. **Repair is studied via the explicit memory × repair 2×2** (methods {no_memory, ours_full} × {repair 0,
   repair N `--repair_methods all`}) + the `no_memory+repair` apparatus-only arm. Repair's Δ is its own lever.
4. **Deploy-faithful memory headline = the AGENTIC harness** (`--agentic`): native self-correction →
   `monotone_repair` bypassed (`repair_calls=0`); single-shot+`monotone_repair` only STANDS IN where an env
   lacks `agentic_attempt`.
5. **Phase B carries the SAME signal — incl. the repair trajectory — into the deploy hooks' credit/gate** (the
   "learn from repair" sub-story is retained, not dropped).

**Files (docstrings/help/docs only — no logic change):** `eval/self_verify.py` (module docstring → named the
reference-free OUTCOME SIGNAL + the two-role split), `eval/prequential.py` (`--repair_turns`/`--repair_methods`
help + `_repair_budget` docstring), `eval/run.py` (mirrored help), `docs/eval_protocol.md` (new "Reporting
discipline — the repair lever & the deploy-faithful headline" section), `docs/agentic_harness_design.md`
(status → adopted as the deploy-faithful headline), `docs/architecture.md` (new "two levers" section + LEARN
band relabeled to the reference-free OUTCOME SIGNAL + Phase B note). Memory updated: `self-verify-role-split.md`
(decision RESOLVED), `native-design-law.md` (Phase B retains the repair lever), `MEMORY.md` index.
**Validation:** `eval/test_signal_routing.py` + `eval/test_agentic.py` green (zero spend) — behavior unchanged.
**NEXT (unchanged by this decision, now scoped):** (1) the billed `ours_full` reffree-vs-oracle gate A/B
(precision-law-for-gating); (2) P0 stats (paired McNemar + bootstrap CI, ≥3 seeds) + the compute-matched
`no_memory+best-of-k` arm; (3) Phase B — wire the reference-free OUTCOME SIGNAL (incl. repair trajectory) into
the deploy hooks so deployed == evaluated.

### 2026-06-07  (session 14 — 6-paper review → the "reference-free signal" refactor: A1/A2/A3 + gate/train alignment, NO train-inference mismatch)
Reviewed `papers/` (MemOp / SkillOpt / CoEvoSkills / MUSE / "Useful Memories Become Faulty…" / "Harness
Updating Is Not Harness Benefit") against our engine+eval. **All code below is unit-validated with ZERO claude
spend** (`eval/test_signal_routing.py` 25/25 + regressions green); the billed A/B is the NEXT step.

**Strategic findings (full reasoning in memory: `lit-critique-strategy.md` + `native-design-law.md`):**
- Our DETERMINISM rule is the strongest pillar (paper5: LLM-wholesale-rewrite collapses, ARC 100→52.6). The
  threats are (a) the abstract/skill tier rarely earns its keep (paper5 abstract-only ≤ zero-shot; paper6
  "updating is FLAT, 9B≈Opus"; our own gate-rarely-helps) → reframe C1 around the *gate*, not tier-count; and
  (b) attribution/validity (1–2 seed, no CI, single-solver, memory⊗repair⊗compute conflated) threatens all empirics.
- **Code-verified correctness-signal audit:** every offline optimizer gates on GOLD at train; NONE evolves on a
  reference-free signal at no-gold DEPLOY (offline ones freeze; "online" ones are measured in-situ on gold
  benchmarks). CoEvoSkills proves reference-free CAN drive evolution (dense surrogate > sparse gold, −30pp).
  ⇒ **"reference-free self-eval driving ONLINE no-gold deploy evolution" is the unfilled gap = our C2 thesis.**

**THE DESIGN DECISION (north star): ONE system = the reference-free deploy loop; gold is only a read-only eval
overlay (+ an opt-in oracle CEILING). Implemented as the SIGNAL the system's own credit/reflect/gate run on.**
- **A1 gate / A2 credit / A3 reflect now take a SIGNAL knob** (`--gate_signal / --credit_signal /
  --reflect_signal ∈ {reffree, oracle}`, **default `oracle` for back-compat**). `reffree` = the deploy-available
  `self_verify` (execution / in-prompt constraints / self-critique; reads NO gold). `oracle` = GOLD (`env.score`
  em / gold-grounded `collect_evidence` incl. the N3 semantic value-diff). Pure module-level helpers
  (`reffree_verdict / reffree_ok / make_judge / reffree_evidence_dict`) keep routing unit-testable; the rf verdict
  is computed AT MOST ONCE per learned task and reused for episode-success + credit + reflection across all 3
  learn paths (sequential / serving / batched). **Honest cost of `reffree`: the gold N3 semantic reflection is
  not deploy-faithful → it lives only on the `oracle` path** (so a `reffree` headline loses N3, by design).
- **Gate ↔ inference ALIGNMENT (no train-inference mismatch):** the promotion gate's held-out A/B previously
  solved with a BARE single-shot call and DUMPED all candidate skills (skills-first) — neither matched how
  inference actually solves (single-shot **+ repair**, or agentic) or presents skills (`skills_block`: top-k by
  relevance, 560-char-truncated, skills-LAST). Fixed: `verify.paired_ab/lift_over_base/rolling_gate` gained
  `solve_fn` (the gate now solves via the REAL `solve()`) and a per-task callable `skill_block`; factored
  `retrieve.render_skills_block` so the gate renders CANDIDATE skills with the EXACT same function/format/order
  inference uses for ACTIVE skills. ⇒ a skill is now judged on the repaired/agentic answer it will actually face.
  (For `repair_turns=0` non-agentic this is identical cost to before; the extra cost appears only where the old
  gate was *wrong*.)
- **external_optimizer train ↔ deploy ALIGNMENT:** `train_external` gained `solve_fn`; its offline rollouts now
  go through the SAME `solve()` the frozen skill is deployed under (moved the training call to after `solve()` is
  defined). No-op for single-shot; fixes the **agentic** train(bare)/deploy(multi-turn) mismatch and is more
  faithful to SkillOpt's own multi-turn training. (Still a partial faithfulness fix — external lacks the
  selection-gate / bounded-edits / multi-epoch / rejected-buffer; that fuller rebuild is the separate P1 item.)

**Files:** `engine/evolve/{verify,retrieve}.py`, `eval/{prequential,run,external_opt}.py`; new
`eval/test_signal_routing.py` (25/25, zero spend). **Defaults unchanged (oracle) → existing runs reproduce.**
**Decisions:** keep `oracle` default for reproducibility; `reffree` is the deploy-faithful target; flip the
default only after the A/B. **NEXT:** (1) the billed **`ours_full` reffree-vs-oracle A/B** (= precision-law-for-
gating: how much of the gold gate's lift survives a no-gold gate) — the first validation of the whole refactor;
(2) P0 stats (paired McNemar + bootstrap CI, ≥3 seeds) + the compute-matched `no_memory+best-of-k` arm;
(3) Phase B — carry reference-free credit/gate into the deploy hooks (`promote.run` → `induce`+reference-free
rolling-gate over replayed recent episodes) so deployed == evaluated.

### 2026-06-07  (session 13 cont. — ZebraLogic-6x6 skill-formation run COMPLETE → weak memory, skill rejected)
Re-ran to completion with **`--batch_size 4`** (bounded-staleness parallel acquisition — the only sequential
bottleneck; verified it routes through `learn_stream`→`batched_learn` in the frozen path). 40 puzzles, frozen
acquire16/val12/test12, seed0, no_memory vs ours_full, repair off, lexical, induce_every 8.
| method | testEM | cellF1 | cost |
|---|---|---|---|
| no_memory | 0.750 | 0.847 | $2.19 |
| **ours_full** | **0.833** | 0.859 | $13.38 |
**Memory +0.083 EM** (rescued 2 / broke 1, net **+1/12**) — directionally positive but **within noise** (n=12,
1 seed, ~0.7 SE). **The SKILL tier was REJECTED:** the gate induced two constraint-propagation skills and
rejected BOTH (cum broke 4 / rescued 1 on val → `candidate`, no active skill), so the small lift is from the
**2 distilled bullets, not a skill**. **Verdict: ZebraLogic-6x6 is a WEAK memory/skill regime** despite ideal
reuse structure — haiku-4.5 near-solves it, so a procedure-skill adds little and DISRUPTS (gate correctly
gates it out). Contrast dyck (+0.188, skill ACTIVATED) / word_sorting (+0.479) = the stronger ground. **Cost
note: 6x6 responses avg ~28K output tokens (max ~60K) → generation-bound + pricey ($15.58 total/run).**
**CONCLUSION on the benchmark hunt: the headroom that exists at the very hardest reasoning tasks is the WRONG
KIND for skill formation** (model slips ≠ missing procedure). The skill tier pays off where a TRANSFERABLE
PROCEDURE is genuinely missing (dyck's stack algorithm), not where a capable model occasionally errs.
**NEXT: return to BBH word_sorting/dyck for the skill-OFF attribution + ≥3 seeds** (the real C1 result).
Results: `results/zebra6x6_final/` (complete); `results/zebra6x6_skillform/` (partial, superseded).
Data: `eval/data/zebra_6x6.jsonl` (tracked).

### 2026-06-06  (session 13 — HoVer env built, but closed-book FLOORS haiku → not viable; the headroom pattern crystallizes)
Built **HoVer env** (`eval/envs/hover.py`, multi-hop claim verification, num_hops 2/3/4 families, binary
SUPPORTED/NOT_SUPPORTED EM, decomposition-procedure evidence; closed-book because `supporting_facts` lack
text and the wiki corpus is multi-GB; `test_hover_env.py` 19/19, balanced 300-claim val). **Headroom probe
(no_memory, haiku, n=60 stratified): EM=0.533 ≈ guessing floor** (hop2 0.60 / hop3 0.55 / hop4 **0.45 below
chance**; model BIASED to NOT_SUPPORTED 38/60, 8 no-verdict). **Closed-book HoVer FLOORS haiku** — it can't
verify multi-hop claims from parametric knowledge → guesses → no room for memory/skill. Env kept for a
future OPEN-BOOK version (needs the wiki corpus). **THE SESSION-13 HEADROOM PATTERN (3 benchmarks probed):**
haiku-4.5 has headroom ONLY on **tedious symbolic manipulation** (BBH word_sorting 0.52 / dyck 0.73);
**knowledge/reasoning benchmarks CEILING** (BBH MC 6/8 ≥0.85, MATH L1-3) or the model **can't do them →
FLOOR** (HoVer closed-book). ⇒ for a haiku target, reliable headroom = symbolic/algorithmic tasks; knowledge
QA is a dead end. Probe: `results/_hover_probe/`.
**[UPDATE — AIME-2025 probe (reused the `math` env, n=30): no_memory EM=0.767 (23/30).]** Even hard
competition math NEAR-CEILINGS haiku-4.5, and AIME is **not reuse-structured** (diverse problems, no shared
procedure) + tiny n → triple-strike, not viable.
**[UPDATE 2 — ZebraLogic probe (built `eval/envs/zebra.py`, logic-grid puzzles, WildEval filled solutions,
`test_zebra_env.py` 15/15). Tested the FULL difficulty gradient 2x2→6x6 (the dataset max; n=172). no_memory
puzzle-EM: everything ≤5x5 = **1.00** (verified genuine: one 5x5 → exact 25-cell grid via real constraint
reasoning); 6x4/6x5/5x6 = 0.92; **6x6 (max) = 0.67** (cell-F1 0.87 — failures are NEAR-MISSES, 1-2 cells off).
So haiku-4.5 nearly solves the whole benchmark that stumps GPT-4o; headroom exists ONLY at the absolute
hardest size. **ZebraLogic 6x6 IS a usable headroom family** (0.67, ideal single-procedure reuse, recoverable
near-miss failures, ~40 puzzles available) — the best-STRUCTURED headroom benchmark found, though thin n.]**
**FIVE-PROBE META-FINDING (CONCLUSIVE): haiku-4.5 is too capable for standard benchmarks to leave clean
headroom — knowledge QA, competition math (AIME 0.767), AND logic-grid puzzles (Zebra 1.000) all CEILING;
HoVer FLOORS. The ONLY reliable headroom + reuse-structure is tedious MECHANICAL-TEDIUM symbol manipulation
(word_sorting 0.52, dyck 0.73) — where a SMART model still slips on the TEDIUM, not the reasoning. Refined
scope: memory/skill helps where the model is CAPABLE-BUT-ERROR-PRONE (mechanical tedium), not where it is
already reliable. Benchmark-hunting for a haiku-4.5 target is EXHAUSTED.** Implication: either (a) CONSOLIDATE
on the mechanical-tedium symbolic regime (word_sorting/dyck + harder variants → finish skill-formation:
skill-OFF + seeds), or (b) make a deliberate TARGET-MODEL choice (a weaker target opens the benchmark space
but re-baselines everything). Probes (gitignored): `results/_{aime,hover,zebra}_probe/`. New tracked data/env:
`eval/data/{aime25,zebra_val}.jsonl`, `eval/envs/zebra.py`.

### 2026-06-06  (session 13 — BBH skill-formation: FIRST DURABLE gate activation + strong memory wins on procedure-families)
Built the **BBH env** (family-structured shared-procedure regime) to give the skill-promotion gate its
first FAIR test: a family where the procedure transfers to EVERY instance (→ no dilution → no gate
false-positive) and mid-range base gives val power (→ no false-negative). Frozen protocol
(acquire 32 / val 32 / test 96), 2 arms (no_memory / ours_full), 1 seed, haiku, **repair off, lexical
retrieval**, max-parallel (3 families × `run.py`, peak ~42 concurrent).

**Dataset reality check (validity-first: no_memory launched FIRST as the headroom probe).** BBH is MOSTLY
CEILING for haiku-4.5 — 6/8 probed families ≥0.85 (logical_deduction_five **1.000**, multistep_arithmetic
**0.990**, temporal_sequences 1.000, tracking_shuffled 1.000, date_understanding 0.938, geometric_shapes
0.854). Only symbol-manipulation families keep headroom. Killed the ceiling families BEFORE spending
ours_full on them (the headroom-first design paid off; logical_deduction + multistep dropped).

**Result — the 2 headroom families:**
| family | no_memory | ours_full | rescued/broke (n=96) | skill tier |
|---|---|---|---|---|
| **word_sorting** | 0.521 | **1.000** | **46 / 0** (net +46, MONOTONE) | gate REJECTED (val saturated 32/32) → memory-only |
| **dyck_languages** | 0.729 | **0.917** | 23 / 5 (net +18) | gate **ACTIVATED** `dyck-language-stack-algorithm` |

**Findings:**
1. **ours_full strongly beats no_memory on both procedure-families** (+0.479 *monotone* on word_sorting,
   46 rescued / 0 broken; +0.188 on dyck). The method clearly works in the shared-procedure regime.
2. **FIRST DURABLE GATE ACTIVATION in the project.** dyck promoted `dyck-language-stack-algorithm` — a
   QUALITATIVELY CORRECT skill (stack-based bracket tracking + the key *"output only the completion
   FRAGMENT, not the full string"* insight = exactly the failure mode), kept **active at freeze/test**
   (`PROMOTED_SKILL.md`). The induce→gate pipeline produced and durably retained a real skill — the
   long-standing "gate never fires" gap, finally closed on the right regime.
3. **The gate is well-calibrated.** ACTIVATE when headroom + skill robustly beats memory (dyck @15:
   base27→full29, rescued4 broke2, n32, sat=False); REJECT when memory saturates val (word_sorting,
   base 32/32 every checkpoint) OR a candidate doesn't robustly beat memory (dyck's 2nd candidate @31:
   cum full57<base58 → reject, kept as candidate). "Promote iff it beats memory on held-out val, else
   degrade gracefully."

**HONEST caveats:**
- **Skill ATTRIBUTION unresolved.** With only no_memory/ours_full (skill-OFF arm dropped per user call),
  we can't isolate the skill's marginal contribution to dyck's +0.188 from the memory's. word_sorting's
  +0.479 is PURE memory (skill rejected). The gate's val A/B showed the dyck skill +2 @15 but ~neutral @31
  → modest/uncertain marginal value. **NEXT: add the skill-OFF arm (`--induce_every 0`) to isolate "the
  skill caused X on held-out test"** — this is now the single highest-value follow-up for the C1 skill claim.
- **1 seed, 2 families** → signal not significance.
- **BBH-haiku ceiling**: only 2/8 families had headroom; BBH is too easy for haiku-4.5. Lesson for
  skill-formation headroom: need harder symbolic tasks (e.g. word_sorting/dyck longer, 7-object variants)
  or a weaker target model.
- **Spend $22.42** (over the ~$13 estimate: ours_full ran $6.3–7.5/family — acquire + gate A/B + test —
  and the ceiling families' no_memory probes + the 4-family MC probe added ~$6).

Files: `eval/envs/bbh.py`, `eval/test_bbh_env.py` (28/28), `eval/data/bbh/`. Results: `results/bbh_skillform/`
(+ `dyck_languages/PROMOTED_SKILL.md`). **NEXT:** the skill-OFF vs skill-ON(forced) arm to isolate the skill;
≥3 seeds; harder-headroom families (or weaker target) so the skill tier has more room than memory.

### 2026-06-06  (session 13 — IFBench ours-vs-baseline headline + retrieval switched to the NATIVE agentic-index paradigm)
Two threads: (1) the requested clean `ours_full` vs `no_memory` headline on a NEW non-math benchmark
(no component ablations); (2) per the user, replaced the lexical top-k memory retriever with Claude
Code's OWN native memory paradigm.

**1. IFBench headline (ours_full vs vanilla, prequential n=24 seed0, haiku, LEXICAL retrieval).**
| method | preqEM | F1 | 1stH | 2ndH | cost$ | bullets | skills |
|---|---|---|---|---|---|---|---|
| no_memory | 0.708 | 0.757 | 0.750 | 0.667 | 0.34 | 0 | 0 |
| **ours_full** | **0.792** | **0.840** | 0.750 | **0.833** | 2.57 | 10 | 0 |
→ **Memory +0.083 EM/F1** — rescued 3 (idx 15,16,18), broke 1 (idx 23) = **+2/24**. **Clean learning
fingerprint:** identical 1st-half (0.750), ours pulls ahead 2nd-half (**0.833 vs 0.667**, all 3 rescues
back-half). Lift is from **distilled+episodic, NOT the gated skill** (rolling gate REJECTED @15, broke 2
rescued 0 → active_skills=0 — the usual conservative-gate story). Cost **7.6×** (~5 calls/task: solve +
repair[5/24] + self_both critique + reflect). **CAVEAT:** 1 seed, n=24, SE≈0.083 ⇒ +0.083 ≈ 1 SE =
SIGNAL not significance. This is the clean vanilla(single-shot, no repair) vs full-apparatus contrast, so
NOT comparable to session-8's IFBench 2×2 (which gave no_memory a repair loop). Results + figs:
`results/ifbench_headline/`.

**2. Retrieval → native agentic-index paradigm (researched, built, offline-validated).** Researched (via
the claude-code-guide agent) how Claude Code's OWN memory retrieval works: it uses **NO embedding / vector
/ lexical scoring** — every built-in memory subsystem (CLAUDE.md hierarchy, MEMORY.md auto-memory, the
`memory_20250818` tool, managed-agents store) is uniformly **"load a plain-text INDEX, let the model
agentically decide what to read"**; only optional third-party MCP servers add embedding/BM25/graph
retrieval. Our engine's lexical bag-of-words top-k (`retrieve.select`, score = overlap + 0.1·helpful −
0.5·harmful) is therefore a **non-native paradigm bolted onto a native-memory project**.
- **BUILT** `retrieve.select_agentic` / `select_and_block_agentic`: present the active-memory index
  (`- [id] <one-liner>`); a single cheap `claude` call returns the relevant `[id]`s (MODEL selection, not
  a lexical score); inject those bodies. Single-shot compatible; **PRESERVES the `(block, injected_ids)`
  contract** so `curate.credit` + the promotion gate keep their deterministic signal; **fail-safe** to
  no-memory on any error (empty store / claude error / unparseable / no valid ids); **ledger-billed**.
- **WIRED** `--retrieval {lexical,agentic}`, **DEFAULT now `agentic`** (per user; pass `lexical` to
  reproduce pre-2026-06-06 runs). Routed BOTH `inject()` and the gate's `base_block` through one helper
  so the gate's A/B compares like-with-like.
- **OFFLINE-VALIDATED 14/14** (`eval/test_agentic_retrieval.py`, fake llm — priority order, cap-k,
  invalid/inactive/dup filtering, empty-selection, unparseable / non-list / empty-store(no wasted call) /
  llm-error fail-safes, prompt embeds task+index, excludes archived). **ZERO claude spend.**
- **Scope/notes:** applied to the eval harness `inject()`; the live hook adapter (`hook_user_prompt_submit`)
  + codex runner still use lexical `context_block` (deployment behavior unchanged) — follow-up. Our
  distilled bullets are already terse one-liners so index-entry == body; a deeper V2 (inject the linked
  episode as the on-demand "body") and a true `--agentic` Read-on-demand variant are noted but unbuilt.
Files: `engine/evolve/retrieve.py`, `eval/{prequential,run,test_agentic_retrieval}.py`; method diagram
`docs/architecture.md` (Mermaid + ASCII, accurate to the agentic-index method).

**A/B RESULT (billed, IFBench n=24 seed0 haiku — agentic vs lexical, IDENTICAL config, the only diff is
`--retrieval`):**
| ours_full retrieval | preqEM | F1 | 1stH | 2ndH | cost$ | calls |
|---|---|---|---|---|---|---|
| LEXICAL top-k | 0.792 | 0.840 | 0.750 | 0.833 | 2.57 | 119 |
| **AGENTIC-INDEX (native)** | **0.833** | 0.833 | **0.833** | 0.833 | 3.10 | 164 |

(shared `no_memory` 0.708.) Agentic **+0.042 EM** over lexical (net +1 task: rescued idx 9 & 23, broke idx
17), **flat on F1** (0.833 vs 0.840), and a higher **1st-half** (0.833 vs 0.750 — better selection even with
few bullets). Cost **+21%** (+45 selection calls). vs vanilla **+0.125**. **CAVEAT:** 1 seed, n=24, SE≈0.08
⇒ +0.042 ≈ 0.5 SE = WITHIN NOISE — directionally positive on EM, a wash on F1; the native paradigm DID NOT
HURT and is the more on-thesis design, but this n/seed cannot call it a win. Results: `results/ifbench_agentic/`.
**NEXT:** ≥3 seeds on this A/B; carry to **SB** (lexical is weakest on diverse, low-overlap codegen tasks →
highest expected gain — the real test of agentic-index); optionally switch the live hook adapter to agentic.

### 2026-06-06  (session 12 — agentic skill billed verdict + micro-batch parallelism + MATH env + the "is batching native?" analysis)
Three threads: closed the agentic-skill side-experiment, built the parallelism+memory tradeoff knob, and
started the cross-benchmark generalization expansion.

**1. Agentic self-verify skill — billed verdict: small, NOT significant on haiku; wording is not the lever.**
SB agentic no_memory, idx-aligned: noskill 0.500 / skill-v1 0.562 / skill-v2 (sharpened wording) 0.562.
v1 vs noskill = rescued 3/broke 1 (net +2/32, McNemar p=0.625). v2 == v1 EM, v2-vs-v1 = 2 flips each way
(pure noise) and slightly pricier. The n=12 smoke's +0.167 was a small-sample fluctuation; at n=32 it's
+0.062 within noise. Probe diagnosis (confirmed): haiku writes formula-string poison even WITH the skill
and **does not execute the mandatory verify step** — the bottleneck is the model's agentic discipline, not
the skill text. **Decision (user): the self-verify skill is an APPARATUS capability-booster, decoupled from
the paper's gate main line; it would need a model that actually follows it (sonnet) to pay off.** Runs
(gitignored): `results/_ag_sb32_{noskill,skill,skill_v2}/`.

**2. Micro-batch parallelism — the speed↔memory-fidelity tradeoff knob (`--batch_size B`).** `batched_learn`
in `prequential.py`: solve B tasks CONCURRENTLY against one committed memory snapshot, then learn (record/
credit/reflect, writes serialized) before the next batch → **memory staleness ≤ B** (vs whole-stream under
full serving). B=1 == strict sequential (max fidelity); B=N == full parallel (no online memory). Threaded
through `run.py`. Validated end-to-end (MATH ours_full n=8 B=4: ran clean, $0.17).
**Is batching "native"? — analysis (user asked):** YES at the mechanism level — reflect→curate→promote in
the loop, deterministic curation, no external trainer, all unchanged; batching only changes scheduling/
concurrency, and bounded-staleness concurrent serving is what a REAL native deployment does. It only relaxes
strict online causality WITHIN a batch (B→N drifts toward offline). **Resolution for generalization testing:
separate "parallelize evaluation" (always native-safe: held-out deploy is READ-ONLY, no learning to
compromise) from "parallelize learning" (the batching tradeoff). Use FROZEN protocol — native sequential
(B=1) learning on a small few-shot acquisition set → freeze → fully-parallel read-only deploy on held-out.**
Parallelism lands on the no-learning phase → native claim untouched. Batching stays the serving/scalability
story, reported with its staleness; the native online-curve headline stays B=1.

**3. MATH env (`eval/envs/math.py`) — built + offline-validated; new SHARED-PROCEDURE regime.** Data already
staged (`eval/data/math/`, 960 tasks, topics algebra/number_theory/counting/prealgebra). Boxed-answer
extractor + Hendrycks-style normalizer (frac/decimal/commas/$/degrees), exact-answer score, FORMAT-only
ref-free verify (memory-carried regime, repair idle — the MATH↔SB mirror), gold-grounded evidence for
method-level reflection. `eval/test_math_env.py` 4/4 pass. **CAVEAT: only levels 1–3 are staged and they
CEILING haiku (n=8 → 8/8, memory didn't grow — all-pass → nothing to reflect).** Need harder difficulty
(re-extract levels 4–5 from the HF parquets) for real headroom, else MATH is a ceiling regime for haiku.

**Benchmark expansion plan (from the user's 13-list):** ADOPT HoVer (claim-verification, hop-families,
hotpot-shaped, low effort) + MATH (built, needs harder levels). REJECT for now: OfficeQA/DocVQA (vision),
PUPA (LLM-judge+API), ARC-AGI (anti-reuse+floors), WebShop/ScienceWorld/AppWorld/ALFWorld (stateful
multi-turn env simulators = separate weeks-each initiative). **NEXT:** re-extract harder MATH (or
deprioritize for haiku); build HoVer env; run the few-shot single-seed generalization sweep under
frozen+parallel-deploy (B=1 native acquisition) across the 6 envs (SB/searchqa/HotpotQA/IFBench/HoVer/MATH).

### 2026-06-05  (session 11 — #5 AGENTIC harness + the native verify-repair SKILL [code built, offline-validated, billed run pending])
Acted on the design discussion: the single-shot harness STRUCTURALLY suppresses the skill tier — a
*procedural* skill (run→observe→fix) is dead text when the agent has `allowedTools=Read`, no `cwd`, no
execution surface (the session-7 Flaw 1). Built the agentic upgrade so a procedural skill can finally
pay off, and hand-authored the expert verify-repair skill as a NATIVE (discoverable) Claude Code skill.
Full design: **`docs/agentic_harness_design.md`**.

**The three roles of "verify" (the load-bearing split).** Going agentic, `env.verify` splits into:
(A) inference-time self-correction → moves INSIDE the agent, as a SKILL; (B) grader/scorer → stays
EXTERNAL + gold-isolated (`env.score` unchanged); (C) promotion-gate validation → stays EXTERNAL (the
paper's thesis). Only A internalizes. Internalizing B = teaching to the test; internalizing C = throwing
away the contribution. Bonus: A via the agent's native `Bash` is genuinely dataset-agnostic, dissolving
the session-8 "`verify` embeds dataset knowledge" critique — `self_verify` was scaffolding for a bodyless agent.

**Built (all offline-validated, ZERO claude spend):**
- **`engine/skills/self-verify-and-repair/SKILL.md`** — the hand-authored expert procedural skill
  (role A), **GENERAL / dataset-agnostic** (per user direction — a native capability, not an SB hack):
  derive a reference-free check from the task → pick the channel (EXECUTE runnable code / check explicit
  CONSTRAINTS / check GROUNDING+form) → run → repair to the specific failure → cover the form-clean-but-
  value-wrong blind spot. openpyxl formula-string poison is ONE worked example among code/instruction-
  following/QA. The verify methodology lives ONLY in the skill (env prompt = task-spec + tools), so the
  no-skill arm truly lacks it → clean ablation.
- **`engine/evolve/llm.py`** — `call_claude` gained `permission_mode` / `max_turns` / `max_retries`
  (single-shot path unchanged). Handles the two gotchas the guide surfaced: `--max-turns` EXITS NON-ZERO
  on overflow (→ agentic uses `max_retries=1`, won't burn K sessions), and `acceptEdits` blocks `python`
  in headless (→ agentic uses `bypassPermissions`).
- **`eval/envs/spreadsheetbench.py`** — `agentic_attempt()`: per-task `/tmp` sandbox, copies ONLY the
  first case's `*_init.xlsx` in (never `*_golden*`), installs named native skills into
  `sandbox/.claude/skills/`, prompts write+run+verify `solution.py`, extracts final code (prefers
  `solution.py`, else fenced block) for the UNCHANGED `score()` to grade on ALL cases.
- **`eval/{prequential,run}.py`** — `--agentic` / `--agentic_max_turns 20` / `--native_skills <names>`;
  in `solve()` the agent self-solves and the harness `monotone_repair` loop is BYPASSED (clean attribution).
  Cost is one honest `total_cost_usd` per task (aggregates the whole multi-turn session; also fixes the old
  `self_verify` critique cost leak).
- **`eval/test_agentic.py`** — offline validation with a fake `call_claude`: GOLD ISOLATION (no `*golden*`
  in the sandbox), skill install, `solution.py`-over-fenced extraction precedence, cost passthrough, prompt
  skill-line/INPUT_PATH contract, graceful-empty→miss. **3/3 pass.** Flags + symlink discovery confirmed.

**Experiment arms (clean attribution; tool-use is the ENV, available to all arms — the skill is the treatment):**
| arm | `--agentic` | `--native_skills` | tests |
|---|---|---|---|
| agentic baseline | on | "" | does bare multi-turn tool-use alone move SB? |
| + native skill (oracle ceiling) | on | self-verify-and-repair | does the hand-authored verify-repair skill give the SkillOpt-style jump? |
| (later) learned skill | on | "" + ours_full | can memory→gate LEARN a skill approaching the native ceiling? (C1) |

**Validity caveat (documented, mitigation ready):** soft gold-isolation (sandbox holds only the input;
graded by running CODE on all cases) — `bypassPermissions`+Bash could technically `find` golden on this
box; for the billed headline enable the bubblewrap OS sandbox (`--settings` `denyRead` the dataset dir),
noted in the design doc.

**FIRST BILLED AGENTIC RESULT (smoke, `no_memory` SB n=12 seed0, stratified, agentic max_turns=20, haiku):**
| arm | EM | per-idx | rescued/broke | $/task |
|---|---|---|---|---|
| noskill (bare agentic) | 0.417 | 000011011100 | — | $0.087 |
| **+ self-verify-and-repair** | **0.583** | 000111011101 | **2 / 0** | $0.078 |
→ **The native procedural skill helped MONOTONICALLY (+0.167 = 2/12; rescued 2, broke 0) AND was CHEAPER**
(skill arm converges in fewer turns). End-to-end probe confirmed the harness is sound: real multi-turn tool
use, skill discovered+installed, agent wrote+ran `solution.py`, gold isolation held. **Two readings, both
useful:** (a) bare agentic 0.417 ≈ the old single-shot baseline (~0.47 @n=32) ⇒ multi-turn tool-use ALONE
barely moves SB; the SKILL is the treatment that adds the lift — the cleanest "procedural skill needs a body
AND the right content" story. (b) Even the skill arm isn't perfect (the probe still wrote formula-string
poison on one task) — haiku follows the verify step imperfectly, so the lift is real but capped by the model.
**CAVEATS:** 1 seed, n=12, SE≈0.144 ⇒ +0.167 ≈ 1.2 SE = SIGNAL, not significance. Runs (gitignored):
`results/_ag_sb_{noskill,skill}/`. **NEXT:** ≥3 seeds + larger n on this 2-arm A/B to firm up; add the
single-shot no_memory row as the floor; then the `ours_full` agentic arm (learned+gated skill vs the
native-skill ceiling, the C1 / calibrated-promotion story); optional: bubblewrap hard isolation for the headline.

### 2026-06-05  (session 10 — `self_both`+N3 made the default; SB 2×2 rerun → SUBSTITUTE flips to COMPLEMENT)
Acted on the session-9 NEXT ("run the N3 probe; re-run the SB lever-map cell under the FIXED loop"). Made
the deployment-realistic combo the **default verification** and reran the full SB make-or-break 2×2 under it.

**Config change (3 default flips, `eval/run.py` + `eval/prequential.py`): `--verify_mode` default `self` →
`self_both`** = run BOTH dataset-agnostic channels (EXECUTION + LLM semantic self-critique) every verify, with
the session-9 guardrail intact (a clean execution stays AUTHORITATIVE, so on code the critique is ADVISORY —
enriches the failure feedback, never flips ok→fail → can't drag below baseline). N3 gold-grounded semantic
reflection is unconditional in the SB env (train-only, firewalled from the gold-free verify), so it rides
along for free on any ours_full SB run. Old modes kept (`oracle`/`self`/`self_exec`, pass explicitly).

**SB 2×2 (memory × repair), prequential n=32 seed0, stratify=instruction_type, induce_every=16, `self_both`+N3:**
| preqEM | repair=0 | repair=1 |
|---|---|---|
| no_memory | 0.531 (A) | 0.625 (B) |
| ours_full | 0.625 (C) | **0.750 (D)** |

Marginals: memory @r0 (C−A)=**+0.094**, memory @r1 (D−B)=**+0.125**; repair @no_mem (B−A)=**+0.094** (11/32
fire), repair @ours_full (D−C)=**+0.125** (only **1/32** fire). **Interaction (D−C)−(B−A)=+0.031>0; D=0.750 is
the BEST cell, > repair-alone (0.625) AND > memory-alone (0.625), slightly super-additive (0.531+0.094+0.094=
0.719<0.750) ⇒ COMPLEMENT.** Rolling gate **ACTIVATED 6 skills @31** (rescued=4 broke=2) — the FIRST positive
SB activation in the project (too late in the stream to move this run's EM, but the gate finally fired right).

**THE FLIP vs session-8 (oracle, no N3) — same SB cell:**
| | session-8 (oracle, no-N3) | session-10 (`self_both`+N3) |
|---|---|---|
| memory @ repair-on (D−B) | **−0.093 (HARMFUL)** | **+0.125 (HELPFUL)** |
| best cell vs repair-alone | D 0.719 **<** B 0.812 | D 0.750 **>** B 0.625 |
| verdict | SUBSTITUTE | **COMPLEMENT** |

The substantive change: **memory stopped fighting repair** — exactly the session-9 N3 hypothesis (semantic
memory covers verify's blind spot → SB joins IFBench's complement regime).

**CAVEATS (don't over-read).** (1) 1 seed, n=32, SE≈0.09 (~3 tasks): every delta (+0.09…+0.13) is ~1 SE and
the +0.031 interaction is ~1 task → SIGNAL, not significance. (2) **Confounded:** vs session-8 BOTH verify
changed (oracle→self_both — repair is much WEAKER now, no_mem repair +0.094 vs +0.343) AND N3 was added; the
flip may be partly "weaker repair leaves headroom for memory," not solely N3 semantic memory. Clean attribution
needs a **(self_both, no-N3) control** (N3 is unconditional today → add `--no_semantic_reflect`). (3) repair
fired 1/32 in cell D → D is essentially memory-carried; "complement" = memory no longer conflicts, not two big
independent stacking gains. **Spend: $11.31 / 1 seed.** Runs (gitignored): `results/_n3both_sb_r{0,1}/`.
**NEXT:** (a) ≥3 seeds on this 2×2; (b) the (self_both, no-N3) attribution control (~$5); (c) carry the
`self_both`+N3 default into the other regimes' `ours_full` cells for the deployment-realistic lever map.

### 2026-06-05  (session 9 — critique-safety: the 0.375 was a LOOP BUG; monotone repair + exec-authoritative + N3 semantic-diff + routing-by-code-block)
User scrutinized the precision-law result (SB exec+critique 0.375 < baseline 0.469): "a critique signal should at worst be IGNORED, never drag BELOW baseline." Correct — the drop was a **non-monotone repair-loop BUG**, not merely a noisy signal. All fixes unit-validated offline (zero spend), then confirmed with a billed n=32 A/B.

**Diagnosis.** The old `solve()` repair loop (a) blindly REPLACED the attempt with each repair without checking it improved anything, and (b) with `repair_turns=1` the final repair was SCORED WITHOUT EVER BEING VERIFIED. So an over-firing critique that spuriously rejected a CORRECT first attempt discarded it and scored a worse rewrite → below baseline. A purely additive optional-repair signal must asymptote to baseline, never below it.

**Fix B — `monotone_repair` (general, `prequential.py`).** Verify-gated + MONOTONE: a repair replaces the single-shot attempt ONLY if it RE-VERIFIES as ok; else the baseline is kept (at most we iterate from the failing candidate for context). Extracted to a module-level, directly unit-tested function (8 cases incl. the exact regression). Closes both bugs.

**Fix A — execution-authoritative critique (`self_verify.py`).** A clean execution VERDICT vetoes the critique: on code, critique is ADVISORY (never flips ok→fail; only ENRICHES the repair feedback when execution already failed). Forcing critique on can no longer trigger a spurious repair on correct code.

**Validation (billed, haiku, SB no_memory n=32 seed0, repair_turns 1):**
| condition | EM |
|---|---|
| baseline (no repair) | 0.469 |
| OLD exec+critique (`_p3_sb_self`) | 0.375  ← the bug (below baseline) |
| **NEW exec+critique (`self_both`, FIXED)** | **0.719  (+0.344 recovery; now ≥ baseline ≈ exec-only)** |
| exec-only (`self_exec`, monotone refactor) | 0.688  (≈ OLD 0.750; 0.7 SE = haiku noise, no regression) |
→ **The fix works: critique can no longer drag below baseline** (0.375→0.719, ~11 tasks ≫ noise). The precision-law "backfire" was AMPLIFIED by the non-monotone loop; with a monotone+authoritative loop a noisy signal DEGRADES GRACEFULLY to the precise channel's level instead of backfiring. The precision law still holds in spirit (critique adds NO value beyond exec on code) — it just no longer HURTS. `self_both` cost ≈ 2× exec-only (84 vs 42 calls). New `--verify_mode self_both` (force exec+critique).

**Also this session:**
- **Routing by code-block, not env (`self_verify.py`).** `_has_code_block(attempt)` picks the channel (code→exec, else critique) — a property of the ATTEMPT, never the dataset. `--verify_mode` default flipped **oracle → self** (deployment-realistic; oracle must now be passed explicitly to reproduce the session-8 oracle map). Unit-validated (6 routing cases).
- **N3 semantic-diff code (`spreadsheetbench.py` + `reflector.md`), ready as the $3–4 probe.** Gold-grounded `_gold_vs_pred` value diff (train-only; rides on `score()`'s gold, NEVER reachable from the gold-free `verify()`/`try_run()` — statically asserted); a SEMANTIC reflection branch in `_diagnose` gated on "form-clean AND value-mismatch"; a parallel "fix the LOGIC not the form" principle in `reflector.md`. Tests if SB flips SUBSTITUTE→COMPLEMENT. Unit-validated; NOT yet run online.

Files: `eval/{self_verify,prequential,run}.py`, `eval/envs/spreadsheetbench.py`, `engine/prompts/reflector.md`. Results (gitignored): `results/_fix_sb_self{both,exec}/`. **NEXT:** run the N3 probe; re-run the routed-self lever-map `ours_full` cells under the FIXED loop; ≥3 seeds; N5 cost-leak fix (still open).

### 2026-06-05  (session 8 — oracle-vs-self verify A/B → the precision law + channel-routing fix)
A/B'd the dataset-blind `self_verify` against the oracle on the cleanest repair cell (no_memory,
repair_turns 1, same splits/seed as today's oracle runs). Comparison added ~$5.8 (Phase-3 total
**$28.64 / 1124 calls**):

| no_memory r1 | baseline | oracle | self (exec+crit) | self_exec (exec only) | **self (routed)** |
|---|---|---|---|---|---|
| **SB** (32) | 0.469 | 0.812 | **0.375** | **0.750** | **0.750** |
| **IFBench** (24) | 0.667 | 0.792 | **0.792** | — | **0.792** |

**Findings:**
1. **IFBench: self-critique == oracle (0.792).** IFEval's constraints are STATED IN THE PROMPT, so "did I
   follow my own instructions" is precisely LLM-self-checkable WITHOUT dataset knowledge → repair win REAL.
2. **SB: execution-only (dataset-blind) recovers +0.28 of the +0.34 oracle win** (0.750 vs 0.812; the
   ~0.06 gap = oracle's answer_position). A coding agent running its own code gets it → repair win REAL.
3. **BUT naive self (exec+critique) CRASHED to 0.375 — below baseline.** The LLM self-critique of CODE
   correctness is NOISY: it over-fires (29/32 vs 13), nitpicks correct code, and the spurious "fixes"
   break it. Same `solve()` loop — ONLY the signal changed — so a noisy signal turns +0.34 into −0.09.

**THE PRECISION LAW (answers the validity critique):** a dataset-blind verify recovers the repair win
WHEN ITS SIGNAL IS PRECISE — execution for code; explicit in-prompt constraints for instruction-following —
and BACKFIRES when noisy (LLM vibes-critique of code correctness). **FIX:** `self_verify` now AUTO-ROUTES
(`use_critique=None` default): execution verdict present → execution only; no execution → self-critique.
It keys on "is there code to run?", NOT the dataset, so it stays deployment-realistic. Routed self =
0.750 (SB) / 0.792 (IFBench), both validated by the channel-isolation runs. Cost: self ≈ 2× oracle (the
extra critique call); the per-row `cum_cost` undercounts self's critique calls (ledger authoritative) — a
known accounting gap. `--verify_mode {oracle, self, self_exec}`.
**CONCLUSION:** the lever map SURVIVES a dataset-blind verifier — repair's value is REAL, not an oracle
artifact — PROVIDED the verify channel matches the failure type (execution↔code, constraint-critique↔
instruction-following). The naive "LLM-judge everything" verify is the wrong design; channel-routing is right.

### 2026-06-05  (session 8 — deployment-realistic self_verify: removing dataset knowledge from verify)
Addressed a VALIDITY critique (user): the per-env `verify()` functions embed dataset knowledge a real
deployment lacks — IFBench's pre-parsed rubric, SB's answer_position, QA format heuristics, and the
env-name DISPATCH itself (deployment doesn't know which dataset a task is from). Implemented a
dataset-agnostic `eval/self_verify.py` (NO env dispatch, NO gold, NO answer key):
- **Channel 1 — generic execution** (`env.try_run`, optional): run the candidate on its INPUT only
  (never golden/answer_position), report crashes + formula-strings the code WROTE (found by input↔output
  diff — general openpyxl reasoning). SB implements it; QA envs don't (no code to run).
- **Channel 2 — LLM self-critique**: ONE claude call — the agent lists the explicit, objectively-checkable
  requirements it violated in its OWN prompt+attempt. Fully general, reference-free, IMPERFECT (the
  realistic degradation), and NOT free (1 call/check — the honest cost of a general verify).
`--verify_mode {oracle,self}` selects it (oracle = per-env ceiling, default/back-compat; self =
deployment-realistic). Wired through `solve()` + `run.py`; unit-validated (channel logic; SB try_run
never opens golden; QA→critique-only). **Triage:** the strongest result — SB repair via EXECUTION — is
ALREADY deployment-realistic (a coding agent runs its own code); the oracle borrowing was mainly IFBench
(rubric) + QA heuristics. **NEXT (needs budget): A/B oracle vs self on IFBench (most-affected) + SB** to
measure the oracle artifact — does the lever map survive a dataset-blind verifier? New: `eval/self_verify.py`,
SB `try_run`, `--verify_mode`.

### 2026-06-05  (session 8 — Phase 3 IFBench: 4th regime reveals a SECOND axis → the two-axis lever map)
Built a new **IFBench/IFEval env** (`eval/envs/ifbench.py`): reference-free constraint verifiers,
stdlib-only reimplementation of 23 IFEval instruction types (skipped `language:response_language`
[needs langdetect] + `nth_paragraph_first_word`; fetch FILTERS to fully-covered prompts). The defining
property: **IFEval has no gold — the rubric IS the verifier set — so `verify()` == `score()`'s checks**
(the most COMPLETE verify possible). Unit-validated (23 verifier pass/fail pairs + score/verify/evidence).
Data: `eval/data/ifbench_val.jsonl` (60 prompts, 48% multi-constraint). 2×2 prequential n=24 seed0.

| IFBench preqEM (n=24 seed0) | repair=0 | repair=1 |
|---|---|---|
| no_memory | 0.667 | 0.792 |
| ours_full | 0.708 | **0.875** |

repair +0.125 (no_memory) / **+0.167 (ours_full)**, 10/24 fires (most of any env — verify=rubric makes
every miss visible); memory +0.042 (r0). **The combined cell 0.875 is the BEST and SUPER-ADDITIVE**
(0.667+0.042+0.125=0.834 < 0.875; ours_full(r1) F1=0.944 of constraints) ⇒ **memory & repair COMPLEMENT.**
Contrast SB, where combined (0.719) < repair-alone (0.812) ⇒ **SUBSTITUTE.** The discriminator: repair
helps ours_full MORE than no_memory on IFBench (+0.167 > +0.125) but FAR LESS on SB (+0.03 << +0.34).
[Repair-yield nuance: IFBench fires repair most but a SINGLE turn only nets +0.125 because multi-constraint
prompts interact (fixing one constraint breaks another) — strict all-pass is iterative; repair_turns 2–3
would climb.] Gate REJECTED again (broke 2 > rescued 1).

**THE TWO-AXIS LEVER MAP (four regimes, 1 seed each, preqEM):**
| regime | env (n) | repair Δ (fires) | memory Δ (r0) | memory×repair | verify character |
|---|---|---|---|---|---|
| diverse codegen | SB (32) | **+0.34** (13/32) | +0.22 | **SUBSTITUTE** (combined<repair) | partial (form) → big BLIND SPOT |
| ref-free verifiable | IFBench (24) | +0.13/+0.17 (10/24) | +0.04 | **COMPLEMENT** (combined best) | **COMPLETE** (verify==rubric) |
| shared-proc QA | searchqa (24) | ~0 (1–2/24) | **+0.17** | — (repair idle) | weak (format only) |
| family multi-hop | HotpotQA (24) | 0 (0–1/24) | +0.04 | — (repair idle) | weak; bridge diverse |

**Two orthogonal axes, both governed by `verify`:**
- **Axis 1 — does repair fire/help?** ∝ verify-VISIBILITY of failures. Crashes/constraint-violations are
  visible (SB, IFBench) → repair active; QA semantic errors are invisible (searchqa, hotpot) → repair idle.
- **Axis 2 — do memory & repair STACK or FIGHT?** ∝ verify-COMPLETENESS (blind-spot size). Complete verify
  (IFBench) → memory's un-prevented failures stay catchable by repair → COMPLEMENT. Incomplete verify with a
  large blind spot (SB, form-only) → memory pushes failures into the blind spot where repair can't reach →
  SUBSTITUTE. **General answer to "why do verify & memory conflict": they conflict IFF verify is INCOMPLETE —
  the conflict IS the blind spot.** Design implication: make verify more complete (add semantic checks on SB)
  to convert the SB substitution into IFBench-style complementarity (this is the same "memory should target
  the semantic layer" fix, reframed as verify-completeness).

**Caveats:** 1 seed each. ROBUST: lever identity, fire counts, the qualitative substitute(SB)/complement
(IFBench) contrast. SOFT: exact magnitudes, super-additivity. **Phase-3 total $22.81 / 929 calls.** New files:
`eval/envs/ifbench.py`, `eval/data/ifbench_val.jsonl`. Results: `results/_p3_if_r0/`, `results/_p3_if_r1/`.
**NEXT:** the verify-completeness fix on SB (semantic-layer reflection/checks → test if SB flips to complement);
≥3 seeds; frozen-reuse + accuracy-vs-cost-vs-external.

### 2026-06-05  (session 8 — Phase 3 CAPSTONE: HotpotQA 2×2 + the three-regime LEVER MAP)
Third regime (HotpotQA, families), same memory×repair 2×2, prequential n=24 seed0, stratified by type.
r0 and r1 came out IDENTICAL per method (repair fired 0–1/24 and changed nothing → repair fully idle).
Phase-3 cumulative **$19.30 / 719 calls**.

| HotpotQA (n=24 seed0) | flat | bridge (n=20) | comparison (n=4) |
|---|---|---|---|
| no_memory (r0=r1) | 0.708 | 0.650 | 1.000 |
| ours_full (r0=r1) | 0.750 | 0.700 | 1.000 |

Memory +0.042 flat (+0.05 bridge) — direction consistent with searchqa but **within noise (1 task)**; repair
**exactly 0**. Per-type explains the weakness: **comparison** (the crisp shared-procedure family where memory
should shine) is at **CEILING (1.000)** → no headroom; **bridge** (the headroom family, 0.65) is **diverse**
(different entity each hop) → no shared procedure + semantic failures verify can't see. Gate REJECTED again
(rescued=0=broke) — no skill activation; the skill-formation test couldn't fire because its shared-procedure
family has no headroom. So HotpotQA-bridge = the regime where NEITHER lever has strong purchase.

**THE THREE-REGIME LEVER MAP (Phase-3 deliverable; 1 seed each, preqEM):**
| regime | env | repair (fire rate) | memory (r0) | carried by | precondition met |
|---|---|---|---|---|---|
| diverse codegen | SB n=32 | **+0.34** (13/32) | +0.22 | **REPAIR** | failures verify-VISIBLE (crash/poison) |
| shared-proc QA | searchqa n=24 | ~0 (1–2/24) | **+0.17** | **MEMORY** | shared procedure + HEADROOM |
| family multi-hop | HotpotQA n=24 | 0 (0–1/24) | +0.04 | weak/NEITHER | comparison=ceiling, bridge=diverse |

**Refined principle (the answer to "works across benchmark natures"):** the apparatus carries TWO levers and
each regime auto-draws the one whose precondition holds — **repair** fires iff failures are *verify-visible*
(executable-form: codegen yes, QA no); **memory** helps iff a *shared procedure AND headroom* coexist
(searchqa yes; SB yes via trace-grounded reflection but dominated by repair; HotpotQA neither family qualifies).
They SUBSTITUTE only where verify's blind spot is large (SB). Generality = carrying both, not one mechanism
winning everywhere. **NEXT:** ≥3 seeds to firm magnitudes; the "make memory target the SEMANTIC layer so it
covers repair's blind spot and they STACK" fix on SB; a headroom-bearing shared-procedure family (IFBench, or
non-ceiling comparison) to give the skill-formation gate a fair test; frozen-reuse + accuracy-vs-cost-vs-external.
Results: `results/_p3_hp_r0/`, `results/_p3_hp_r1/`.

### 2026-06-04  (session 8 — Phase 3 CROSS-REGIME: searchqa 2×2 mirrors SB → the lever-identity result)
Ran the SAME 2×2 (memory × repair) on **searchqa (shared-procedure regime)**, prequential n=24 seed0,
verify_n=12, to test whether the memory↔repair interaction is regime-dependent. It is — searchqa is the
MIRROR of SB. searchqa spend ~$3 (Phase-3 cumulative **$16.14 / 524 calls**).

| searchqa preqEM (n=24 seed0) | repair=0 | repair=1 |
|---|---|---|
| no_memory | 0.750 | 0.875 |
| ours_full | **0.917** | 0.833 |

Repair fired **1–2/24** (vs SB 13/32). **Memory effect (r0) = +0.167** (0.917 vs 0.750). ours_full
**2nd-half EM = 1.000 in BOTH r0 and r1** (learns the shared format procedure, nails the back half) —
the cleanest learning fingerprint. Gate REJECTED the format skill (val near-saturated, base 9–10/12,
rescued≈broke) ⇒ ours_full's lift comes from the **distilled tier** (the "minimal answer span" bullet),
NOT the gated skill — session-7's gate false-negative persists, now surfaced as *inconclusive* not silent.
**HONEST caveat:** repair fires ~once on searchqa ⇒ the whole repair COLUMN is within haiku noise (±2
tasks); ours_full(r1) 0.833 < no_memory(r1) 0.875 is a 1-task noise gap, NOT SB-style interference (no
repair fires → nothing to interfere). Robust signal = the r0 column + the fire counts + the 2nd-half=1.0.

**CROSS-REGIME SYNTHESIS — the answer to "works across benchmark natures":**
| | SB (diverse) | searchqa (shared-proc) |
|---|---|---|
| repair effect | **+0.34** (13/32 fire) | ~0 (1–2/24 fire) |
| memory effect (r0) | +0.22 | +0.167 |
| **carried by** | **REPAIR** | **MEMORY** |

**One apparatus, two mechanisms; WHICH one matters is set by whether failures are verify-VISIBLE.**
Malformed/crashing/poison code (SB) → verify fires → repair fixes (gold-free). Semantically-wrong-but-
well-formed output with a shared latent procedure (searchqa) → verify is blind → repair idle → the
distilled memory internalizes the procedure. The memory↔repair **substitution conflict appears only where
verify's blind spot is large (SB)**; in searchqa the blind spot is the whole task, so memory owns it
uncontested (helps in both columns, no interference). This is the cross-benchmark thesis: the method is
general because it carries BOTH levers, and each regime auto-draws on the one its failure-structure needs.
**ROBUST @1 seed:** lever identity (repair→SB, memory→searchqa) + fire counts + 2nd-half learning.
**NEEDS SEEDS:** exact magnitudes, SB interference (−0.09 ~1 SE), searchqa repair-column ordering (noise).
Results: `results/_p3_sq_r0/`, `results/_p3_sq_r1/`.

### 2026-06-04  (session 8 — Phase 3 FIRST ONLINE RESULTS: SB repair×memory 2×2 make-or-break)
First billed validation of the session-8 apparatus on real haiku. Smoke (searchqa n=4) + SB micro-check
confirmed end-to-end wiring, then the SB make-or-break: a clean **2×2 (memory × repair)** ablation,
SpreadsheetBench prequential, n=32, seed 0, stratified by instruction_type, full apparatus (rolling gate
on). Two parallel run.py calls (repair_turns 1 / 0). **Total Phase-3 spend $13.12 / 327 claude calls.**

| preqEM (SB n=32 seed0) | repair=0 | repair=1 |
|---|---|---|
| no_memory | 0.469 | **0.812** |
| ours_full | 0.688 | 0.719 |

Marginal effects: **repair** = +0.343 on no_memory (0.469→0.812), +0.031 on ours_full; **memory** = +0.219
at repair=0 (0.469→0.688), −0.093 at repair=1. Repair fired 13/32 (no_memory) vs 4/32 (ours_full). Gate
REJECTED skills at both checkpoints in both runs (rescued≈broke → no false-positive; lift is from
episodic+distilled, not the skill tier). bullets≈30–33.

**Three findings:**
1. **Trace-grounded reflection FIXED the memory tier on SB — session-7's question answered YES.**
   ours_full(r0) 0.688 ≫ no_memory(r0) 0.469 (+0.22). Session-7 ours_full was 0.446 ≤ 0.454 (net-harmful)
   with the trace-BLIND reflector that learned the inverse skill. With evidence-grounded reflection,
   consolidation now HELPS on diverse SB ⇒ the inverse-skill poison was the culprit, NOT SB's diversity
   (the Phase-0 hypothesis, confirmed on real haiku). [Protocol caveat: this is PREQUENTIAL/online, not
   session-7's FROZEN reuse — two changes (protocol + reflection), so the within-run r0 column is the
   clean comparison; the cross-session number is directional.]
2. **Reference-free repair is the single biggest lever: +0.34 (0.469→0.812), gold-free, conditional.**
   no_memory(r0)=0.469 reproduces session-7's 0.454 ⇒ the jump is purely repair, not a harness change.
   Captures most of SkillOpt's execute-repair upside cheaply (only 13/32 fires).
3. **Memory and repair are SUBSTITUTES, not complements (sub-additive).** Best cell = no_memory+repair
   (0.812); memory+repair (0.719) is BELOW repair-alone. Both target the same failure class (malformed /
   crashing / formula-poison code) — memory prevents some up front, repair fixes some after — so they
   overlap; memory's residue (verify-passing-but-semantically-WRONG code) caps it and suppresses repair
   (4 vs 13 fires). ⇒ on genuinely-diverse SB the general lever is REPAIR; the memory tier helps alone
   but is dominated once repair is on.

**Caveats:** n=32, 1 seed, SE≈0.09. Repair (+0.34, ~11 tasks) far beyond noise — SOLID. Memory-at-r0
(+0.22, ~7 tasks) likely real (>2 SE). The interference (−0.09, ~3 tasks) ~1 SE — SUGGESTIVE, needs seeds.
**NEXT (needs budget):** ≥3 seeds on the SB 2×2 to firm up the interference; then the same 2×2 on searchqa
(shared-proc — expect memory & repair to stack differently) + HotpotQA (families); then frozen-reuse
headline. Smoke validations: searchqa n=4 reflection produced the RIGHT grounded heuristic ("emit minimal
answer span, match granularity" — not the inverse poison); SB repair fires correctly (fixes crash/poison,
stays silent on well-formed-but-wrong). Results: `results/_p3_sb_r0/`, `results/_p3_sb_r1/`.

### 2026-06-04  (session 8 — cross-benchmark apparatus redesign: feedback taxonomy, repair loop, trace-grounded reflection)
User constraint: the涨点 plan must work for benchmarks of DIFFERENT NATURES, not just SB. Reframed
session-7's SB-specific fixes into a general principle and built it as Phases 0–2. **All code is
unit-validated with ZERO claude spend; online validation (Phase 3) is the next step, pending budget.**

**The organizing idea — every benchmark affords two feedback channels; the harness now consumes both
via the env interface (so generality lives in the interface, with per-env bodies that degrade
gracefully):**
- **V = reference-free verifier** `env.verify(task, attempt)` — reads NO gold, so valid even at
  frozen-TEST time; powers the conditional repair loop. Strength varies by env (IFBench: the exact
  rubric; SB: execute + literal/None check; QA: format + grounding). `None` ⇒ loop never fires.
- **E = reference-grounded evidence** `env.evidence(task, resp, ev)` — gold allowed (reflection only
  runs on train tasks); structured diff that the reflector reads. Default falls back to `summarize()`.

**Phase 0 — trace-grounded reflection (general).** `eval/envs/__init__.py` gained `collect_evidence` /
`render_evidence` / `run_verify` (uniform accessors, safe defaults). `evidence()` for searchqa /
hotpotqa / spreadsheetbench; SB `score()` now keeps an UNTRUNCATED `_diag` (full traceback + per-cell
diff + a target-cell inspector that NAMES the formula-string poison via `data_only=False`). Reflection
(`prequential.py` both sites) routes through evidence; `reflector.md` rewritten around "match the
grader's expected FORM" (compute-literals / strip-articles are instances). gsm8k untouched → falls back.
*Validated:* 7/7 — SB poison named with the correct fix, QA token diffs, fallback intact.

**Phase 1 — reference-free conditional repair loop (general).** The 3 call sites (`process` /
`deploy_parallel` / `serve_one`) collapse into one `solve(task, mem, want_cost)` = single-shot + up to
`--repair_turns` rounds, each firing ONLY on an `env.verify` rejection; repair cost folds into the
ledger, the error→fix trace rides on `ev`. Per the user's call, repair is **ours-only** (`--repair_methods
ours`; baselines single-shot) with `--repair_methods no_memory` as the apparatus-only ABLATION arm (so
"you just added a repair loop" is answerable). `verify()` for all 3 envs, **provably gold-free** (searchqa
accepts "Paris" with gold `["TOTALLY-WRONG-GOLD"]`; SB runs on `*_init.xlsx` only, never opens the trap
golden). Flags threaded through `run.py`. *Validated:* verify on good/bad inputs across 3 envs + the
repair-loop contract (fires/stops/caps/accrues-cost/builds-trace) via a fake LLM.

**Phase 2 — memory×feedback closure (general).** (a) **signature-keyed episodic** (`episodic.py`):
`record(...signature=)`, `retrieve_by_signature`, `repair_hint(query, sig)` — a worked fix for failure
mode S transfers to a lexically-UNRELATED task with the same S (diverse → shared *failure* knowledge);
`solve()` feeds the hint into repair round ≥2 (retrieval-augmented repair). (b) **repair-trace
reflection** — `collect_evidence` attaches the error→fix history so the reflector learns to pre-empt the
failure. (c) **`verify.rolling_gate`** replaces the one-shot tiny-val gate: accumulate paired A/B across
checkpoints (persisted), activate only on power floor + margin + non-dilution (broke≤rescued) → kills
false-POSITIVES; report rescue/saturation so a no-headroom val is INCONCLUSIVE not a false-REJECT.
`--gate_min_n` / `--gate_margin`. *Validated:* signature transfer + graceful-empty; rolling_gate
accumulation/power/margin/saturation; repair-history rendering (structured + fallback).

**Design decisions.** (1) repair belongs to the ours family — it IS the伴生 inference-time self-correction
that produces the traces the method learns from; baselines stay single-shot; clean decomposition via the
`no_memory+repair` ablation arm. (2) Validity guardrail: V never reads gold (asserted per env) so the
repair loop is legitimate during the frozen TEST phase. (3) Backward-compat: with `--repair_turns 0` and
no `verify`, behavior reduces to the old single-shot harness; evidence defaults to `summarize`.

**Files:** `eval/envs/{__init__,searchqa,hotpotqa,spreadsheetbench}.py`, `engine/prompts/reflector.md`,
`engine/evolve/{episodic,verify}.py`, `eval/{prequential,run}.py`.
**NEXT (Phase 3, needs budget sign-off):** a tiny real-claude smoke to validate end-to-end, then the
online trio across searchqa/SB/HotpotQA with `--repair_turns 1–2` (ablated 0/1/2), accuracy-vs-total-cost
vs external, ≥3 seeds; then the rolling-gate false-pos/neg check and IFBench.

### 2026-06-04  (session 7 — first frozen runs at scale + the SkillOpt-discrepancy correction)
Ran the first frozen-protocol experiments at SkillOpt sizes, then traced a discrepancy the user
flagged that **overturns our SB headline conclusion**.

**1. SB 80/40/280 frozen, 1 seed, serving (the signal run).** Replicated SkillOpt's exact SB split
(stratified by instruction_type), serving acquisition, 1000×10s retry. **4/6 methods finished**
(orchestrator died mid-run on a transient `claude` usage cap — see op-notes); ace/external never ran.
| method | testEM (n=280) | Cell-Level (192) | Sheet-Level (88) |
|---|---|---|---|
| no_memory | 0.454 | 0.380 | 0.614 |
| **episodic** | **0.504** | **0.469** | 0.580 |
| ours_mem | 0.400 | 0.323 | 0.568 |
| ours_full | 0.446 | 0.370 | 0.614 |
→ Signal lives in the harder **Cell-Level** family (episodic +0.089 there); Sheet-Level near-flat.
The gate **ACTIVATED 6 skills** on ours_full (base 15→16 on val — marginal). Per-family figures in
`results/sb_frozen/runs/`.

**2. searchqa frozen, 16/8/16 × 3 seeds (the "does ours_full ever help?" validation).**
| method | testEM (mean±sd) |
|---|---|
| no_memory | 0.792 ± 0.078 |
| episodic | 0.833 ± 0.059 |
| ours_full | 0.854 ± 0.029 |
| **external_optimizer** | **0.917 ± 0.029** |
→ In the SHARED-PROCEDURE regime a skill IS useful (external +0.13). ours_full **doesn't dilute**
(≥ episodic ≥ no_memory; opposite of SB). BUT the **gate REJECTED ours's own skills** (val saturated
8/8 → no detectable lift) — a **false negative**: ours_full *induced a genuinely good skill*
(`exact-match-format-qa`: strip parentheticals, articles, whitespace ≈ what external captured) and
threw it away. So the **gate has BOTH error modes**: false-POSITIVE on SB (activated diluting skills),
false-NEGATIVE on searchqa (rejected a useful one). Root: deciding on a tiny/saturated val set.
Results in `results/searchqa_frozen/`.

**3. THE BIG ONE — SkillOpt 0.4→0.8 vs our degradation (5-agent investigation, both repos).**
User asked why SkillOpt (`/mlx_devbox/users/siqi.zhu/playground/SkillOpt`) doubles SB while ours
drops. **Two independent flaws, neither about SB:**
- **Flaw 1 (apparatus):** SkillOpt SB = `mode: multi, max_turns: 30` execute→error→repair loop on
  **gpt-5.5** (`configs/spreadsheetbench/default.yaml`, `configs/_base_/default.yaml`,
  `codegen_agent.py::run_multi`). Its skill is a **verify-and-repair workflow** ("run solution.py,
  reload workbook, verify target cells are non-formula literals, fix and rerun"). Our harness is
  **single-shot haiku, no execution feedback** → that skill is dead text → our external_optimizer
  scores *exactly* no_memory (0 gain).
- **Flaw 2 (learner):** our reflector gets only a 240-char reason, never the traceback, so it learned
  the **INVERSE** skill — verified: ≈38% of SB bullets formula-framed; induced skill says *"write the
  formula string in actual Excel/Sheets on a test cell first"* (the openpyxl-None failure). This is
  why consolidation falls *below* no_memory and episodic (no distilled bullets) wins.
- Ruled out: scoring/test-cases (both verified-400, 1 instance/task, byte-identical evaluator; no
  pass@k). **⇒ "SB diverse → consolidation dilutes" RETRACTED** (see Results note above).

**4. Positioning + optimization direction (design decision).** Confirmed the user's framing: our
method is **online/native — optimization born ALONGSIDE inference** (reflect→curate→promote in the
hook loop), fundamentally unlike SkillOpt's **offline external optimizer** (separate gpt-5.5 trainer,
~4 epochs, validation-gated edits). **Cost advantage is real in principle** (learning = incremental
reflection amortized into real work, vs a dedicated offline budget) — but only counts once the method
GAINS. **The涨点 plan that both fixes the flaws AND embodies the "伴生" vision: learn from the agent's
own REPAIR TRAJECTORY.** Ranked: (1) shallow **conditional** execute→feedback→repair loop in the SB
env (1–2 turns, only on failure → cheap; gives the upside + produces error→fix traces); (2)
**trace-grounded reflection** (feed real traceback + wrong-cell diff; add "never write formula
strings, compute literals" to `reflector.md`) → kills the inverse-skill poison; (3) error-keyed
episodic retrieval ("you hit error E before; fix was Y" — turns SB's diversity into shared *bug*
knowledge); (4) pre-emptive guard checklist; (5) online rolling-window gate (live A/B, fixes the
false-pos/neg). Cost-advantage experiment: accuracy-vs-TOTAL-cost, ours (learns from own traces)
vs external (offline), agentic SB, haiku fixed.

**Op-notes (for reproducibility):** (a) `workers=1` (one method-run at a time) gave ~54 calls/min vs
~15/min when 6 runs oversubscribed the box at 60-wide — run methods serially, give each run the full
concurrency. (b) A transient `claude` usage/rate cap after ~1000 calls returned `exit 1` persistently;
the 1000×10s fixed retry rides it out, BUT a fully-stalled call hung the process ~15 min and the
background task got killed — finished methods were safe on disk, restart only the unfinished one.
**NEXT:** implement涨点 plan #1+#2 (shallow conditional repair loop + trace-grounded reflection), rerun
the SB trio online (haiku fixed) — does ours_full flip from −0.01 to clearly positive? Then complete
the 6-method SB headline (ace/external) and add ≥3 seeds.

### 2026-06-04  (session 6 — SkillOpt-style frozen-deployment protocol + SB exact-split replication)
Implemented the **frozen-deployment protocol** (the carried NEXT #1: acquisition→FROZEN→held-out
test) grounded in SkillOpt's train/val/test manifest. Full design: **`docs/eval_protocol.md`**.
- **Two protocols in `prequential.py`** via `--protocol`: `prequential` (online learning curve,
  default, unchanged) and `frozen` (acquire on train → gate skill edits on val → FREEZE → headline
  on held-out test → measures REUSE, not local adaptation). Per-task work factored into
  `process(task,idx,learn,phase)`; `acquire(stream,phase)` is the shared online loop; each row
  carries a `phase` field (`eval`|`acquire`|`test`); acquisition trace saved to `*_acquire.jsonl`.
- **SkillOpt three-role split** (train=rollout evidence / val=accept-reject skill-edit gate /
  test=frozen headline), manifest ratio ~20/10/70. New `stratified_split(all_tasks, sizes, seed,
  key)`: exact sizes, optional family-stratification (SB `instruction_type`, HotpotQA `type`);
  `key=""` is byte-identical to the old slicing (existing prequential results reproduce). Cost
  model: acquisition paid up front (folds into the first test row's `cum_cost`), deployment is
  1 call/task identical across methods → **C2 "lower total cost" = acquisition cost**.
- **Under-powered gate fixed:** `--verify_n` default **6 → 18** (6 haiku tasks, SE≈0.2, can't
  resolve a real skill lift; session-4's "gate rubber-stamps" was partly low power; SkillOpt val
  18–40). `run.py` threads `--protocol/--test_n/--verify_n/--stratify_key/--induce_every`.
- **Validated** (no-claude unit tests + a real frozen SB smoke, 4/2/4 stratified, scratch
  `results/_sb_frozen_smoke/`): splitter exact 80/40/280 with strata preserved (~0.69/0.31),
  disjoint, reproducible, back-compatible; end-to-end acquire→freeze→test works for no_memory /
  episodic / ours_full; **gate induced 2 skills, rejected on val → candidate (graceful degrade)**;
  acquisition cost correctly folded into deployment cost. (Tiny-n EMs are noise — mechanism check.)
- **SB exact replication wired** (not yet run — needs budget sign-off; ~thousands of billed haiku
  calls): `--protocol frozen --train_n 80 --verify_n 40 --test_n 280 --stratify_key instruction_type
  --induce_every 0` over all 400 SB tasks = SkillOpt's 80/40/280, directly comparable to their
  headline.

**Throughput + robustness (same session, so the SB run is efficient):**
- **Parallelism:** the frozen DEPLOY phase (held-out test, ~70% of calls) is embarrassingly
  parallel (frozen store). `run.py --max_concurrency N` (default 16; set up to ~64) → the runner
  fans out all NO-WRITES work at `N//workers` concurrent claude requests: frozen test deploy (all
  methods), no_memory/external in prequential, the **consolidation gate A/B** (`verify.lift_over_base`,
  `workers=`), and the **external optimizer's train rollouts** (`train_external(workers=)`).
  Online acquisition stays sequential (prequential dependency). cum_cost is reconstructed in task
  order from each call's own cost (deterministic despite out-of-order completion); ledger appends
  mutex-guarded; SB code-exec already uses a per-task tempdir.
- **Robust retries** (`llm.call_claude`): non-zero exit / timeout / empty stdout retried with
  exponential backoff + jitter (env `NATIVE_EVOLVE_MAX_RETRIES`=5, `NATIVE_EVOLVE_RETRY_BASE`=2.0s);
  still-failing call → scored a miss, fan-out continues. Optional `return_cost` for the parallel path.
- Validated: hotpotqa frozen deploy_workers=8 (2 methods × (8 acquire + 24 deploy) in 84s wall,
  out-of-order completion, cum_cost monotonic/idx-ordered); SB parallel gate + external rollouts +
  concurrent code-exec smoke (ours_full SB EM 0.67). Files: `engine/evolve/{llm,verify}.py`,
  `eval/{prequential,run,external_opt}.py`.
- **Serving (async) mode** (`--acquire_mode serving`): parallelizes the LEARNING phase too, for the
  real serving scenario. Serve requests CONCURRENTLY (deploy_workers) against the LIVE store while
  reflection writes ASYNC in a background `learn_workers` pool; expensive reflect (claude) runs in
  parallel, only the cheap deterministic store write is serialized (`store.STORE_LOCK`) + atomic;
  all learning DRAINED before freeze. `store.save`/`save_skill_state` now atomic (tmp+os.replace);
  `reflect.reflect_deltas` split out the no-write claude half. The "online learning is sequential"
  limit is a MEASUREMENT artifact, not a system one — frozen headline depends only on the final
  committed store (curation ≈ order-independent), so serving ≈ sequential at the headline but fully
  parallel. Also hardens a REAL deployment (concurrent Stop-hook reflections no longer race).
  Validated: 30 concurrent merges → 30 bullets / 0 lost updates / 0 torn reads; hotpotqa serving
  smoke (12 served concurrently out-of-order, drained, then gated deploy). Files:
  `engine/evolve/{store,reflect}.py`, `eval/{prequential,run}.py`.

**NEXT:** launch SB frozen run with `--max_concurrency 64` (decide seeds/methods/test-size for
budget), then HotpotQA frozen at the 20/10/70 ratio.

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
