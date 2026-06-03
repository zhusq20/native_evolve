"""SearchQA environment (context-grounded trivia QA, EM/F1 scoring)."""
import json
import pathlib
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
