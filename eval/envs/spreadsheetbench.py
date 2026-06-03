"""SpreadsheetBench environment (code-generation over .xlsx, cell-exact scoring).

The thesis-fit env: mid-range accuracy + many DISTINCT reusable procedural skills
(openpyxl idioms, header handling, preserving untouched cells, range math). LLM is
our `claude` CLI; the deterministic harness (code execution + official cell compare)
is reused from SkillOpt's standalone executor/evaluator (openpyxl-only), copied into
eval/envs/sb_lib/ so this project is self-contained.

Task file = the extracted dataset.json; spreadsheet files resolve relative to it.
"""
import glob
import json
import os
import pathlib
import sys
import tempfile

import openpyxl

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "sb_lib"))
import executor as _exec      # noqa: E402  run_generated_code(code, in, out, timeout)
import evaluator as _evalmod  # noqa: E402  evaluate(pred, gold, itype, answer_position)

NAME = "spreadsheetbench"

_SYSTEM = (
    "You are an expert Python programmer specializing in spreadsheet manipulation. "
    "Write a single self-contained Python script that reads the workbook at the path in "
    "variable INPUT_PATH, performs the requested manipulation, and saves the result to "
    "OUTPUT_PATH. Use ONLY the Python standard library and openpyxl (pandas is NOT "
    "available). Do not print. Do not call input(). Do not hardcode file paths or row "
    "counts — iterate over all actual rows/columns. Preserve every other cell unchanged. "
    "Return ONLY the Python code inside a single ```python ... ``` fenced block."
)


def load_tasks(path):
    p = pathlib.Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    root = p.parent
    out = []
    for r in data:
        r = dict(r)
        r["question"] = r.get("instruction", "")   # generic key used by the runner
        r["_root"] = str(root)
        out.append(r)
    return out


def _task_dir(task):
    sp = task.get("spreadsheet_path", "spreadsheet/%s" % task.get("id"))
    return sp if os.path.isabs(sp) else os.path.join(task["_root"], sp)


def _test_cases(task_dir):
    """Return [(init_xlsx, golden_xlsx), ...] for a task (verified_400 layout)."""
    pairs = []
    for ip in sorted(glob.glob(os.path.join(task_dir, "*_init.xlsx"))):
        gp = ip.replace("_init.xlsx", "_golden.xlsx")
        if os.path.exists(gp):
            pairs.append((ip, gp))
    if not pairs:  # bare fallback
        bi, bg = os.path.join(task_dir, "initial.xlsx"), os.path.join(task_dir, "golden.xlsx")
        if os.path.exists(bi) and os.path.exists(bg):
            pairs.append((bi, bg))
    return pairs


def _answer_position(task):
    ap = task.get("answer_position", "")
    sheet = task.get("answer_sheet", "")
    if ap and sheet and "!" not in ap:
        return "%s!%s" % (sheet, ap)
    return ap


def _preview(xlsx, max_rows=5, max_cols=20):
    try:
        wb = openpyxl.load_workbook(xlsx, data_only=False)
    except Exception as e:  # noqa: BLE001
        return "(failed to preview: %s)" % e
    chunks = []
    for sn in wb.sheetnames:
        ws = wb[sn]
        chunks.append("## Sheet: %s (dim=%s, max_row=%s, max_col=%s)"
                      % (sn, ws.dimensions, ws.max_row, ws.max_column))
        for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, max_rows),
                                max_col=min(ws.max_column, max_cols), values_only=False):
            cells = []
            for c in row:
                v = c.value
                s = "" if v is None else (str(v)[:37] + "..." if len(str(v)) > 40 else str(v))
                cells.append("%s=%s" % (c.coordinate, s))
            chunks.append(" | ".join(cells))
        if ws.max_row > max_rows:
            chunks.append("... (%d more rows)" % (ws.max_row - max_rows))
        chunks.append("")
    wb.close()
    return "\n".join(chunks)


def _extract_code(text):
    if not text or "```" not in text:
        return (text or "").strip()
    start = text.find("```")
    nl = text.find("\n", start)
    end = text.find("```", nl + 1)
    if nl == -1 or end == -1:
        return text.strip()
    return text[nl + 1:end].strip()


def build_prompt(task, mem):
    cases = _test_cases(_task_dir(task))
    preview = _preview(cases[0][0]) if cases else "(no input workbook found)"
    body = (
        _SYSTEM + "\n\n"
        "# Instruction\n" + task.get("instruction", "") +
        "\nInstruction type: " + str(task.get("instruction_type", "")) +
        "\nExpected answer position: " + _answer_position(task) +
        "\n\n# Input spreadsheet preview\n" + preview +
        "\n\n# Task\nReturn only a ```python``` code block."
    )
    return (mem + "\n\n" + body) if mem else body


def score(task, response):
    code = _extract_code(response)
    cases = _test_cases(_task_dir(task))
    ap = _answer_position(task)
    itype = task.get("instruction_type", "")
    n_pass, reason = 0, ""
    tmp = tempfile.mkdtemp(prefix="sb_")
    try:
        for i, (init, golden) in enumerate(cases):
            pred = os.path.join(tmp, "%d_pred.xlsx" % i)
            ok_exec, err = _exec.run_generated_code(code, init, pred, timeout=60)
            if not ok_exec:
                reason = reason or ("exec error: " + (err or "")[:240])
                continue
            ev = _evalmod.evaluate(pred, golden, itype, ap)
            if ev.get("ok"):
                n_pass += 1
            else:
                reason = reason or ("wrong cells: " + str(ev.get("reason", ""))[:240])
    finally:
        try:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
        except Exception:
            pass
    em = 1.0 if (cases and n_pass == len(cases)) else 0.0
    soft = (n_pass / len(cases)) if cases else 0.0
    return {"em": em, "f1": soft, "sub_em": em, "predicted_answer": "(python code)",
            "gold_answers": ["cells %s" % ap], "_reason": reason,
            "_npass": n_pass, "_ncases": len(cases), "_code": code}


def summarize(task, response, ev):
    return (
        "USER TASK (SpreadsheetBench, %s):\n%s\n\nANSWER POSITION: %s\n\n"
        "WAS CORRECT: %s  (passed %d/%d test cases)\n"
        "FAILURE REASON: %s\n\n"
        "AGENT CODE (truncated):\n%s"
        % (task.get("instruction_type", ""), task.get("instruction", "")[:900],
           _answer_position(task), ev["em"] == 1.0, ev.get("_npass", 0),
           ev.get("_ncases", 0), ev.get("_reason", "") or "(none)",
           (ev.get("_code", "") or "")[:900])
    )
