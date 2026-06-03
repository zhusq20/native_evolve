"""Deterministic retrieval: pick the memory bullets relevant to a task prompt.

Lexical overlap + feedback weighting. No embeddings (keeps the deploy dep-free
and within the "only CLI for LLM" constraint). Swap `score()` for a stronger
retriever later without touching the rest of the pipeline.
"""
import re

from . import config, store


def _tokens(text):
    return set(re.findall(r"\w+", (text or "").lower()))


def score(bullet, query_tokens):
    if bullet.get("status") != "active":
        return -1.0
    bag = _tokens(bullet.get("content", "") + " " + bullet.get("scope", ""))
    if not bag:
        return -1.0
    overlap = len(bag & query_tokens)
    return overlap + 0.1 * bullet.get("helpful", 0) - 0.5 * bullet.get("harmful", 0)


def select(prompt, k=None):
    k = k or config.RETRIEVE_TOPK
    q = _tokens(prompt)
    scored = []
    for b in store.load():
        s = score(b, q)
        if s > 0:
            scored.append((s, b))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [b for _, b in scored[:k]]


def context_block(prompt, k=None):
    """The text injected into the harness context (empty string if nothing relevant)."""
    selected = select(prompt, k)
    if not selected:
        return ""
    lines = "\n".join(
        "- [{}] {}".format(b["id"], b.get("content", "")) for b in selected
    )
    return (
        "Relevant experience learned from past tasks. "
        "If you rely on any item, cite its [id] at the very end of your final answer "
        "so it can be reinforced:\n" + lines
    )


def full_playbook_block(cap=60):
    """Inject the ENTIRE active playbook (ACE-style single-tier), not a top-k slice.

    This is the C1 contrast: ACE grows one monolithic context that is injected
    in full every turn (-> context bloat), versus our retrieval + skill promotion.
    """
    active = [b for b in store.load() if b.get("status") == "active"]
    if not active:
        return ""
    active = active[:cap]
    lines = "\n".join("- [{}] {}".format(b["id"], b.get("content", "")) for b in active)
    return (
        "Your accumulated playbook (apply what is relevant; cite [id]s you use "
        "at the end of your final answer):\n" + lines
    )
