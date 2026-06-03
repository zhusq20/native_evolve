# PROGRESS — native_evolve

Living state of the project. Newest session at the top of the Changelog.
Read `CLAUDE.md` for how-to-work; this file is what's-been-done + what's-next.

---

## Thesis
Internalize an external skill optimizer (SkillOpt/GEPA) into the agent's own online
loop. Reflect → curate (deterministic) → promote-with-gate, via Claude Code hooks.

- **C1** two-tier (memory + gated skill) + top-k retrieval  >  single-tier ACE playbook.
- **C2** native *online* self-evolution  ≥  external *offline* optimizer, at lower total cost.

## Method abstraction (eval/prequential.py, test-then-train / prequential)
For a shuffled task stream, each task is first **evaluated** (test) with the memory built
from tasks `1..i-1`, then **learned from** (train). Cumulative cost is logged per task so
acc-vs-cost is fair. Baselines, all on the same `claude` CLI + same target model:
- `no_memory`        — lower bound.
- `ours_full`        — top-k memory retrieval + reflect + skill promotion (gate).
- `ace`              — single-tier: inject the FULL playbook every task, reflect, NO promotion.
- `external_optimizer` — SkillOpt/GEPA style: offline-train ONE global SKILL.md on a disjoint
                         split (cost paid up front + logged), then FROZEN during eval.

## Status (what works, validated)
- Engine: store / retrieve / curate(deterministic) / reflect(claude) / promote+gate(claude). ✓
- Deployment: Claude Code hooks (UserPromptSubmit→inject memory, Stop→reflect, recursion-guarded). ✓
- Eval harness: prequential runner, 4 baselines, `--workers` parallel across runs, SVG plots. ✓
- Envs: searchqa ✓, spreadsheetbench ✓ (codegen+exec+official cell-compare), gsm8k ✓ (deprecated: too easy).
- Skills visible in `./skills/` with `.claude/skills` symlink. ✓
- Parallelism: across (method,seed) runs only; a single online run is inherently sequential
  (prequential dependency). Confirmed isolated (per-run home/ledger).

## Results so far  (haiku target, n small, 2 seeds — SIGNALS not significance)

### SearchQA (n=24)  — stationary, format-bound QA
| method | EM | cost$ |
|---|---|---|
| no_memory | 0.708 | 0.37 |
| **external/SkillOpt (offline)** | **0.896** | 0.56 |
| ace | 0.812 | 0.65 |
| ours | 0.833 | 0.77 |
→ **External WINS here.** One global format skill, learned offline & cheaply, suffices on a
stationary format-bound distribution. ours learns gradually, pays reflection tax. C2 NOT supported here.

### SpreadsheetBench (n=16)  — diverse procedural codegen (SkillOpt's home turf)
| method | EM | seed0 | seed1 | cost$ | bullets |
|---|---|---|---|---|---|
| no_memory | 0.375 | .375 | .375 | 0.59 | 0 |
| external/SkillOpt (offline) | 0.375 | .375 | .375 | 0.94 | 0 |
| ace | 0.375 | .438 | .312 | 0.98 | ~40 |
| **ours** | **0.500** | **.562** | **.438** | 1.05 | ~40 |
→ **ours WINS on both seeds.** External's single frozen skill gives zero net gain (=no_memory)
on diverse tasks → **C2 supported here**. ours (top-k retrieval) > ACE (dump 40 bullets) → **C1 partly supported**.
- **CRITICAL CAVEAT**: the promotion gate **never fired** (0 skills promoted; helpful≥5 needs a longer
  stream). So at n=16, "ours" = memory + retrieval ONLY; the **skill-promotion tier is UNTESTED**.
- Base accuracy 0.40 = good mid-range (headroom, no floor/ceiling). Figures: `eval/out/sb_haiku/*.svg`.

**Cross-setting story (the paper's spine):** stationary/format-bound → external offline wins;
diverse/multi-skill/procedural → native online wins. Each paradigm has its regime.

## Open questions / NEXT (priority order)
1. **Fire the promotion gate** — the headline mechanism (memory→skill) is still untested.
   Run SpreadsheetBench with a LONGER stream so thresholds trigger:
   `n=48, seeds 0-2`, all 4 methods. (~1.5–2h, ~$40 on haiku.) This is the #1 gap.
2. **Significance** — bump to ≥5 seeds, report mean ± CI; current n/seeds give signals only.
3. **A/B promotion gate** — current gate is presence-based; make it counterfactual
   (with-skill vs without-skill) so promotion = proven causal lift (also a C1 metric).
4. **Context-budget + poisoning stress** (C1's natural battleground): cap injected tokens to
   force ACE playbook bloat/dilution; inject p% misleading bullets, measure auto-deprecate.
5. **Non-stationary stream** (C2's natural battleground): concatenate task families so a frozen
   global skill underfits while online accumulation adapts.
6. (Optional) tool-using agent variant: pass `--add-dir` + allow Bash so the target reads the
   xlsx and iterates via execution, instead of pure codegen. Different, more "native harness".

## Design decisions (and why)
- Reuse SkillOpt's deterministic spreadsheet parts (executor+evaluator, openpyxl-only) →
  copied into `eval/envs/sb_lib/` so the repo is self-contained; faithful to the official benchmark.
- LLM only via `claude -p` (constraint). Curation deterministic (anti context-collapse, ACE).
- Cost accounting via a per-run ledger (`home/ledger.jsonl`); external optimizer's training
  cost is paid before the eval loop so acc-vs-cost is honest.
- Recursion guard for the Stop-hook reflector: `--setting-sources user` + `NATIVE_EVOLVE_REFLECTING=1` + Read-only.

## Data
SpreadsheetBench (gitignored, 38 MB). Re-fetch:
```bash
mkdir -p eval/data/spreadsheet && cd eval/data/spreadsheet
curl -sSL -o sb400.tar.gz \
  "https://huggingface.co/datasets/KAKA22/SpreadsheetBench/resolve/main/spreadsheetbench_verified_400.tar.gz"
tar xzf sb400.tar.gz   # -> spreadsheetbench_verified_400/dataset.json (+ spreadsheet/<id>/)
# task file = .../spreadsheetbench_verified_400/dataset.json
```
SearchQA: `eval/data/searchqa_val.jsonl` (tracked). GSM8K: `python3 eval/fetch.py --env gsm8k --n 40`.

---

## Changelog
### 2026-06-02  (session 1 — build + first results)
- Built engine, hooks, prequential harness, 4 baselines, SVG plots, env-pluggable.
- Envs: searchqa, gsm8k (deprecated: ceiling), spreadsheetbench (integrated SkillOpt exec/eval).
- Results: SearchQA (external wins), SpreadsheetBench (ours wins both seeds; gate didn't fire).
- Made skills visible (`./skills/` + `.claude/skills` symlink; `evolve setup`).
- Set up handoff: CLAUDE.md, this file, requirements.txt, .gitignore, git.
- **Next session: do NEXT #1 (longer SpreadsheetBench stream to fire the promotion gate).**
