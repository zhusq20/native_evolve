---
name: self-verify-and-repair
description: Use BEFORE finishing ANY task that produces a checkable artifact (generated code, a spreadsheet/file you write, constraint-bound text, or a factual answer). You are NOT done until you have RUN a reference-free check on your own output and it PASSED. For files/spreadsheets you MUST write the COMPUTED LITERAL value a reader consumes — never a formula string ('=...'), which is stored as text and never evaluated. Derive the check from the task itself, run it, repair, repeat until it passes.
---

## Rules (non-negotiable — read first)
1. **Write the VALUE in the exact form the consumer reads.** For an openpyxl/spreadsheet output that means the **computed literal** in each answer cell: compute it in Python and assign the number/string. **NEVER assign a string that starts with `=`.** A leading `=` is a formula; openpyxl stores it verbatim and never computes it, so the grader reads the formula text (or `None`) and marks it WRONG. This single mistake is the most common failure — do not make it.
   - **This applies even if the task is naturally "a formula."** If you catch yourself BUILDING an Excel formula string — any text containing `=`, `IF(`, `SUM(`, `COUNTIF`, `VLOOKUP`, etc. — to assign into a cell (directly OR via a variable like `f = "=IF(...)"; ws[c] = f`): **STOP.** Re-implement that same logic in plain Python over the worksheet data and write the **resulting value** into the cell. The grader wants the computed answer, never the formula that would produce it.
2. **You may NOT finish until you have actually EXECUTED the check below and seen it print `VERIFY OK`.** Reading your code is not a check. If you have not run the check this turn, you are not done — run it now.
3. **Repair to the specific failure, then re-run the check.** Never stop on an unchecked first attempt.

## Steps
1. **Inspect the input** and restate, from the task alone, what a correct output must satisfy: which cells/fields, what value, what form.
2. **Produce the artifact** (e.g. write `solution.py`). Compute every required value in Python and write **literals, not formulas**.
3. **Run it** (`python solution.py`) to produce the output. Fix any crash from the full traceback before continuing.
4. **Run the verification — this step is MANDATORY, do not skip it.** Re-open the produced output and assert each required cell holds a correct LITERAL. For an openpyxl output, run exactly this kind of check (fill in the answer cells from the task's "Expected answer position"):
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
   **Do not finish while it prints `VERIFY FAIL`.** (Even better: paste this assertion at the END of `solution.py` so running your script self-checks and fails loudly on poison.)
5. **Check the VALUE, not just the form.** A cell can hold a clean literal that is the wrong number. Recompute one or two answers by hand from the task (right operation / filter / rounding / units / which rows) and compare.
6. **Repair and re-run steps 3–5** until the form check passes AND the values look right. Only then finish and output the final artifact.

## What the check catches by task type
- **Spreadsheet / openpyxl (most common here):** formula-string poison (`cell = "=SUM(...)"` stored as text → reader sees the formula/`None`; FIX: `cell = sum(...)`, the Python-computed literal); empty answer cells; header/index off-by-one (openpyxl rows/cols are 1-indexed); clobbering cells you weren't asked to change.
- **Generated code (any language):** crashes you never hit because you never ran it; "works on my one example" but not the real input shape; hardcoded paths or row/element counts.
- **Instruction-following:** some constraints satisfied while others are violated (they interact — fixing one can break another); iterate until ALL stated constraints pass at once.
- **Factual / QA:** verbose answer when an exact minimal span was asked (form mismatch); a claim not grounded in the given evidence; wrong granularity or units.
