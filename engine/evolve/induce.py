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

from . import config, episodic, llm, store


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


def _episode_digest(eps, max_items=40, max_q=600, max_sol=800):
    """Render a cluster's TRAIN episodes (raw task -> outcome -> solution) as the inducer's input.
    Shows both FIXED and FAILED traces so the inducer can package the pitfall AND its fix."""
    lines = []
    for e in eps[:max_items]:
        tag = "FIXED" if e.get("passed") else "FAILED"
        lines.append("[%s | sig=%s] Task: %s\nSolution:\n%s"
                     % (tag, e.get("signature", ""), (e.get("question", "") or "").strip()[:max_q],
                        (e.get("solution", "") or "").strip()[:max_sol]))
    return "\n\n".join(lines)


def induce_clustered(min_cluster=4, gate_min=2):
    """Cluster raw EPISODES by failure `signature`, split each cluster TRAIN/GATE (deterministic by
    id), and induce one skill per cluster from the TRAIN half ONLY. Returns a list of
    {"name","md","skill","signature","train_eps","gate_eps"} — the caller gates each skill on its own
    held-out GATE half (within-cluster A/B), so the gate set is same-failure-mode but instance-disjoint
    from what wrote the skill (no leakage). gate_eps NEVER enters the inducer prompt.

    A cluster is skipped (no candidate) when it cannot supply both halves: fewer than `min_cluster`
    episodes, or fewer than `gate_min` on the gate side — honest: no held-out evidence, no promotion.
    """
    eps = episodic.load()
    bysig = {}
    for e in eps:
        sig = e.get("signature") or ""
        if sig:                                   # signature == "" -> clean first pass, no failure mode
            bysig.setdefault(sig, []).append(e)
    template = (config.PROMPTS_DIR / "skill_inducer.md").read_text(encoding="utf-8")
    out = []
    for sig, group in sorted(bysig.items()):
        group = sorted(group, key=lambda e: str(e.get("id", "")))   # deterministic split (no RNG)
        if len(group) < min_cluster:
            continue
        cut = len(group) // 2
        train_eps, gate_eps = group[:cut], group[cut:]
        if not train_eps or len(gate_eps) < gate_min:
            continue
        raw = llm.call_claude(
            template + "\n\n=== FAILURE-MODE SAMPLES (signature=%s) ===\n" % sig
            + _episode_digest(train_eps), allowed_tools="Read")
        obj = llm.extract_json(raw) or {}
        skills = obj.get("skills", []) if isinstance(obj, dict) else []
        for sk in skills:
            if not isinstance(sk, dict):
                continue
            md, name = render_skill_md(sk)
            out.append({"name": name, "md": md, "skill": sk, "signature": sig,
                        "train_eps": train_eps, "gate_eps": gate_eps})
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
