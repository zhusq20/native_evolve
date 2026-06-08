"""IFBench / IFEval environment — instruction-following with REFERENCE-FREE verifiers.

The scoring modality the project lacked: each task is a prompt + a list of programmatically
checkable constraints (instruction_id_list + kwargs). Scoring runs the constraint verifiers on
the response — there is NO gold answer, the rubric IS the verifier set. That makes this the
cleanest case for our reference-free repair loop AND a genuine TYPE-1 gate signal: `verify()`
runs the SAME checks `score()` will (both call `_check_all`), so the reference-free signal ==
the gold criterion BY CONSTRUCTION (zero label leakage — there are no labels). em = prompt-level
STRICT accuracy (all constraints satisfied); f1 = fraction of constraints satisfied.

Verifiers are the OFFICIAL google-research IFEval `instructions_registry`, VENDORED verbatim into
`eval/envs/ifeval_lib/` (like sb_lib/ vendors SkillOpt's executor) — not a reimplementation. All
25 instruction types are supported (incl. `language:response_language` via langdetect and
`length_constraints:nth_paragraph_first_word`). We replicate the official strict-check loop
(`evaluation_lib.test_instruction_following_strict`): build_description(**kwargs) → re-build with
the prompt if the instruction needs it → check_following. Deps: nltk (+punkt), langdetect,
immutabledict, absl-py. Data = google/IFEval (541 prompts) via the HF datasets-server.
"""
import json
import pathlib
import time
import urllib.request

# Vendored official IFEval registry (package-relative so it is imported as envs.ifeval_lib.*,
# never polluting the top-level namespace — avoids shadowing stdlib `math` with our envs/math.py).
from .ifeval_lib import instructions_registry as _registry

NAME = "ifbench"
_DS = "https://datasets-server.huggingface.co/rows"

_INSTRUCTION_DICT = _registry.INSTRUCTION_DICT
SUPPORTED = set(_INSTRUCTION_DICT)


# ---------------- env interface ----------------

def load_tasks(path):
    return [json.loads(l) for l in pathlib.Path(path).read_text().splitlines() if l.strip()]


def build_prompt(task, mem):
    head = task["prompt"]
    return (mem + "\n\n" + head) if mem else head


def _check_all(task, response):
    """Return [(instruction_id, ok, description), ...] for every constraint on the task, using the
    OFFICIAL IFEval verifiers and the official STRICT-check convention (build_description(**kwargs);
    re-build with the prompt if the instruction's args include it; require a non-empty response)."""
    out = []
    prompt = task.get("prompt", "")
    ids = task.get("instruction_id_list", []) or []
    kwargs_list = task.get("kwargs", []) or []
    resp = response or ""
    for index, iid in enumerate(ids):
        cls = _INSTRUCTION_DICT.get(iid)
        if cls is None:
            continue                                     # unknown id (filtered at fetch; never scored)
        kw = {}
        if index < len(kwargs_list):
            kw = {k: v for k, v in (kwargs_list[index] or {}).items() if v is not None}
        try:
            inst = cls(iid)
            desc = inst.build_description(**kw)
            args = inst.get_instruction_args()
            if args and "prompt" in args:                # prompt-dependent instructions (e.g. repeat_prompt)
                desc = inst.build_description(prompt=prompt)
            ok = bool(resp.strip() and inst.check_following(resp))
        except Exception as exc:                         # a checker crash counts as not-satisfied
            ok, desc = False, "%s (checker error: %s)" % (iid, exc)
        out.append((iid, bool(ok), desc))
    return out


def score(task, response):
    results = _check_all(task, response)
    n = len(results)
    npass = sum(1 for _, ok, _ in results if ok)
    em = 1.0 if (n > 0 and npass == n) else 0.0          # prompt-level STRICT accuracy
    soft = (npass / n) if n else 0.0
    return {"em": em, "f1": soft, "sub_em": em,
            "predicted_answer": (response or "").strip()[:80],
            "gold_answers": [i for i, _, _ in results],
            "_results": results, "_npass": npass, "_n": n}


def verify(task, attempt):
    """REFERENCE-FREE check == the rubric itself (IFEval has no gold). Tells the agent exactly
    which constraints failed so the repair loop can fix them. None if no implemented constraints."""
    results = _check_all(task, attempt)
    if not results:
        return None
    failed = [(i, d) for i, ok, d in results if not ok]
    if not failed:
        return {"ok": True, "signature": "", "feedback": ""}
    sig = ",".join(sorted(set(i.split(":")[0] for i, _ in failed)))
    fb = ("Your response VIOLATED these required constraints:\n"
          + "\n".join("- %s" % d for _, d in failed)
          + "\nRewrite the response so it satisfies ALL constraints at once, staying on-topic.")
    return {"ok": False, "signature": sig[:60], "feedback": fb}


def evidence(task, response, ev):
    results = ev.get("_results") or _check_all(task, response)
    failed = [d for i, ok, d in results if not ok]
    correct = ev["em"] == 1.0
    return {
        "outcome": "PASS" if correct else "FAIL",
        "task": "IFBench instruction-following: " + (task.get("prompt", "")[:600]),
        "predicted": "satisfied %d/%d constraints; response: %s"
                     % (ev.get("_npass", 0), ev.get("_n", 0), (response or "").strip()[:200]),
        "gold": "ALL constraints must hold: " + "; ".join(i for i, _, _ in results),
        "diagnosis": "" if correct else ("Violated constraints:\n" + "\n".join("- " + d for d in failed)),
    }


def summarize(task, response, ev):
    results = ev.get("_results") or _check_all(task, response)
    failed = [d for i, ok, d in results if not ok]
    return ("USER TASK (IFBench instruction-following):\n%s\n\nWAS CORRECT (all constraints): %s "
            "(%d/%d)\nVIOLATED:\n%s\n\nRESPONSE:\n%s"
            % (task.get("prompt", "")[:700], ev["em"] == 1.0, ev.get("_npass", 0), ev.get("_n", 0),
               "\n".join("- " + d for d in failed) or "(none)", (response or "")[:600]))


def fetch(n, out, split="train", config="default"):
    """Materialize an IFBench/IFEval task file. With the official registry ALL 25 instruction types
    are supported, so the filter now keeps every standard IFEval prompt (it remains as a safety net
    against any future unknown id, so scoring stays faithful on every retained task)."""
    out = pathlib.Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    kept, offset = [], 0
    while len(kept) < n and offset < 600:
        url = (_DS + "?dataset=google%2FIFEval&config=" + config + "&split=" + split
               + "&offset=" + str(offset) + "&length=100")
        with urllib.request.urlopen(url, timeout=30) as r:
            page = json.loads(r.read().decode("utf-8"))
        batch = page.get("rows", [])
        if not batch:
            break
        for entry in batch:
            row = entry.get("row", {})
            ids = row.get("instruction_id_list", []) or []
            if ids and all(i in SUPPORTED for i in ids):
                kept.append({
                    "id": str(row.get("key", "if-%d" % offset)),
                    "prompt": row.get("prompt", ""),
                    "question": row.get("prompt", ""),
                    "instruction_id_list": ids,
                    "kwargs": [{k: v for k, v in (kw or {}).items() if v is not None}
                               for kw in row.get("kwargs", [])],
                })
        offset += len(batch)
        time.sleep(0.2)
    with out.open("w", encoding="utf-8") as f:
        for r in kept[:n]:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("wrote %d ifbench tasks -> %s" % (min(len(kept), n), out))
