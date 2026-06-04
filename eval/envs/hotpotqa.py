"""HotpotQA environment (distractor setting): multi-hop QA over 10 paragraphs, EM/F1.

The FAMILY-STRUCTURED env the project was missing. Each task carries `type`
(bridge | comparison) and `level` (easy | medium | hard): comparison questions share a
crisp latent procedure ("extract property of A, extract property of B, compare -> yes/no")
that a promoted skill can capture and transfer — the cleanest in-harness test of C1 skill
formation. Distractor setting only (10 gold+distractor paragraphs pasted into the prompt,
exactly like SearchQA context); fullwiki would need 5M-article retrieval and is out of scope.

Scoring is the official HotpotQA answer EM/F1 (vendored, pure python, yes/no-aware).
Track per-`type` EM downstream: comparison answers are often 2-way yes/no, so a flat EM can
hide guessing — the runner logs `id`, join back to `type` for the family breakdown.
"""
import json
import pathlib
import sys
import time
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))  # eval/
import scoring_hotpotqa as _scoring  # noqa: E402

NAME = "hotpotqa"
_MAX_CONTEXT_CHARS = 8000  # 10 Wikipedia intro paragraphs; cap to bound per-task tokens
_DS = "https://datasets-server.huggingface.co/rows"


def load_tasks(path):
    return [json.loads(l) for l in pathlib.Path(path).read_text().splitlines() if l.strip()]


def _context_block(task):
    chunks, total = [], 0
    for title, sents in task.get("paragraphs", []):
        para = " ".join(s.strip() for s in sents).strip()
        block = "### %s\n%s" % (title, para)
        if total + len(block) > _MAX_CONTEXT_CHARS and chunks:
            break
        chunks.append(block)
        total += len(block)
    return "\n\n".join(chunks)


def build_prompt(task, mem):
    head = (
        "Answer the multi-hop question using ONLY the provided context paragraphs. "
        "Reason across the paragraphs as needed (the question may require chaining facts "
        "from more than one). For yes/no questions answer exactly 'yes' or 'no'. "
        "Reply with ONLY the final answer wrapped in <answer></answer> tags — "
        "no explanation, no extra words.\n\n"
        "## Context\n" + _context_block(task) +
        "\n\n## Question\n" + task["question"]
    )
    return (mem + "\n\n" + head) if mem else head


def score(task, response):
    return _scoring.evaluate(response, task["answer"])


def summarize(task, response, ev):
    return (
        "USER TASK (HotpotQA %s/%s multi-hop question):\n%s\n\n"
        "AGENT FINAL OUTPUT:\n%s\n\n"
        "GROUND-TRUTH ANSWER: %s\n"
        "WAS THE AGENT CORRECT (exact match): %s"
        % (task.get("type", ""), task.get("level", ""), task["question"],
           (response or "")[:1500], json.dumps(task["answer"]), ev["em"] == 1.0)
    )


def fetch(n, out, split="validation", config="distractor"):
    """Materialize a HotpotQA distractor task file via the HF datasets-server rows API.

    Normalizes the HF column shape (context = {title:[...], sentences:[[...]]}) into a
    compact paragraphs list [[title, [sent, ...]], ...].
    """
    out = pathlib.Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows, offset = [], 0
    while len(rows) < n:
        length = min(100, n - len(rows))
        url = ("%s?dataset=hotpotqa%%2Fhotpot_qa&config=%s&split=%s&offset=%d&length=%d"
               % (_DS, config, split, offset, length))
        with urllib.request.urlopen(url, timeout=30) as r:
            page = json.loads(r.read().decode("utf-8"))
        batch = page.get("rows", [])
        if not batch:
            break
        for entry in batch:
            row = entry.get("row", {})
            ctx = row.get("context", {}) or {}
            titles = ctx.get("title", []) or []
            sent_groups = ctx.get("sentences", []) or []
            paragraphs = [[titles[i], sent_groups[i]]
                          for i in range(min(len(titles), len(sent_groups)))]
            q, a = row.get("question", ""), row.get("answer", "")
            if q and a:
                rows.append({
                    "id": row.get("id", "hotpot-%d" % offset),
                    "question": q,
                    "answer": a,
                    "type": row.get("type", ""),
                    "level": row.get("level", ""),
                    "paragraphs": paragraphs,
                })
        offset += len(batch)
        time.sleep(0.3)
    with out.open("w", encoding="utf-8") as f:
        for r in rows[:n]:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("wrote %d hotpotqa tasks -> %s" % (min(len(rows), n), out))
