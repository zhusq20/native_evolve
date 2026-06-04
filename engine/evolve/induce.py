"""LLM skill induction: synthesize a SMALL set of high-leverage, reusable skills
from the accumulated memory — instead of inflating one bullet into one skill.

This is the "useful skill production" path. The LLM clusters related lessons
(especially recurring failure->fix pitfalls) into coherent, generalizing, actionable
skills. It READS memory (never rewrites it, so the determinism / anti-context-collapse
rule stays intact) and emits skills as additive artifacts. Whether an induced skill is
actually USEFUL is then decided by a counterfactual gate (with-skill vs without-skill on
held-out tasks), not by retrieval frequency — see verify.counterfactual_gate.
"""
import re

from . import config, llm, store


def _slug(text):
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:48] or "skill"


def _is_failure_derived(b):
    """A lesson born from a failure: a pitfall, or content with failure-language."""
    t = b.get("type", "")
    c = (b.get("content", "") or "").lower()
    return t == "pitfall" or any(w in c for w in (
        "fail", "error", "wrong", "avoid", "don't", "doesn't", "silent",
        "corrupt", "mismatch", "missing", "incorrect"))


def memory_digest(items, max_items=120, focus_failures=False):
    """Render active/promoted memory bullets (with stats) as the inducer's input.

    focus_failures=True keeps only failure-derived lessons (pitfalls / failure-language)
    so induction targets real failure bottlenecks rather than restating good practice.
    Most-proven first, so truncation (if any) keeps the highest-signal lessons.
    """
    pool = [b for b in items if b.get("status") in ("active", "promoted")]
    if focus_failures:
        fpool = [b for b in pool if _is_failure_derived(b)]
        if fpool:
            pool = fpool
    pool.sort(key=lambda b: (b.get("uses", 0) + b.get("helpful", 0)), reverse=True)
    lines = []
    for b in pool[:max_items]:
        lines.append(
            "[%s] (type=%s | scope=%s | uses=%d helpful=%d harmful=%d) %s"
            % (b["id"], b.get("type", ""), b.get("scope", ""), b.get("uses", 0),
               b.get("helpful", 0), b.get("harmful", 0), (b.get("content", "") or "").strip())
        )
    return "\n".join(lines)


def render_skill_md(skill):
    """Turn an induced-skill dict into (SKILL.md text, slug-name)."""
    name = _slug(skill.get("name", ""))
    desc = (skill.get("description") or skill.get("scope") or name).strip().replace("\n", " ")
    when = skill.get("when_to_use") or []
    if isinstance(when, str):
        when = [when]
    steps = skill.get("steps") or []
    if isinstance(steps, str):
        steps = [steps]
    out = ["---", "name: %s" % name, "description: %s" % desc, "---", "", "## When to use"]
    out += ["- %s" % w for w in when] or ["- (unspecified)"]
    out += ["", "## Steps"]
    out += ["%d. %s" % (i, s) for i, s in enumerate(steps, 1)] or ["1. (unspecified)"]
    return "\n".join(out) + "\n", name


def induce(model_items=None, focus_failures=True):
    """Synthesize skills from current memory. Returns a list of
    {"name", "md", "skill"} dicts (no disk writes — caller/gate decides activation).

    focus_failures=True (default) induces from failure-derived lessons only, so skills
    target real bottlenecks (correct-but-idle tips don't help and only dilute context).
    """
    items = model_items if model_items is not None else store.load()
    digest = memory_digest(items, focus_failures=focus_failures)
    if not digest.strip():
        return []
    template = (config.PROMPTS_DIR / "skill_inducer.md").read_text(encoding="utf-8")
    raw = llm.call_claude(
        template + "\n\n=== ACCUMULATED MEMORY ===\n" + digest, allowed_tools="Read"
    )
    obj = llm.extract_json(raw) or {}
    skills = obj.get("skills", []) if isinstance(obj, dict) else []
    out = []
    for sk in skills:
        if not isinstance(sk, dict):
            continue
        md, name = render_skill_md(sk)
        out.append({"name": name, "md": md, "skill": sk})
    return out


def write_skill(item, status="active"):
    """Publish an induced skill to disk + skill_state. NON-DESTRUCTIVE: never touches the
    memory store (the source bullets stay active and retrievable — we consolidate WITHOUT
    overwriting the evidence). `item` is a dict from induce(): {"name","md","skill"}.
    """
    name, md, sk = item["name"], item["md"], item.get("skill", {})
    if status == "active":
        config.ensure_skill_link()
    target = (config.SKILLS_DIR if status == "active" else config.CANDIDATE_DIR) / name
    target.mkdir(parents=True, exist_ok=True)
    (target / "SKILL.md").write_text(md, encoding="utf-8")
    state = store.load_skill_state()
    rec = state.get(name, {"version": 0})
    rec["version"] = rec.get("version", 0) + 1
    rec["status"] = status
    rec["source_ids"] = sk.get("source_ids", [])
    state[name] = rec
    store.save_skill_state(state)
    return name
