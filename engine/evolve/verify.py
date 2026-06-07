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


def paired_ab(skill_block, base_block_fn, tasks, env, allowed_tools="Read", workers=1,
              judge=None, solve_fn=None):
    """Paired with/without-skill A/B on the SAME tasks (difficulty held fixed). Returns per-task
    {base_em, full_em}. Fans out at `workers` concurrent requests (no writes).

    To eliminate any train(gate)/inference MISMATCH, solve & skill-presentation default to the way
    real inference works and can be overridden to match it exactly:
      * `solve_fn(task, mem_block) -> resp`: the harness's REAL solve path (single-shot + repair, or
        agentic), so a skill is judged on the repaired/agentic answer it will ACTUALLY face at
        serving — not a bare single-shot. Default = bare single-shot call (back-compat).
      * `skill_block`: a per-task CALLABLE (task->str) rendered like the inference skill block, OR a
        static string. It is appended AFTER the base block (base = episodic+distilled, skill LAST),
        matching inference's inject() order (episodic, distilled, skills).
      * `judge(task, resp) -> bool`: the CORRECTNESS SIGNAL. Default = GOLD (env.score em == 1.0), the
        measurement/oracle a real deployment lacks; pass a REFERENCE-FREE judge (self_verify ok) for
        the deploy-faithful gate (see prequential `--gate_signal`)."""
    if judge is None:
        judge = lambda task, resp: env.score(task, resp)["em"] == 1.0
    if solve_fn is None:
        solve_fn = lambda task, mem: llm.call_claude(env.build_prompt(task, mem),
                                                     allowed_tools=allowed_tools)

    def one(t):
        b = base_block_fn(t) if callable(base_block_fn) else (base_block_fn or "")
        sb = skill_block(t) if callable(skill_block) else (skill_block or "")
        full = "\n\n".join(x for x in (b, sb) if x)        # base THEN skill (inference inject() order)
        try:
            rb = solve_fn(t, b)
        except Exception:
            rb = ""
        try:
            rf = solve_fn(t, full)
        except Exception:
            rf = ""
        return {"base_em": int(bool(judge(t, rb))),
                "full_em": int(bool(judge(t, rf)))}
    return llm.pmap(one, tasks, workers)


def paired_ab_multi(skill_block, base_block_fn, tasks, env, judges, allowed_tools="Read",
                    workers=1, solve_fn=None):
    """Like `paired_ab`, but solves base & full ONCE per task and scores each answer with MULTIPLE
    judges, so every judge sees the IDENTICAL pair of answers. This is the clean
    precision-law-FOR-GATING audit: comparing an oracle (gold) judge against a reference-free judge
    on the SAME answers removes solve-stochasticity from the comparison (re-running paired_ab per
    judge would re-solve and the answers would differ from claude noise). `judges` is a dict
    {name: judge(task, resp)->bool}. Returns a list of per-task dicts {<name>_base, <name>_full}."""
    if solve_fn is None:
        solve_fn = lambda task, mem: llm.call_claude(env.build_prompt(task, mem),
                                                     allowed_tools=allowed_tools)

    def one(t):
        b = base_block_fn(t) if callable(base_block_fn) else (base_block_fn or "")
        sb = skill_block(t) if callable(skill_block) else (skill_block or "")
        full = "\n\n".join(x for x in (b, sb) if x)        # base THEN skill (inference inject() order)
        try:
            rb = solve_fn(t, b)
        except Exception:
            rb = ""
        try:
            rf = solve_fn(t, full)
        except Exception:
            rf = ""
        out = {}
        for name, j in judges.items():
            try:
                out[name + "_base"] = int(bool(j(t, rb)))
            except Exception:
                out[name + "_base"] = 0
            try:
                out[name + "_full"] = int(bool(j(t, rf)))
            except Exception:
                out[name + "_full"] = 0
        return out
    return llm.pmap(one, tasks, workers)


def gate_tally(rows, name, min_n=18, margin=2):
    """Tally one judge's paired_ab_multi rows into the SAME accept rule rolling_gate uses for a
    single (non-accumulated) round: powered ∧ beats-margin ∧ not-diluting. Returns the decision dict."""
    bp = sum(r[name + "_base"] for r in rows)
    fp = sum(r[name + "_full"] for r in rows)
    n = len(rows)
    base_fail = [r for r in rows if r[name + "_base"] == 0]
    rescued = sum(1 for r in base_fail if r[name + "_full"] == 1)
    broke = sum(1 for r in rows if r[name + "_base"] == 1 and r[name + "_full"] == 0)
    powered = n >= min_n
    beats = (fp - bp) >= margin
    not_diluting = broke <= rescued
    return {"base_pass": bp, "full_pass": fp, "n": n, "rescued": rescued, "broke": broke,
            "base_fail": len(base_fail), "powered": powered, "beats_margin": beats,
            "not_diluting": not_diluting, "saturated": len(base_fail) == 0,
            "activate": bool(powered and beats and not_diluting)}


def signal_agreement(rows, a, b):
    """Per-task agreement between two judges (a vs b) over paired_ab_multi rows — the
    PRECISION-OF-THE-SIGNAL metric. A reference-free gate can only TRACK gold if its per-task verdict
    matches gold's per-task verdict (aggregate pass-counts can coincide while per-task verdicts diverge
    — e.g. a saturated/blind judge). Returns fraction matching on the base answer and on the full
    answer. (dyck: reffree blind -> low base_agree on the gold-failing tasks; IFBench: precise -> high.)"""
    n = len(rows) or 1
    base = sum(1 for r in rows if r[a + "_base"] == r[b + "_base"])
    full = sum(1 for r in rows if r[a + "_full"] == r[b + "_full"])
    # agreement restricted to the tasks gold marks as base-FAILURES (where a gate's rescue signal
    # actually lives) — the discriminating subset; blind judges score ~0 here even at high overall agree.
    gold_fail = [r for r in rows if r[a + "_base"] == 0]
    fail_agree = (sum(1 for r in gold_fail if r[b + "_base"] == 0) / (len(gold_fail) or 1))
    return {"base_agree": round(base / n, 3), "full_agree": round(full / n, 3),
            "base_fail_agree": round(fail_agree, 3), "n_base_fail": len(gold_fail), "n": len(rows)}


def lift_over_base(skill_block, base_block_fn, tasks, env, allowed_tools="Read", workers=1,
                   judge=None, solve_fn=None):
    """The explicit consolidation gate: does ADDING skill_block on top of the episodic+
    distilled BASE injection raise held-out accuracy? Consolidation must EARN its place by
    beating the episodic-first baseline (per the agentic-memory finding); otherwise the
    system degrades gracefully to base-only. Returns (base_pass, full_pass, n). `judge` selects
    the correctness signal (default GOLD; reference-free for the deploy-faithful gate); `solve_fn`
    selects the solve path (default bare single-shot; pass the real solve() to match inference)."""
    rows = paired_ab(skill_block, base_block_fn, tasks, env, allowed_tools, workers, judge, solve_fn)
    return sum(r["base_em"] for r in rows), sum(r["full_em"] for r in rows), len(rows)


def rolling_gate(skill_block, base_block_fn, tasks, env, state_path, allowed_tools="Read",
                 workers=1, min_n=18, margin=2, judge=None, solve_fn=None):
    """Online consolidation gate: ACCUMULATE paired A/B evidence ACROSS consolidation checkpoints
    (persisted in `state_path`) and activate skills only on a sufficiently-powered, dilution-guarded
    lift over the episodic+distilled base. Fixes the one-shot tiny/saturated-val gate's two failure
    modes: (1) false-POSITIVE — a marginal/noise 'lift' no longer flips activation (require a real
    cumulative margin AND that skills RESCUE more base-failures than they BREAK); (2) it reports the
    base-failure rescue / saturation signal so a no-headroom val reads as INCONCLUSIVE (keep skills
    as candidates, graceful degrade) instead of a silent false-REJECT.

    `judge` selects the correctness signal (default GOLD env.score; pass a reference-free judge —
    self_verify ok — for the deploy-faithful gate, per prequential `--gate_signal`). `solve_fn`
    selects the solve path (default bare single-shot; pass the harness's real solve() so skills are
    judged under the SAME repair/agentic conditions inference uses — no train/inference mismatch).

    Returns (base_cum, full_cum, n_cum, activate, info)."""
    rows = paired_ab(skill_block, base_block_fn, tasks, env, allowed_tools, workers, judge, solve_fn)
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
