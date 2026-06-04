"""Counterfactual usefulness gate: a skill is USEFUL only if it lifts held-out success.

Runs held-out tasks WITH vs WITHOUT a skills block (same target model + env scorer) and
reports the lift. This replaces retrieval-frequency promotion + the rubber-stamp replay
gate with a direct causal test: keep a skill (or set) only when with-skill > without-skill
on tasks the skill never trained on. Held-out tasks MUST be disjoint from the eval stream.
"""
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


def lift_over_base(skill_block, base_block_fn, tasks, env, allowed_tools="Read"):
    """The explicit consolidation gate: does ADDING skill_block on top of the episodic+
    distilled BASE injection raise held-out accuracy? Consolidation must EARN its place by
    beating the episodic-first baseline (per the agentic-memory finding); otherwise the
    system degrades gracefully to base-only. Returns (base_pass, full_pass, n).
    """
    base_pass, full_pass, n = 0, 0, 0
    for t in tasks:
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
        base_pass += int(env.score(t, rb)["em"] == 1.0)
        full_pass += int(env.score(t, rf)["em"] == 1.0)
        n += 1
    return base_pass, full_pass, n
