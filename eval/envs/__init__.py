"""Pluggable evaluation environments.

Each env module exposes a uniform interface so the prequential runner and all
baselines are env-agnostic:

    NAME : str
    load_tasks(path)            -> list[dict]
    build_prompt(task, mem)     -> str         # mem is the injected memory/skill block ("" if none)
    score(task, response)       -> dict        # must contain em/f1/sub_em + predicted_answer; em is primary
    summarize(task, resp, ev)   -> str         # reflection input describing the outcome
    fetch(n, out, **kw)         -> None        # optional: materialize a task file

Add a new env by dropping in envs/<name>.py with these symbols.
"""
import importlib


def get_env(name):
    return importlib.import_module("envs." + name)
