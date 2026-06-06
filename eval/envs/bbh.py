"""BBH (BIG-Bench-Hard) environment — the FAMILY-STRUCTURED, shared-PROCEDURE regime.

Each BBH task (file) is one PROCEDURE-FAMILY: ~250 instances solved by the SAME latent algorithm
(word_sorting = lexicographic compare; dyck_languages = bracket-stack LIFO; multistep_arithmetic =
operator precedence; logical_deduction = constraint elimination; ...). This is the regime the
skill-formation gate was missing: within a family the procedure transfers to EVERY instance, so an
induced skill is genuinely correct for the whole family (no dilution -> no gate false-positive), and a
mid-range base-rate gives the val/replay set headroom (gate power -> no false-negative).

Answers are deterministic exact-match: multiple-choice "(A)" or a free-form literal (a number, or the
exact requested sequence/list). The reference-free verify is FORMAT-only (semantic correctness needs
gold), so like MATH this is a MEMORY/SKILL-carried regime with repair mostly idle.

Data: eval/data/bbh/<family>.jsonl  (rows: {input, target}). Pass one .jsonl (a single family) OR the
directory (all families mixed; stratify with --stratify_key family). Re-fetch: see docs/PROGRESS.md "Data".
"""
import json
import pathlib
import re

NAME = "bbh"

_SYSTEM = (
    "Solve the problem below. Reason briefly step by step, then end with a line EXACTLY of the form:\n"
    "Answer: <your answer>\n"
    "If the problem lists options like (A) (B) (C), answer with the letter in parentheses, "
    "e.g. 'Answer: (C)'. Otherwise put the literal final answer (a number, or the exact "
    "sequence/list the problem asks for) after 'Answer:'."
)


def load_tasks(path):
    p = pathlib.Path(path)
    files = sorted(p.glob("*.jsonl")) if p.is_dir() else [p]
    out = []
    for fp in files:
        fam = fp.stem
        for i, line in enumerate(fp.read_text(encoding="utf-8").splitlines()):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            q = r.get("input", r.get("question", ""))
            out.append({
                "id": r.get("id", "%s-%04d" % (fam, i)),
                "family": fam,
                "question": q,
                "answer": str(r.get("target", r.get("answer", ""))).strip(),
            })
    return out


def build_prompt(task, mem):
    body = _SYSTEM + "\n\n# Problem\n" + task.get("question", "") + "\n\nEnd with 'Answer: <answer>'."
    return (mem + "\n\n" + body) if mem else body


# --- answer extraction + normalization (deterministic; no gold leakage) ---
_MC_GOLD = re.compile(r"^\(([A-Za-z])\)$")


def _answer_region(resp):
    """The text the model intends as its answer: after the LAST 'Answer:' line, else the last
    non-empty line. Reference-only (no gold)."""
    s = resp or ""
    hits = list(re.finditer(r"(?im)^\s*answer\s*:\s*(.+?)\s*$", s))
    if hits:
        return hits[-1].group(1).strip()
    # fallback: also accept inline "answer is X"
    m = re.findall(r"(?i)answer\s*(?:is|=)\s*(.+)", s)
    if m:
        return m[-1].strip().splitlines()[0].strip()
    lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def _norm(s):
    s = (s or "").strip()
    s = s.strip().strip(".").strip()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("`", "").replace("“", '"').replace("”", '"')
    return s.lower()


def _extract(resp, gold):
    """Return the model's predicted answer, shaped to compare with `gold`."""
    region = _answer_region(resp)
    if _MC_GOLD.match(gold):                                  # multiple-choice: pull the (letter)
        opts = re.findall(r"\(([A-Za-z])\)", region) or re.findall(r"\(([A-Za-z])\)", resp or "")
        return "(%s)" % opts[-1].upper() if opts else region
    return region


def _equiv(pred, gold):
    if _norm(pred) == _norm(gold):
        return True
    # numeric tolerance (multistep_arithmetic etc.): strip commas, compare as floats
    try:
        a = float(re.sub(r"(?<=\d),(?=\d)", "", _norm(pred)))
        b = float(re.sub(r"(?<=\d),(?=\d)", "", _norm(gold)))
        return abs(a - b) < 1e-9
    except (ValueError, TypeError):
        return False


def score(task, response):
    gold = str(task.get("answer", "")).strip()
    pred = _extract(response or "", gold)
    em = 1.0 if _equiv(pred, gold) else 0.0
    return {"em": em, "f1": em, "sub_em": em, "predicted_answer": (pred or "(none)")[:120],
            "gold_answers": [gold], "_pred_raw": pred, "_reason": "" if em else "wrong final answer"}


def verify(task, attempt):
    """REFERENCE-FREE format check (reads no gold): is there a non-empty final 'Answer:'? Semantic
    correctness is not checkable without gold -> memory/skill-carried regime, repair mostly idle."""
    a = attempt or ""
    if not re.search(r"(?im)^\s*answer\s*:", a) and not re.search(r"(?i)answer\s*(?:is|=)", a):
        return {"ok": False, "signature": "no-final-answer",
                "feedback": "You did not give a final answer. Re-solve and END with 'Answer: <answer>'."}
    if not _answer_region(a).strip():
        return {"ok": False, "signature": "empty-answer",
                "feedback": "Your final answer is empty. Put the answer after 'Answer:'."}
    return {"ok": True, "signature": "", "feedback": ""}


def evidence(task, response, ev):
    correct = ev["em"] == 1.0
    return {
        "outcome": "PASS" if correct else "FAIL",
        "task": "BBH [%s]: %s" % (task.get("family", ""), task.get("question", "")[:600]),
        "predicted": "answer: %s" % (ev.get("_pred_raw", "") or "(none)"),
        "gold": str(task.get("answer", "")),
        "diagnosis": "" if correct else (
            "Wrong final answer. Every '%s' problem is solved by the SAME procedure — work out that "
            "general algorithm (the step-by-step method that applies to ALL instances of this family), "
            "and record it as a TRANSFERABLE skill, not this specific answer." % task.get("family", "")),
    }


def summarize(task, response, ev):
    return (
        "USER TASK (BBH [%s]):\n%s\n\nWAS CORRECT: %s\nPREDICTED: %s   GOLD: %s\n\n"
        "RESPONSE (truncated):\n%s"
        % (task.get("family", ""), task.get("question", "")[:700], ev["em"] == 1.0,
           ev.get("_pred_raw", ""), task.get("answer", ""), (response or "")[:700])
    )
