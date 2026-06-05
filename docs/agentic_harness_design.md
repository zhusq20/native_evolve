# Agentic harness (#5) — design + the native verify-repair skill

Status: **implemented, offline-validated, billed run pending budget sign-off** (2026-06-05, session 11).
Read `PROGRESS.md` for project state; this is the design rationale for the agentic upgrade.

## Why (the gap this closes)
The single-shot harness reduced the target to a function with **zero environment feedback on the
gradeable artifact**: `solve()` called `claude -p` with `allowedTools="Read"`, no `cwd`, no files —
the agent emitted code as text it never executed; the harness ran it (`score`/`verify`) on its own
side. Claude Code still reasoned multi-turn, but every turn saw the same fixed text — deliberation,
not a feedback loop.

Consequence: the **skill tier could not demonstrate value**. A reusable *declarative* fact (a format
rule) survives single-shot, but a reusable *procedural* skill (a run→observe→fix workflow — exactly
what SkillOpt's SB skill is, and what doubled SB 0.4→0.8) is dead text with no execution surface.
This is the session-7 "Flaw 1": our `external_optimizer` scored = `no_memory` on SB because its skill
was inert. So C1 (two-tier > single-tier) was structurally capped, regardless of the gate.

## The three roles of "verify" (the load-bearing distinction)
Going agentic, `env.verify` splits into three roles that must NOT be conflated:

| role | what | where it goes | status |
|---|---|---|---|
| **A. inference-time self-correction** (run→see traceback→fix) | the agent runs its own code and iterates | **INSIDE the agent, as a SKILL** | `self-verify-and-repair` (this doc) |
| **B. grader / scorer** (gold cell-compare) | the experimenter's measurement instrument | **EXTERNAL, gold-isolated, never in agent reach** | `env.score()` unchanged |
| **C. promotion-gate validation** (held-out A/B / replay decides memory→skill) | the strict validation online systems lack | **EXTERNAL — this is the paper's thesis** | `verify.rolling_gate` / `promote.gate_pass` unchanged |

Only **A** moves inside the agent. B and C stay external. Internalizing B = teaching to the test
(invalid measurement); internalizing C = throwing away the contribution.

Bonus: role A done by the agent's native `Bash` is genuinely dataset-agnostic execution, so it also
dissolves the session-8 validity critique ("`env.verify` embeds dataset knowledge a deployment
lacks"). The hand-built `self_verify` module was scaffolding for an agent with no body; #5 lets the
agent + skill do it natively.

## What changed in the code
- **`engine/skills/self-verify-and-repair/SKILL.md`** — the hand-authored expert procedural skill
  (role A), git-tracked. **GENERAL / dataset-agnostic on purpose** (per the thesis: a native capability,
  not an SB hack): the methodology is "derive a reference-free check from the task itself → pick the
  channel that fits the artifact (EXECUTE runnable code / check explicit CONSTRAINTS / check
  GROUNDING+form) → run it → repair to the specific failure → cover the form-clean-but-value-wrong blind
  spot." openpyxl formula-string poison etc. appear only as ONE worked failure-mode example among
  code / instruction-following / QA. The verify methodology lives ONLY in the skill (the env prompt is
  task-spec + tools only), so the no-skill arm genuinely lacks it → clean ablation.
- **`engine/evolve/llm.py`** — `call_claude` gained `permission_mode`, `max_turns`, `max_retries`
  params (single-shot path unchanged: defaults `acceptEdits` / no cap / env-default retries).
- **`eval/envs/spreadsheetbench.py`** — new `agentic_attempt(task, mem, native_skills, max_turns,
  call_claude)`: builds a per-task `/tmp` sandbox, copies ONLY the first case's `*_init.xlsx` in as
  `input.xlsx` (never `*_golden*`), installs the named native skills into `sandbox/.claude/skills/`,
  prompts the agent to write+test+verify `solution.py`, then extracts the final code (prefers
  `sandbox/solution.py`, else the fenced block) and returns it for grading. The agent runs with
  `--allowedTools Read,Write,Edit,Bash,Skill --permission-mode bypassPermissions --max-turns K`.
- **`eval/prequential.py`** — `--agentic`, `--agentic_max_turns` (default 20), `--native_skills`
  (comma list resolved from `engine/skills/`). In `solve()`, when `--agentic` and the env implements
  `agentic_attempt`, the agent self-solves and the **harness repair loop is bypassed** (repair_calls=0)
  — clean attribution: the agent's own iteration, not the harness's `monotone_repair`.
- **`eval/run.py`** — threads the three flags.
- **`eval/test_agentic.py`** — offline validation (fake `call_claude`): asserts gold isolation (no
  `*golden*` in the sandbox), skill install, code extraction, and the prompt's skill line. Zero spend.

## Operational flags (confirmed against Claude Code docs)
- Skills auto-discover from the process `cwd`'s `.claude/skills/` (independent of `--setting-sources`);
  the agent must have `Skill` in `--allowedTools` to invoke them.
- `--max-turns K` bounds agentic turns but **exits non-zero on overflow** → the agentic path uses
  `max_retries=1` (don't burn 5 expensive sessions on the backstop) and falls back to reading
  `sandbox/solution.py` even when the call errors.
- `--output-format json`'s `total_cost_usd` aggregates the WHOLE multi-turn session → one honest cost
  number per task (this also fixes the old `self_verify` critique-call cost leak — no side calls now).
- `acceptEdits` would block `python` in headless; the agent needs `bypassPermissions` to run its own
  code. See "Isolation" for the safety tradeoff.

## Isolation (validity guarantee for role B)
- **Soft (implemented):** the sandbox is a fresh `/tmp` dir holding only `input.xlsx`; the golden lives
  in the dataset dir elsewhere and is never named or copied. The agent only ever sees ONE case's input,
  but is graded by running its CODE on ALL cases — so even a peek can't be memorized into a pass.
- **Hard (documented next, for the billed headline):** `bypassPermissions` + `Bash` can technically
  `find` the golden on this box. For a rigorous run, enable the OS sandbox
  (`--settings '{"sandbox":{"enabled":true,"filesystem":{"allowWrite":["<sandbox>"],"denyRead":["<dataset_dir>"]}}}'`,
  bubblewrap on Linux) so reads of the dataset dir are physically blocked. Left off by default because
  `denyRead` can break system-lib reads; turn on for the headline.

## Experiment design (clean attribution)
Agentic mode makes tool-use available to ALL arms (it's the environment, not the treatment). The
make-or-break ablation isolates the *procedural skill*:

| arm | `--agentic` | `--native_skills` | method | tests |
|---|---|---|---|---|
| **agentic baseline** | on | "" | no_memory | does bare multi-turn tool-use alone move SB? |
| **+ native skill (oracle ceiling)** | on | self-verify-and-repair | no_memory | does the hand-authored verify-repair skill give the SkillOpt-style jump? |
| **single-shot baseline** | off | — | no_memory | the old lower bound (for reference) |
| **(later) learned skill** | on | "" | ours_full | can memory→gate LEARN a skill that approaches the native ceiling? |

The first two rows are the immediate test: **does a well-formed procedural skill, executed by an agent
with a body, produce the gain the single-shot harness structurally suppressed?** If yes, the skill
tier finally has demonstrable value and the native skill becomes the oracle upper bound the learned,
gate-promoted skill is measured against (the C1 / "calibrated promotion" story).

## How to run (after budget sign-off)
```bash
# A/B the native procedural skill on SB, agentic, no_memory (golden-isolated, multi-turn)
python3 eval/run.py --tasks <SB dataset.json> --env spreadsheetbench --n 24 \
  --methods no_memory --seeds 0 --stratify_key instruction_type \
  --agentic --agentic_max_turns 20 --native_skills "" \
  --outdir results/_ag_sb_noskill
python3 eval/run.py --tasks <SB dataset.json> --env spreadsheetbench --n 24 \
  --methods no_memory --seeds 0 --stratify_key instruction_type \
  --agentic --agentic_max_turns 20 --native_skills self-verify-and-repair \
  --outdir results/_ag_sb_skill
# expect: skill arm >> no-skill arm if procedural skills pay off in the agentic harness
```
Cost is higher per task (multi-turn) but captured honestly per task via `total_cost_usd`. Start at
n=12 seed0 as a smoke before committing seeds.
