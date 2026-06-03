"""The ONLY LLM entrypoint: shell out to the `claude` / `codex` CLI.

Reflector / skill-writer / gate calls all go through call_claude. To prevent the
self-evolution loop from recursing, these sub-sessions:
  - set NATIVE_EVOLVE_REFLECTING=1 (the Stop hook no-ops when it sees this), and
  - use --setting-sources user by default (so the project's Stop hook isn't loaded).
"""
import json
import os
import re
import subprocess

from . import config


def _run(cmd, env_extra=None, cwd=None, timeout=600):
    env = dict(os.environ)
    env["NATIVE_EVOLVE_REFLECTING"] = "1"
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, env=env, cwd=cwd
    )


def call_claude(
    prompt,
    allowed_tools="Read",
    add_dir=None,
    cwd=None,
    setting_sources="user",
    timeout=600,
):
    cmd = [
        config.CLAUDE_BIN, "-p", prompt,
        "--output-format", "json",
        "--setting-sources", setting_sources,
        "--permission-mode", "acceptEdits",
        "--allowedTools", allowed_tools,
    ]
    if add_dir:
        cmd += ["--add-dir", str(add_dir)]
    if config.MODEL:
        cmd += ["--model", config.MODEL]

    proc = _run(cmd, cwd=cwd, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError("claude CLI failed: " + (proc.stderr or "")[:500])

    out = (proc.stdout or "").strip()
    try:
        obj = json.loads(out)
        if isinstance(obj, dict) and "result" in obj:
            _log_ledger(obj)
            return obj["result"]
    except Exception:
        pass
    return out


def _log_ledger(obj):
    """Append per-call cost/usage to NATIVE_EVOLVE_LEDGER (jsonl) when set.

    Captures EVERY claude call through this module — target, Reflector, gate — so
    the eval runner can compute true cumulative cost including self-evolution.
    """
    path = os.environ.get("NATIVE_EVOLVE_LEDGER")
    if not path:
        return
    try:
        usage = obj.get("usage") or {}
        rec = {
            "cost_usd": float(obj.get("total_cost_usd") or 0.0),
            "output_tokens": int(usage.get("output_tokens") or 0),
            "input_tokens": int(usage.get("input_tokens") or 0),
        }
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception:
        pass


def call_codex(prompt, timeout=600):
    proc = _run([config.CODEX_BIN, "exec", prompt], timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError("codex CLI failed: " + (proc.stderr or "")[:500])
    return (proc.stdout or "").strip()


def extract_json(text):
    """Pull the first balanced {...} object out of an LLM reply (tolerant of fences)."""
    if not text:
        return None
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except Exception:
                    return None
    return None
