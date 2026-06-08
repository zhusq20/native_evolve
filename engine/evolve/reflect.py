"""Reflector orchestration: transcript -> deltas -> curate -> promote.

Triggered by the Claude Code Stop hook (async) or the Codex wrapper, or manually
via `evolve reflect --transcript <path>`.
"""
import argparse
import json
import pathlib
import sys

from . import config, curate, llm, promote


def _walk_content(content, tools, errors, skills=None):
    """Flatten a message `content` (str | list of blocks) into plain text. Also collects tool names
    into `tools`, error text into `errors`, and — for `Skill` invocations — the invoked skill name(s)
    into `skills` (from the tool_use input; any string value, so we're robust to the exact key)."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = []
    for x in content:
        if isinstance(x, str):
            parts.append(x)
        elif isinstance(x, dict):
            t = x.get("type")
            if t == "text":
                parts.append(x.get("text", ""))
            elif t == "tool_use":
                nm = x.get("name", "")
                tools.append(nm)
                if nm == "Skill" and skills is not None:
                    inp = x.get("input", {})
                    if isinstance(inp, dict):
                        for v in inp.values():
                            if isinstance(v, str):
                                skills.append(v)
            elif t == "tool_result":
                inner = x.get("content")
                txt = inner if isinstance(inner, str) else _walk_content(inner, tools, errors, skills)
                if txt and "error" in txt.lower():
                    errors.append(txt[:300])
    return "\n".join(p for p in parts if p)


def summarize_transcript(path, max_chars=12000):
    """Compact a Claude Code transcript.jsonl into a small reflection input.

    Returns (summary_text, invoked_skills, had_errors): `invoked_skills` = the Skill names the agent
    invoked (for credit attribution); `had_errors` = any tool error observed (the deploy-available,
    REFERENCE-FREE success proxy used to weight credit, since a live session has no gold/env)."""
    p = pathlib.Path(path)
    if not p.exists():
        return "", [], False
    user, assistant, tools, errors, skills = [], [], [], [], []
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        msg = obj.get("message") if isinstance(obj.get("message"), dict) else obj
        role = obj.get("type") or msg.get("role")
        text = _walk_content(msg.get("content"), tools, errors, skills)
        if role == "user" and text:
            user.append(text)
        elif role == "assistant" and text:
            assistant.append(text)

    out = []
    if user:
        out.append("USER TASK:\n" + user[0][:2000])
    if assistant:
        out.append("FINAL ASSISTANT OUTPUT:\n" + assistant[-1][:3000])
    if tools:
        out.append("TOOLS USED: " + ", ".join(t for t in tools[:50] if t))
    if errors:
        out.append("ERRORS OBSERVED:\n" + "\n".join(errors[:5]))
    return "\n\n".join(out)[:max_chars], skills, bool(errors)


def reflect_deltas(summary):
    """The EXPENSIVE half of reflection: claude reads the session summary and proposes curation
    deltas. Pure (no store write), so a serving deployment can run many reflections concurrently
    and serialize only the cheap deterministic merge. Returns the list of delta dicts."""
    if not (summary or "").strip():
        return []
    template = (config.PROMPTS_DIR / "reflector.md").read_text(encoding="utf-8")
    raw = llm.call_claude(
        template + "\n\n=== SESSION SUMMARY ===\n" + summary,
        allowed_tools="Read",
    )
    return (llm.extract_json(raw) or {}).get("deltas", [])


def run(transcript_path=None, summary=None, promote_skills=True):
    """Returns the number of memory changes applied.

    DEPLOY path (transcript_path given): reflect+curate into memory, CREDIT the memory the agent
    actually INVOKED (read from the transcript; reference-free success = no tool error observed), and
    consolidate via the experiment's induce+gate (promote.consolidate_deploy). This mirrors the eval
    learning loop (curate.credit + induce + verify gate) — see PROGRESS session-19.
    EXPERIMENT path (summary given, e.g. prequential's evidence): credit + consolidation are handled
    by the harness's own native_solve/consolidate, so this only reflect+curates (promote_skills=False).

    promote_skills=False keeps a single-tier playbook (the ACE baseline): reflect+curate, no promotion.
    """
    invoked_skills, had_errors = [], False
    if summary is None:
        if transcript_path:
            summary, invoked_skills, had_errors = summarize_transcript(transcript_path)
        else:
            summary = ""
    deltas = reflect_deltas(summary)
    n = curate.merge(deltas)

    # CREDIT the distilled bullets the agent actually invoked (deploy attribution; deterministic).
    if invoked_skills:
        try:
            from . import materialize
            ids = materialize.invoked_to_bullet_ids(invoked_skills)
            if ids:
                curate.credit(ids, success=not had_errors)
        except Exception as exc:
            sys.stderr.write("native_evolve credit error: %s\n" % exc)

    if promote_skills:
        try:
            promote.consolidate_deploy()     # induce + held-out gate (aligned with the experiment)
        except Exception as exc:  # promotion must never break the reflection step
            sys.stderr.write("native_evolve promote error: %s\n" % exc)
    return n


def main():
    ap = argparse.ArgumentParser(description="Reflect on a finished session.")
    ap.add_argument("--transcript", help="path to a Claude Code transcript.jsonl")
    args = ap.parse_args()
    n = run(transcript_path=args.transcript)
    sys.stderr.write("native_evolve: merged %d delta(s)\n" % n)


if __name__ == "__main__":
    main()
