"""Offline validation of the DEPLOY learning loop aligned to the experiment (reflect credit +
consolidate_deploy). ZERO claude spend (claude-touching steps are monkeypatched). Asserts:
  (1) summarize_transcript extracts invoked Skill names + an errors flag from a transcript.jsonl.
  (2) reflect.run CREDITS the invoked mem-* bullets (uses+1 always; helpful+1 iff no error observed) —
      the deploy analogue of the experiment's reffree credit.
  (3) consolidate_deploy with NO replay benchmark STAGES induced candidates (never auto-activates blind).
  (4) ensure_skill_link is a NO-OP on a real-dir catalog (doesn't clobber the native assembly).
Run: python3 eval/test_deploy_learning.py
"""
import json
import os
import pathlib
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parent.parent
_HOME = tempfile.mkdtemp(prefix="deploy_home_")
os.environ["NATIVE_EVOLVE_HOME"] = _HOME
os.environ["NATIVE_EVOLVE_DEPLOY_INDUCE_EVERY"] = "1"     # force consolidation to run each call
sys.path.insert(0, str(REPO / "engine"))
from evolve import reflect, promote, store, curate, config, induce  # noqa: E402

# Stub the claude-touching halves so the whole test is offline.
reflect.reflect_deltas = lambda s: []
induce.induce = lambda focus_failures=True: []            # default: no candidates (overridden in test 3)

RESULTS = []


def check(name, cond):
    RESULTS.append(bool(cond))
    print(("ok   " if cond else "FAIL ") + name)


def _write_transcript(path, with_error):
    """A minimal Claude Code transcript.jsonl: user task, an assistant msg that invokes a Skill,
    and (optionally) a tool_result carrying an error."""
    lines = [
        {"type": "user", "message": {"role": "user", "content": "do the thing"}},
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "text", "text": "let me check memory"},
            {"type": "tool_use", "name": "Skill", "input": {"skill": "mem-m-0001"}},
        ]}},
    ]
    if with_error:
        lines.append({"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "content": "Traceback ... Error: boom"}]}})
    lines.append({"type": "assistant", "message": {"role": "assistant", "content": "done"}})
    pathlib.Path(path).write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")


def _seed_store():
    store.save([{"id": "m-0001", "type": "heuristic", "content": "x", "scope": "y",
                 "status": "active", "helpful": 0, "harmful": 0, "uses": 0}])


def test_transcript_extract():
    tp = os.path.join(_HOME, "t_err.jsonl"); _write_transcript(tp, with_error=True)
    summary, skills, had_errors = reflect.summarize_transcript(tp)
    check("extracts invoked Skill name from tool_use input", skills == ["mem-m-0001"])
    check("flags observed errors", had_errors is True)
    check("summary lists TOOLS USED", "TOOLS USED" in summary and "Skill" in summary)
    tp2 = os.path.join(_HOME, "t_clean.jsonl"); _write_transcript(tp2, with_error=False)
    _, _, err_clean = reflect.summarize_transcript(tp2)
    check("clean transcript -> no errors flag", err_clean is False)


def test_credit_success_and_fail():
    _seed_store()
    tp = os.path.join(_HOME, "ok.jsonl"); _write_transcript(tp, with_error=False)
    reflect.run(transcript_path=tp)
    b = {x["id"]: x for x in store.load()}["m-0001"]
    check("clean session credits uses+1 AND helpful+1", b["uses"] == 1 and b["helpful"] == 1)

    _seed_store()
    tp = os.path.join(_HOME, "bad.jsonl"); _write_transcript(tp, with_error=True)
    reflect.run(transcript_path=tp)
    b = {x["id"]: x for x in store.load()}["m-0001"]
    check("errored session credits uses+1 but NOT helpful", b["uses"] == 1 and b["helpful"] == 0)


def test_consolidate_stages_without_replay():
    # no replay cases in this home -> induced candidates must be STAGED, never auto-activated
    induce.induce = lambda focus_failures=True: [
        {"name": "sk-test", "md": "---\nname: sk-test\ndescription: d\n---\n\nbody\n", "skill": {}}]
    try:
        out = promote.consolidate_deploy()
    finally:
        induce.induce = lambda focus_failures=True: []
    state = store.load_skill_state()
    check("no replay -> candidate staged (not active)",
          out == [("sk-test", "candidate")] and state.get("sk-test", {}).get("status") == "candidate")


def test_ensure_skill_link_noop_on_realdir():
    link = config.CLAUDE_SKILLS_LINK
    link.mkdir(parents=True, exist_ok=True)
    (link / "marker.txt").write_text("keep me", encoding="utf-8")
    config.ensure_skill_link()
    check("ensure_skill_link does NOT clobber a real-dir catalog",
          link.is_dir() and not link.is_symlink() and (link / "marker.txt").exists())


if __name__ == "__main__":
    test_transcript_extract()
    test_credit_success_and_fail()
    test_consolidate_stages_without_replay()
    test_ensure_skill_link_noop_on_realdir()
    n, p = len(RESULTS), sum(RESULTS)
    print("\n%d/%d passed" % (p, n))
    sys.exit(0 if p == n else 1)
