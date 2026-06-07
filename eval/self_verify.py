"""The reference-free OUTCOME SIGNAL — deployment-realistic, DATASET-AGNOSTIC self-verification.

This module is the system's own correctness signal: a reference-free judge of "did this attempt go
well?" available with NO gold at deploy. It serves TWO distinct roles (see `docs/architecture.md` +
the `self-verify-role-split` design note) that must NOT be conflated:
  • Role 2 — the OUTCOME SIGNAL for self-evolution: drives credit / promotion-gate / reflection (via
    `--{credit,gate,reflect}_signal reffree`). CORE — the precondition for label-free memory evolution
    (with no gold at deploy this is the only feedback channel that tells good from bad).
  • Role 1 — feed for the inference-time REPAIR loop (`monotone_repair`). Repair is a SEPARATE, LABELED
    lever, NEVER folded into "memory": memory claims are always read off the repair=0 column, and the
    deploy-faithful headline is the AGENTIC harness (the agent self-corrects natively, so the harness
    `monotone_repair` is bypassed and only STANDS IN for that native self-correction in single-shot).
  (Design decision (a), session 15: keep repair as this labeled, ablatable lever — do not drop it.)

The per-env `verify()` functions embed dataset knowledge a real deployment would NOT have: the
benchmark's pre-parsed rubric (IFBench), answer-cell/answer-position semantics (SB), and tuned
format heuristics (QA). In production the agent just gets a task and does not know which dataset
it came from. `self_verify()` removes that knowledge and uses ONLY signals available in deployment:

  1. GENERIC EXECUTION (`env.try_run`, optional): run the candidate and observe a crash / no-output /
     self-evidently-broken artifact. A coding agent runs its own code in any real runtime; this uses
     the task's INPUT only — NEVER a gold/answer key, NEVER answer-position. Envs without code return None.
  2. LLM SELF-CRITIQUE: the agent re-reads its OWN task prompt + attempt and lists the explicit,
     objectively-checkable requirements it violated. Fully general (any task), reference-free (no gold),
     and IMPERFECT (it may miss or misjudge a requirement — the realistic degradation vs an oracle
     verifier). Costs one `claude` call per check (a general verify is not free, unlike code regex).

No env-name dispatch, no rubric, no answer key. Returns the same {ok, signature, feedback} shape as
`env.verify`, so the repair loop in `solve()` is unchanged — only the SOURCE of the signal differs.
"""
import json

# Self-critique prompt: judge ONLY stated, objectively-checkable requirements (not unknowable facts).
_CRITIQUE = (
    "You just attempted the task below. Critique YOUR OWN output against ONLY the explicit, "
    "objectively-checkable requirements STATED IN THE TASK — e.g. output format/wrapper, length, "
    "required or forbidden words/characters, structure (sections, bullets, JSON), exact-answer form, "
    "valid syntax. Do NOT invent requirements and do NOT judge factual correctness you cannot verify "
    "from the task text itself. For each requirement your output VIOLATES, write one short, specific, "
    "fixable sentence.\n"
    "Output ONLY a JSON object: {\"violations\": [\"...\", ...]}  — an EMPTY list if your output "
    "satisfies every stated requirement.\n\n=== TASK ===\n%s\n\n=== MY OUTPUT ===\n%s"
)


def _has_code_block(attempt):
    """Dataset-agnostic detector: does the agent's OWN output contain a fenced code block?
    This — a property of the ATTEMPT, not the env/dataset identity — is what decides whether the
    EXECUTION channel applies. A non-code answer (QA, instruction-following) has no fence and routes
    to self-critique; a code answer routes to execution. No env-name dispatch anywhere."""
    return "```" in (attempt or "")


def self_verify(task, attempt, env, use_exec=True, use_critique=None):
    """Dataset-agnostic reference-free check. Returns {ok, signature, feedback}, or None if there was
    nothing to check (no exec hook and critique unavailable) so the repair loop simply doesn't fire.

    ROUTING (use_critique=None, the default) keys on a property of the ATTEMPT — does it carry a fenced
    code block? (`_has_code_block`) — NOT on the env/dataset. A code attempt is executed and we DON'T
    also run the LLM self-critique; a non-code attempt is sent to self-critique. Measured rationale: on
    code tasks the self-critique of correctness is noisy — it nitpicks correct code, over-fires repair,
    and breaks working solutions (SB: exec+critique 0.375 vs exec-only 0.750 vs oracle 0.812) — while it
    is precise for the EXPLICIT, in-prompt constraints of non-code tasks (IFBench: critique 0.792 ==
    oracle). So: code present -> execution channel; no executable code -> self-critique. Deployment-
    realistic (no dataset knowledge). Force with use_critique True (run critique too — but a clean
    execution stays AUTHORITATIVE, so on code the critique is advisory and only enriches the repair
    feedback when execution already failed) / False (execution only)."""
    fails, sigs, had_channel = [], [], False
    exec_ran = False                                   # did the execution channel yield a verdict?
    exec_ok = None                                     # ...and was it a PASS? (None = no verdict)
    has_code = _has_code_block(attempt)

    # (1) execution probe — applies IFF the attempt itself carries code to run; the routing keys on the
    #     code block, NOT on which env/dataset this is. Runs my own code, observes crashes / poison
    #     (no gold, no answer-position). Envs without a runner simply produce no verdict here.
    if use_exec and has_code:
        runner = getattr(env, "try_run", None)
        if runner is not None:
            try:
                ran_ok, fb = runner(task, attempt)
            except Exception:
                ran_ok, fb = None, ""
            if ran_ok is not None:
                had_channel = True
                exec_ran = True
                exec_ok = bool(ran_ok)
                if ran_ok is False:
                    fails.append((fb or "Execution failed.")[:800])
                    sigs.append("exec")

    # (2) LLM self-critique — fires when execution produced NO verdict (a non-code attempt, or code no
    #     runtime here could execute), unless forced. Routing = "did execution decide?", set by has_code.
    do_critique = use_critique if use_critique is not None else (not exec_ran)
    if do_critique:
        from evolve import llm  # engine is on sys.path once the runner has set it up
        prompt = task.get("prompt") or task.get("question") or ""
        try:
            raw = llm.call_claude(_CRITIQUE % (prompt[:3000], (attempt or "")[:3000]),
                                  allowed_tools="Read")
            obj = llm.extract_json(raw) or {}
            viols = [str(x).strip() for x in (obj.get("violations") or []) if str(x).strip()][:8]
            had_channel = True
            # EXECUTION IS AUTHORITATIVE: a clean run is a precise verdict, whereas the LLM's
            # correctness-critique of CODE is noisy and over-fires (SB exec+critique 0.375 << exec-only
            # 0.750). So when the execution VERDICT == pass, critique is ADVISORY ONLY — it can never
            # flip ok -> fail (so it can never trigger a spurious repair that breaks correct code). It
            # still ENRICHES the repair feedback when execution already FAILED (more detail to fix).
            if viols and not (exec_ran and exec_ok):
                fails.extend(viols)
                sigs.append("constraint")
        except Exception:
            pass

    if not had_channel:
        return None                                  # nothing checkable -> no repair signal
    if not fails:
        return {"ok": True, "signature": "", "feedback": ""}
    fb = ("Your own self-check found these problems with your output:\n"
          + "\n".join("- " + f for f in fails)
          + "\nRewrite to fix ALL of them while staying on-task.")
    return {"ok": False, "signature": ",".join(sorted(set(sigs)))[:60], "feedback": fb}
