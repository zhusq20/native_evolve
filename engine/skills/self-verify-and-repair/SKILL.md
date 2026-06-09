---
name: self-verify-and-repair
description: Use BEFORE finishing ANY task that produces a checkable artifact (generated code, a spreadsheet/file you write, constraint-bound text, or a factual answer). You are NOT done until an INDEPENDENT, ISOLATED check has RUN on your output and PASSED. The check must be done by a fresh verifier that sees ONLY the task + your output — never your reasoning — and it must verify by RUNNING (execute code, assert cells/constraints), not by re-reading. For files/spreadsheets you MUST write the COMPUTED LITERAL a reader consumes — never a formula string ('=...'), which is stored as text and never evaluated. Repair to the specific failure, re-verify, repeat until it passes.
---

## Rules (non-negotiable — read first)
1. **Write the VALUE in the exact form the consumer reads.** For an openpyxl/spreadsheet output that means the **computed literal** in each answer cell: compute it in Python and assign the number/string. **NEVER assign a string that starts with `=`.** A leading `=` is a formula; openpyxl stores it verbatim and never computes it, so the grader reads the formula text (or `None`) and marks it WRONG. This single mistake is the most common failure — do not make it.
   - **This applies even if the task is naturally "a formula."** If you catch yourself BUILDING an Excel formula string — any text containing `=`, `IF(`, `SUM(`, `COUNTIF`, `VLOOKUP`, etc. — to assign into a cell (directly OR via a variable like `f = "=IF(...)"; ws[c] = f`): **STOP.** Re-implement that same logic in plain Python over the worksheet data and write the **resulting value** into the cell. The grader wants the computed answer, never the formula that would produce it.
2. **You are NOT done until an INDEPENDENT, ISOLATED verifier has RUN on your output and PASSED.** Re-reading your own work in your own head does not count — a checker that can see the reasoning that produced an answer tends to rubber-stamp it (it will rationalize the same mistake). The verifier must start FRESH and verify by RUNNING. See "The isolated check" below.
3. **Repair to the specific failure the verifier reported, then re-verify.** Never stop on an unchecked first attempt; never stop while the verifier reports a failure.

## The isolated check (the heart of this skill — do not skip or shortcut)
**Why isolated:** an honest check needs a verifier that did NOT see how you got the answer. If it sees your chain-of-thought, your retrieved memory, or your active skills, it inherits your assumptions and approves your own output (self-preference bias). A FRESH verifier, given only the task and the artifact, catches what you rationalized.

**Spawn a separate verification subagent.** Prefer a subagent/Task tool if your harness exposes one; otherwise launch a fresh agent via Bash (a new `claude -p` process is a clean context). Hand it ONLY the payload below and have it return a verdict.

**Payload contract — what the verifier MAY and MUST NOT see:**
- ✅ MAY see: the **task exactly as you received it** (including any stated answer location/format/constraints) and the **artifact you produced** (the file, the code, the final answer).
- ❌ MUST NOT see: your reasoning / chain-of-thought, your intermediate choices, your retrieved memory bullets, or the text of any skill you used. (Things like "expected answer cells" are part of the TASK — pass those; they are not your private choices.)

**What the verifier does (it authors its OWN check — do not pre-write it for it):**
1. From the task ALONE, independently restate what a correct output must satisfy (which cells/fields, what value, what form, which constraints).
2. **Verify by RUNNING, not by re-reasoning** — execute the code, open the produced file and assert each required cell, check each in-prompt constraint, run the program on the shown examples. Running is the independent channel that makes the verdict faithful; an opinion formed by re-reading is not.
3. Return a verdict: `{"ok": true}` if every requirement holds, else `{"ok": false, "violations": ["one specific, fixable sentence", ...]}`.

**Honest limit:** isolation removes bias but cannot invent knowledge. If a requirement is a pure fact with nothing to run or check against (no code, no constraint, no example), the isolated verifier is still limited — it should say so / lower its confidence rather than rubber-stamp. Where there IS something to run, run it.

## Steps
1. **Inspect the input** and restate, from the task alone, what a correct output must satisfy.
2. **Produce the artifact** (e.g. write `solution.py`). Compute every required value in Python and write **literals, not formulas**.
3. **Run it** (`python solution.py`) to produce the output. Fix any crash from the full traceback before continuing.
4. **Run the isolated verification (MANDATORY).** Spawn the fresh verifier per "The isolated check" with the payload contract. It re-derives the requirements and checks them by RUNNING. For an openpyxl output the verifier runs exactly this kind of assertion (answer cells come from the task's "Expected answer position"):
   ```python
   import openpyxl
   wb = openpyxl.load_workbook(OUTPUT_PATH, data_only=False)
   bad = []
   for sheet, coord in ANSWER_CELLS:                 # e.g. [("Sheet1", "B2"), ("Sheet1", "B3")]
       v = wb[sheet][coord].value
       if isinstance(v, str) and v.startswith("="):  bad.append((coord, "FORMULA-STRING", v))
       elif v is None:                                bad.append((coord, "EMPTY"))
   print("VERIFY FAIL:", bad) if bad else print("VERIFY OK")
   ```
   (Even better: paste this assertion at the END of `solution.py` so the script self-checks and fails loudly on poison; the isolated verifier still re-derives and re-runs independently.)
5. **Check the VALUE, not just the form.** A cell can hold a clean literal that is the wrong number. The verifier recomputes one or two answers from the task (right operation / filter / rounding / units / which rows) and compares.
6. **Repair to the reported violations and re-run steps 3–5** until the verifier returns `ok` AND the values look right. Only then finish and output the final artifact.

## What the check catches by task type
- **Spreadsheet / openpyxl (most common here):** formula-string poison (`cell = "=SUM(...)"` stored as text → reader sees the formula/`None`; FIX: `cell = sum(...)`, the Python-computed literal); empty answer cells; header/index off-by-one (openpyxl rows/cols are 1-indexed); clobbering cells you weren't asked to change.
- **Generated code (any language):** crashes you never hit because you never ran it; "works on my one example" but not the real input shape; hardcoded paths or row/element counts. The verifier runs the code on the real/shown inputs.
- **Instruction-following:** some constraints satisfied while others are violated (they interact — fixing one can break another); the verifier checks ALL stated constraints at once, independently of how you wrote the text.
- **Factual / QA:** verbose answer when an exact minimal span was asked (form mismatch); a claim not grounded in the given evidence; wrong granularity or units. (Pure-knowledge claims hit the "honest limit" above — verify what is checkable, flag the rest.)
