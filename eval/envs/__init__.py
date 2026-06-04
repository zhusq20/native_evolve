"""Pluggable evaluation environments.

Each env module exposes a uniform interface so the prequential runner and all
baselines are env-agnostic:

    NAME : str
    load_tasks(path)            -> list[dict]
    build_prompt(task, mem)     -> str         # mem is the injected memory/skill block ("" if none)
    score(task, response)       -> dict        # must contain em/f1/sub_em + predicted_answer; em is primary
    summarize(task, resp, ev)   -> str         # reflection input describing the outcome (LEGACY fallback)
    fetch(n, out, **kw)         -> None        # optional: materialize a task file

Two OPTIONAL feedback hooks make the harness consume the two channels every
benchmark affords (the cross-benchmark generalization, see docs/PROGRESS.md):

    evidence(task, resp, ev)    -> dict        # REFERENCE-GROUNDED structured outcome for reflection.
                                               # gold IS allowed (reflection only runs on train tasks).
                                               # Default: wrap summarize(). Render with render_evidence().
    verify(task, attempt)       -> dict|None   # REFERENCE-FREE inference-time check (NO gold/answers).
                                               # Powers the conditional repair loop; valid to call during
                                               # the FROZEN TEST phase (uses only task inputs + attempt).
                                               # Returns None when the env has no meaningful ref-free check
                                               # -> repair loop never fires. Shape when present:
                                               #   {"ok": bool, "signature": "<short failure class>",
                                               #    "feedback": "<text to show the agent>"}

Add a new env by dropping in envs/<name>.py with these symbols. evidence/verify
are optional — envs without them degrade gracefully via the helpers below.
"""
import importlib


def get_env(name):
    return importlib.import_module("envs." + name)


# ---- uniform accessors with safe defaults (so old envs work unchanged) ----

def collect_evidence(env, task, resp, ev):
    """Reference-grounded structured outcome for reflection. Falls back to wrapping the
    legacy summarize() so envs that don't implement evidence() keep working. If the task went
    through the self-repair loop, attach a compact repair history (uniform across envs) so the
    reflector can learn a heuristic to PRE-EMPT that failure mode next time."""
    fn = getattr(env, "evidence", None)
    if fn is not None:
        try:
            d = fn(task, resp, ev)
        except Exception as exc:  # never let evidence-building break the learning step
            d = {"text": "evidence() error: %s" % exc}
    else:
        d = {"text": env.summarize(task, resp, ev)}
    trace = ev.get("_repair_trace") if isinstance(ev, dict) else None
    if trace and isinstance(d, dict):
        steps = ["round %d: attempt failed check [%s] — %s"
                 % (i, s.get("signature", ""), (s.get("feedback", "") or "")[:300])
                 for i, s in enumerate(trace, 1)]
        d = dict(d)
        d["repair"] = ("This task needed %d self-repair round(s) before the final answer. Record a "
                       "transferable heuristic to AVOID this failure mode up front:\n" % len(trace)
                       + "\n".join(steps))
    return d


def render_evidence(d):
    """Render an evidence dict into the plain-text reflection input the Reflector reads.
    A bare {"text": ...} (the summarize fallback) renders verbatim; the structured shape
    renders labeled sections in a fixed order, skipping empty fields."""
    if not isinstance(d, dict):
        return str(d or "")
    if "text" in d:                                   # legacy summarize fallback (+ optional repair)
        out = d["text"]
        if d.get("repair"):
            out += "\n\nSELF-REPAIR HISTORY:\n" + d["repair"]
        return out
    order = [("outcome", "OUTCOME"), ("task", "TASK"), ("predicted", "AGENT OUTPUT"),
             ("gold", "REFERENCE ANSWER"), ("diagnosis", "GROUNDED DIAGNOSIS (real execution/diff)"),
             ("code", "AGENT CODE (truncated)"), ("repair", "SELF-REPAIR HISTORY")]
    lines = []
    for key, label in order:
        v = d.get(key)
        if v not in (None, "", []):
            lines.append("%s:\n%s" % (label, v))
    return "\n\n".join(lines) if lines else d.get("text", "")


def run_verify(env, task, attempt):
    """Reference-free inference-time check (None if the env has no verifier). Used by the
    repair loop; MUST NOT read gold — each env's verify() is responsible for that."""
    fn = getattr(env, "verify", None)
    if fn is None:
        return None
    try:
        return fn(task, attempt)
    except Exception:
        return None
