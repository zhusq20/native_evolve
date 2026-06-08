# How to do FAITHFUL no-gold self-checking & memory/skill recording — literature answer

The core research question of this project: **with no answer key at deploy, how does an agent (a) faithfully
check whether its own output is correct, and (b) decide what to write into memory/skill?** This doc answers
it from the 6 `papers/` works + the external literature (surveyed session 18). Plain-language; terms in
`docs/glossary.md`; policy in `docs/signal_and_gold_policy.md`.

---

## The one-principle answer (everything below is a special case of this)

> **A no-gold self-check is trustworthy ONLY when it is grounded in an INDEPENDENT channel the generator
> did not already use** — running code, calling a tool, retrieving evidence, checking an explicit in-prompt
> constraint, or comparing many independent samples. **A free-form "let me re-read and judge my own
> reasoning" check, done by the same model from the same knowledge, is a blind proxy — it is biased upward
> and often makes things WORSE.** You then **record to memory/skill ONLY when a grounded check passes**,
> store it **deterministically** (never an LLM wholesale rewrite), and **abstain** when the check is weak.

This is exactly our **precision law** (type-1 = grounded/independent channel == gold; type-2 = shares the
generator's blind spot). The value of the survey: **the whole field independently arrives at this principle**
— it is not idiosyncratic to us; it is the unifying lens, and we are the ones who name it and study its
*gate* consequence in an online no-gold loop.

---

## Part A — the faithful no-gold self-CHECK

### The menu of label-free signals, ranked by grounding (strong → weak)
| rank | signal | why faithful | where it applies | our envs |
|---|---|---|---|---|
| (a) | **execution / environment success** | the runtime IS the criterion | code, agents in a world | SB, ARC `try_run` |
| (b) | **explicit-constraint / unit-test checks** | the rule is written down / the test is the spec | instruction-following, codegen-with-tests | IFBench, MUSE skills |
| (c) | **self-consistency / majority vote** across independent samples | truth is the stable attractor; vote-margin = confidence | reasoning, QA (no executable check) | **none yet** |
| (d) | **tool / retrieval-grounded** confirmation | an external fact channel the generator lacked | factual QA | none yet |
| (e) | ⚠️ **free-form LLM self-judgment** | NOT grounded → biased, often negative | last resort only | self_verify critique channel |

### The hard evidence that (e) is blind (use these citations to defend the law)
- **LLMs Cannot Self-Correct Reasoning Yet** (Huang et al., ICLR 2024, arXiv:2310.01798): intrinsic
  self-correction *degrades* reasoning — GPT-4 GSM8K **95.5 → 91.5 → 89.0** over two self-correction rounds.
  It only flips positive with an **oracle label** telling it which answers to fix — exactly what deploy lacks.
- **Self-enhancement bias** (Zheng et al., MT-Bench, NeurIPS 2023, arXiv:2306.05685): a model grading its own
  output inflates it — GPT-4 **+~10%**, Claude-v1 **+~25%** win-rate over human judges.
- **Models favor their own generations** (Panickssery et al., NeurIPS 2024, arXiv:2404.13076): self-recognition
  *causally* drives self-preference — **the more self-aware the model, the LESS trustworthy its self-grade.**
- **Generator–verifier gap** (*Mind the Gap*, arXiv:2412.02674): verification only helps when the verifier has
  a channel the generator lacked (e.g. execution); for **knowledge-bound facts the gap vanishes** — verifier
  and generator share the blind spot. This is the formal reason (a)/(d) work and (e) doesn't.
- **CRITIC** (Gou et al., ICLR 2024, arXiv:2305.11738): strip the external tool and QA self-critique is
  "close to useless"; with the tool, **+7.7 F1**. Grounding is the whole game.

### Two faithfulness UPGRADES the literature gives us that we don't yet have
1. **Verifier information-isolation (CoEvoSkills, paper3).** Their reference-free verifier writes its checks
   from **only the task instruction + the agent's output files — blind to the generator's reasoning, code, and
   skills.** That conditional independence is the concrete defense against the self-preference bias above. Our
   `self_verify` self-critique currently judges in the *same* context — isolating the verifier is a cheap
   faithfulness upgrade for type-2-ish tasks.
2. **Self-consistency as the no-gold confidence signal (rank c) — the missing channel for non-executable
   tasks.** Sample N independent answers, take the majority; the **vote margin is a gold-free confidence
   estimate** (Self-Consistency, Wang et al., ICLR 2023, arXiv:2203.11171: GSM8K **+17.9%**). This is the B→A
   "engineer the proxy" tool for QA/reasoning where execution can't help — and ARC **demo cross-validation**
   (split shown demos into fit/check) is the same idea (an independent held-out channel).

---

## Part B — the faithful no-gold memory/skill RECORDING

The field has converged on **three composable gating patterns**:

### Pattern 1 — GATE-ON-VERIFIED-SUCCESS (the canonical reference-free gate)
Write a skill/memory **only after a verifier confirms the task succeeded.** Identical across the strongest
systems:
- **Voyager** (Wang et al., 2023, arXiv:2305.16291): *"this iterative process repeats until self-verification
  validates the task's completion, at which point we add this new skill to the skill library."* The verifier
  is a GPT-4 critic over the agent's **environment state** (grounded), and the skill is stored **verbatim**.
- **AWM** (Wang et al., ICML 2025, arXiv:2409.07429): *"if eₜ is predicted as success … we then transform it
  into workflow(s)."* In the online no-gold setting the success bit comes from an **LM-evaluator**.
- **MUSE** (paper4): **create → run self-authored unit tests in a sandbox → register the skill only if all
  tests pass**, plus **prune skills that consistently fail or stay unused** (forgetting) and **merge**
  duplicates (dedup).

### Pattern 2 — DETERMINISTIC curation; the LLM only PROPOSES (the anti-collapse law)
Never let an LLM rewrite the whole memory store — it collapses:
- **paper5** ("Useful Memories Become Faulty…", arXiv:2605.12978): a streamed **wholesale LLM rewrite** of the
  store drops ARC **100% → 52.6%** *even with gold solutions on every episode* — the killer is **mandatory
  per-step rewrite**, not missing labels. An **episodic-only** baseline beats all the consolidators. ⇒ keep
  raw episodes as first-class, make abstraction opt-in / delayed / family-grouped / gated.
- **ExpeL** (Zhao et al., AAAI 2024, arXiv:2308.10144): insights survive by **counted UPVOTE/DOWNVOTE**, not
  one LLM whim — deterministic vote rules prevent collapse; failures are mined too.
- **MemOp** (paper1): accept a memory only if it is **Pareto-non-negative & strictly-positive** on a 10-metric
  counterfactual replay (`∀i Δ_i≥0 ∧ ∃i Δ_i>0`) — a deterministic threshold; the LLM only drafts candidates.
- **Generative Agents** (Park et al., UIST 2023): consolidation **triggers deterministically** when
  accumulated "importance" crosses a threshold.

### Pattern 3 — ABSTAIN / DECAY on low confidence (the graceful-degradation half)
When the signal is a vote, not a hard check: **require a strong consensus margin; write nothing below it**
(selective prediction), and **decay** memory that later proves wrong (ExpeL downvote). This is the formal
mechanism behind our "Group B → don't evolve on a blind signal."

### The hard limit you MUST cite (it bounds C2's reach)
- **TTRL** (Zuo et al., NeurIPS 2025, arXiv:2504.16084): majority-vote pseudo-labels drive **+~211% on AIME
  with NO labels** — *but* **"when the model's majority-voted answer is incorrect, the reward signal itself
  becomes corrupted, potentially reinforcing systematic errors."** Self-consistency gates **inherit the base
  model's prior**: better-than-chance → it works; worse-than-chance → it amplifies error. ⇒ compose
  **gate-on-pass + abstain-on-weak-consensus + decay**, never trust a single self-signal.
- **Stratify the gold (CoEvoSkills):** if you allow *any* gold, demote it to **≤1 non-leaking bit** that only
  *triggers verifier escalation* (strengthen the check on disagreement); let a dense **reference-free**
  surrogate carry all the per-item feedback that shapes edits. A strictly no-gold variant drops even that bit.

---

## Part C — what this means for native_evolve

1. **The precision law is vindicated by the whole field — make it the thesis.** Type-1 = an independent
   grounding channel (execution/constraint/consensus/tool); type-2 = shares the generator's blind spot. Huang,
   the generator-verifier-gap papers, CRITIC, and CoEvoSkills' information-isolation are all evidence FOR it.
   Nobody else names it as a *law with a gate consequence* — that is our slot.

2. **Our differentiation is intact:** every system gates on **gold@train** (SkillOpt, MemOp) or an
   **environment-success bit** (Voyager, AWM, MUSE, paper6). **Reference-free gating in an ONLINE-DEPLOY loop,
   gold only a read-only eval overlay** is the un-occupied niche. CoEvoSkills is the closest (dense reffree
   surrogate + 1 gold bit), and even it keeps a gold oracle in the train loop.

3. **Three concrete, literature-backed mechanisms to ADD** — and they resolve the design forks from the prior
   session:
   - **Self-consistency / majority-vote channel** (rank c) → the "engineer the proxy" escape hatch for
     non-executable type-2 tasks (QA, ARC generalization via demo cross-validation). *Resolves fork 3.*
   - **Abstain-on-low-confidence** (selective prediction) → graceful degradation as a **per-task confidence
     gate**, not a static per-env label. *Resolves fork 1 (measured, not hardcoded).*
   - **Verifier information-isolation** (CoEvoSkills) → make the self-critique judge from task+output only,
     not the generator's own reasoning → less self-preference bias.

4. **Cheap reflector is justified (paper6):** harness-updating is flat in evolver scale (≤3.1pp; a 9B evolver
   ≈ Opus) — so using haiku as the online reflector/curator is principled, and compute should go to the
   *task-solving agent's* ability to **activate and adhere to** the recorded skill (paper6's two failure modes).

---

## Citation quick-list
Local: paper1 MemOp · paper2 SkillOpt (arXiv:2605.23904) · paper3 CoEvoSkills (arXiv:2604.01687) · paper4
MUSE (arXiv:2605.27366) · paper5 Faulty-Memories/ARC-Stream (arXiv:2605.12978) · paper6 Harness-Updating
(arXiv:2605.30621). External: Huang 2310.01798 · Reflexion 2303.11366 · Self-Refine 2303.17651 · CRITIC
2305.11738 · Zheng 2306.05685 · Panickssery 2404.13076 · Mind-the-Gap 2412.02674 · Self-Consistency
2203.11171 · TTRL 2504.16084 · Self-Rewarding 2401.10020 · AWM 2409.07429 · Voyager 2305.16291 · ExpeL
2308.10144 · Generative-Agents 2304.03442.
