---
name: self-verify-and-repair
description: Use BEFORE finishing ANY task that produces a checkable artifact — generated code or a spreadsheet/file output, text bound by explicit constraints (format/length/keywords/schema), or a factual answer. Derive a reference-free check from the task ITSELF (no answer key needed), run it, read the real result, and repair the artifact until the check passes. Turns a plausible-but-wrong first attempt into a verified one. Dataset-agnostic: pick the check channel that fits the artifact.
---

## When to use
- Always, as the last step before you consider a task done — your first attempt looks right far more
  often than it is right.
- Especially when the task produces something you can OBJECTIVELY check without the answer: code you can
  run, a file whose cells/fields you can read back, output that must satisfy stated rules, or a claim you
  can trace to given evidence.

## Steps
1. **State what a correct answer must satisfy**, reading only the task (never an answer key). Extract the
   concrete, checkable requirements: must it run without error? must it hit specific constraints? must it
   be in an exact form / grounded in the given evidence?
2. **Pick the strongest available check channel** for THIS artifact:
   - **Runnable artifact** (a script, generated code, a spreadsheet-manipulation program): **EXECUTE it**
     on the given input and inspect the ACTUAL output. This is the most objective channel — prefer it
     whenever something can be run.
   - **Explicit constraints in the task** (required format, length, must-include words, JSON schema,
     section structure): check your output against EACH constraint, one at a time.
   - **Free-form / factual answer**: check **grounding** (is every claim supported by the given evidence?),
     **form** (does it match the requested format, units, and granularity EXACTLY?), and self-consistency.
3. **Run the check and read the real result** — the traceback, the values actually produced, the per-
   constraint pass/fail. Do not assume; observe.
4. **Repair to the specific failure.** Diagnose the exact thing that failed and fix only that, then re-run
   the check. Iterate a few rounds; each fix targets the observed failure, never a blind rewrite.
5. **Cover the blind spot (form-clean but meaning-wrong).** A check can pass on FORM while the VALUE is
   wrong: code that ran and wrote literals but computed the wrong number; constraints all satisfied but the
   answer is off-topic. Spend one pass re-deriving the answer from the task (right operation, filter,
   rounding, units, which rows/entities) to catch the semantic errors the surface check misses.
6. **Stop when the check passes AND the value sanity-holds**, then output the final artifact in the form
   the task requested.

## Failure modes (keep — do not delete; worked examples across task types)
- **"Right idea, wrong form" (the universal silent failure).** The output's TYPE, GRANULARITY, or
  literal-vs-expression shape does not match what the consumer/grader compares. Every example below is an
  instance of this.
- **Spreadsheet / openpyxl — formula-string poison (#1 killer).** Writing `cell = "=SUM(A:A)"` stores the
  *string*; openpyxl never evaluates it, so a reader sees the formula text (or `None`), not the number.
  FIX: compute the value in Python and write the **literal**. Verify by reloading
  (`load_workbook(path, data_only=False)`) and confirming the answer cells hold concrete values — not a
  string starting with `"="`, not `None`. Also: empty answer cells, header/index off-by-one (rows/cols are
  1-indexed), and clobbering cells you weren't asked to change.
- **Generated code (any language).** Crashes you never hit because you never executed it; "works on my
  one example" but not on the real input shape; hardcoded paths or row/element counts instead of iterating
  the actual data. FIX: run it on the given input before finishing.
- **Instruction-following.** Satisfying some constraints while violating others — and multi-constraint
  prompts interact, so fixing one can break another. Iterate until ALL stated constraints pass at once;
  do not silently drop a required format/length/keyword.
- **Factual / QA.** A verbose answer with explanation when a minimal exact span was asked (form mismatch);
  a claim not actually supported by the provided evidence (grounding failure); wrong granularity or units.
  FIX: emit exactly the requested form, and ground each claim in the evidence.
