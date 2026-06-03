"""SearchQA scoring, vendored faithfully from SkillOpt's evaluator (pure python).

Kept standalone so we don't import the SkillOpt package (which pulls heavy deps).
EM / token-F1 / substring-EM, SQuAD-style normalization, <answer> extraction.
"""
import re
import string
from collections import Counter


def extract_answer(text):
    if not text:
        return ""
    matches = re.findall(r"<answer>(.*?)</answer>", text, flags=re.IGNORECASE | re.DOTALL)
    if matches:
        return matches[-1].strip()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if lines:
        return lines[-1]
    return text.strip()


def normalize_answer(s):
    s = (s or "").lower()
    s = "".join(ch for ch in s if ch not in set(string.punctuation))
    s = re.sub(r"\b(a|an|the)\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def exact_match(prediction, gold_answers):
    p = normalize_answer(prediction)
    return 1.0 if any(p == normalize_answer(g) for g in gold_answers) else 0.0


def f1_score(prediction, gold_answers):
    p_tokens = normalize_answer(prediction).split()
    best = 0.0
    for g in gold_answers:
        g_tokens = normalize_answer(g).split()
        if not p_tokens or not g_tokens:
            best = max(best, 1.0 if p_tokens == g_tokens else 0.0)
            continue
        common = Counter(p_tokens) & Counter(g_tokens)
        same = sum(common.values())
        if same == 0:
            continue
        precision = same / len(p_tokens)
        recall = same / len(g_tokens)
        best = max(best, 2 * precision * recall / (precision + recall))
    return best


def sub_em(prediction, gold_answers):
    p = normalize_answer(prediction)
    for g in gold_answers:
        gn = normalize_answer(g)
        if gn and (gn in p or p in gn):
            return 1.0
    return 0.0


def evaluate(prediction_text, gold_answers):
    pred = extract_answer(prediction_text)
    return {
        "em": exact_match(pred, gold_answers),
        "f1": f1_score(pred, gold_answers),
        "sub_em": sub_em(pred, gold_answers),
        "predicted_answer": pred,
        "gold_answers": gold_answers,
    }
