# Implementation plan — native agent verifier for ALL datasets

> **⚠️ DEFERRED / DESCOPED by the session-18 pivot (2026-06-08).** The project refocused on the **memory↔skill
> boundary (C1)** under an **offline train-with-gold → FREEZE → deploy** protocol, where verification is NOT
> load-bearing (gold drives training; frozen deploy learns nothing). The "native agent verifier for ALL
> datasets / make every env agentic" scope (esp. scope B / Phases 3–4) is OUT. If verification ever returns,
> it returns as a small OPTIONAL train-time ablation. Kept for the record. See `PROGRESS.md` session 18 +
> `memory/refocus-memory-over-verification.md`.


**Goal (user, session 18):** every dataset uses the **native agent verifier** — an isolated, grounded
*subagent* that checks the agent's output by RUNNING, instead of a per-env deterministic stub or a weak
single-shot text critique. Companion to `docs/isolated_verifier_plumbing.md` (the primitive),
`docs/signal_and_gold_policy.md` (the type-1/2 classification), `docs/related_work_no_gold.md` (why).

## The honest consequence to accept before building (precision law)
A *uniform* native verifier across all datasets does NOT make all datasets faithfully self-verifiable. The
verifier's mechanism is uniform; its **trustworthiness is still governed by the precision law**:
- **Runnable / constraint tasks** (SB code, ARC programs, IFBench constraints, word_sorting sortedness): the
  native verifier verifies-by-running → **faithful (type-1)**.
- **Knowledge / semantic tasks** (searchqa, hotpotqa, hover, math-value): there is nothing to run → the
  native verifier must **abstain** or fall back to **self-consistency** (a label-free confidence vote), and
  on abstain the system **withholds credit/promotion** (graceful degradation).

So "native verifier everywhere" = **one uniform verifier that KNOWS when it cannot faithfully check and says
so**, not "all datasets become self-verifiable." That abstention is a feature (it is the precision law made
operational), and it must be visible in the plan, the code, and the writeup.

## The verifier contract (frozen first — Phase 0)
`native_verify(task, attempt, env) -> {ok: bool|None, violations: [...], channel, confidence}`
- **channels**, tried strongest-first:
  - `exec` — the attempt carries runnable code → execute it (existing `env.try_run` / a sandbox run). type-1.
  - `constraint` — the task states checkable requirements (format/length/required words/answer-cells) → the
    verifier writes+runs programmatic checks. type-1.
  - `consistency` — nothing runnable, but we can sample N independent answers and use the **vote margin** as a
    gold-free confidence. type-2-but-usable when consensus is strong.
  - `abstain` — none of the above apply (pure knowledge fact) → `ok=None`. Honest blind.
- **isolation:** built on `llm.call_claude` (fresh process = clean context; sees ONLY task + attempt; never
  the solver's reasoning/memory/skills). Structural, per `docs/isolated_verifier_plumbing.md`.
- **abstention semantics:** `ok=None` → the harness withholds reffree credit / promotion / reflection for
  that task (does not evolve on a blind signal). `ok` true/false drives repair + the evolution signal as today.

## Phases (validity-first; zero-spend work lands before any billed run)

### Phase 0 — freeze the contract + per-env channel map (design, 0 spend)
- Write the contract above into code as a docstring + a typed return.
- Tag each env with its primary channel (reuse the `signal_and_gold_policy.md` table): SB→exec(+constraint),
  ARC→exec, IFBench→constraint, bbh/word_sorting→constraint (needs the sortedness check built),
  searchqa/hotpotqa/hover→consistency-or-abstain, math→exec(answer-recompute)/abstain.

### Phase 1 — the grounded isolated verifier primitive + routing (0 spend; unit-tested with FAKES)
- `eval/self_verify.py` → grow into `native_verify` with the four channels. `exec` = current execution
  channel; `constraint` = the grounded subagent (Bash + artifact-in-sandbox, authors+runs its own checks —
  upgrade of today's text critique); `consistency` = sample-N + vote-margin; `abstain` = `ok=None`.
- `eval/test_native_verify.py` (NEW, fakes for `call_claude`/`try_run`, ZERO claude spend):
  payload-isolation (no reasoning/memory/skill in the verifier prompt), channel routing, each channel's
  verdict, **abstain→ok=None**, verdict shape, exec-authoritative regression.
- Default OFF (`NATIVE_EVOLVE_VERIFY=native` opt-in) so every existing run reproduces.

### Phase 2 — wire as the reffree signal + abstention into the evolution loop (0 spend; unit-tested)
- `prequential.reffree_verdict/reffree_ok/make_judge` consume `native_verify`; **`ok=None` ⇒ skip credit /
  skip gate vote / skip reflect** for that task (graceful degradation). Oracle path unchanged (ceiling).
- `--verify_mode native` flag; `make_judge` and the gate A/B handle abstain. Unit-test the skip-on-abstain.

### Phase 3 — the SKILL-invoked native version + verdict capture (needs a billed smoke)
- Install a tiny **`verify` tool** into the agent sandbox (alongside `_install_skills`) that the SKILL calls
  via Bash: it runs `native_verify` and writes `verdict.json {ok, violations, channel}`; the agent reads it
  to repair, the harness reads it for the signal (= deploy==evaluated / Phase B). Cost auto-ledgers.
- This makes the verifier *agent-invoked* (deploy-faithful), not just harness-invoked.

### Phase 4 — a GENERIC agentic solve path so non-SB envs can run the SKILL (needs a billed smoke)
- Today only `spreadsheetbench.agentic_attempt` exists. Add a generic agentic runner: `env.agentic_prompt`
  (build) + `env.extract_answer` (parse) + a shared loop in the runner (claude multi-turn, SKILL installed,
  Bash). SB's xlsx-sandbox stays a special case; text envs (QA/bbh/ARC) need no file sandbox.
- For envs we DON'T make agentic, the **harness-invoked** `native_verify` (Phase 1–2) still applies on the
  single-shot artifact — so "native verifier everywhere" holds even before every env is agentic-solved.

### Phase 5 — per-env enablement + contrast smoke (billed, gated, ≥1 type-1 + ≥1 type-2)
- Build the missing groundings: word_sorting sortedness check; math answer-recompute; the consistency channel
  for QA. Confirm the per-env channel map end-to-end.
- **Smoke (1 seed each, budget-gated):** IFBench (type-1 → native verifier should TRACK gold,
  `base_fail_agree` high) vs searchqa (type-2 → native verifier ABSTAINS / consistency-only). This is the
  precision law demonstrated on the uniform native verifier.

### Phase 6 — validity & cost (the rigor pass)
- A/B: native-verifier reffree vs oracle vs the old self_verify; report agreement per env.
- Cost: each verify is an extra agent call — cumulative auto-ledgers; thread per-task verify cost into
  `meta["cost"]` (fix the known per-row undercount). ≥3 seeds on the headline contrast.

## Cost & confound warnings (validity-first)
- **Cost:** a native agent verifier per task (multi-turn, can run code) is far pricier than the current
  deterministic `verify()` / one-shot critique. Across all envs this multiplies spend → keep it flag-gated,
  smoke on 2 envs before broadening, and watch the ledger.
- **Confound:** switching every env to an agent verifier (and some to agentic solve) is a regime change;
  prior single-shot numbers become a different setting. Aligns with the deploy-faithful north star, but state
  it — don't compare new agentic-verifier numbers against old single-shot tables.

## Recommended order
Phases 0–2 are **zero-spend, default-off, fully unit-testable** → land them first (the uniform verifier +
abstention, reproducing all existing runs). Then ONE billed smoke (Phase 5, IFBench vs searchqa) to validate
the contract before broadening. Phases 3–4 (agent-invoked + generic agentic solve) follow once the primitive
is proven.

## Open decision (scope fork — needs the user)
Does "all datasets use the native agent verifier" mean **(A)** keep solving as-is and make only the
VERIFICATION a native agent everywhere (cheaper, smaller, Phases 0–2 cover it), or **(B)** also make every
env SOLVE agentically so the SKILL spawns the verifier natively mid-solve (deploy-faithful, but Phase 4 +
much higher cost + the confound above)? Recommendation: **(A) first** (uniform native verifier as the
signal, abstaining honestly), then **(B)** only on the envs where we want the billed deploy-faithful headline.
