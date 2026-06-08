"""GO/NO-GO smoke for the NATIVE retrieval mechanism — does a headless `claude -p` actually
DISCOVER skills from a sandbox `.claude/skills/`, INVOKE them, and fire our PostToolUse hook?

This is the one thing the offline unit tests cannot cover (it needs real claude). It costs ~1
claude call. The seeded memory bullet carries a SECRET the model cannot otherwise know, so a correct
answer proves the whole chain at once: catalog discovery -> Skill invocation -> body reached the
answer; the .invoked file independently proves the hook fired (-> attribution works).

Run:  NATIVE_EVOLVE_MODEL=haiku python3 eval/smoke_native.py
"""
import os
import pathlib
import shutil
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parent.parent
_HOME = tempfile.mkdtemp(prefix="smoke_home_")
os.environ["NATIVE_EVOLVE_HOME"] = _HOME
os.environ["NATIVE_EVOLVE_LEDGER"] = os.path.join(_HOME, "ledger.jsonl")
os.environ.setdefault("NATIVE_EVOLVE_MODEL", "haiku")          # cheap target for the smoke
sys.path.insert(0, str(REPO / "engine"))
from evolve import materialize, llm  # noqa: E402

SECRET = "BANANA-7741"
BULLET = {
    "id": "m-0001", "status": "active", "helpful": 3, "harmful": 0,
    "scope": "use when the task asks for the project's secret passphrase",
    "content": "The project's secret passphrase is %s. Answer with exactly that token." % SECRET,
}
HOOK = REPO / "engine" / "adapters" / "claude_code" / "hook_post_tool_use.py"


def main():
    sandbox = tempfile.mkdtemp(prefix="smoke_native_")
    invoked_path = os.path.join(sandbox, ".invoked")
    setting_sources = os.environ.get("SMOKE_SETTING_SOURCES", "project")
    known = materialize.setup_sandbox(
        sandbox, HOOK, invoked_path, items=[BULLET],
        include_promoted=False, include_episodes=False)
    print("catalog @ %s/.claude/skills:" % sandbox)
    for d in sorted(os.listdir(os.path.join(sandbox, ".claude", "skills"))):
        print("  -", d)
    print("setting_sources =", setting_sources, "| model =", os.environ.get("NATIVE_EVOLVE_MODEL"))

    prompt = (
        "What is the project's secret passphrase? You have access to project Skills capturing "
        "lessons from past tasks — review the available skills and INVOKE any that are relevant, "
        "then answer with ONLY the passphrase token, nothing else."
    )
    try:
        resp, cost = llm.call_claude(
            prompt, allowed_tools="Skill,Read", cwd=sandbox, add_dir=sandbox,
            setting_sources=setting_sources, permission_mode="bypassPermissions",
            max_turns=4, max_retries=1, timeout=900, return_cost=True)
    except Exception as exc:
        print("\nFAIL: claude call errored:", exc)
        return 1

    log = open(invoked_path, encoding="utf-8").read() if os.path.exists(invoked_path) else ""
    invoked = materialize.match_invoked(log, known)
    invoked_ids = materialize.invoked_to_bullet_ids(invoked)

    print("\n--- answer ---")
    print((resp or "").strip()[:400])
    print("\n--- attribution ---")
    print("hook .invoked exists:", os.path.exists(invoked_path), "| raw:", (log or "").strip()[:200])
    print("invoked skills      :", invoked)
    print("credited bullet ids :", invoked_ids)
    print("cost (usd)          : %.5f" % cost)

    answer_has_secret = SECRET in (resp or "")
    hook_fired = bool(invoked)
    print("\n=== RESULT ===")
    print("discovery+use (answer carries the secret):", "PASS" if answer_has_secret else "FAIL")
    print("hook attribution (.invoked -> mem-m-0001):", "PASS" if (hook_fired and "m-0001" in invoked_ids) else "FAIL")
    if os.environ.get("NATIVE_EVOLVE_KEEP_SANDBOX") != "1":
        shutil.rmtree(sandbox, ignore_errors=True)
    # go/no-go: the catalog must be USED. Attribution is the secondary signal (a different mechanism).
    return 0 if answer_has_secret else 1


if __name__ == "__main__":
    sys.exit(main())
