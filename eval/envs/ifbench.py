"""IFBench / IFEval environment — instruction-following with REFERENCE-FREE verifiers.

The scoring modality the project lacked: each task is a prompt + a list of programmatically
checkable constraints (instruction_id_list + kwargs). Scoring runs the constraint verifiers on
the response — there is NO gold answer, the rubric IS the verifier set. That makes this the
cleanest case for our reference-free repair loop: `verify()` runs the SAME checks the scorer
will, so a failed attempt can be told EXACTLY which constraints it violated and fix them, with
zero label leakage (there are no labels). em = prompt-level STRICT accuracy (all constraints
satisfied); f1 = fraction of constraints satisfied.

Data = google/IFEval (541 prompts) via the HF datasets-server. Verifiers are a faithful
stdlib-only reimplementation of the IFEval `instructions_registry`. Two instruction types are
NOT implemented (no stdlib-faithful version): `language:response_language` (needs langdetect) and
`length_constraints:nth_paragraph_first_word` (brittle); `fetch` FILTERS to prompts whose every
instruction is implemented, so scoring is faithful on every retained task. Word/sentence/paragraph
counts use regex approximations of the nltk tokenizers the official code uses (close, not identical).
"""
import json
import pathlib
import re
import time
import urllib.request

NAME = "ifbench"
_DS = "https://datasets-server.huggingface.co/rows"


# ---------------- counting helpers (regex approximations of the nltk utils) ----------------

def _words(text):
    return re.findall(r"\b\w+\b", text or "")


def _sentences(text):
    return [s for s in re.split(r"[.!?]+", text or "") if s.strip()]


def _paragraphs(text):
    return [p for p in re.split(r"\n\s*\n", (text or "").strip()) if p.strip()]


def _rel(count, relation, target):
    r = (relation or "").lower()
    if "at least" in r or "more than or equal" in r:
        return count >= target
    if "less than" in r:
        return count < target
    if "at most" in r or "no more than" in r:
        return count <= target
    if "more than" in r:
        return count > target
    if "exactly" in r or "equal" in r:
        return count == target
    return count >= target


def _count_highlights(text):
    num = 0
    for m in re.findall(r"\*[^\n\*]*\*", text or ""):
        if m.strip("*").strip():
            num += 1
    for m in re.findall(r"\*\*[^\n\*]*\*\*", text or ""):
        if m.strip("*").strip():
            num += 1
    return num


# ---------------- verifier registry: id -> fn(response, kwargs) -> (ok, short_description) ----------------

def _v_no_comma(t, k):
    return ("," not in t, "use NO commas anywhere")

def _v_number_words(t, k):
    n = len(_words(t)); tgt = k.get("num_words") or 0
    return (_rel(n, k.get("relation"), tgt), "%s %d words (had %d)" % (k.get("relation"), tgt, n))

def _v_number_sentences(t, k):
    n = len(_sentences(t)); tgt = k.get("num_sentences") or 0
    return (_rel(n, k.get("relation"), tgt), "%s %d sentences (had %d)" % (k.get("relation"), tgt, n))

def _v_number_paragraphs(t, k):
    n = len(_paragraphs(t)); tgt = k.get("num_paragraphs") or 0
    return (n == tgt, "exactly %d paragraphs separated by blank lines (had %d)" % (tgt, n))

def _v_forbidden_words(t, k):
    low = (t or "").lower()
    bad = [w for w in (k.get("forbidden_words") or []) if re.search(r"\b%s\b" % re.escape(w.lower()), low)]
    return (not bad, "do NOT use the word(s): %s" % ", ".join(k.get("forbidden_words") or []))

def _v_existence(t, k):
    low = (t or "").lower()
    missing = [w for w in (k.get("keywords") or []) if w.lower() not in low]
    return (not missing, "must include keyword(s): %s (missing %s)" % (k.get("keywords"), missing))

def _v_frequency(t, k):
    kw = (k.get("keyword") or ""); n = len(re.findall(r"\b%s\b" % re.escape(kw.lower()), (t or "").lower()))
    tgt = k.get("frequency") or 0
    return (_rel(n, k.get("relation"), tgt), "keyword '%s' %s %d times (had %d)" % (kw, k.get("relation"), tgt, n))

def _v_letter_frequency(t, k):
    let = (k.get("letter") or ""); n = (t or "").lower().count(let.lower()); tgt = k.get("let_frequency") or 0
    return (_rel(n, k.get("let_relation"), tgt), "letter '%s' %s %d times (had %d)" % (let, k.get("let_relation"), tgt, n))

def _v_lowercase(t, k):
    return (not any(c.isupper() for c in (t or "")), "all text must be lowercase")

def _v_capital(t, k):
    return (not any(c.islower() for c in (t or "")), "ALL text must be UPPERCASE")

def _v_capital_word_freq(t, k):
    n = sum(1 for w in _words(t) if w.isupper() and any(c.isalpha() for c in w)); tgt = k.get("capital_frequency") or 0
    return (_rel(n, k.get("capital_relation"), tgt),
            "all-caps words %s %d (had %d)" % (k.get("capital_relation"), tgt, n))

def _v_title(t, k):
    return (bool(re.search(r"<<[^>]+>>", t or "")), "include a title wrapped in <<double angular brackets>>")

def _v_highlights(t, k):
    n = _count_highlights(t); tgt = k.get("num_highlights") or 0
    return (n >= tgt, "at least %d *highlighted* sections (had %d)" % (tgt, n))

def _v_bullets(t, k):
    n = len(re.findall(r"(?m)^\s*[\*\-]\s+\S", t or "")); tgt = k.get("num_bullets") or 0
    return (n == tgt, "exactly %d markdown bullet points (had %d)" % (tgt, n))

def _v_placeholders(t, k):
    n = len(re.findall(r"\[[^\]]*\]", t or "")); tgt = k.get("num_placeholders") or 0
    return (n >= tgt, "at least %d [square-bracket placeholders] (had %d)" % (tgt, n))

def _v_postscript(t, k):
    mk = (k.get("postscript_marker") or "P.S.")
    return (mk.lower().replace(" ", "") in (t or "").lower().replace(" ", ""),
            "include a postscript starting with '%s'" % mk)

def _v_end_checker(t, k):
    ph = (k.get("end_phrase") or "").strip()
    return ((t or "").strip().endswith(ph), "end with EXACTLY the phrase: '%s'" % ph)

def _v_quotation(t, k):
    s = (t or "").strip()
    return (len(s) >= 2 and s.startswith('"') and s.endswith('"'), "wrap the WHOLE response in double quotes")

def _v_constrained(t, k):
    return ((t or "").strip() in ("My answer is yes.", "My answer is no.", "My answer is maybe."),
            "answer with exactly one of: 'My answer is yes./no./maybe.'")

def _v_two_responses(t, k):
    parts = [p for p in (t or "").split("******") if p.strip()]
    return (len(parts) == 2, "give TWO different responses separated by 6 asterisks ******")

def _v_json(t, k):
    s = (t or "").strip()
    s = re.sub(r"^```(?:json)?\s*", "", s); s = re.sub(r"\s*```$", "", s)
    try:
        json.loads(s); return (True, "entire response must be valid JSON")
    except Exception:
        return (False, "entire response must be valid JSON")

def _v_repeat_prompt(t, k):
    rep = re.sub(r"\s+", " ", (k.get("prompt_to_repeat") or "").strip().lower())
    got = re.sub(r"\s+", " ", (t or "").strip().lower())
    return (rep and got.startswith(rep), "first REPEAT the request verbatim, then answer")

def _v_multiple_sections(t, k):
    sp = (k.get("section_spliter") or "SECTION"); tgt = k.get("num_sections") or 0
    n = len(re.findall(re.escape(sp), t or "", flags=re.IGNORECASE))
    return (n >= tgt, "at least %d sections each marked '%s'" % (tgt, sp))


_REGISTRY = {
    "punctuation:no_comma": _v_no_comma,
    "length_constraints:number_words": _v_number_words,
    "length_constraints:number_sentences": _v_number_sentences,
    "length_constraints:number_paragraphs": _v_number_paragraphs,
    "keywords:forbidden_words": _v_forbidden_words,
    "keywords:existence": _v_existence,
    "keywords:frequency": _v_frequency,
    "keywords:letter_frequency": _v_letter_frequency,
    "change_case:english_lowercase": _v_lowercase,
    "change_case:english_capital": _v_capital,
    "change_case:capital_word_frequency": _v_capital_word_freq,
    "detectable_format:title": _v_title,
    "detectable_format:number_highlighted_sections": _v_highlights,
    "detectable_format:number_bullet_lists": _v_bullets,
    "detectable_content:number_placeholders": _v_placeholders,
    "detectable_content:postscript": _v_postscript,
    "startend:end_checker": _v_end_checker,
    "startend:quotation": _v_quotation,
    "detectable_format:constrained_response": _v_constrained,
    "combination:two_responses": _v_two_responses,
    "detectable_format:json_format": _v_json,
    "combination:repeat_prompt": _v_repeat_prompt,
    "detectable_format:multiple_sections": _v_multiple_sections,
}
SUPPORTED = set(_REGISTRY)


# ---------------- env interface ----------------

def load_tasks(path):
    return [json.loads(l) for l in pathlib.Path(path).read_text().splitlines() if l.strip()]


def build_prompt(task, mem):
    head = task["prompt"]
    return (mem + "\n\n" + head) if mem else head


def _check_all(task, response):
    """Return [(instruction_id, ok, description), ...] for every constraint on the task."""
    out = []
    for iid, kw in zip(task.get("instruction_id_list", []), task.get("kwargs", [])):
        fn = _REGISTRY.get(iid)
        if fn is None:
            continue
        try:
            ok, desc = fn(response or "", kw or {})
        except Exception as exc:  # a verifier crash counts as not-satisfied, never crashes the run
            ok, desc = False, "%s (checker error: %s)" % (iid, exc)
        out.append((iid, bool(ok), desc))
    return out


def score(task, response):
    results = _check_all(task, response)
    n = len(results)
    npass = sum(1 for _, ok, _ in results if ok)
    em = 1.0 if (n > 0 and npass == n) else 0.0     # prompt-level STRICT accuracy
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
    """Materialize an IFBench/IFEval task file, KEEPING only prompts whose every instruction is
    implemented stdlib-only (so scoring is faithful on every retained task)."""
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
