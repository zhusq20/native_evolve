# Plan — Option B: online NO-GOLD deploy evolution, with the precision law as the theory core

*(Session 23, 2026-06-09. The positioning review — PROGRESS session-23 entry + the in-chat 6-paper
field map — picked this as the highest-ceiling thesis: the one lane none of papers/ 1–6 occupies.
This doc is the experiment design; the demo-CV mechanism it needs landed the same session.)*

## The question (plain language)

A deployed agent has **no answer key**. Can it still *learn from its own work* — write memory,
credit what helped, promote skills — using only signals it can compute itself? The field's answer
so far is "train offline with labels, freeze, deploy" (SkillOpt/MemOp/CoEvoSkills). Our claim:

> **Online no-gold self-evolution works exactly where the agent's self-signal tests the gold
> criterion (type-1), fails where it tests a proxy (type-2) — and for example-driven tasks the
> proxy can be ENGINEERED into type-1 with zero gold, by holding out one of the task's own
> examples (demo cross-validation).**

The three contributions: (1) the no-gold online loop as a native harness capability (the gap all
six papers leave open); (2) the **precision law** + type-1/type-2 taxonomy as the predictor of
when it works; (3) **demo-CV** as the constructive type-2→type-1 escape hatch, demonstrated.

## The signal menu (what each arm "sees" instead of gold)

| signal | what it checks | type | LLM cost | code |
|---|---|---|---|---|
| `oracle` | gold answer (env.score) | ceiling, NOT deployable | 0 | existing |
| `reffree` | self_verify: execution on SHOWN demos + critique | type-2 on ARC ("consistent ≠ generalizes") | ~1 call/task (non-code) | existing |
| `demo_cv` | execute on a demo **WITHHELD from the prompt** | engineered **type-1** (a true generalization probe) | **0** (pure python) | NEW (session 23) |

Mechanism (all landed, 24/24 unit checks + suites green): `--demo_holdout k` moves the last k demos
of every task to `task["cv_demos"]` and re-renders the question (no leak through prompt/retrieval/
episodic); `arc.cv_check` runs the candidate `solve()` on the withheld pair; `--gate/credit/
reflect_signal demo_cv` routes all three learning signals through it; per-task `signal_ok` is
logged for offline signal-vs-gold agreement (the precision measurement).

## Design rules (validity first)

- **Identical solve context across signal arms:** `--demo_holdout 1` applies to ALL arms of a run,
  so arms differ ONLY in the learning signal, never in what the solver sees. (The cost of the
  holdout itself is measured separately: `no_memory @holdout=0` vs `@holdout=1`.)
- **Protocol = prequential (online test-then-train):** deploy IS the learning stream; gold is used
  only by the measurement overlay (the EM curve), never enters the loop in no-gold arms.
- Repair off (memory claims read repair=0); native memory + fixed skill load (current defaults);
  same model (haiku) everywhere.
- Data: `arc_gbs.jsonl` (group_by_shape, 4 demos/task → holdout 1 leaves 3; the regime with the
  reproduced +0.40/+0.50 memory headroom). Real-ARC follow-up: `arc2_train_full.jsonl` (all ≥2 demos).

## Experiment tiers (budget-gated)

- **T0 (done, $0):** demo-CV mechanism + tests. The discriminating unit case holds: an overfit
  solve passes try_run (consistent on shown demos) but FAILS cv_check.
- **T1 — mechanism smoke (~$3–5, 1 seed, n=12):** arms {no_memory, ours_full} with all three
  signals = `demo_cv`, `--demo_holdout 1`, `--induce_every 8`, `--gate_sample 6`. Pass criteria:
  cv verdicts computed (signal_ok in rows), credit/reflect/gate all fire gold-free, no crash;
  signal_ok-vs-em agreement readable from tasks.jsonl.
- **T2 — the law pilot (~$15–25, 1 seed, n=24):** 5 arms on arc_gbs:
  1. `no_memory` @holdout=1 (floor)
  2. `ours_full` signals=oracle (gold ceiling for online evolution)
  3. `ours_full` signals=reffree (naive type-2: predicted to mis-credit overfit programs)
  4. `ours_full` signals=demo_cv (the money arm)
  5. `no_memory` @holdout=0 (prices the held-out demo)
  Headline read: demo_cv recovers ≥~70% of (oracle − no_memory) while reffree recovers less /
  shows lower signal precision (signal_ok vs em agreement per arm). Cost story: demo_cv's signal
  is FREE (no LLM calls) — cheaper than reffree AND closer to gold.
- **T3 — significance + breadth (after T2 signal):** ≥3 seeds + eval/stats.py McNemar/CI;
  IFBench as the natural type-1 positive (verify==rubric, no engineering needed); real ARC-AGI-2;
  the faithful external_optimizer comparison (offline+gold vs online+no-gold, acc-vs-total-cost).

## Honest risks

- Holding out a demo may lower the floor (3 fit demos instead of 4); arm 5 measures it.
- One cv demo is a 1-sample generalization probe — noisy per task; the law claim is about the
  AGGREGATE precision (agreement with gold across the stream), which the per-row signal_ok logs.
- Credit falls back to GOLD on a rare UNAVAILABLE verdict (no code in the answer). Count the
  fallbacks (rows without signal_ok among learned tasks); on arc_gbs they should be ~0.
- Session-18 chose frozen+gold deliberately; this plan REVERSES that for the headline. The frozen
  boundary results stay as a chapter (they are signal-independent findings).
