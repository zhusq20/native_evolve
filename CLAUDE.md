# native_evolve — working notes for Claude

You are continuing a research project. **Read `docs/PROGRESS.md` first** — it is the
living log of what's done, what the results were, and what to do next. This file is the
stable "how to work here"; PROGRESS.md is the evolving state.

## What this project is
Make **self-evolving memory/skill** a *native* capability of a CLI coding agent
(Claude Code / Codex), then **evaluate** it against baselines. The agent reflects on
each finished task, curates itemized memory, and promotes proven memory into gated
skills — all in the harness's own loop (hooks), no external trainer.
Design rationale: `docs/native_memory_skill_design_cli.md`.

Two scientific claims under test:
- **C1**: two-tier (memory + gated skill) + retrieval beats single-tier ACE playbook.
- **C2**: native *online* self-evolution ≥ external *offline* optimizer (SkillOpt/GEPA) at lower total cost.

## Golden rules / gotchas (read before coding)
- **Python 3.9** on the dev box → no 3.10+ syntax (`X | Y`, `match`). Use `typing`.
- The LLM is ONLY the **`claude` CLI** (headless `claude -p`). No SDK, no model API.
  Set the binary + model via env (below). `claude` may not be on PATH → use an abs path.
- **No pandas** installed → the spreadsheet codegen prompt says "openpyxl only".
- **Determinism rule**: an LLM never rewrites memory wholesale (ACE context-collapse).
  Curation is deterministic Python; only `claude` does reflect / skill-draft / gate.
- **Skills are visible**: promoted skills live in `./skills/` (git-tracked); `.claude/skills`
  is a generated symlink → `../skills` so the harness still auto-discovers them.
  Run `python3 scripts/evolve setup` after a fresh clone to (re)create the symlink + dirs.

## Environment
```bash
pip install -r requirements.txt                 # openpyxl
export NATIVE_EVOLVE_CLAUDE_BIN=$(command -v claude || echo ~/.local/bin/claude)
export NATIVE_EVOLVE_MODEL=haiku                 # cheap target for experiments; "" = harness default
python3 scripts/evolve setup                     # dirs + .claude/skills symlink
python3 scripts/evolve doctor                    # sanity check (python/claude/paths/skills)
```
Data: SpreadsheetBench is gitignored (38 MB). Re-fetch — see `docs/PROGRESS.md` → "Data".
SearchQA tasks file (`eval/data/searchqa_val.jsonl`) is tracked.

## Layout
```
evolve/          self-evolution engine (deterministic except llm.py)
  config.py      paths/thresholds/binaries + ensure_skill_link()
  store, retrieve, curate, promote, reflect, llm
adapters/        claude_code (hooks) + codex (wrapper)   ← deployment
eval/            experiment harness (the research half)
  run.py         dispatch (method,seed) runs; --workers parallelizes across runs
  prequential.py one run: test-then-train stream over a task file; --env, --method
  envs/          searchqa.py, gsm8k.py, spreadsheetbench.py (+ sb_lib/ exec+eval)
  external_opt.py  SkillOpt-style offline optimizer baseline
  plot.py        pure-python SVG figures from out/<exp>/runs/*
  fetch.py       materialize task files for envs that implement fetch()
prompts/         reflector.md, skill_writer.md, external_optimizer.md
memory/          store.jsonl, skill_state.json, replay/ (promotion-gate cases)
skills/          promoted skills (VISIBLE; .claude/skills symlinks here)
docs/            PROGRESS.md (state) + design docs
```

## Key commands
```bash
# run an experiment (4 methods, 2 seeds, parallel across the 8 runs)
python3 eval/run.py --tasks eval/data/searchqa_val.jsonl --env searchqa --n 24 \
  --methods no_memory,external_optimizer,ace,ours_full --seeds 0,1 --workers 4 \
  --outdir eval/out/<name>
python3 eval/plot.py eval/out/<name>            # -> fig_learning_curve.svg, fig_acc_vs_cost.svg

# methods: no_memory | ours_full | ace | external_optimizer
# envs:    searchqa | spreadsheetbench | gsm8k(too easy, deprecated)
```

## Recording progress (do this every session)
1. Append a dated entry to `docs/PROGRESS.md` (what changed, results, decisions, next).
2. `git add -A && git commit -m "..."` — commit messages are the coarse log; PROGRESS.md is the fine log.
3. Keep results-of-record (curve.csv / summary.json / *.svg / tasks.jsonl) committed; the
   bulky per-run `home/` dirs are gitignored.
