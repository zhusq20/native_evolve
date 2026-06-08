#!/usr/bin/env python3
"""Offline validation of the IFBench env (eval/envs/ifbench.py) on the VENDORED OFFICIAL IFEval
verifiers (eval/envs/ifeval_lib/). ZERO spend. Run: python3 eval/test_ifbench_env.py

Confirms: (1) all 25 official instruction types load; (2) per-type pass/fail is correct via the
official `check_following`; (3) the 2 types the old regex version could NOT do are now supported;
(4) the TYPE-1 property — verify() agrees with score() on the same response (reference-free signal
== gold criterion by construction); (5) the official strict convention (faithfulness details the
regex version got wrong, e.g. number_words only supports 'less than'/'at least').
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from envs import ifbench  # noqa: E402

passed = 0


def check(name, cond):
    global passed
    print(("PASS " if cond else "FAIL ") + name)
    assert cond, name
    passed += 1


def em(iids, kwargs, resp, prompt="Write a short note about cats."):
    task = {"prompt": prompt, "instruction_id_list": iids, "kwargs": kwargs}
    return ifbench.score(task, resp)["em"]


# ---- registry / vendoring ----
check("all 25 official instruction types loaded", len(ifbench.SUPPORTED) == 25)
check("vendored from the official registry (not the regex stub)",
      "language:response_language" in ifbench.SUPPORTED
      and "length_constraints:nth_paragraph_first_word" in ifbench.SUPPORTED)

# ---- per-type pass/fail (structural) ----
check("no_comma PASS", em(["punctuation:no_comma"], [{}], "no commas at all here") == 1.0)
check("no_comma FAIL", em(["punctuation:no_comma"], [{}], "this, has a comma") == 0.0)
check("json_format PASS", em(["detectable_format:json_format"], [{}], '{"a": 1, "b": [2,3]}') == 1.0)
check("json_format FAIL", em(["detectable_format:json_format"], [{}], "not json") == 0.0)
check("title PASS", em(["detectable_format:title"], [{}], "<<On Cats>>\nThey purr.") == 1.0)
check("title FAIL", em(["detectable_format:title"], [{}], "no title line") == 0.0)
check("quotation PASS", em(["startend:quotation"], [{}], '"the whole thing in quotes"') == 1.0)

# ---- per-type pass/fail (counting; punkt/regexp tokenizers) ----
check("number_words >=3 PASS", em(["length_constraints:number_words"],
      [{"num_words": 3, "relation": "at least"}], "one two three four") == 1.0)
check("number_words >=10 FAIL", em(["length_constraints:number_words"],
      [{"num_words": 10, "relation": "at least"}], "too few words") == 0.0)
check("number_sentences <2 PASS (punkt, Dr. abbrev not a boundary)",
      em(["length_constraints:number_sentences"], [{"num_sentences": 2, "relation": "less than"}],
         "Dr. Smith is here.") == 1.0)

# ---- the 2 NEWLY-supported types (impossible in the old regex version) ----
check("response_language en PASS", em(["language:response_language"], [{"language": "en"}],
      "This is clearly written in the English language about cats.") == 1.0)
check("response_language en FAIL on French",
      em(["language:response_language"], [{"language": "en"}],
         "Ceci est un texte en français sur les chats.") == 0.0)
check("nth_paragraph_first_word PASS", em(["length_constraints:nth_paragraph_first_word"],
      [{"num_paragraphs": 2, "nth_paragraph": 1, "first_word": "Cats"}],
      "Cats are great.\n\nThey also purr.") == 1.0)

# ---- official strictness the regex version got WRONG ----
# number_words only supports 'less than' / 'at least' — 'exactly' is rejected by build_description.
task = {"prompt": "x", "instruction_id_list": ["length_constraints:number_words"],
        "kwargs": [{"num_words": 2, "relation": "exactly"}]}
ev = ifbench.score(task, "two words here")
check("unsupported relation -> checker error counts as not-satisfied (faithful, never crashes)",
      ev["em"] == 0.0 and ev["_n"] == 1)

# ---- multi-constraint prompt-level STRICT em ----
multi = (["punctuation:no_comma", "length_constraints:number_words"],
         [{}, {"num_words": 2, "relation": "at least"}])
check("strict em: ALL pass -> 1.0", em(*multi, "clean two words") == 1.0)
check("strict em: one fails -> 0.0", em(*multi, "has, two words") == 0.0)

# ---- TYPE-1: verify() agrees with score() (reference-free == gold criterion) ----
vtask = {"prompt": "x", "instruction_id_list": ["punctuation:no_comma", "startend:quotation"],
         "kwargs": [{}, {}]}
for resp in ['"clean quoted text"', 'bad, unquoted']:
    ev = ifbench.score(vtask, resp)
    vf = ifbench.verify(vtask, resp)
    check("verify()==score() on %r (TYPE-1)" % resp[:20], (ev["em"] == 1.0) == vf["ok"])
check("verify() returns None when no constraints", ifbench.verify({"instruction_id_list": [], "kwargs": []}, "x") is None)

# ---- the tracked dataset loads + every task is fully supported (faithful scoring) ----
data = pathlib.Path(__file__).resolve().parent / "data" / "ifbench_val.jsonl"
if data.exists():
    tasks = ifbench.load_tasks(str(data))
    check("dataset loads", len(tasks) > 0)
    allsup = all(all(i in ifbench.SUPPORTED for i in t.get("instruction_id_list", [])) for t in tasks)
    check("every dataset task uses only supported (officially-scored) instructions", allsup)
    ev = ifbench.score(tasks[0], "A short note.\n\nAbout cats here.")
    check("score runs on a real task", "em" in ev and ev["_n"] >= 1)

print("\n%d checks passed" % passed)
