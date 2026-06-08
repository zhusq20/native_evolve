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
import os
import pathlib
import re
import shutil
import tempfile

from . import config, llm, store

# DEPLOY consolidation cadence: induce+gate is expensive (claude calls), so don't pay it on every Stop
# reflection — only every Nth. Credit (cheap, deterministic) still runs every reflection.
DEPLOY_INDUCE_EVERY = int(os.environ.get("NATIVE_EVOLVE_DEPLOY_INDUCE_EVERY", "8"))


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


def _reflect_tick():
    """Increment + return the deploy reflection counter (so consolidation is frequency-gated)."""
    p = config.MEMORY_DIR / ".reflect_count"
    n = 0
    try:
        if p.exists():
            n = int((p.read_text(encoding="utf-8") or "0").strip() or "0")
    except Exception:
        n = 0
    n += 1
    try:
        config.MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        p.write_text(str(n), encoding="utf-8")
    except Exception:
        pass
    return n


def _deploy_catalog_solve(task, extra):
    """Solve one replay task with the DEPLOY-faithful native catalog (materialized memory + ALL
    authored skills + `extra` candidate skills as discoverable), via native skill discovery — the
    SAME mechanism deploy inference uses. Returns the model's text (or "" on error)."""
    from . import materialize
    sandbox = tempfile.mkdtemp(prefix="deploy_gate_")
    sdir = os.path.join(sandbox, ".claude", "skills")
    try:
        materialize.materialize_into(sdir, include_promoted=False, extra_skills=extra)
        materialize.link_all_skills(sdir)             # deploy-faithful: surface all authored skills
        try:
            return llm.call_claude(
                task, allowed_tools="Read,Bash,Skill", cwd=sandbox, add_dir=sandbox,
                setting_sources="project", permission_mode="bypassPermissions",
                max_turns=6, max_retries=1) or ""
        except Exception:
            return ""
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


def consolidate_deploy():
    """DEPLOY consolidation, ALIGNED with the experiment (replaces the legacy per-bullet `run()`):
    cluster memory into candidate skills via `induce.induce` (NOT one-skill-per-bullet), then GATE
    them against the replay cases (the deploy held-out benchmark) with the experiment's SAME accept
    rule (`verify.rolling_decision`, native with/without A/B). With NO replay benchmark there is no
    held-out evidence, so candidates are STAGED for review (honest — never auto-activate blind).
    Frequency-gated (every DEPLOY_INDUCE_EVERY reflections). Returns [(name, status), ...]."""
    from . import induce, verify, materialize
    if _reflect_tick() % DEPLOY_INDUCE_EVERY != 0:
        return []
    cands = induce.induce(focus_failures=True)
    if not cands:
        return []
    cases = _replay_cases()
    if not cases:
        for c in cands:
            induce.write_skill(c, status="candidate")     # no held-out set -> stage (honest)
        materialize.assemble_deploy_catalog()
        return [(c["name"], "candidate") for c in cands]
    # held-out gate: native with/without A/B over the replay cases, substring judge (the replay gold)
    cand_pairs = [(c["name"], c["md"]) for c in cands]
    rows = []
    for case in cases:
        task = case.get("task", "")
        expect = (case.get("expect_substring", "") or "").lower()
        if not task or not expect:
            continue
        rb = _deploy_catalog_solve(task, None)
        rf = _deploy_catalog_solve(task, cand_pairs)
        rows.append({"base_em": int(expect in rb.lower()), "full_em": int(expect in rf.lower())})
    _, _, _, activate, _ = verify.rolling_decision(
        rows, str(config.MEMORY_DIR / "gate_window.json"))   # underpowered (few cases) -> stays candidate
    status = "active" if activate else "candidate"
    for c in cands:
        induce.write_skill(c, status=status)
    materialize.assemble_deploy_catalog()                 # refresh the discoverable catalog now
    return [(c["name"], status) for c in cands]


def run():
    """LEGACY promotion (pre-session-19): per-bullet draft + replay-substring gate. Superseded by
    consolidate_deploy() for the native deploy loop; kept for reference / --memory_mode inject.
    Scan for promotable bullets and (gate) promote them. Returns names touched."""
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
