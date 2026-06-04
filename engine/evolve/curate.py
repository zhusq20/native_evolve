"""Deterministic Curator: merge Reflector deltas into the store.

NEVER lets an LLM rewrite the store wholesale (ACE: that causes context collapse).
Only three ops, each touching a single bullet:
  add        -> append a new bullet (or reinforce a near-duplicate)
  reinforce  -> bump helpful/harmful counters of an existing id
  revise     -> replace the content of an existing id (id stays stable)
"""
import datetime
import re

from . import config, store


def _tokens(text):
    return set(re.findall(r"\w+", (text or "").lower()))


def _near_duplicate(content, items):
    c = _tokens(content)
    if not c:
        return None
    for b in items:
        other = _tokens(b.get("content", ""))
        union = c | other
        if union and len(c & other) / len(union) > config.DEDUP_JACCARD:
            return b
    return None


def merge(deltas):
    """Apply a list of delta dicts. Returns the number of changes applied."""
    items = store.load()
    by_id = {b["id"]: b for b in items}
    today = datetime.date.today().isoformat()
    nid = store.next_id(items)
    changed = 0

    for d in deltas or []:
        op = d.get("op")

        if op == "add":
            content = (d.get("content") or "").strip()
            if not content:
                continue
            dup = _near_duplicate(content, items)
            if dup is not None:  # treat near-dup as reinforcement, not a new row
                dup["helpful"] = dup.get("helpful", 0) + 1
                dup["last_used"] = today
                changed += 1
                continue
            bullet = {
                "id": "m-{:04d}".format(nid),
                "type": d.get("type", "heuristic"),
                "content": content,
                "scope": d.get("scope", ""),
                "helpful": 1,
                "harmful": 0,
                "uses": 0,
                "last_used": today,
                "source_tasks": [],
                "status": "active",
            }
            items.append(bullet)
            by_id[bullet["id"]] = bullet
            nid += 1
            changed += 1

        elif op == "reinforce" and d.get("id") in by_id:
            b = by_id[d["id"]]
            b["uses"] = b.get("uses", 0) + 1
            b["last_used"] = today
            if d.get("helpful", True):
                b["helpful"] = b.get("helpful", 0) + 1
            else:
                b["harmful"] = b.get("harmful", 0) + 1
            # repeatedly misleading -> auto-deprecate (acts as the reject-buffer)
            if b["harmful"] >= config.DEPRECATE_HARMFUL and b["harmful"] > b["helpful"]:
                b["status"] = "deprecated"
            changed += 1

        elif op == "revise" and d.get("id") in by_id:
            content = (d.get("content") or "").strip()
            if content:
                by_id[d["id"]]["content"] = content
                changed += 1

    if changed:
        store.save(items)
    return changed


def credit(ids, success):
    """Deterministically credit the bullets that were in-context for an evaluated task.

    Presence-based, gold-grounded attribution: every injected bullet gets uses+1; on a
    PASSING task it also gets helpful+1. A failure does NOT add harmful — a bullet being
    present when an (often unrelated) task fails is not evidence it misled, and a false
    harmful would wrongly deprecate it and permanently block the gate (harmful==0). This
    is the deterministic signal that lets uses/helpful climb so the promotion gate can
    fire; like the rest of curation it NEVER lets an LLM rewrite the store. Proving
    causal (not merely correlational) lift is the job of the counterfactual gate.

    Returns the number of bullets credited.
    """
    if not ids:
        return 0
    items = store.load()
    by_id = {b["id"]: b for b in items}
    today = datetime.date.today().isoformat()
    changed = 0
    for i in ids:
        b = by_id.get(i)
        if b is None:
            continue
        b["uses"] = b.get("uses", 0) + 1
        b["last_used"] = today
        if success:
            b["helpful"] = b.get("helpful", 0) + 1
        changed += 1
    if changed:
        store.save(items)
    return changed
