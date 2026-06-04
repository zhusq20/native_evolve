"""Episodic memory: raw task -> solution -> outcome traces, retrieved as few-shot exemplars.

Motivated by the agentic-memory finding that LLM CONSOLIDATION (rewriting episodes into
abstract lessons/skills) is often faulty and can fall below the no-memory baseline, while an
episodic-only control that simply RETAINS raw trajectories stays competitive. So we treat raw
episodes as first-class evidence: append-only (never rewritten/overwritten), and retrieve a
similar PAST SUCCESS as a worked example. For code-gen this is the most direct, lowest-risk
form of memory — no lossy consolidation step between the experience and its use.
"""
import json
import re

from . import config


def _path():
    return config.MEMORY_DIR / "episodes.jsonl"


def _tokens(text):
    return set(re.findall(r"\w+", (text or "").lower()))


def record(task_id, question, solution, passed, signature=""):
    """Append one raw episode. Non-destructive by construction (append-only).

    `signature` is the reference-free failure CLASS this trajectory encountered (from env.verify,
    e.g. 'formula-string-in-target', 'verbose-answer'); "" if the first attempt verified cleanly.
    A PASSED episode carrying a signature is a worked FIX for that failure mode — retrievable by
    signature across lexically-unrelated tasks, which is how a diverse / no-shared-procedure env
    still accumulates shared *failure* knowledge."""
    config.MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    rec = {"id": task_id, "question": question or "", "solution": solution or "",
           "passed": bool(passed), "signature": signature or ""}
    with open(_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def load():
    p = _path()
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out


def retrieve(query, k=2, successes_only=True):
    """Top-k past episodes most lexically similar to `query` (prefer successes)."""
    eps = load()
    if successes_only:
        eps = [e for e in eps if e.get("passed")]
    if not eps:
        return []
    q = _tokens(query)
    scored = sorted(eps, key=lambda e: len(_tokens(e.get("question", "")) & q), reverse=True)
    return [e for e in scored if len(_tokens(e.get("question", "")) & q) > 0][:k]


def exemplar_block(query, k=2, max_solution_chars=1100, max_q_chars=400):
    """Inject up to k similar past SUCCESSES as worked examples (empty if none)."""
    eps = retrieve(query, k)
    if not eps:
        return ""
    parts = []
    for e in eps:
        sol = (e.get("solution", "") or "")[:max_solution_chars]
        parts.append("### A similar task you previously solved CORRECTLY\nTask: %s\nYour working solution:\n%s"
                     % ((e.get("question", "") or "")[:max_q_chars], sol))
    return ("Worked examples retrieved from your past successes — adapt the approach to the "
            "current task (do not copy blindly):\n\n" + "\n\n".join(parts))


def retrieve_by_signature(query, signature, k=2):
    """Past SUCCESSES that overcame the SAME failure signature, ranked by query similarity.
    Keyed by failure MODE rather than task topic, so a fix transfers across unrelated tasks."""
    if not signature:
        return []
    eps = [e for e in load() if e.get("passed") and e.get("signature") == signature]
    if not eps:
        return []
    q = _tokens(query)
    eps.sort(key=lambda e: len(_tokens(e.get("question", "")) & q), reverse=True)
    return eps[:k]


def repair_hint(query, signature, max_solution_chars=900, max_q_chars=300):
    """A worked FIX for the failure mode just hit: the most query-similar past SUCCESS that
    overcame the SAME signature. Returns "" if none yet (graceful: the loop runs without a hint).
    Reference-free — uses only past episodes, valid at frozen-test time."""
    eps = retrieve_by_signature(query, signature, k=1)
    if not eps:
        return ""
    e = eps[0]
    return ("When you previously hit the same failure (%s), THIS solution worked on a similar task:\n"
            "Task: %s\nWorking solution:\n%s"
            % (signature, (e.get("question", "") or "")[:max_q_chars],
               (e.get("solution", "") or "")[:max_solution_chars]))
