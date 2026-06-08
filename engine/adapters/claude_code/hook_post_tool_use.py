#!/usr/bin/env python3
"""PostToolUse hook: record which SKILL the agent invoked, for native-retrieval attribution.

When the solve runs with the native skill catalog (memory + promoted skills as discoverable
`.claude/skills`), the harness no longer chooses what's in context — the AGENT does. To credit the
memory it actually used (and to score the gate), we observe invocations here: on every PostToolUse
for the `Skill` tool, append the raw event to a log file. The eval reads that file after the run and
matches the distinctive skill names (`mem-*` etc.) it materialized. Robust to the exact Skill
tool-input schema (we log the whole event and substring-match known names).

Target log path resolution (first that is set):
  1. argv[1]                         (native_solve bakes an absolute path into the sandbox settings)
  2. env NATIVE_EVOLVE_INVOKED
  3. <cwd>/.invoked
Never blocks, never errors out (a logging hook must not break the agent run)."""
import json
import os
import sys


def _target():
    if len(sys.argv) > 1 and sys.argv[1].strip():
        return sys.argv[1].strip()
    return os.environ.get("NATIVE_EVOLVE_INVOKED") or os.path.join(os.getcwd(), ".invoked")


def main():
    try:
        event = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(event, dict):
        return 0
    tool = event.get("tool_name") or event.get("tool") or ""
    if tool != "Skill":
        return 0
    rec = {"tool": tool, "tool_input": event.get("tool_input", {})}
    try:
        with open(_target(), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
