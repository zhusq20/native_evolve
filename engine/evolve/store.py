"""Single source of truth for the memory store + skill state (deterministic I/O).

Serving-safe: writes are ATOMIC (tmp + os.replace, so a concurrent reader/retrieval never
sees a truncated file) and STORE_LOCK serializes read-modify-write mutations (curate.merge/
credit, episodic append) so concurrent learners can't lose updates. This makes a parallel
serving deployment — many requests served against the live store while reflection writes in
the background — race-free, without changing the deterministic curation logic.
"""
import json
import os
import threading

from . import config

# Serializes read-modify-write store mutations across threads (the serving learner pool, or
# concurrent Stop-hook reflections in a real deployment). Reentrant so a holder can nest.
STORE_LOCK = threading.RLock()


def _atomic_write(path, text):
    config.MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    tmp = "%s.tmp.%d" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, str(path))           # atomic on POSIX: a reader sees old-or-new, never partial


def load():
    """Return the list of memory bullets (tolerant of malformed lines)."""
    if not config.STORE.exists():
        return []
    items = []
    for line in config.STORE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except Exception:
            continue
    return items


def save(items):
    body = "\n".join(json.dumps(b, ensure_ascii=False) for b in items)
    _atomic_write(config.STORE, body + ("\n" if body else ""))


def next_id(items):
    n = 0
    for b in items:
        try:
            n = max(n, int(str(b.get("id", "m-0")).split("-")[1]))
        except Exception:
            pass
    return n + 1


def load_skill_state():
    if config.SKILL_STATE.exists():
        try:
            return json.loads(config.SKILL_STATE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_skill_state(state):
    _atomic_write(config.SKILL_STATE, json.dumps(state, ensure_ascii=False, indent=2))
