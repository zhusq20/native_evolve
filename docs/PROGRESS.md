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
- **Session-8 apparatus (cross-benchmark; unit + online validated):** uniform `solve()` = single-shot +
  conditional **repair** (`--repair_turns`) driven by a reference-free verify; gold-grounded
  `env.evidence()` → **trace-grounded reflection** (killed the inverse-skill poison); **signature-keyed
  episodic** + `repair_hint`; **rolling-window** consolidation gate; **dataset-blind `self_verify`**
  (execution + self-critique, auto-routed; `--verify_mode oracle|self|self_exec`). New env: **IFBench**
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
  realistic verifier; repair's value is real, not an oracle artifact.**
- Two robust wins: reference-free repair ~doubles SB gold-free (0.47→0.81); trace-grounded reflection
  flipped SB memory from net-harmful (session-7) to +0.22. **All 1-seed signals — details in the session-8
  changelog.** Raw runs: gitignored `results/_p3_*/`.

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
  COMPLEMENT (the IFBench pattern). This is the highest-insight follow-up.
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
