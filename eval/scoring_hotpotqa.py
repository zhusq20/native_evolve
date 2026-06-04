"""HotpotQA answer scoring, vendored faithfully from the official hotpot_evaluate_v1.py.

Pure python, no deps. SQuAD-style normalization + token-F1, but with HotpotQA's
yes/no/noanswer special-casing (a comparison answer of 'yes' must match exactly — it
cannot earn partial F1 from token overlap). <answer></answer> extraction mirrors the
SearchQA scorer so build_prompt can keep the same answer-tag contract.

HotpotQA gold is a SINGLE string per question (not a list); evaluate() wraps it into the
env-interface gold_answers list for uniformity with the other envs.
"""
import re
import string
from collections import Counter

_YESNO = ("yes", "no", "noanswer")


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


def exact_match(prediction, gold):
    return 1.0 if normalize_answer(prediction) == normalize_answer(gold) else 0.0


def f1_score(prediction, gold):
    np_, ng = normalize_answer(prediction), normalize_answer(gold)
    # yes/no/noanswer must match exactly — no partial credit from token overlap.
    if np_ in _YESNO and np_ != ng:
        return 0.0
    if ng in _YESNO and np_ != ng:
        return 0.0
    p_tokens, g_tokens = np_.split(), ng.split()
    common = Counter(p_tokens) & Counter(g_tokens)
    same = sum(common.values())
    if same == 0:
        return 0.0
    precision = same / len(p_tokens)
    recall = same / len(g_tokens)
    return 2 * precision * recall / (precision + recall)


def sub_em(prediction, gold):
    p, g = normalize_answer(prediction), normalize_answer(gold)
    if not g:
        return 0.0
    return 1.0 if (g in p or p in g) else 0.0


def evaluate(prediction_text, gold_answer):
    pred = extract_answer(prediction_text)
    return {
        "em": exact_match(pred, gold_answer),
        "f1": f1_score(pred, gold_answer),
        "sub_em": sub_em(pred, gold_answer),
        "predicted_answer": pred,
        "gold_answers": [gold_answer],
    }
