# Dataset feasibility assessment — expanding the eval scope

Date: 2026-06-04. Method: 14 web-grounded research agents (one per candidate) scored
against this harness's hard constraints, then synthesized. Companion to `PROGRESS.md`.

## The decisive filter

Every candidate is judged against **harness constraint #1** (`eval/prequential.py:163`):

> Each task is **one headless `claude -p` call** — a single prompt string in, a single
> text/code response out (`allowedTools="Read"`). No agent↔environment loop, no live
> tools/internet, no vision. SpreadsheetBench works only because the model emits *code the
> harness executes*; SearchQA works because retrieved context is *pasted into the prompt*.

Plus: scoring must be programmatic (or an extra `claude -p` judge call); Python 3.9 /
openpyxl-only / no pandas; haiku must land **mid-range** (no floor/ceiling); experiments
are small (n=16–48 × 4–6 methods × 2–3 seeds), so token size & latency matter.

What the project still **needs** (from PROGRESS NEXT list): (a) a **family-structured**
shared-procedure benchmark where skill *formation* can pay off; (b) a **frozen-deployment**
protocol + generalization stressors; (c) coverage beyond searchqa + spreadsheetbench + MATH.

## Verdict table (sorted by recommendation, then CLI-fit)

| Dataset | Task type | Modality | CLI fit | Scoring (det?) | Regime | Effort | Verdict |
|---|---|---|:--:|---|---|---|---|
| **HotpotQA** (distractor) | multi-hop QA | text | **5** | EM/F1 (yes) | family-structured | low | **ADOPT 1st** |
| **IFBench** | instruction-following | text | **5** | verifier (yes) | family-structured | medium | **ADOPT 2nd** |
| **HoVer** (oracle) | multi-hop fact verify | text | 4 | label EM (yes) | family-structured | medium | **ADOPT 3rd** |
| DocVQA (OCR-text) | extractive doc QA | text | 4 | ANLS (yes) | diverse | medium | adopt-with-work (optional) |
| LiveBench-Math | competition math | text | 4 | exact (yes) | family-structured | low | adopt-with-work (optional) |
| Spreadsheet-912 | diverse codegen | text | 3 | cell-compare (yes) | diverse | low | defer (volume only) |
| PUPA (PAPILLON) | privacy redaction+QA | text | 2 | LLM-judge (**no**) | shared-procedure | high | defer |
| WebShop | web-shopping agent | interactive | 1 | env reward | family-structured | very-high | defer |
| AIME-2025 | competition math | text | 4 | numeric EM (yes) | not-a-fit | low | reject (haiku floor, n=30) |
| ARC-AGI (static) | grid puzzles | text | 4 | grid match (yes) | not-a-fit | low | reject (floor + anti-reuse) |
| OfficeQA Pro | doc-grounded QA | interactive | 0 | numeric tol (yes) | diverse | very-high | reject (tools+vision+huge docs) |
| ScienceWorld | embodied science agent | interactive | 0 | env reward | family-structured | very-high | reject (needs agent loop) |
| AppWorld | multi-app coding agent | interactive | 0 | DB state-diff | family-structured | very-high | reject (needs agent loop) |
| ALFWorld | embodied household agent | interactive | 0 | env success | family-structured | very-high | reject (needs agent loop) |

## Tiered rationale

### Tier A — adopt now (single-prompt text + programmatic scoring + real reuse structure)
- **HotpotQA (distractor, answer-EM).** Near-verbatim `searchqa.py` clone: 10 gold+distractor
  paragraphs paste in like SearchQA context; model emits a tagged short answer; score with the
  official ~40-line pure-Python normalizer (`hotpot_evaluate_v1.py`). **Labeled families**
  (`type` ∈ {bridge, comparison}, `level` ∈ {easy/med/hard}); comparison questions share a crisp
  "extract A-prop, extract B-prop, compare→yes/no" procedure a promoted skill can capture — the
  cleanest in-harness test of C1 skill formation/transfer. CC BY-SA. *Lock in:* distractor only
  (fullwiki = 5M-doc retrieval, infeasible); cap the paragraph block; track **per-type EM** so
  2-way yes/no guessability isn't read as learning.
- **IFBench (prompt-level loose).** Textbook single-turn fit, scored by **deterministic
  reference-free Python verifiers** (no gold answer, no judge — a scoring modality none of the
  current envs have). Family structure = per-constraint-type recipe reused across unrelated base
  prompts; ships a **built-in OOD generalization stressor** (models overfit a fixed constraint
  set). Mid-range haiku headroom (7–8B ~30%; GPT-4.1/Claude-3.7 <50%); cheap tokens. *Cost:*
  vendoring the verifier (spacy/nltk + corpora) needs a **one-time online warmup to pre-cache
  assets** before the offline loop; reproduce upstream `sample_output.jsonl` as a unit test.

### Tier B — adopt with bounded work
- **HoVer (oracle, binary label EM).** searchqa-shaped; unique **`num_hops` family axis (2/3/4-hop)**
  → clean compositional frozen-deployment split (learn 2-hop → freeze → deploy 4-hop). *Work:* a
  one-time offline build resolving `(title, sent_idx)` supporting-facts into evidence text via the
  HotpotQA intro-paragraph corpus (~1.5 GB). Oracle framing only (full retrieval ~15%). *Risk:*
  as a shared-verification procedure it may **reconfirm** the SearchQA consolidation story unless
  the `num_hops` generalization experiment is made the headline.
- **DocVQA (OCR-text, ANLS).** Adds **fuzzy continuous scoring** (tests format normalization, a
  different signal than EM) and **noisy OCR input** (robustness/context-shift axis). MIT pixparse
  variant ships OCR text+Q+A. *Work:* OCR reading-order serialization, ANLS, parquet-without-pandas.
  Strengthens the *diverse/context-shift* story, **not** the family gap.
- **LiveBench-Math (math_comp + easy AMPS_Hard only).** Near-clone of the materialized MATH env;
  adds **contamination-freshness** (monthly refresh) that strengthens C2. *Gate:* haiku floors on
  olympiad/AMPS_Hard — restrict difficulty, **drop the olympiad reordering subtask**, port the
  multi-fallback extractor faithfully. High overlap with MATH → complement, not priority.

### Tier C — defer
- **Spreadsheet-912:** near-zero effort (existing `sb_lib` parses its schema) but adds only ~2×
  volume of the **same diverse/no-family regime** (confirmed: 386 unique base ids, the 14
  two-variant ids carry *different* instructions). Cannot test skill formation. Add only if more
  held-out room for frozen-deployment is specifically wanted.
- **PUPA:** quality metric needs a live proprietary-model call at task time (breaks #1) and is
  irreducibly LLM-judge (cost + nondeterminism); regime is shared-procedure (≈ SearchQA). Revisit
  only if a privacy domain is wanted, as a redaction-only task with a substring-leakage scorer.
- **WebShop:** the only feasible single-turn variant needs a Pyserini/Java BM25 index over 1.18M
  products (very-high infra, no Java on box) and strips the navigation that makes it distinctive,
  collapsing toward SearchQA-like retrieval.

### Tier C′ — reject *today*: need a new multi-turn agent↔env harness (constraint #1)
**AppWorld, ALFWorld, ScienceWorld, OfficeQA, native WebShop.** All are scientifically excellent
family-structured / frozen-deployment-ready testbeds, but the task *is* an observe-then-act loop —
structurally impossible in a single call. Unblocking them is a **separate multi-week initiative**:
one shared driver doing per-step `claude -p` calls with growing trajectory context, action
parsing/validation, env stepping + reward bookkeeping, and a per-env runtime bridge (py4j for
ScienceWorld, TextWorld for ALFWorld, the FastAPI engine for AppWorld). If/when built, priority is
**AppWorld → ALFWorld → ScienceWorld** (AppWorld has the best reuse structure: a ready
Test-Normal→Test-Challenge distribution-shift split).

### Tier D — reject: mechanically fit but poor memory-thesis fit
- **AIME-2025:** n=30 too small for a prequential stream; non-thinking headless haiku floors near
  0–10% (the cited 63% is Haiku-4.5 *with extended thinking*); deliberately one-off puzzles → no
  shared procedure. Dominated by MATH.
- **ARC-AGI (static):** adversarially **anti-reuse by design** (every task a novel rule); static
  non-reasoning models ≲10% v1 / ~0% v2 → haiku floors. (Note: ARC-AGI-3 is interactive — don't
  confuse it for the static set.)

## Mapping survivors to project needs

| Open need | Best fit | Runner-up |
|---|---|---|
| (a) **family-structured** (skill formation pays off) | **HotpotQA** (bridge/comparison families) | IFBench (per-constraint recipe), HoVer (num_hops) |
| (b) **frozen-deployment / generalization stressor** | **IFBench** (OOD-constraint is its core design) | HoVer (compositional 2→4-hop), DocVQA (OCR context shift), HotpotQA (distractor = adversarial shortcut) |
| (c) **deterministic instruction-following regime** | **IFBench** (only candidate; reference-free verifier) | — |
| (d) second diverse-codegen point | Spreadsheet-912 (redundant — skip) | none clean within constraints |

## Integration roadmap (ordered)

1. **HotpotQA-distractor** — `eval/envs/hotpotqa.py` clones searchqa; flatten distractor
   paragraphs → pasteable block; vendor `hotpot_evaluate_v1.py` normalizer → `{em,f1,sub_em}`;
   carry `type`/`level` for per-family analysis. **Effort: low (~½ day).** Gate on a 24-task haiku
   dry-run (confirm mid-range, check yes/no inflation).
2. **IFBench** — `eval/envs/ifbench.py`; load the 300-row parquet (HF quirk: test under split
   `train`); vendor `instructions*.py` + `evaluation_lib.py` → `score()` returns
   `em=prompt-level-loose`, per-instruction `sub_em`. **Effort: medium (~½ day)** + a **one-time
   online warmup** to pre-cache nltk/spacy assets; validate against upstream `sample_output.jsonl`.
3. **HoVer-oracle** — `eval/envs/hover.py`; paste resolved gold evidence + claim → SUPPORTED/
   NOT_SUPPORTED; binary EM. **Effort: medium** (env trivial; ~hours for the one-time evidence
   index build). Oversample 3/4-hop; document the oracle caveat.

Optional 4th/5th by axis: **DocVQA-OCR** (fuzzy-scoring + OCR robustness) · **LiveBench-Math**
(contamination-freshness for C2). **Skip:** Spreadsheet-912, PUPA, WebShop, AIME, ARC.
**Out of scope until a multi-turn harness exists:** OfficeQA, ScienceWorld, AppWorld, ALFWorld.

## Cross-dataset risks
- **Haiku floor** (the most common killer): AIME, ARC, OfficeQA, LiveBench-hard floor near 0 → no
  signal. **Run a 24-task dry-run before committing seeds for every adopted env.**
- **Guessability/ceiling:** HotpotQA yes/no (track per-type EM); HoVer easy-2-hop (oversample hard);
  IFBench strict floors → use loose.
- **Token/cost blowup:** HotpotQA 10-paragraph context > SearchQA's 4000-char cap; HoVer 4-hop &
  DocVQA dense forms run long — cap lengths, check per-task cost across all method×seed cells.
- **Offline friction:** IFBench (spacy/nltk corpora) & DocVQA (pyarrow) need a one-time online
  setup pass before the no-internet loop.
- **Scoring fidelity:** IFBench/LiveBench have multi-fallback verifiers — reproduce upstream sample
  scores as a unit test before trusting numbers (LiveBench had a documented AMPS_Hard 0-score bug).
- **License:** adopt set is permissive (HotpotQA/HoVer CC BY-SA, IFBench Apache/ODC-BY, DocVQA-
  pixparse MIT, LiveBench MIT). Watch-outs: AIME CC BY-NC-SA (research-only), Text2Analysis
  unspecified, OfficeQA HF-gated.
- **Scope discipline (hardcode/document):** HotpotQA distractor-only; HoVer oracle-only; DocVQA is
  the OCR-text setting (not visual); LiveBench drop olympiad; ARC use static v1/v2 not v3.
