"""SearchQA environment (context-grounded trivia QA, EM/F1 scoring)."""
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))  # eval/
import scoring_searchqa as _scoring  # noqa: E402

NAME = "searchqa"


def load_tasks(path):
    return [json.loads(l) for l in pathlib.Path(path).read_text().splitlines() if l.strip()]


def build_prompt(task, mem):
    head = (
        "Answer the question using ONLY the provided context. "
        "Reply with ONLY the final answer wrapped in <answer></answer> tags — "
        "no explanation, no extra words.\n\n"
        "## Context\n" + (task.get("context", "") or "")[:4000] +
        "\n\n## Question\n" + task["question"]
    )
    return (mem + "\n\n" + head) if mem else head


def score(task, response):
    return _scoring.evaluate(response, task["answers"])


def summarize(task, response, ev):
    return (
        "USER TASK (SearchQA question):\n" + task["question"] +
        "\n\nAGENT FINAL OUTPUT:\n" + (response or "")[:1500] +
        "\n\nGROUND-TRUTH ANSWERS: " + json.dumps(task["answers"]) +
        "\nWAS THE AGENT CORRECT (exact match): " + str(ev["em"] == 1.0)
    )


def _form_diagnosis(response, pred, golds):
    """Grounded, gold-allowed diagnosis of WHY the normalized EM failed: the concrete
    form-level mismatch (no answer tag / extra words / articles / wrong span) that a
    transferable format heuristic should fix. Train-time only (reads gold)."""
    notes = []
    if not response or "<answer>" not in response.lower():
        notes.append("Output had NO <answer>...</answer> tag (the scorer fell back to the last "
                     "line). Always wrap ONLY the final answer in <answer></answer>.")
    np = _scoring.normalize_answer(pred)
    best = min(golds, key=lambda g: abs(len(_scoring.normalize_answer(g).split()) - len(np.split())),
               default="")
    ng = _scoring.normalize_answer(best)
    pt, gt = np.split(), ng.split()
    extra = [w for w in pt if w not in gt]
    missing = [w for w in gt if w not in pt]
    notes.append("After SQuAD normalization (lowercase, drop punctuation + a/an/the): "
                 "pred=%r vs nearest gold=%r." % (np, ng))
    if extra:
        notes.append("Pred has EXTRA tokens not in gold: %s (answer too verbose / copied prompt "
                     "words / added qualifiers — emit only the minimal answer span)." % extra)
    if missing:
        notes.append("Pred is MISSING gold tokens: %s (wrong granularity / incomplete span)." % missing)
    if np and ng and len(pt) > len(gt) and all(w in pt for w in gt):
        notes.append("Pred CONTAINS the gold but with extra words — the substring is right; trim to it.")
    return "\n".join(notes)


def evidence(task, response, ev):
    golds = task.get("answers", []) or []
    correct = ev["em"] == 1.0
    return {
        "outcome": "PASS" if correct else "FAIL",
        "task": "SearchQA question: " + task["question"],
        "predicted": "extracted answer: %r  (raw output: %s)"
                     % (ev.get("predicted_answer", ""), (response or "")[:300]),
        "gold": json.dumps(golds),
        "diagnosis": "" if correct else _form_diagnosis(response, ev.get("predicted_answer", ""), golds),
    }


def verify(task, attempt):
    """REFERENCE-FREE format/grounding check. Reads ONLY the task context + the attempt — NEVER
    task['answers'] (gold) — so it is valid to run during the frozen TEST phase. Flags the dominant
    exact-match failure modes (missing/empty answer tag, an explanation instead of a span, an answer
    with no support in the context). Returns None when nothing is wrong (no repair fires)."""
    text = attempt or ""
    tags = re.findall(r"<answer>(.*?)</answer>", text, flags=re.IGNORECASE | re.DOTALL)
    if not tags:
        return {"ok": False, "signature": "no-answer-tag",
                "feedback": "Your output had no <answer>...</answer> tag. Wrap ONLY the final answer "
                            "in <answer></answer> with no other text."}
    ans = tags[-1].strip()
    if not ans:
        return {"ok": False, "signature": "empty-answer",
                "feedback": "The <answer> tag was empty. Put the minimal answer span inside it."}
    nwords = len(ans.split())
    if nwords > 15:
        return {"ok": False, "signature": "verbose-answer",
                "feedback": "Your answer is %d words — far too long for an exact-match answer. Return "
                            "ONLY the minimal answer span (usually 1-5 words), no explanation." % nwords}
    ctx = task.get("context", "") or ""
    if ctx:
        ctx_tokens = set(_scoring.normalize_answer(ctx).split())
        ans_tokens = set(_scoring.normalize_answer(ans).split())
        if ans_tokens and not (ans_tokens & ctx_tokens):
            return {"ok": False, "signature": "ungrounded-answer",
                    "feedback": "None of your answer's words appear in the provided context. Answer "
                                "using ONLY facts from the context and extract the exact span."}
    return {"ok": True, "signature": "", "feedback": ""}
