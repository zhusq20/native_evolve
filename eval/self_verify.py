"""Deployment-realistic, DATASET-AGNOSTIC self-verification for the repair loop.

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


def self_verify(task, attempt, env, use_exec=True, use_critique=True):
    """Dataset-agnostic reference-free check. Returns {ok, signature, feedback}, or None if there was
    nothing to check (no exec hook and critique unavailable) so the repair loop simply doesn't fire."""
    fails, sigs, had_channel = [], [], False

    # (1) generic execution probe — run my own code, observe crashes (no gold, no answer-position)
    if use_exec:
        runner = getattr(env, "try_run", None)
        if runner is not None:
            try:
                ran_ok, fb = runner(task, attempt)
            except Exception:
                ran_ok, fb = None, ""
            if ran_ok is not None:
                had_channel = True
                if ran_ok is False:
                    fails.append((fb or "Execution failed.")[:800])
                    sigs.append("exec")

    # (2) LLM self-critique against the task's OWN stated requirements (general, reference-free)
    if use_critique:
        from evolve import llm  # engine is on sys.path once the runner has set it up
        prompt = task.get("prompt") or task.get("question") or ""
        try:
            raw = llm.call_claude(_CRITIQUE % (prompt[:3000], (attempt or "")[:3000]),
                                  allowed_tools="Read")
            obj = llm.extract_json(raw) or {}
            viols = [str(x).strip() for x in (obj.get("violations") or []) if str(x).strip()][:8]
            had_channel = True
            if viols:
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
