"""Promotion gate: a high-value memory bullet -> a verified Agent Skill.

A bullet is a candidate once it has proven useful across several tasks
(helpful/uses thresholds, zero harm). The LLM drafts a SKILL.md; the draft is
then verified by *replaying stored cases* before it is allowed to go live.

Replay verification needs a benchmark (memory/replay/*.json). With none present
the draft is STAGED under memory/skill_candidates/ for human review instead of
auto-activating — honest behaviour for a fresh deployment. Set
NATIVE_EVOLVE_AUTO_PROMOTE=1 to skip the gate (not recommended in production).
"""
import json
import pathlib
import re
import tempfile

from . import config, llm, store


def _slug(text):
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:48] or "skill"


def candidates():
    out = []
    for b in store.load():
        if (
            b.get("status") == "active"
            and b.get("helpful", 0) >= config.PROMOTE_HELPFUL
            and b.get("uses", 0) >= config.PROMOTE_USES
            and b.get("harmful", 0) == 0
        ):
            out.append(b)
    return out


def draft_skill(bullet):
    template = (config.PROMPTS_DIR / "skill_writer.md").read_text(encoding="utf-8")
    prompt = (
        template
        + "\n\n=== EXPERIENCE TO PACKAGE ===\n"
        + bullet.get("content", "")
        + "\nscope: "
        + bullet.get("scope", "")
    )
    return llm.call_claude(prompt, allowed_tools="Read")


def _replay_cases():
    cases = []
    if config.REPLAY_DIR.exists():
        for f in sorted(config.REPLAY_DIR.glob("*.json")):
            try:
                cases.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                pass
    return cases


def gate_pass(name, md):
    """Return pass-rate in [0,1], or None when there is no benchmark to verify against.

    Each replay case is {"task": "...", "expect_substring": "..."}. The candidate
    skill is dropped into a throwaway project root so Claude discovers it natively.
    """
    cases = _replay_cases()
    if not cases:
        return None
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        sdir = root / ".claude" / "skills" / name
        sdir.mkdir(parents=True, exist_ok=True)
        (sdir / "SKILL.md").write_text(md, encoding="utf-8")
        passed = 0
        for c in cases:
            task = c.get("task", "")
            expect = c.get("expect_substring", "")
            if not task:
                continue
            try:
                out = llm.call_claude(
                    task,
                    allowed_tools="Read,Bash,Skill",
                    cwd=str(root),
                    setting_sources="project",  # project root is empty except our skill
                )
            except Exception:
                out = ""
            if expect and expect.lower() in (out or "").lower():
                passed += 1
        return passed / max(1, len(cases))


def _write_skill(name, md, status, bullet, rate):
    if status == "active":
        config.ensure_skill_link()   # keep .claude/skills -> ../skills before publishing
    target = (config.SKILLS_DIR if status == "active" else config.CANDIDATE_DIR) / name
    target.mkdir(parents=True, exist_ok=True)
    (target / "SKILL.md").write_text(md, encoding="utf-8")

    state = store.load_skill_state()
    rec = state.get(name, {"version": 0, "promoted_from": []})
    rec["version"] = rec.get("version", 0) + 1
    if bullet["id"] not in rec.get("promoted_from", []):
        rec.setdefault("promoted_from", []).append(bullet["id"])
    rec["status"] = status
    if rate is not None:
        rec["pass_rate"] = round(rate, 3)
    state[name] = rec
    store.save_skill_state(state)

    # mark the source bullet so it is not re-promoted forever
    items = store.load()
    for it in items:
        if it["id"] == bullet["id"]:
            it["status"] = "promoted"
    store.save(items)


def run():
    """Scan for promotable bullets and (gate) promote them. Returns names touched."""
    state = store.load_skill_state()
    touched = []
    for b in candidates():
        name = _slug(b.get("scope") or b.get("content", "")[:30])
        if state.get(name, {}).get("status") == "active":
            continue
        md = draft_skill(b)
        rate = gate_pass(name, md)
        if rate is None:
            status = "active" if config.AUTO_PROMOTE else "candidate"
        else:
            status = "active" if rate >= config.GATE_PASS_RATE else "candidate"
        _write_skill(name, md, status, b, rate)
        touched.append((name, status, rate))
    return touched
