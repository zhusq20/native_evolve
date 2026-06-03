"""Single source of truth for the memory store + skill state (deterministic I/O)."""
import json

from . import config


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
    config.MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    body = "\n".join(json.dumps(b, ensure_ascii=False) for b in items)
    config.STORE.write_text(body + ("\n" if body else ""), encoding="utf-8")


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
    config.MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    config.SKILL_STATE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )
