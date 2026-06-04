#!/usr/bin/env python3
"""Counterfactual validation of LLM-induced skills.

Induce skills from an accumulated memory store (NATIVE_EVOLVE_HOME), then A/B them on a
HELD-OUT slice of SB tasks (disjoint from the pilot's 0:32 stream) — with vs without the
skills injected, scored by the official cell-compare. Answers: are the induced skills
actually useful (do they lift held-out accuracy)?

Usage:
  NATIVE_EVOLVE_HOME=<pilot home> NATIVE_EVOLVE_MODEL=haiku \
  NATIVE_EVOLVE_LEDGER=/tmp/verify_ledger.jsonl \
  python3 eval/verify_induced.py <dataset.json> [seed] [start] [count]
"""
import json
import pathlib
import random
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
ENGINE = REPO / "engine"
sys.path.insert(0, str(ENGINE))
sys.path.insert(0, str(REPO / "eval"))

from evolve import induce, verify  # noqa: E402
import envs as envs_pkg  # noqa: E402


def main():
    tasks_path = sys.argv[1]
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    start = int(sys.argv[3]) if len(sys.argv) > 3 else 32
    count = int(sys.argv[4]) if len(sys.argv) > 4 else 10
    topk = int(sys.argv[5]) if len(sys.argv) > 5 else 2   # relevance-gated injection: skills per task

    env = envs_pkg.get_env("spreadsheetbench")
    all_tasks = env.load_tasks(tasks_path)
    random.Random(seed).shuffle(all_tasks)          # same shuffle as the pilot
    heldout = all_tasks[start:start + count]         # disjoint from pilot stream [0:32]
    sys.stderr.write("held-out: %d tasks (idx %d..%d)\n" % (len(heldout), start, start + count - 1))

    skills = induce.induce(focus_failures=True)
    sys.stderr.write("induced %d skills: %s\n" % (len(skills), [s["name"] for s in skills]))
    if not skills:
        sys.stderr.write("no skills induced; abort\n")
        return

    header = "## Skills for this task (apply those relevant):\n\n"

    def _tokens(s):
        return set(re.findall(r"\w+", (s or "").lower()))

    def skills_for(task):
        """Relevance-gate: inject only the top-k induced skills lexically relevant to THIS task."""
        q = _tokens(task.get("question", ""))
        scored = sorted(skills, key=lambda s: len(_tokens(s["md"]) & q), reverse=True)
        chosen = [s for s in scored if len(_tokens(s["md"]) & q) > 0][:topk]
        return (header + "\n\n".join(s["md"] for s in chosen)) if chosen else ""

    res = verify.ab_eval(skills_for, heldout, env)
    n = res["n"] or 1
    print(json.dumps({
        "n": res["n"],
        "topk_injected": topk,
        "tasks_with_skills": sum(1 for r in res["rows"] if r.get("had_skills")),
        "without_rate": round(res["without"] / n, 3),
        "with_rate": round(res["with"] / n, 3),
        "lift": round((res["with"] - res["without"]) / n, 3),
        "skills": [s["name"] for s in skills],
        "rows": res["rows"],
    }, indent=2))


if __name__ == "__main__":
    main()
