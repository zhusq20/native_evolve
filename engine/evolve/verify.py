"""Counterfactual usefulness gate: a skill is USEFUL only if it lifts held-out success.

Runs held-out tasks WITH vs WITHOUT a skills block (same target model + env scorer) and
reports the lift. This replaces retrieval-frequency promotion + the rubber-stamp replay
gate with a direct causal test: keep a skill (or set) only when with-skill > without-skill
on tasks the skill never trained on. Held-out tasks MUST be disjoint from the eval stream.
"""
import json
import os

from . import llm


def ab_eval(skills_text, tasks, env, allowed_tools="Read"):
    """A/B each task with vs without skills injected. Returns counts + per-task rows.

    `skills_text` may be a string (same block for every task) or a callable task->str
    (per-task relevance-gated injection; return "" to inject nothing for that task).
    """
    res = {"with": 0, "without": 0, "n": 0, "rows": []}
    for t in tasks:
        st = skills_text(t) if callable(skills_text) else skills_text
        try:
            r0 = llm.call_claude(env.build_prompt(t, ""), allowed_tools=allowed_tools)
        except Exception:
            r0 = ""
        e0 = env.score(t, r0)
        try:
            r1 = llm.call_claude(env.build_prompt(t, st), allowed_tools=allowed_tools)
        except Exception:
            r1 = ""
        e1 = env.score(t, r1)
        res["without"] += int(e0["em"] == 1.0)
        res["with"] += int(e1["em"] == 1.0)
        res["n"] += 1
        res["rows"].append({"id": t.get("id"), "without_em": e0["em"],
                            "with_em": e1["em"], "had_skills": bool(st)})
    return res


def multi_arm(arms, tasks, env, allowed_tools="Read"):
    """Score each task under several injection ARMS on the SAME instances (difficulty held
    fixed). `arms` is a dict name->callable(task)->mem_block. Returns per-arm pass counts +
    per-task rows. Used for the nothing / retrieved-memory / induced-skills diagnostic.
    """
    names = list(arms)
    counts = {n: 0 for n in names}
    rows = []
    for t in tasks:
        row = {"id": t.get("id")}
        for n in names:
            mem = arms[n](t)
            try:
                r = llm.call_claude(env.build_prompt(t, mem), allowed_tools=allowed_tools)
            except Exception:
                r = ""
            em = env.score(t, r)["em"]
            counts[n] += int(em == 1.0)
            row[n] = em
        rows.append(row)
    return {"counts": counts, "n": len(tasks), "rows": rows}


def paired_ab(skill_block, base_block_fn, tasks, env, allowed_tools="Read", workers=1):
    """Paired with/without-skill A/B on the SAME tasks (difficulty held fixed). Returns per-task
    {base_em, full_em}. Fans out at `workers` concurrent requests (no writes)."""
    def one(t):
        b = base_block_fn(t) if callable(base_block_fn) else (base_block_fn or "")
        full = (skill_block + "\n\n" + b) if b else skill_block
        try:
            rb = llm.call_claude(env.build_prompt(t, b), allowed_tools=allowed_tools)
        except Exception:
            rb = ""
        try:
            rf = llm.call_claude(env.build_prompt(t, full), allowed_tools=allowed_tools)
        except Exception:
            rf = ""
        return {"base_em": int(env.score(t, rb)["em"] == 1.0),
                "full_em": int(env.score(t, rf)["em"] == 1.0)}
    return llm.pmap(one, tasks, workers)


def lift_over_base(skill_block, base_block_fn, tasks, env, allowed_tools="Read", workers=1):
    """The explicit consolidation gate: does ADDING skill_block on top of the episodic+
    distilled BASE injection raise held-out accuracy? Consolidation must EARN its place by
    beating the episodic-first baseline (per the agentic-memory finding); otherwise the
    system degrades gracefully to base-only. Returns (base_pass, full_pass, n)."""
    rows = paired_ab(skill_block, base_block_fn, tasks, env, allowed_tools, workers)
    return sum(r["base_em"] for r in rows), sum(r["full_em"] for r in rows), len(rows)


def rolling_gate(skill_block, base_block_fn, tasks, env, state_path, allowed_tools="Read",
                 workers=1, min_n=18, margin=2):
    """Online consolidation gate: ACCUMULATE paired A/B evidence ACROSS consolidation checkpoints
    (persisted in `state_path`) and activate skills only on a sufficiently-powered, dilution-guarded
    lift over the episodic+distilled base. Fixes the one-shot tiny/saturated-val gate's two failure
    modes: (1) false-POSITIVE — a marginal/noise 'lift' no longer flips activation (require a real
    cumulative margin AND that skills RESCUE more base-failures than they BREAK); (2) it reports the
    base-failure rescue / saturation signal so a no-headroom val reads as INCONCLUSIVE (keep skills
    as candidates, graceful degrade) instead of a silent false-REJECT.

    Returns (base_cum, full_cum, n_cum, activate, info)."""
    rows = paired_ab(skill_block, base_block_fn, tasks, env, allowed_tools, workers)
    bp = sum(r["base_em"] for r in rows)
    fp = sum(r["full_em"] for r in rows)
    n = len(rows)
    base_fail = [r for r in rows if r["base_em"] == 0]
    rescued = sum(1 for r in base_fail if r["full_em"] == 1)      # skill turned a base-FAIL into a pass
    broke = sum(1 for r in rows if r["base_em"] == 1 and r["full_em"] == 0)  # skill broke a base-pass

    state = {"base": 0, "full": 0, "n": 0, "rescued": 0, "base_fail": 0, "broke": 0, "rounds": 0}
    try:
        if state_path and os.path.exists(state_path):
            with open(state_path, "r", encoding="utf-8") as f:
                state.update(json.load(f))
    except Exception:
        pass
    state["base"] += bp; state["full"] += fp; state["n"] += n
    state["rescued"] += rescued; state["base_fail"] += len(base_fail)
    state["broke"] += broke; state["rounds"] += 1
    try:
        if state_path:
            os.makedirs(os.path.dirname(state_path), exist_ok=True)
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump(state, f)
    except Exception:
        pass

    powered = state["n"] >= min_n
    beats = (state["full"] - state["base"]) >= margin
    not_diluting = state["broke"] <= state["rescued"]
    activate = bool(powered and beats and not_diluting)
    info = dict(state)
    info["round"] = {"base": bp, "full": fp, "n": n, "rescued": rescued,
                     "base_fail": len(base_fail), "broke": broke}
    info["decision"] = {"powered": powered, "beats_margin": beats, "not_diluting": not_diluting,
                        "saturated": state["base_fail"] == 0}
    return state["base"], state["full"], state["n"], activate, info
