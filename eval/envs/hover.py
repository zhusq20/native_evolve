"""HoVer environment — multi-hop CLAIM VERIFICATION (a new, fact-checking regime).

Each claim is verified SUPPORTED vs NOT_SUPPORTED. The dataset is **family-structured by
`num_hops` (2/3/4)** — deeper claims chain more facts — which is the shared-structure axis for
memory/skill (the learnable procedure: decompose the claim into atomic sub-claims, verify each,
AND/aggregate). Scoring is deterministic binary EM (label match).

DESIGN NOTE — CLOSED-BOOK: HoVer's `supporting_facts` only reference Wikipedia titles+sentence-ids,
not text; assembling evidence needs the multi-GB wiki corpus. So this env is closed-book (verify from
the model's parametric knowledge). This (a) keeps it text-only / low-dependency, (b) preserves the
hop-families and the decomposition procedure, but (c) is BINARY (50% guessing floor) and tests
knowledge-chaining rather than retrieval-grounded reasoning. Track per-`family` EM (deeper hops = more
headroom) and read the floor caveat when interpreting small lifts.

Data: eval/data/hover_val.jsonl (rows: id, question=claim, answer=label, family=hopN, num_hops).
Re-fetch: GitHub hover-nlp/hover data/hover/hover_dev_release_v1.1.json (see docs/PROGRESS.md "Data").
"""
import json
import pathlib
import re

NAME = "hover"

_SYSTEM = (
    "You are a fact-checker. Decide whether the CLAIM is fully SUPPORTED by real-world facts, or "
    "NOT_SUPPORTED (any part is false, unverifiable, or contradicted). Multi-hop claims chain several "
    "facts — verify EACH atomic part; the claim is SUPPORTED only if ALL parts hold. Reason briefly, "
    "then end with a line EXACTLY:\nAnswer: SUPPORTED   or   Answer: NOT_SUPPORTED"
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
            r["question"] = r.get("question", r.get("claim", ""))
            r["answer"] = str(r.get("answer", r.get("label", ""))).strip().upper()
            r.setdefault("family", "hop%s" % r.get("num_hops", "?"))
            out.append(r)
    return out


def build_prompt(task, mem):
    body = _SYSTEM + "\n\n# Claim\n" + task.get("question", "") + "\n\nEnd with 'Answer: SUPPORTED' or 'Answer: NOT_SUPPORTED'."
    return (mem + "\n\n" + body) if mem else body


def _answer_region(resp):
    s = resp or ""
    hits = list(re.finditer(r"(?im)^\s*answer\s*:\s*(.+?)\s*$", s))
    if hits:
        return hits[-1].group(1).strip()
    lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def _label(text):
    """Map free text to SUPPORTED / NOT_SUPPORTED / '' (unknown). NOT-checks come first so
    'not supported' never falls through to SUPPORTED."""
    t = (text or "").lower()
    if re.search(r"not[\s_-]*support|unsupport|refut|contradict|\bfalse\b|incorrect|disprov", t):
        return "NOT_SUPPORTED"
    if re.search(r"support|\btrue\b|entail|\bverified\b|\bcorrect\b", t):
        return "SUPPORTED"
    return ""


def score(task, response):
    gold = str(task.get("answer", "")).strip().upper()
    pred = _label(_answer_region(response or "")) or _label(response or "")
    em = 1.0 if pred and pred == gold else 0.0
    return {"em": em, "f1": em, "sub_em": em, "predicted_answer": (pred or "(none)"),
            "gold_answers": [gold], "_pred_raw": pred, "_reason": "" if em else "wrong verdict"}


def verify(task, attempt):
    """REFERENCE-FREE format check (reads no gold): did the model produce a clear verdict?"""
    if not _label(_answer_region(attempt or "")):
        return {"ok": False, "signature": "no-verdict",
                "feedback": "You did not give a clear verdict. End with 'Answer: SUPPORTED' or "
                            "'Answer: NOT_SUPPORTED'."}
    return {"ok": True, "signature": "", "feedback": ""}


def evidence(task, response, ev):
    correct = ev["em"] == 1.0
    return {
        "outcome": "PASS" if correct else "FAIL",
        "task": "HoVer [%s]: %s" % (task.get("family", ""), task.get("question", "")[:500]),
        "predicted": "verdict: %s" % (ev.get("_pred_raw", "") or "(none)"),
        "gold": str(task.get("answer", "")),
        "diagnosis": "" if correct else (
            "Wrong verdict on a %s claim. The reliable procedure: DECOMPOSE the claim into its atomic "
            "factual sub-claims, verify EACH independently, and mark SUPPORTED only if ALL hold "
            "(one false part => NOT_SUPPORTED). Record this verification PROCEDURE, not this claim's "
            "answer." % task.get("family", "multi-hop")),
    }


def summarize(task, response, ev):
    return (
        "USER TASK (HoVer [%s] claim verification):\n%s\n\nWAS CORRECT: %s\nPREDICTED: %s   GOLD: %s\n\n"
        "RESPONSE (truncated):\n%s"
        % (task.get("family", ""), task.get("question", "")[:600], ev["em"] == 1.0,
           ev.get("_pred_raw", ""), task.get("answer", ""), (response or "")[:600])
    )
