"""MATH environment (competition math; exact-answer scoring, shared solution procedures).

A SHARED-PROCEDURE regime for the memory/skill story: problems within a topic (algebra /
number_theory / counting_and_probability / prealgebra) and level share latent solution
procedures (setups, identities, casework patterns) -> reusable distilled heuristics. The
reference-free verify is FORMAT-only (semantic correctness is invisible without gold), so
this is a MEMORY-leaning regime where repair stays mostly idle (the mirror of SpreadsheetBench
in the lever map: SB = repair-carried, MATH = memory-carried).

Data: eval/data/math/<topic>.jsonl  (fields: id, question, answer, level, topic, split).
Pass a single .jsonl OR the directory (loads all topics, mixed). Stratify with --stratify_key topic.
"""
import json
import os
import pathlib
import re

NAME = "math"

_SYSTEM = (
    "Solve the math problem. Think step by step briefly, then give the FINAL answer on the last "
    "line as \\boxed{<answer>}. Put ONLY the final simplified answer inside \\boxed{} (a number, "
    "fraction, or simplified expression — no units, no words)."
)


def load_tasks(path):
    p = pathlib.Path(path)
    files = sorted(p.glob("*.jsonl")) if p.is_dir() else [p]
    out = []
    for fp in files:
        for line in fp.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            r["question"] = r.get("question", "")
            out.append(r)
    return out


def build_prompt(task, mem):
    body = (_SYSTEM + "\n\n# Problem\n" + task.get("question", "")
            + "\n\nEnd with the final answer as \\boxed{}.")
    return (mem + "\n\n" + body) if mem else body


# --- answer extraction + normalization (compact Hendrycks-MATH-style matcher) ---
def _last_boxed(s):
    """Return the content of the LAST \\boxed{...} (balanced braces); fall back to 'answer is X'
    or the last number in the text."""
    s = s or ""
    idx = s.rfind("\\boxed")
    if idx < 0:
        m = re.findall(r"answer\s*(?:is|=|:)\s*\$?\\?\(?\s*([^\n$.,]+)", s, re.I)
        if m:
            return m[-1].strip()
        nums = re.findall(r"-?\d+(?:\.\d+)?(?:/\d+)?", s)
        return nums[-1] if nums else ""
    i = s.find("{", idx)
    if i < 0:                                            # \boxed12 style (rare)
        return s[idx + 6:].strip().split("$")[0].split()[0] if s[idx + 6:].strip() else ""
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1:j]
    return s[i + 1:]


def _strip(s):
    s = (s or "").strip()
    for tok in ("\\left", "\\right", "\\!", "\\,", "\\;", "\\ ", "\\$", "\\\\"):
        s = s.replace(tok, "")
    s = s.replace("\\dfrac", "\\frac").replace("\\tfrac", "\\frac")
    s = s.replace("\\%", "").replace("%", "").replace("$", "")
    s = re.sub(r"\^\s*\{?\\?circ\}?", "", s)                       # degrees
    s = re.sub(r"\\text\s*\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\mbox\s*\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}", r"\1/\2", s)  # \frac{a}{b} -> a/b
    s = re.sub(r"\\frac\s*(\d)\s*(\d)", r"\1/\2", s)                 # \frac12 -> 1/2
    s = s.replace(" ", "")
    s = re.sub(r"(?<=\d),(?=\d)", "", s)                            # 1,000 -> 1000
    while len(s) >= 2 and s[0] == "{" and s[-1] == "}":
        s = s[1:-1]
    s = s.rstrip(".")
    if re.fullmatch(r"-?\d+\.0+", s):                              # 4.0 -> 4
        s = s.split(".")[0]
    return s


def _equiv(a, b):
    if a == b:
        return True
    na, nb = _strip(a), _strip(b)
    if na == nb:
        return True
    try:
        return abs(float(na) - float(nb)) < 1e-6
    except (ValueError, TypeError):
        return False


def score(task, response):
    pred = _last_boxed(response or "")
    gold = str(task.get("answer", ""))
    em = 1.0 if _equiv(pred, gold) else 0.0
    return {"em": em, "f1": em, "sub_em": em, "predicted_answer": (pred or "(none)")[:80],
            "gold_answers": [gold], "_pred_raw": pred, "_reason": "" if em else "wrong final answer"}


def verify(task, attempt):
    """REFERENCE-FREE format check (reads no gold): is there a non-empty final \\boxed{} answer?
    Repair fires when the model forgot to box / left it empty. Semantic correctness is NOT checkable
    without gold -> this regime is memory-carried, repair mostly idle (returns ok once a boxed answer
    is present, so a correct-looking answer never triggers a wasteful repair)."""
    a = attempt or ""
    if "\\boxed" not in a and not re.search(r"answer\s*(?:is|=|:)", a, re.I):
        return {"ok": False, "signature": "no-final-answer",
                "feedback": "You did not give a final answer. Re-solve and END with \\boxed{<answer>}."}
    if not _last_boxed(a).strip():
        return {"ok": False, "signature": "empty-answer",
                "feedback": "Your final answer box is empty. Put the simplified final answer inside \\boxed{}."}
    return {"ok": True, "signature": "", "feedback": ""}


def evidence(task, response, ev):
    correct = ev["em"] == 1.0
    return {
        "outcome": "PASS" if correct else "FAIL",
        "task": "MATH (%s, level %s): %s"
                % (task.get("topic", ""), task.get("level", ""), task.get("question", "")[:600]),
        "predicted": "final answer: %s" % (ev.get("_pred_raw", "") or "(none)"),
        "gold": str(task.get("answer", "")),
        "diagnosis": "" if correct else (
            "Wrong final answer. Re-derive the solution METHOD for this kind of %s problem — the setup, "
            "identity, or casework that applies — and record a TRANSFERABLE procedure (the steps), not "
            "this specific number." % task.get("topic", "")),
    }


def summarize(task, response, ev):
    return (
        "USER TASK (MATH %s, level %s):\n%s\n\nWAS CORRECT: %s\nPREDICTED: %s   GOLD: %s\n\n"
        "RESPONSE (truncated):\n%s"
        % (task.get("topic", ""), task.get("level", ""), task.get("question", "")[:700],
           ev["em"] == 1.0, ev.get("_pred_raw", ""), task.get("answer", ""),
           (response or "")[:700])
    )
