# native_evolve

Make **self-evolving memory/skill** a *native* capability of your CLI coding agent.

Deploy this directory, launch `claude` (or `codex`) inside it, and the harness
starts learning across tasks — distilling experience into persistent memory after
every session, and promoting proven memory into reusable Agent Skills — **without
any external trainer**. The only LLM access is the `claude` / `codex` CLI itself.

It is the *internalized* version of an external skill optimizer (e.g. SkillOpt):
the reflect → curate → gate loop runs inside the agent's own runtime via hooks,
instead of an offline outer-loop program treating the harness as a black box.

---

## How it works

```
task ─► [UserPromptSubmit hook] retrieve.py injects relevant memory bullets
     ─► native .claude/skills/ progressive disclosure loads matching skills
     ─► agent does the work (transcript.jsonl written natively)
     ─► [Stop hook] (async, detached) reflect:
            claude -p (Reflector) → delta bullets        (LLM, recursion-guarded)
            curate.py merges deltas → memory/store.jsonl  (deterministic)
            promote.py: proven bullet → SKILL.md → replay gate → .claude/skills/
```

Design rules (enforced, from the ACE / Voyager / Externalization literature):

- **Curator is deterministic** — an LLM never rewrites memory wholesale (avoids
  *context collapse*). Only `add` / `reinforce` / `revise`, each on one bullet.
- **Two layers** — cheap high-frequency memory bullets; low-frequency skills that
  must pass a **replay verification gate** before going live.
- **Detail preserved** — the Reflector is told to keep heuristics & failure modes
  (no *brevity bias*).
- **Self-correcting** — a bullet that repeatedly misleads auto-deprecates.

---

## Layout

```
evolve/                 harness-agnostic core (pure python, deterministic except llm.py)
  config.py             paths + thresholds (all env-overridable)
  store.py  retrieve.py curate.py  promote.py  reflect.py  llm.py
adapters/
  claude_code/          hooks (UserPromptSubmit, Stop) + settings.json  ← fully native
  codex/runner.py       wrapper runner (Codex has no equivalent hooks)
prompts/                reflector.md, skill_writer.md
memory/                 store.jsonl, skill_state.json, replay/, skill_candidates/
.claude/                settings.json (hooks) + skills/ (promoted skills land here)
scripts/evolve          CLI: status / retrieve / reflect / seed / doctor / install-claude
```

---

## Quick start

### Claude Code (fully native, zero install)

```bash
cd native_evolve
python3 scripts/evolve doctor     # check python + claude on PATH
python3 scripts/evolve seed       # optional: a couple of example bullets
claude                            # launch here; approve the hooks when prompted
```

Just use Claude normally. After each task the Stop hook reflects in the background.
Watch memory grow:

```bash
python3 scripts/evolve status
python3 scripts/evolve retrieve "write a spreadsheet formula from the header row"
```

### Install into another project

```bash
python3 scripts/evolve install-claude --into /path/to/your/project
cd /path/to/your/project && claude
```

This copies the engine to `<project>/.native_evolve/` and writes hooks into the
project's `.claude/settings.json`, with `NATIVE_EVOLVE_HOME` pointed at the copy so
each project evolves its own memory.

### Codex

Codex lacks UserPromptSubmit/Stop hooks, so drive it through the wrapper (which
injects memory, runs the task, then reflects):

```bash
python3 adapters/codex/runner.py "your task here"
```

---

## Configuration (env vars)

| var | default | meaning |
|---|---|---|
| `NATIVE_EVOLVE_HOME` | this dir | where memory/prompts/skills live |
| `NATIVE_EVOLVE_CLAUDE_BIN` | `claude` | path to the claude binary |
| `NATIVE_EVOLVE_CODEX_BIN` | `codex` | path to the codex binary |
| `NATIVE_EVOLVE_MODEL` | (harness default) | model for reflect/skill-writer/gate |
| `NATIVE_EVOLVE_TOPK` | `8` | bullets injected per task |
| `NATIVE_EVOLVE_PROMOTE_HELPFUL` / `_USES` | `5` / `5` | bullet→skill thresholds |
| `NATIVE_EVOLVE_GATE_RATE` | `0.8` | replay pass-rate required to go live |
| `NATIVE_EVOLVE_AUTO_PROMOTE` | `0` | `1` skips the gate (not recommended) |
| `NATIVE_EVOLVE_REFLECTING` | — | internal recursion guard; do not set manually |

---

## The promotion gate

`promote.py` drafts a `SKILL.md`, then verifies it by replaying cases in
`memory/replay/*.json` — each `{"task": "...", "expect_substring": "..."}`. The
candidate skill is dropped into a throwaway project root so Claude discovers it
natively; it goes live only at `>= NATIVE_EVOLVE_GATE_RATE`.

**With no replay cases** (fresh deploy) the gate can't verify, so drafts are
**staged** under `memory/skill_candidates/` for human review instead of
auto-activating. Add replay cases (or set `AUTO_PROMOTE=1`) to close the loop.

---

## Status

Deterministic core (retrieve / curate / promote bookkeeping / hooks) is tested and
runs on Python 3.9+. The three LLM steps (Reflector, skill-writer, gate) require a
working `claude` (or `codex`) CLI at deploy time. Wire `memory/replay/` to your real
task set to make skill promotion fully autonomous.

See `../SkillOpt-main/docs/native_memory_skill_design_cli.md` for the design rationale.
```
