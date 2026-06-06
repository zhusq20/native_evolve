#!/usr/bin/env python3
"""Offline validation of the agentic-index retriever (engine/evolve/retrieve.py).

Zero `claude` spend: we monkeypatch store.load (canned bullets) and llm.call_claude
(canned JSON replies) and assert the model-selection + (block, ids) contract holds,
including the fail-safe paths. Run: python3 eval/test_agentic_retrieval.py
"""
import os
import pathlib
import sys
import tempfile

ENGINE_DIR = pathlib.Path(__file__).resolve().parents[1] / "engine"
os.environ.setdefault("NATIVE_EVOLVE_HOME", tempfile.mkdtemp(prefix="ne_test_"))
sys.path.insert(0, str(ENGINE_DIR))

from evolve import retrieve  # noqa: E402

BULLETS = [
    {"id": "m-0001", "status": "active", "content": "Lesson one about paragraphs."},
    {"id": "m-0002", "status": "active", "content": "Lesson two about JSON output."},
    {"id": "m-0003", "status": "active", "content": "Lesson three about word counts."},
    {"id": "m-0099", "status": "archived", "content": "Inactive lesson (must be ignored)."},
]

_calls = {"n": 0, "last_prompt": ""}


def _fake_store_load():
    return list(BULLETS)


def _fake_llm(reply):
    def _call(prompt, *a, **k):
        _calls["n"] += 1
        _calls["last_prompt"] = prompt
        return reply
    return _call


def _patch(reply):
    retrieve.store.load = _fake_store_load
    retrieve.llm.call_claude = _fake_llm(reply)


passed = 0


def check(name, cond):
    global passed
    print(("PASS " if cond else "FAIL ") + name)
    assert cond, name
    passed += 1


# 1. Happy path: model returns valid ids in priority order -> selected in that order.
_patch('{"ids": ["m-0002", "m-0001"]}')
sel = retrieve.select_agentic("write some JSON", k=8)
check("happy: 2 selected", len(sel) == 2)
check("happy: priority order preserved", [b["id"] for b in sel] == ["m-0002", "m-0001"])

# 2. (block, ids) contract: ids match block, header present.
_patch('{"ids": ["m-0001"]}')
block, ids = retrieve.select_and_block_agentic("paragraph task")
check("contract: ids == ['m-0001']", ids == ["m-0001"])
check("contract: block cites the id", "[m-0001]" in block and "Lesson one" in block)

# 3. Cap at k.
_patch('{"ids": ["m-0001", "m-0002", "m-0003"]}')
sel = retrieve.select_agentic("anything", k=2)
check("cap: k=2 truncates 3->2", [b["id"] for b in sel] == ["m-0001", "m-0002"])

# 4. Invalid / inactive / duplicate ids are filtered.
_patch('{"ids": ["m-0099", "m-9999", "m-0002", "m-0002"]}')
sel = retrieve.select_agentic("x", k=8)
check("filter: archived+unknown+dup dropped -> only m-0002", [b["id"] for b in sel] == ["m-0002"])

# 5. None selected -> empty block + empty ids (no crash).
_patch('{"ids": []}')
block, ids = retrieve.select_and_block_agentic("irrelevant")
check("empty selection: ('', [])", block == "" and ids == [])

# 6. Unparseable reply -> fail-safe [] (no exception).
_patch("the model rambled with no json")
check("unparseable -> []", retrieve.select_agentic("x") == [])

# 7. Non-list ids field -> [].
_patch('{"ids": "m-0001"}')
check("non-list ids -> []", retrieve.select_agentic("x") == [])

# 8. Empty store -> [] WITHOUT calling the model (no wasted spend).
retrieve.store.load = lambda: []
_calls["n"] = 0
retrieve.llm.call_claude = _fake_llm('{"ids": ["m-0001"]}')
out = retrieve.select_agentic("x")
check("empty store -> [] and no claude call", out == [] and _calls["n"] == 0)

# 9. call_claude raising -> fail-safe [] (task must not crash).
retrieve.store.load = _fake_store_load

def _boom(*a, **k):
    raise RuntimeError("claude down")

retrieve.llm.call_claude = _boom
check("llm error -> []", retrieve.select_agentic("x") == [])

# 10. The selection prompt actually presents the index (ids + content) and the task.
_patch('{"ids": ["m-0001"]}')
retrieve.select_agentic("MY-UNIQUE-TASK-STRING", k=8)
p = _calls["last_prompt"]
check("prompt embeds the task", "MY-UNIQUE-TASK-STRING" in p)
check("prompt embeds the index ids+content",
      "[m-0001]" in p and "Lesson one about paragraphs." in p)
check("prompt excludes archived bullet", "m-0099" not in p)

print("\n%d/%d checks passed" % (passed, passed))
