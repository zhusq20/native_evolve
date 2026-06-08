# Glossary — native_evolve (plain-language)

The recurring terms in `PROGRESS.md` / `findings_synthesis.md`, defined in the simplest words
possible. If a term reads like jargon, look it up here. Written to be readable by a newcomer —
no term is used in its own definition.

中文速查表在文末。

---

## The one analogy (everything maps to this)

Picture **a student who just finished an exam and wants to know whether they got a question right.**

| term | the analogy | one line |
|---|---|---|
| **gold** | the teacher's official answer key | the truth that *defines* "correct" |
| **oracle** | the student is allowed to peek at the answer key | judging with the truth (a cheat / upper bound) |
| **reffree** | no answer key — the student must check their own work | judging without the truth (the real deploy situation) |
| **type-1** | a self-check that is *as good as* the answer key (plug the root back into the equation → if it holds, it's provably right) | the self-check **equals** the gold criterion → reliable |
| **type-2** | a self-check that is only a *hunch* (re-read the essay, "sounds fine") — but "sounds fine" ≠ "is correct" | the self-check is a **proxy** → it can be blind |

One sentence: **gold is the truth; oracle peeks at the truth; reffree has no truth and must guess;
a type-1 guess is provably reliable, a type-2 guess can be silently wrong.**

---

## Terms

### gold  (标准答案)
The ground-truth correct answer the dataset ships with. It *defines* right vs. wrong. We grade with
it (`env.score()` → EM). In a real product there is **no gold** at deploy time — that absence is the
whole problem this project studies.

### oracle  (偷看标准答案 = 上界/作弊模式)
Letting the system **use gold to make a decision** during an experiment — e.g. when deciding "is this
memory useful?" or "should this skill be promoted?", look at the answer key. Flags: `--gate_signal oracle`,
`--credit_signal oracle`, `--reflect_signal oracle`.
- **Not deploy-realistic** (production has no answer key).
- Its job is to be the **ceiling**: "even peeking at the answers, the gain is only X — so X is the limit."

### reffree  (reference-free, 无参考自评 = 真实部署模式)
The system judges its own correctness **without gold**, using only what a real deployment has. This is
the setting the paper is actually about. Two channels exist (see "How it's implemented" below):
- **execution** — if the answer contains code, run it on the task's *input* and watch for crashes /
  no-output. Uses no answer key.
- **self-critique** — if the answer is not code, the model re-reads its own task + answer and lists the
  *stated, checkable* requirements it violated.

### type-1 signal  (自检 ≡ 标准答案 → 可靠)
A reffree check whose verdict **always matches** what gold would say — because the check **is** the gold
criterion, just computed without the answer key.
- **IFBench**: the task *states* the constraints ("exactly 3 paragraphs, contain word X"). Checking them
  needs no answer key, and "satisfies the constraints" **is** the grading rule. So `verify() == score()`.
- **word_sorting** (if implemented this way): gold = "output is the input words in sorted order"; you can
  fully self-check "is it sorted? is it the same words?" with no answer key.
→ Here reffree **tracks** oracle. No-gold self-evolution is trustworthy.

### type-2 signal  (自检只是近似 → 会瞎)
A reffree check that is only a **proxy** for gold, so it can disagree with gold and not even know it.
- **ARC**: gold = "generalizes to a *held-out* new grid"; the only deploy-available check is "reproduces
  the *shown* demos". A program can nail the demos yet fail the new grid (few demos under-determine the
  rule). Measured: `base_fail_agree ≈ 0` (the self-check is blind to exactly the cases gold catches).
- **dyck**: "looks like valid brackets" ≠ "is valid"; self-critique passed 32/32 while gold failed 4.
- **SB value layer**: "the code runs" ≠ "the number is right".
→ Here reffree goes **blind**; any agreement with oracle is coincidental.

### The PRECISION LAW (why these two types exist)
The headline finding: **a reffree signal can replace oracle iff it is type-1, not type-2** — and crucially
**"executable / runnable" looks type-1 but can be type-2** (ARC's check runs fine yet is blind). So
"my self-check executes" is *necessary but not sufficient* for trusting no-gold self-evolution.

---

## How the no-gold self-check is ACTUALLY implemented (two DISTINCT things — do not conflate)

There are **two** separate "self-checks" in this repo. They are **not** the same code and serve different roles.

### 1. The harness signal — `eval/self_verify.py`  (what the EXPERIMENTS measure)
A **fixed Python function** the harness runs. The agent does **not** author it.
- channel A = **execution**: calls `env.try_run(task, attempt)` (runs the agent's code on the task input).
- channel B = **self-critique**: sends ONE hard-coded prompt (`_CRITIQUE` in `self_verify.py`) to `claude`.
- This is the source of every `--*_signal reffree` number. It is a **stand-in** for native self-checking.

### 2. The native skill — `engine/skills/self-verify-and-repair/SKILL.md`  (the DEPLOY-faithful path)
A **hand-authored skill** that, in the **agentic** harness (`env.agentic_attempt` + `--native_skills
self-verify-and-repair`), is injected into the agent's sandbox. The agent then **writes and runs its own
task-specific check** in its own turn (e.g. it emits the actual `openpyxl` assertions for *this* task and
runs them until they print `VERIFY OK`).
- This is the "agent generates its own check" picture.
- Caveat 1: the **procedure** (SKILL.md) is currently **hand-authored/seeded**, not induced by the
  reflect→promote loop. The agent generates the *concrete per-task check*; it does not invent the skill.
- Caveat 2: this agentic path is **built** but is **not yet** the default source of the headline numbers
  (that is the `self_verify.py` stand-in). Aligning the two — measure the reffree signal *via the native
  SKILL-driven check* — is the open "Phase B / deploy == evaluated" item.

**One-line takeaway:** the reffree numbers today come from a fixed harness function (`self_verify.py`),
**not** from the agent using `SKILL.md`. The SKILL-driven, agent-authored check exists on the agentic
path and is the intended deploy-faithful version, but it is not yet what the experiments score.

---

## 中文速查表

| 术语 | 大白话 | 真实部署能用? | 代码位置 |
|---|---|---|---|
| **gold** | 标准答案,定义对错 | —(它就是判据) | `env.score()` |
| **oracle** | 偷看标准答案来决策(作弊/上界) | 否 | `--*_signal oracle` |
| **reffree** | 不看答案,自己检查(真实场景) | 是 | `eval/self_verify.py` |
| **type-1** | 自检 ≡ 标准答案(靠谱) | 是,且可靠 | IFBench、(待补)word_sorting |
| **type-2** | 自检只是近似(会瞎) | 是,但不可靠 | ARC、dyck、SB 数值层 |
| **precision law** | reffree 能不能替代 oracle,取决于它是 type-1 还是 type-2;"能执行"≠"精确" | — | 招牌结论 |

**两个"自我检查"别混:** 跑实验用的 reffree 信号 = 固定的 `eval/self_verify.py`(执行 + 写死的批评 prompt),
**不是** agent 用 `SKILL.md` 自己生成的。agent 用 SKILL 自己写检查的版本 = `engine/skills/self-verify-and-repair/`
(agentic 路径),那才是"部署忠实"的设计,但目前还没成为实验数据的来源(= Phase B 待办)。
