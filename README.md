# native_evolve

Research repo studying **harness-native self-evolving memory/skill** for CLI coding
agents (Claude Code / Codex), and **evaluating** it against baselines (ACE single-tier;
SkillOpt/GEPA external offline optimizer).

The repo is organized in **three layers**:

| Layer | Path | What it is |
|---|---|---|
| **Research / optimization** | repo root: `docs/`, `eval/` | The workspace where we improve & measure the system. Experiment harness + research docs. |
| **Object under study** | `engine/` | The deployable self-evolution system we generate and optimize (the agent's memory/skill engine + hooks). |
| **Experiment data & figures** | `results/` | One subdir per experiment: `curve.csv`, `summary.json`, `fig_*.svg`, per-run `tasks.jsonl`. |

```
native_evolve/
├── CLAUDE.md              ← start here (how to work) ; docs/PROGRESS.md ← current state
├── docs/                  research docs (PROGRESS log + design rationale)
├── eval/                  experiment harness (runner, baselines, envs, plots, data)
├── engine/               ← the object under study (deploy with: cd engine && claude)
│   ├── evolve/ adapters/ prompts/ memory/ skills/ scripts/ .claude/ README.md
└── results/              ← experiment outputs (figures + data)
```

## Quickstart
```bash
pip install -r requirements.txt
export NATIVE_EVOLVE_CLAUDE_BIN=$(command -v claude || echo ~/.local/bin/claude)
python3 engine/scripts/evolve setup        # dirs + engine/.claude/skills symlink
python3 engine/scripts/evolve doctor        # sanity check

# run an experiment
export NATIVE_EVOLVE_MODEL=haiku
python3 eval/run.py --tasks eval/data/searchqa_val.jsonl --env searchqa --n 24 \
  --methods no_memory,external_optimizer,ace,ours_full --seeds 0,1 --workers 4 --outdir results/demo
python3 eval/plot.py results/demo
```

- **Deploy the engine** (use the self-evolution as a native capability): `cd engine && claude`.
  Promoted skills appear in the visible `engine/skills/` (auto-linked from `engine/.claude/skills`).
- **Engine internals & deployment**: see `engine/README.md`.
- **Design rationale**: `docs/native_memory_skill_design_cli.md`.
- **Current state, results, next steps**: `docs/PROGRESS.md`.
