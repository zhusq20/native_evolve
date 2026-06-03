#!/usr/bin/env python3
"""Stop hook: trigger reflection after the agent finishes a task.

Spawns the Reflector as a DETACHED background process so the user's turn ends
immediately; reflection/curation/promotion then happen asynchronously.

Recursion guards (the Reflector itself is a `claude` session):
  - no-op if NATIVE_EVOLVE_REFLECTING=1 is already set
  - no-op if stop_hook_active (Claude's own re-entrancy flag)
  - the Reflector runs with --setting-sources user, so this project hook isn't loaded
"""
import json
import os
import pathlib
import subprocess
import sys


def main():
    try:
        event = json.load(sys.stdin)
    except Exception:
        event = {}

    if os.environ.get("NATIVE_EVOLVE_REFLECTING") == "1":
        return 0
    if event.get("stop_hook_active"):
        return 0

    transcript = event.get("transcript_path", "")
    if not transcript:
        return 0

    home = (
        os.environ.get("NATIVE_EVOLVE_HOME")
        or os.environ.get("CLAUDE_PROJECT_DIR")
        or str(pathlib.Path(__file__).resolve().parents[2])
    )
    env = dict(os.environ)
    env["NATIVE_EVOLVE_REFLECTING"] = "1"
    env["NATIVE_EVOLVE_HOME"] = home

    try:
        subprocess.Popen(
            [sys.executable, "-m", "evolve.reflect", "--transcript", transcript],
            cwd=home,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
