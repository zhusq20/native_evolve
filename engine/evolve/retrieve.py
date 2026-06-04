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


_RETRIEVE_HEADER = (
    "Relevant experience learned from past tasks. "
    "If you rely on any item, cite its [id] at the very end of your final answer "
    "so it can be reinforced:\n"
)


def _render(selected):
    lines = "\n".join(
        "- [{}] {}".format(b["id"], b.get("content", "")) for b in selected
    )
    return _RETRIEVE_HEADER + lines


def context_block(prompt, k=None):
    """The text injected into the harness context (empty string if nothing relevant)."""
    selected = select(prompt, k)
    return _render(selected) if selected else ""


def select_and_block(prompt, k=None):
    """Like context_block, but ALSO return the ids that were injected.

    The harness credits exactly these ids after the task is graded (deterministic
    presence/gold attribution in curate.credit), which is what lets uses/helpful
    climb and the promotion gate fire. The cite-[id] channel the header asks for is
    unusable under the envs' answer-only / code-only output formats, so attribution
    cannot rely on the agent echoing ids back.
    """
    selected = select(prompt, k)
    if not selected:
        return "", []
    return _render(selected), [b["id"] for b in selected]


# --- skill tier: promoted, verified skills fed back into the target (two-tier) ---
def _skill_summary(md, max_body=560):
    """Compact a SKILL.md into (description, truncated body) for injection."""
    desc, body = "", md
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", md, re.S)
    if m:
        fm, body = m.group(1), m.group(2)
        dm = re.search(r"^description:\s*(.+)$", fm, re.M)
        if dm:
            desc = dm.group(1).strip()
    body = body.strip()
    if len(body) > max_body:
        body = body[:max_body].rstrip() + " …"
    return desc, body


def _active_skills_with_value():
    """Active promoted skills + a proven-ness score (max uses among source bullets)."""
    state = store.load_skill_state()
    by_id = {b["id"]: b for b in store.load()}
    out = []
    for name, rec in state.items():
        if rec.get("status") != "active":
            continue
        md_path = config.SKILLS_DIR / name / "SKILL.md"
        if not md_path.exists():
            continue
        srcs = rec.get("promoted_from", [])
        value = max((by_id.get(i, {}).get("uses", 0) for i in srcs), default=0)
        out.append({"name": name, "md": md_path.read_text(encoding="utf-8"), "value": value})
    return out


def skills_block(prompt, k=3):
    """Inject the top-k active gated skills (tier 2), ranked by relevance then proven-ness.

    Promoted skills are proven-general, so we always surface up to k of them (preferring
    lexical relevance to this task, breaking ties by how often their source memory was
    used). This is the feedback path that makes promotion BENEFICIAL: a lesson that
    graduates from volatile top-k memory into a verified skill stays available — always.
    Bounded at k, so it stays compact (the C1 contrast with ACE's dump-everything playbook).
    """
    skills = _active_skills_with_value()
    if not skills:
        return ""
    q = _tokens(prompt)
    scored = []
    for s in skills:
        overlap = len(_tokens(s["md"]) & q)
        scored.append((overlap, s["value"], s))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    parts = []
    for _, _, s in scored[:k]:
        desc, body = _skill_summary(s["md"])
        parts.append("### %s\n%s\n%s" % (s["name"], desc, body))
    return (
        "Verified skills promoted from experience proven across many past tasks "
        "(apply those relevant to this task):\n\n" + "\n\n".join(parts)
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
