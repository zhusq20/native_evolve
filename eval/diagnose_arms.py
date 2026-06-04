#!/usr/bin/env python3
"""3-arm held-out diagnostic: nothing vs retrieved-memory vs induced-skills.

Settles the root question: does accumulated memory TRANSFER to disjoint tasks (retrieval
arm), and do induced skills help / hurt / stay neutral — measured on the SAME task
instances so difficulty is controlled. Held-out tasks are disjoint from the pilot stream.

Usage:
  NATIVE_EVOLVE_HOME=<pilot home> NATIVE_EVOLVE_MODEL=haiku \
  NATIVE_EVOLVE_LEDGER=/tmp/diag_ledger.jsonl \
  python3 eval/diagnose_arms.py <dataset.json> [seed] [start] [count] [topk_skills]
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

from evolve import induce, verify, store  # noqa: E402
import envs as envs_pkg  # noqa: E402


def _tok(s):
    return set(re.findall(r"\w+", (s or "").lower()))


def main():
    tasks_path = sys.argv[1]
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    start = int(sys.argv[3]) if len(sys.argv) > 3 else 32
    count = int(sys.argv[4]) if len(sys.argv) > 4 else 15
    topk = int(sys.argv[5]) if len(sys.argv) > 5 else 2

    env = envs_pkg.get_env("spreadsheetbench")
    all_tasks = env.load_tasks(tasks_path)
    random.Random(seed).shuffle(all_tasks)
    heldout = all_tasks[start:start + count]
    sys.stderr.write("held-out: %d tasks (idx %d..%d)\n" % (len(heldout), start, start + count - 1))

    # memory arm: top-8 lexical retrieval over ALL accumulated lessons (active+promoted),
    # i.e. the memory an online ours_mem would carry (no promotion drains it here).
    pool = [b for b in store.load() if b.get("status") in ("active", "promoted")]

    def memory_block(t):
        q = _tok(t.get("question", ""))
        scored = sorted(pool, key=lambda b: len(_tok(b.get("content", "") + " " + b.get("scope", "")) & q),
                        reverse=True)
        chosen = [b for b in scored if len(_tok(b.get("content", "") + " " + b.get("scope", "")) & q) > 0][:8]
        if not chosen:
            return ""
        return ("Relevant lessons from past tasks (apply if useful):\n"
                + "\n".join("- %s" % b.get("content", "") for b in chosen))

    skills = induce.induce(focus_failures=True)
    sys.stderr.write("induced %d skills: %s\n" % (len(skills), [s["name"] for s in skills]))

    def skills_block(t):
        q = _tok(t.get("question", ""))
        scored = sorted(skills, key=lambda s: len(_tok(s["md"]) & q), reverse=True)
        chosen = [s for s in scored if len(_tok(s["md"]) & q) > 0][:topk]
        return ("## Skills (apply if relevant):\n\n" + "\n\n".join(s["md"] for s in chosen)) if chosen else ""

    arms = {"nothing": lambda t: "", "memory": memory_block, "skills": skills_block}
    out = verify.multi_arm(arms, heldout, env)
    c, n = out["counts"], out["n"] or 1
    print(json.dumps({
        "n": out["n"],
        "rates": {k: round(v / n, 3) for k, v in c.items()},
        "lift_memory_vs_nothing": round((c["memory"] - c["nothing"]) / n, 3),
        "lift_skills_vs_nothing": round((c["skills"] - c["nothing"]) / n, 3),
        "skills": [s["name"] for s in skills],
        "rows": out["rows"],
    }, indent=2))


if __name__ == "__main__":
    main()
