#!/usr/bin/env python3
"""UserPromptSubmit hook: inject relevant memory bullets into the session context.

Reads the hook event JSON from stdin, retrieves top-k relevant bullets, and emits
them as `additionalContext`. Stays silent (and never blocks) on any error.
"""
import json
import os
import pathlib
import sys


def _home():
    return (
        os.environ.get("NATIVE_EVOLVE_HOME")
        or os.environ.get("CLAUDE_PROJECT_DIR")
        or str(pathlib.Path(__file__).resolve().parents[2])
    )


def main():
    try:
        event = json.load(sys.stdin)
    except Exception:
        event = {}

    home = _home()
    sys.path.insert(0, home)
    os.environ.setdefault("NATIVE_EVOLVE_HOME", home)

    try:
        from evolve import retrieve

        ctx = retrieve.context_block(event.get("prompt", ""))
    except Exception:
        ctx = ""

    if ctx:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": ctx,
            }
        }))
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
