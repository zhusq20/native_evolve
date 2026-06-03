"""GSM8K environment (grade-school math word problems, exact numeric scoring).

A different modality from SearchQA: weak models (haiku) make arithmetic and
output-format errors, so learned procedural discipline ("compute step by step,
put the final number after ####") has real headroom — closer to the paper's
procedural-skill thesis.
"""
import json
import pathlib
import re
import time
import urllib.request

NAME = "gsm8k"
_DS = "https://datasets-server.huggingface.co/rows"


def _extract_num(text):
    if text is None:
        return None
    t = str(text)
    m = re.findall(r"####\s*([-+]?[\d,]*\.?\d+)", t)
    if not m:
        m = re.findall(r"<answer>\s*([-+]?[\d,]*\.?\d+)", t, flags=re.IGNORECASE)
    if not m:
        m = re.findall(r"[-+]?[\d,]*\.?\d+", t)  # fallback: last number
    if not m:
        return None
    try:
        return float(m[-1].replace(",", ""))
    except ValueError:
        return None


def load_tasks(path):
    return [json.loads(l) for l in pathlib.Path(path).read_text().splitlines() if l.strip()]


def build_prompt(task, mem):
    head = (
        "Solve the math word problem. Show brief step-by-step reasoning, then output "
        "the final answer as a plain number on its own line after '####'. "
        "Example final line: '#### 42'.\n\n"
        "Problem:\n" + task["question"]
    )
    return (mem + "\n\n" + head) if mem else head


def score(task, response):
    pred = _extract_num(response)
    gold = task.get("gold")
    if gold is None:
        gold = _extract_num(task.get("answer"))
    em = 1.0 if (pred is not None and gold is not None and abs(pred - gold) < 1e-6) else 0.0
    return {"em": em, "f1": em, "sub_em": em,
            "predicted_answer": ("" if pred is None else str(pred)), "gold_answers": [gold]}


def summarize(task, response, ev):
    return (
        "USER TASK (GSM8K math problem):\n" + task["question"][:1200] +
        "\n\nAGENT FINAL OUTPUT:\n" + (response or "")[:1500] +
        "\n\nGOLD ANSWER: " + str(ev.get("gold_answers", [None])[0]) +
        "\nWAS THE AGENT CORRECT: " + str(ev["em"] == 1.0)
    )


def fetch(n, out, split="test"):
    out = pathlib.Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows, offset = [], 0
    while len(rows) < n:
        length = min(100, n - len(rows))
        url = "%s?dataset=openai%%2Fgsm8k&config=main&split=%s&offset=%d&length=%d" % (_DS, split, offset, length)
        with urllib.request.urlopen(url, timeout=30) as r:
            page = json.loads(r.read().decode("utf-8"))
        batch = page.get("rows", [])
        if not batch:
            break
        for entry in batch:
            row = entry.get("row", {})
            q = row.get("question", "")
            ans = row.get("answer", "")
            gold = _extract_num(ans)
            if q and gold is not None:
                rows.append({"id": "gsm-%d" % offset, "question": q, "answer": ans, "gold": gold})
            offset += 1
        time.sleep(0.3)
    with out.open("w", encoding="utf-8") as f:
        for r in rows[:n]:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("wrote %d gsm8k tasks -> %s" % (min(len(rows), n), out))
