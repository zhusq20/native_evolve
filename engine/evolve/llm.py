"""The ONLY LLM entrypoint: shell out to the `claude` / `codex` CLI.

Reflector / skill-writer / gate calls all go through call_claude. To prevent the
self-evolution loop from recursing, these sub-sessions:
  - set NATIVE_EVOLVE_REFLECTING=1 (the Stop hook no-ops when it sees this), and
  - use --setting-sources user by default (so the project's Stop hook isn't loaded).
"""
import json
import os
import random
import re
import subprocess
import sys
import threading
import time

from . import config

# Ledger appends are serialized: a run's parallel deploy phase fires many concurrent
# call_claude() from worker threads, all writing the SAME per-run ledger file. (Cross-run
# isolation is by separate ledger files, so this process-local lock is sufficient.)
_LEDGER_LOCK = threading.Lock()


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
    return_cost=False,
):
    """Shell out to `claude -p` with robust retries. Returns the result string (or
    (result, cost_usd) when return_cost=True). Retries transient failures — non-zero exit,
    timeout, empty stdout — with exponential backoff + jitter (rate limits / overload /
    flaky network are the common causes during a 64-wide deploy). Tunable via env:
    NATIVE_EVOLVE_MAX_RETRIES (default 5), NATIVE_EVOLVE_RETRY_BASE seconds (default 2.0)."""
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

    max_retries = int(os.environ.get("NATIVE_EVOLVE_MAX_RETRIES", "5"))
    base = float(os.environ.get("NATIVE_EVOLVE_RETRY_BASE", "2.0"))
    # NATIVE_EVOLVE_RETRY_FIXED: if set, use a CONSTANT retry interval (seconds) instead of
    # exponential backoff — e.g. 1000 retries x 10s to patiently ride out long rate-limit outages.
    fixed = os.environ.get("NATIVE_EVOLVE_RETRY_FIXED")
    fixed = float(fixed) if fixed else None
    last_err = "unknown"
    for attempt in range(max_retries + 1):
        try:
            proc = _run(cmd, cwd=cwd, timeout=timeout)
            if proc.returncode == 0:
                out = (proc.stdout or "").strip()
                if out:
                    try:
                        obj = json.loads(out)
                        if isinstance(obj, dict) and "result" in obj:
                            cost = float(obj.get("total_cost_usd") or 0.0)
                            _log_ledger(obj)
                            return (obj["result"], cost) if return_cost else obj["result"]
                    except Exception:
                        pass
                    return (out, 0.0) if return_cost else out   # non-JSON but non-empty: rare
                last_err = "empty stdout"
            else:
                last_err = (proc.stderr or "")[:300] or ("exit %d" % proc.returncode)
        except subprocess.TimeoutExpired:
            last_err = "timeout after %ss" % timeout
        except Exception as exc:                                # noqa: BLE001
            last_err = repr(exc)[:300]
        if attempt < max_retries:
            if fixed is not None:
                delay = fixed
            else:
                delay = min(base * (2 ** min(attempt, 8)) + random.uniform(0, base), 60.0)
            sys.stderr.write("[claude retry %d/%d in %.1fs] %s\n"
                             % (attempt + 1, max_retries, delay, last_err[:140]))
            time.sleep(delay)
    raise RuntimeError("claude CLI failed after %d retries: %s" % (max_retries, last_err))


def pmap(fn, items, workers):
    """Apply fn to items, order-preserving. workers<=1 runs inline; else a bounded thread pool.
    claude calls are subprocess/IO-bound so threads give real concurrency; the ledger append is
    lock-guarded. Shared by the eval deploy phase, the consolidation gate, and external rollouts."""
    items = list(items)
    if workers <= 1 or len(items) <= 1:
        return [fn(x) for x in items]
    import concurrent.futures
    results = [None] * len(items)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fn, x): i for i, x in enumerate(items)}
        for f in concurrent.futures.as_completed(futs):
            results[futs[f]] = f.result()
    return results


def _log_ledger(obj):
    """Append per-call cost/usage to NATIVE_EVOLVE_LEDGER (jsonl) when set, thread-safely.

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
        line = json.dumps(rec) + "\n"
        with _LEDGER_LOCK:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line)
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
