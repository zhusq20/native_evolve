#!/usr/bin/env python3
"""Codex adapter: a thin wrapper that reproduces the native loop Codex lacks.

Codex has no UserPromptSubmit/Stop hook equivalent, so we orchestrate explicitly:
  1. retrieve relevant memory and prepend it to the task,
  2. run `codex exec`,
  3. reflect on (task, output) to update memory + promote skills.

Usage:
  python3 adapters/codex/runner.py "<task text>"
"""
import os
import pathlib
import sys


def main():
    home = os.environ.get("NATIVE_EVOLVE_HOME") or str(
        pathlib.Path(__file__).resolve().parents[2]
    )
    sys.path.insert(0, home)
    os.environ.setdefault("NATIVE_EVOLVE_HOME", home)

    from evolve import llm, reflect, retrieve

    task = " ".join(sys.argv[1:]).strip()
    if not task:
        sys.stderr.write("usage: runner.py <task text>\n")
        return 2

    ctx = retrieve.context_block(task)
    full = (ctx + "\n\n" + task) if ctx else task

    output = llm.call_codex(full)
    print(output)

    summary = "USER TASK:\n" + task + "\n\nFINAL ASSISTANT OUTPUT:\n" + output
    n = reflect.run(summary=summary)
    sys.stderr.write("native_evolve: merged %d delta(s)\n" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
