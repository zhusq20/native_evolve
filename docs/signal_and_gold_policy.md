# Signal & gold policy — which benchmarks have a gold-equivalent self-check, and how gold is allowed to intervene

> **⚠️ SUPERSEDED by the session-18 pivot (2026-06-08).** Part 2's "north star" — *one reference-free loop,
> gold NEVER teaches the deployed agent* — is NO LONGER the project's protocol. The user chose the OFFLINE
> setup: **train-with-gold → FREEZE → deploy-frozen** (`--protocol frozen`, oracle signals = default) to
> study the **memory↔skill boundary (C1)** cleanly; C2 (online reference-free ≥ offline) is set aside. Read
> Part 1 (the type-1/2 benchmark classification) as still-valid SUPPORTING material; treat Part 2's gold
> policy as historical. See `PROGRESS.md` session 18 + `memory/refocus-memory-over-verification.md`.


Plain-language companion to `docs/glossary.md`. Two parts:
1. **Classify every benchmark** by whether the agent has a *no-gold self-check that actually equals gold*.
2. **Decide how gold may intervene** in **train / eval / deploy** when the agent self-checks via the
   `self-verify-and-repair` SKILL — and what to do when no gold-equivalent signal exists.

Terms (gold / oracle / reffree / type-1 / type-2) are defined in `docs/glossary.md`. One-line reminder:
**gold** = the answer key; **reffree** = the agent checking its own work with no answer key; **type-1** =
that self-check provably equals the answer key; **type-2** = the self-check is only a hunch and can be blind.

---

## Part 1 — Benchmark classification

Every dataset *ships* gold (we need it to SCORE in eval). The real question for a deployable self-evolving
agent is different: **at deploy there is no gold — does the agent have a self-check that tells it the truth
anyway?** That splits the benchmarks into two groups.

### Full table

| env | gold (eval scoring) | reffree channel the agent can run with NO gold | reffree type | SKILL-driven path (`agentic_attempt`)? | group |
|---|---|---|---|---|---|
| **ifbench** | constraint verifiers (`_check_all`) | re-check the *in-prompt* constraints (the rule is written in the task) — `verify()` **is** `score()` | **type-1** | ✗ (single-shot) | **A** |
| **spreadsheetbench** | official cell-compare | **execution**: run the code, catch crash / formula-string poison / empty cells | type-1 *on form*, **type-2 *on the value*** | **✓ (only env)** | **A (form) / B (value)** |
| **arc** | held-out test grid EM | **execution**: run `solve()` on the SHOWN demos | **type-2** (demos under-determine the rule → "consistent" ≠ "generalizes") | ✗ | **B** |
| **bbh** (word_sorting/dyck) | string EM | format-only ("is there an `Answer:` line?") | **type-2** (semantic correctness needs gold) — *word_sorting COULD be type-1 with a sortedness check (not built)* | ✗ | **B** (word_sorting upgradable to A) |
| **searchqa** | EM | format heuristic | **type-2** (weak) | ✗ | **B** |
| **hotpotqa** | EM / F1 | format check | **type-2** (weak) | ✗ | **B** |
| **hover** | label match | format ("clear verdict?") | **type-2** | ✗ | **B** |
| **math** | answer match | format-only (`\boxed{}` present) | **type-2** | ✗ | **B** |
| **zebra** | cell-accuracy F1 | format ("parseable grid?") | **type-2** | ✗ | **B** (mostly retired: haiku ceiling) |
| **gsm8k** | numeric | none | **none** (no usable reffree) | ✗ | **B** (deprecated: too easy) |

### The binary the project actually turns on

- **GROUP A — a no-gold self-check that EQUALS gold exists (type-1).** The SKILL-driven agent can know it
  got the answer right **without** the answer key. → label-free self-evolution is trustworthy here.
  - `ifbench` (fully), `spreadsheetbench` **on the form/crash sub-criterion**.
- **GROUP B — gold is genuinely needed; any no-gold self-check is a proxy or absent (type-2 / none).** The
  SKILL-driven agent's self-check can pass while the real answer is wrong, and it *won't know*. → evolving
  on this signal risks learning from noise.
  - `arc`, `bbh`, `searchqa`, `hotpotqa`, `hover`, `math`, `zebra`, `gsm8k`, **and `spreadsheetbench`'s
    value sub-criterion** (the "SUBSTITUTE blind spot": code runs clean, number is wrong).

**The uncomfortable headline fact:** of all envs, **only IFBench is cleanly Group A**, and **only
SpreadsheetBench has the SKILL-driven agentic path built** — and SB is Group A only on form, Group B on
value. So "the SKILL-driven agent self-checks and that's trustworthy" is currently a reality on **at most
one-and-a-half benchmarks**. Everything else is either type-2 (the check can be blind) or single-shot (no
SKILL path yet). This is not a bug to hide; it *is* the precision law, and it scopes what we can claim.

---

## Part 2 — How gold intervenes in train / eval / deploy (with the SKILL-driven agent)

### The north star (one sentence)
**There is ONE loop — the reference-free, SKILL-driven self-check — and it runs identically in train and
deploy. Gold is allowed to touch the system in exactly two ways: (a) as a read-only SCOREBOARD in eval, and
(b) as an opt-in ORACLE CEILING arm in experiments. Gold NEVER feeds back into what the deployed agent
learns.** (Restates `memory/native-design-law.md`.)

Why this rule and not "use gold in train, drop it at deploy": if the learning loop reads gold during train,
the behavior it learns *cannot be reproduced at deploy* (no gold there) — train ≠ deploy, and every train
number is an illusion. So to keep **deploy == evaluated**, train must learn from the *same* signal deploy
has: the SKILL-driven self-check.

### The three phases, defined for this repo
- **train (acquire):** the agent solves a stream of tasks; the system reflects → curates memory → gate-promotes
  skills. The *learning signal* is whatever `--credit/reflect/gate_signal` is set to.
- **eval (measure):** freeze the system, run held-out tasks, grade with `env.score()` (gold). Read-only.
- **deploy:** real Claude-Code-hooks use. **No gold, ever.**

### The matrix — where gold is allowed to touch each phase

| phase | GROUP A (type-1: SKILL self-check == gold) | GROUP B (type-2/none: self-check is a proxy) |
|---|---|---|
| **train** | Loop runs on the **SKILL self-check (reffree)**. Because it equals gold, learning is *as good as* gold-supervised — **without reading gold**. Gold does NOT intervene. *(Optional: log gold read-only to CONFIRM the type-1 equivalence — never to drive learning.)* | Loop **must NOT trust the self-check as truth.** Evolving on a blind signal poisons memory (the type-2 backfire). Policy: **degrade gracefully** — when the self-check has no precise verdict, the loop **withholds credit / promotion** (learn nothing rather than learn noise). Gold stays OUT of the deploy-faithful loop. *Two escape hatches:* **(i)** engineer a type-1 proxy with no gold (e.g. ARC demo cross-validation: split the shown demos into fit/check) → moves B→A; **(ii)** *experiments only*: an explicitly-labeled **oracle ceiling** arm (`--*_signal oracle`) measures what evolution COULD reach if the signal were precise. |
| **eval** | Gold = read-only scoreboard. Also log the reffree verdict → it should agree (a type-1 sanity check). | Gold = read-only scoreboard. **Also log reffree-vs-gold agreement** (`base_fail_agree`) — that disagreement is *itself the result* (it quantifies the blindness = precision-law evidence). |
| **deploy** | No gold. SKILL self-check is trustworthy → **full label-free self-evolution.** This is where the system should actually be shipped. | No gold. SKILL self-check is a proxy → the system must **know it's untrustworthy and not evolve on it** (graceful degradation), OR evolve only through an engineered type-1 proxy (escape hatch i). Honest limitation, directly predicted by the precision law. |

### What "when there is no gold-equivalent signal" means in practice (Group B)
The deployed agent cannot tell right from wrong on the gold-relevant sub-criterion. The *safe* behavior is
**do no harm**: if the self-check yields no precise verdict, the repair loop doesn't fire and the
evolution loop grants no credit / promotes no skill. The system falls back to its prior memory rather than
corrupting it. Three honest responses, in priority order:
1. **Degrade gracefully** (default): no precise signal → no evolution this task. (Already partly true:
   `self_verify` returns `None` when no channel fires; the gap is that type-2 *blindness* still returns a
   confident-looking PASS, which is the dangerous case.)
2. **Engineer the proxy toward type-1 without gold** (the research bet): demo cross-validation / more
   demos / self-held-out checks. If it makes the self-check track gold, Group B → Group A.
3. **Oracle ceiling, experiments only** (never deployed, always labeled): shows the headroom evolution
   leaves on the table because the signal is blind.

### One-line summary
**Group A = ship it (reffree == gold, evolve freely). Group B = don't evolve on the blind check; either
make it precise without gold (demo-CV), or only measure the ceiling with a clearly-labeled oracle arm.
Gold is a scoreboard, never a teacher the deployed agent depends on.**

---

## 中文速查

**Part 1 分类** —— 关键不是"有没有标准答案"(数据集都有,用来打分),而是"**部署时没标准答案,agent 能不能自己知道对错**":
- **A 组(type-1,自检 ≡ 标准答案):** `ifbench`(完全)、`spreadsheetbench`(只在"格式/崩溃"层)。→ 可放心做无 gold 自进化。
- **B 组(type-2/无,自检只是近似):** `arc`、`bbh`、`searchqa`、`hotpotqa`、`hover`、`math`、`zebra`、`gsm8k`,以及 `spreadsheetbench` 的"数值"层。→ 在盲信号上自进化会污染记忆。
- 扎心事实:只有 IFBench 是干净的 A 组;只有 SB 建了 SKILL 驱动的 agentic 路径(且 SB 只在格式层是 A 组)。

**Part 2 gold 怎么介入** —— 北极星:**只有一个循环(SKILL 驱动的无 gold 自检),train 和 deploy 用同一套;gold 只能(a)在 eval 当只读记分牌,(b)在实验里当贴了标签的 oracle 天花板。gold 永远不喂给部署后 agent 的学习。**
- **A 组:** train/deploy 都用自检(=gold),不碰 gold;eval 用 gold 只读打分。
- **B 组:** 自检会瞎 → **优雅降级**(没有精确信号就不学,宁可不学也不学错);两条出路:(i)无 gold 地把 proxy 改造成 type-1(ARC demo 交叉验证);(ii)仅实验用、贴标签的 oracle 天花板。

---

## Implications for code (proposed — NOT yet applied; confirm before editing core signal routing)

This document is the "think first" deliverable. The design above implies a small, contained set of changes:

1. **A per-env signal-type declaration** (e.g. `SIGNAL_TYPE = "type1" | "type2" | "none"` + a one-line
   `reffree_channel` note) so the system *knows* when its self-check is trustworthy instead of that
   knowledge living only in docstrings. This is what lets Group B "degrade gracefully / don't evolve."
2. **A graceful-degradation guard** in the evolution path: on a type-2 env (or when the self-check returns
   no precise verdict), withhold reffree-driven credit/promotion rather than crediting a blind PASS.
3. **(Bigger, separate) the Phase-B wiring**: make the reffree signal actually come from the SKILL-driven
   `agentic_attempt` self-check, and extend `agentic_attempt` beyond SB. This is the "deploy == evaluated"
   alignment and should be scoped as its own change.

Recommended first step (cheap, zero-spend, reversible): items 1–2 (the signal-type registry + the guard),
which make the policy *enforceable* and are a precondition for honestly reporting Group A vs B. Item 3 is
the larger follow-up. **Awaiting confirmation on scope before editing.**
