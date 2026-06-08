# Findings synthesis — the scientific narrative

A standing synthesis of what the project has *established*, the *conceptual framework* that organizes it,
and an honest *evidence map* (which experiment supports which claim, with caveats). This is the paper-skeleton
view; `PROGRESS.md` is the chronological log, `eval_protocol.md`/`architecture.md` are the apparatus.

Status convention: **[robust]** ≥3 seeds or monotone+large; **[signal]** 1–2 seed; **[reframe]** a claim we
*revised* under evidence; **[caveat]** a known validity limit.

---

## 1. Thesis (and how it evolved)

Original two claims:
- **C1** two-tier (memory + gated skill) + retrieval  >  single-tier ACE playbook.
- **C2** native *online* self-evolution  ≥  external *offline* optimizer (SkillOpt/GEPA), at lower total cost.

Both survive, but the evidence pushed two **reframes** and surfaced one larger contribution:
- **C1 reframe → judge the GATE's DISCIPLINE, not the tier count.** The promotion gate almost never durably
  activates a skill; the durable wins live in the *memory/bullet* tier. C1's defensible form: "a disciplined
  gate correctly gates non-beneficial skills OUT and degrades gracefully to memory, which is where the lift
  is." (§4.IV)
- **C2 sharpened → the unfilled gap is *reference-free ONLINE no-gold deploy* evolution.** Every external
  optimizer gates on GOLD at train; none evolves on a reference-free signal at no-gold deploy. That gap is the
  thesis's real territory. (§4.V)
- **The emergent headline contribution: a PRECISION LAW for self-evaluation signals** — when a reference-free
  signal can (and cannot) stand in for gold, formalized as a type-1/type-2 taxonomy. (§4.III) This may be more
  broadly useful than C1/C2 themselves.

---

## 2. The apparatus in one paragraph

A `claude`-CLI agent runs a **prequential** (test-then-train) or **frozen** (acquire→gate→freeze→held-out)
stream. Per finished task it **reflects** (claude, trace-grounded), **curates** memory **deterministically**
(never an LLM wholesale rewrite — the anti-context-collapse pillar), and **promotes** proven memory into a
**gated** skill (claude drafts; a held-out A/B decides). Two levers run on one **reference-free OUTCOME SIGNAL**
(`self_verify`): a conditional **repair** loop and the self-evolving **memory/gate**. Baselines (`no_memory`,
`ace`, `external_optimizer`, `ours_full`) share the same CLI + target model (haiku) for fair acc-vs-cost.

---

## 3. The determinism pillar (the strongest, least-contested leg)

An LLM never rewrites memory wholesale; curation is deterministic Python, and only `claude` does
reflect/skill-draft/gate. The literature corroborates the failure mode we avoid: **LLM-wholesale-rewrite
collapses** (paper5, ARC 100→52.6 under streamed self-consolidation; "useful memories become faulty"). Our
typed, additive, gated curation is the structural antidote. **[robust]** (design + corroborated by 2 memory
papers).

---

## 4. Conceptual contributions

### I. Trace-grounded reflection (a prerequisite, not a result)
A reflector fed only a 240-char reason learns the **inverse** skill (SB: "write the formula string on a test
cell" → openpyxl never evaluates it → grader sees None → fail). Feeding gold-grounded `evidence()` (real
traceback / value-diff) flipped SB memory from net-harmful to **+0.22**. Lesson: memory quality is bounded by
the *evidence* the reflector sees, not the reflector. **[signal]**

### II. The two-axis lever map (what a benchmark draws on is governed by `verify`)
A 2×2 (memory × repair) per regime, across 4 envs (session 8):
- **Axis 1 — repair fires/helps ∝ verify VISIBILITY.** Crashes/constraints are visible → repair engages
  (SB +0.34, IFBench +0.13); QA semantic errors are invisible → repair idle (searchqa/HotpotQA ~0).
- **Axis 2 — memory & repair STACK vs FIGHT ∝ verify COMPLETENESS.** A complete verify (IFBench: verify==rubric)
  → COMPLEMENT; a verify with a big blind spot (SB: form-only) → SUBSTITUTE. *The memory↔repair conflict IS the
  blind spot.* **[signal, 1-seed each]**

### III. ⭐ The PRECISION LAW (the headline), sharpened to a TYPE-1/TYPE-2 taxonomy
A reference-free signal (driving repair OR the gate) recovers the gold-driven win **iff it tests the GOLD
CRITERION, not a proxy.** "Executable" is necessary but **not** sufficient.

- **Type-1 — the reference-free check IS the gold criterion** (signal == oracle by construction):
  - IFBench: the in-prompt constraint verifiers ARE the rubric (`verify()`==`score()`). self==oracle.
  - SkillsBench (papers): a deterministic pytest verifier IS correctness and is runnable reference-free.
  - SB *crashes/poison*: execution catches the FORM faithfully.
  → here the reference-free gate/repair TRACKS gold (precise).
- **Type-2 — gold is reference-DEPENDENT; any reference-free signal is a PROXY** (blind on a sub-criterion):
  - ARC: gold = generalize to a held-out grid; the deploy signal = "reproduces the SHOWN demos" → few demos
    UNDERDETERMINE the rule → "consistent" ≠ "generalizes" (measured `base_fail_agree≈0`).
  - dyck: NL self-critique tests "looks plausible" ≠ "is correct" (blind).
  - SB *values*: "runs clean" ≠ "value correct" (the SUBSTITUTE blind spot).
  - QA: semantic correctness invisible to format/self-critique.
  → here the reference-free gate goes BLIND; agreement with gold is coincidental.

**Two corollaries, both with direct evidence:**
- *Repair corollary:* a precise (type-1) signal recovers the repair win (SB self_exec 0.750 ≈ oracle 0.812;
  IFBench self 0.792 == oracle); a noisy (type-2) signal must be made MONOTONE or it scores below baseline
  (the SB 0.375→0.719 loop-bug fix). **[signal]**
- *Gate corollary (precision-law-FOR-gating):* the no-gold gate tracks gold only on type-1 envs. On ARC
  (type-2, executable!) the reffree gate disagreed with the gold gate at the activating checkpoint and was
  blind to the held-out failures. **[signal]** This is the sharpest statement: it unifies dyck and ARC
  (both proxies) and predicts IFBench/SkillsBench would track gold.

*Engineering the proxy (open):* for type-2 example-driven tasks, **self-held-out validation** (split the given
examples into fit/check; demo cross-validation) may turn "consistent" into a generalization estimate — pushing
a type-2 signal toward type-1 WITHOUT gold. This is the natural test of whether reference-free evolution can
reach reference-dependent tasks (relevant to C2's reach). **[untested]**

### IV. The gate-discipline reframe of C1
Across every env tried — custom and faithful, type-1 and type-2 — the promotion gate **almost never durably
activates a skill**:
- word_sorting: gate REJECTED (val saturated 32/32) → +0.479 is PURE memory.
- dyck: a thin single-round "activation" re-measured to net-neutral (rescued4/broke4) → non-reproducible.
- IFBench: gate REJECTED (diverse constraints → no shared procedure).
- SB: gate REJECTED (diverse, no families).
- ARC group_by_shape: a genuinely-good skill activated on ONE favorable single-round margin, but the
  accumulated rolling gate would reject.

Reframe: **the gate's value is DISCIPLINE** (correctly gating non-beneficial skills out, degrading gracefully
to memory), not skill creation. The durable wins live in the bullet/episodic tier (ARC +0.50, word_sorting
+0.479 are memory). Corroborated by the literature ("updating is FLAT, 9B≈Opus"; "abstract-only ≤ zero-shot").
**[robust pattern across ≥5 envs, each 1-seed]**

### V. C2 — reference-free online no-gold deploy evolution is the unfilled gap
Code-verified audit of the 6 papers: every offline optimizer gates on GOLD at train; the "online" ones are
measured in-situ on gold benchmarks; none evolves on a reference-free signal at no-gold DEPLOY. CoEvoSkills
proves reference-free CAN drive evolution (dense surrogate > sparse gold, −30pp). ⇒ "reference-free self-eval
driving ONLINE no-gold deploy evolution" is our differentiation. The apparatus implements it (the SIGNAL knob
on gate/credit/reflect); the deploy-faithful headline is the AGENTIC harness. **[built; A/B partially run]**

---

## 5. Methodological principles (hard-won, now enforced)

1. **Reuse official scoring — vendor it, never reimplement.** `sb_lib/` vendors SkillOpt's executor; `ifeval_lib/`
   now vendors google-research's IFEval verifiers verbatim (replacing a regex stub that was "close, not
   identical" and could diverge from published IFEval). A reimplementation accrues a faithfulness debt that
   silently corrupts external comparability. **`arc` is the only remaining fully-self-implemented env** —
   justified (P5 released no generator; real ARC isn't family-labeled) but it carries a "our-ARC, no external
   comparability" caveat → treat ARC as a CONTROLLED DIAGNOSTIC, not a comparability headline.
2. **The repair lever is SEPARATE and LABELED.** Memory claims are read off the `repair=0` column; repair's Δ
   is reported via the memory×repair 2×2; the deploy-faithful memory headline is the agentic harness. (Design
   decision (a), session 15; full discipline in `eval_protocol.md`.)
3. **Validity-first spending.** Launch `no_memory` FIRST as a headroom probe (kill ceiling/floor regimes before
   spending `ours_full`); gate billed runs; record what was dropped.
4. **Determinism for curation; `claude` only for reflect/draft/gate.** (§3.)

---

## 6. Benchmark taxonomy (the envs as instruments)

| env | data/scoring provenance | signal type | family structure | role |
|---|---|---|---|---|
| **ifbench** | OFFICIAL IFEval vendored (`ifeval_lib/`) | **type-1** (verify==score) | diverse constraints (focus a family to get one) | faithful + type-1 → the reference-free/gate HEADLINE env |
| spreadsheetbench | SkillOpt executor vendored (`sb_lib/`) | type-1 (crash) / type-2 (value) | weak (97 singletons) | diverse-codegen lever map; SUBSTITUTE→COMPLEMENT under N3 |
| **arc** (ARC-AGI Stream) | SELF-IMPLEMENTED generator (`arc_gen.py`) | **type-2** (demos proxy) | STRONG (7 skills × 3 families) | CONTROLLED DIAGNOSTIC: +0.50 memory; precision-law mechanism + demo-CV |
| bbh (word_sorting/dyck) | official BBH | type-2 (string EM) | strong (procedure families) | gate-discipline evidence; mechanical-tedium headroom |
| searchqa / hotpotqa | official EM/F1 vendored | type-2 (weak) | shared-latent / family | QA regime; repair-idle |
| zebra | WildEval + custom EM | type-2 | strong but haiku ceilings | (mostly retired: ceiling) |
| math / gsm8k / hover | official | type-2 | — | retired (ceiling/floor for haiku) |

Headroom note (5-probe meta-finding): haiku-4.5 has clean headroom mainly on **mechanical-tedium symbol
manipulation**; knowledge/math/logic ceiling, closed-book multi-hop floors. ARC group_by_shape (base ~0.22–0.44)
is the richest *structured* headroom found.

---

## 7. Evidence map (claim → experiment → caveat)

| claim | best evidence | status / caveat |
|---|---|---|
| Memory helps where a transferable procedure is missing (C1+) | ARC group_by_shape **+0.50** (no_memory 0.444→0.944, 9 rescued/0 broke, repair off) | **[signal]** 1-seed, n=18, **custom env**; +0.50 is combined memory (no skill-OFF arm) |
| | word_sorting +0.479 (46/0 monotone); dyck +0.198; SB +0.22; IFBench +0.08 | all **[signal]** 1-seed |
| Gate gates skills OUT (discipline) | REJECT on word_sorting/IFBench/SB; non-reproducible on dyck; single-round-only on ARC | **[robust pattern]**, each 1-seed |
| Precision law (repair) | SB self_exec 0.750≈oracle; IFBench self==oracle; SB 0.375→0.719 monotone fix | **[signal]** |
| Precision law FOR gating (type-1/2) | ARC reffree blind (base_fail_agree≈0) vs gold gate; IFBench reffree signal-grounded | **[signal]** 1-seed |
| Determinism > wholesale rewrite | design + paper5 (ARC 100→52.6) | **[robust]** (corroborated) |
| C2 (native ≥ external, cheaper) | SB ours 0.50 > external 0.375; searchqa external 0.896 wins | **[signal]**, regime-dependent, underexplored |

**The pervasive caveat: almost everything is 1–2 seeds, no CI.** Turning the headline (+0.50; the lever map;
the gate-discipline pattern) from SIGNAL into significance is the single highest-value rigor step (≥3 seeds +
paired McNemar + bootstrap CI + the compute-matched `no_memory+best-of-k` arm).

---

## 8. Open questions (priority)

1. **Stats:** ≥3 seeds + McNemar/bootstrap CI on the ARC +0.50 and the lever map; compute-matched arm.
2. **The clean positive case on a FAITHFUL type-1 env:** a constraint-FAMILY-focused IFBench frozen gate_audit
   (now that IFBench is faithful) — does the reffree gate activate a beneficial skill? (Even a REJECT is clean:
   "bottleneck is skill-value, not signal," on a faithful env.)
3. **Type-2 → type-1 via self-held-out validation (demo-CV) on ARC:** can engineering the proxy recover the
   reffree gate's precision? (Tests reference-free evolution's reach to reference-dependent tasks → C2.)
4. **Skill-OFF attribution** (`--induce_every 0`) to isolate any skill's marginal test contribution from bullets.
5. **C2 frontier:** online self-formed gated skills vs the offline external optimizer under the frozen
   acquire→freeze→deploy protocol, acc-vs-total-cost.
6. **Phase B:** carry the reference-free signal (incl. repair trajectory) into the deploy hooks so deployed ==
   evaluated.

---

## 9. One-paragraph abstract (current best framing)

We make self-evolving memory/skill a *native* capability of a CLI coding agent — reflect, deterministically
curate, and gate-promote in the harness's own loop, with no external trainer and no gold at deploy. Studying it
across nine benchmarks, we find that (i) deterministic curation avoids the documented context-collapse of
LLM-wholesale-rewrite; (ii) which lever a task draws on — conditional repair vs evolving memory — is governed by
the *visibility* and *completeness* of the agent's reference-free verifier; and (iii) a **precision law** governs
self-evaluation: a reference-free signal can stand in for gold **iff it tests the gold criterion, not a proxy**
(a type-1/type-2 taxonomy), which is *necessary but not implied by* mere executability. Memory yields large
clean gains where a transferable procedure is genuinely missing (up to +0.50), while a disciplined promotion
gate correctly withholds non-beneficial skills — relocating the contribution from "two tiers" to "gate
discipline + a reference-free signal that respects the precision law." (All cross-benchmark magnitudes are
single-seed signals pending a multi-seed significance pass.)
