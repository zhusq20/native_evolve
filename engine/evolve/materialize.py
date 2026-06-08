"""Materialize the memory store as DISCOVERABLE Claude Code skills (the native paradigm).

Instead of the harness force-INJECTING a top-k slice of memory into every prompt, we write each
memory item as its own `<name>/SKILL.md` into a `.claude/skills/` directory and let the SOLVING
agent natively discover the catalog (name + description always visible) and INVOKE only what it
judges relevant (body lazy-loaded). This makes the eval harness behave like a real Claude Code
deployment, and unifies the two memory tiers (distilled bullets + episodic exemplars) and the
promoted-skill tier under ONE selection mechanism: the agent's own.

Determinism rule stays intact: this only RE-RENDERS existing store records as skill files (pure
Python). No LLM rewrites memory; reflect/induce/gate are the only LLM steps.

Naming (so attribution can reverse-map what the agent invoked):
  distilled bullet id `m-0001`  -> skill `mem-m-0001`   (credited; reverse = strip the `mem-` prefix)
  episode task id `<tid>`       -> skill `ex-<slug(tid)>-<i>` (NOT credited, like episodic today)
  promoted skill `<name>`       -> symlinked through verbatim (its own skill_state lifecycle)
"""
import json
import os
import re
import shutil

from . import config, store, episodic

MEM_PREFIX = "mem-"
EX_PREFIX = "ex-"

# Coarse upper bound on how many memory units enter the catalog (most-proven first). The agent does
# the fine per-task selection from this capped set — same role as select_agentic's max_index: a
# bound so a huge store can't blow the catalog, NOT a per-task relevance filter.
CATALOG_CAP = int(os.environ.get("NATIVE_EVOLVE_CATALOG_CAP", "40"))
EX_CAP = int(os.environ.get("NATIVE_EVOLVE_EX_CAP", "20"))


def _slug(text):
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:48] or "x"


def _yaml_one_line(text, limit=240):
    """A YAML-safe, single-line double-quoted scalar (memory content is freeform → may hold ':')."""
    t = " ".join((text or "").split())
    if len(t) > limit:
        t = t[: limit - 1].rstrip() + "…"
    return '"' + t.replace("\\", "\\\\").replace('"', '\\"') + '"'


def bullet_skill(bullet):
    """(name, SKILL.md text) for one distilled bullet. description = scope (its 'when to use'),
    falling back to the content when scope is empty."""
    bid = bullet["id"]
    name = MEM_PREFIX + bid
    content = (bullet.get("content", "") or "").strip()
    desc = (bullet.get("scope", "") or "").strip() or content
    md = (
        "---\n"
        "name: %s\n"
        "description: %s\n"
        "---\n\n"
        "%s\n\n"
        "(memory id: %s — if this lesson shaped your answer, you used it)\n"
        % (name, _yaml_one_line(desc), content, bid)
    )
    return name, md


def episode_skill(ep, idx):
    """(name, SKILL.md text) for one past-success episode, rendered as a worked exemplar."""
    name = "%s%s-%d" % (EX_PREFIX, _slug(ep.get("id", "")), idx)
    q = (ep.get("question", "") or "").strip()
    sol = (ep.get("solution", "") or "").strip()
    desc = "A past task you solved CORRECTLY (reuse the approach): " + q
    md = (
        "---\n"
        "name: %s\n"
        "description: %s\n"
        "---\n\n"
        "## A similar task you previously solved CORRECTLY\n"
        "Task: %s\n\n"
        "Your working solution (adapt the approach, do not copy blindly):\n%s\n"
        % (name, _yaml_one_line(desc), q[:600], sol[:1400])
    )
    return name, md


def _clear_generated(skills_dir):
    """Remove only the generated mem-*/ex-* skill dirs (leave promoted skills / symlinks alone)."""
    if not os.path.isdir(skills_dir):
        return
    for child in os.listdir(skills_dir):
        if child.startswith(MEM_PREFIX) or child.startswith(EX_PREFIX):
            shutil.rmtree(os.path.join(skills_dir, child), ignore_errors=True)


def _write_skill(skills_dir, name, md):
    d = os.path.join(skills_dir, name)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write(md)


def _link_promoted(skills_dir):
    """Symlink each ACTIVE promoted skill dir into skills_dir (so the catalog also offers tier-2)."""
    state = store.load_skill_state()
    for nm, rec in state.items():
        if rec.get("status") != "active":
            continue
        src = config.SKILLS_DIR / nm
        if not (src / "SKILL.md").exists():
            continue
        dst = os.path.join(skills_dir, nm)
        if os.path.lexists(dst):
            continue
        try:
            os.symlink(os.path.abspath(str(src)), dst, target_is_directory=True)
        except OSError:
            shutil.copytree(str(src), dst)


def materialize_into(
    skills_dir,
    items=None,
    episodes=None,
    include_promoted=True,
    include_episodes=True,
    extra_skills=None,
    cap=CATALOG_CAP,
    ex_cap=EX_CAP,
):
    """(Re)generate the discoverable-skill catalog under `skills_dir` from the current store.

    items     : distilled bullets (default: store.load()); only status=='active' with content used.
    episodes  : episodic records (default: episodic.load()); past successes only.
    extra_skills: [(name, md), ...] written verbatim — used by the gate to add a CANDIDATE skill.
    Returns a manifest: list of {"name", "kind", "id"} for what was written/linked.
    """
    skills_dir = str(skills_dir)
    os.makedirs(skills_dir, exist_ok=True)
    _clear_generated(skills_dir)
    manifest = []

    items = store.load() if items is None else items
    active = [b for b in items if b.get("status") == "active" and (b.get("content") or "").strip()]
    active.sort(key=lambda b: b.get("helpful", 0) - b.get("harmful", 0), reverse=True)
    for b in active[:cap]:
        name, md = bullet_skill(b)
        _write_skill(skills_dir, name, md)
        manifest.append({"name": name, "kind": "mem", "id": b["id"]})

    if include_episodes:
        eps = episodic.load() if episodes is None else episodes
        eps = [e for e in eps if e.get("passed") and (e.get("solution") or "").strip()]
        for i, e in enumerate(eps[:ex_cap]):
            name, md = episode_skill(e, i)
            _write_skill(skills_dir, name, md)
            manifest.append({"name": name, "kind": "ex", "id": e.get("id", "")})

    for name, md in (extra_skills or []):
        _write_skill(skills_dir, name, md)
        manifest.append({"name": name, "kind": "candidate", "id": name})

    if include_promoted:
        before = set(os.listdir(skills_dir))
        _link_promoted(skills_dir)
        for nm in sorted(set(os.listdir(skills_dir)) - before):
            manifest.append({"name": nm, "kind": "promoted", "id": nm})

    return manifest


def sandbox_settings(hook_path, invoked_path):
    """A .claude/settings.json dict whose PostToolUse hook logs every Skill invocation to invoked_path."""
    return {"hooks": {"PostToolUse": [{"matcher": "Skill", "hooks": [{
        "type": "command",
        "command": 'python3 "%s" "%s"' % (str(hook_path), str(invoked_path))}]}]}}


def setup_sandbox(sandbox, hook_path, invoked_path, items=None, episodes=None,
                  include_promoted=True, include_episodes=True, extra_skills=None,
                  cap=CATALOG_CAP, ex_cap=EX_CAP):
    """Assemble a per-task native-solve sandbox: a .claude/skills catalog (memory + promoted skills,
    + any extra candidate) and a .claude/settings.json PostToolUse hook that records invocations.
    Returns the list of materialized skill names (pass to match_invoked after the run). Shared by the
    eval native_solve and the standalone smoke so they stay in lockstep."""
    skills_dir = os.path.join(sandbox, ".claude", "skills")
    manifest = materialize_into(
        skills_dir, items=items, episodes=episodes, include_promoted=include_promoted,
        include_episodes=include_episodes, extra_skills=extra_skills, cap=cap, ex_cap=ex_cap)
    with open(os.path.join(sandbox, ".claude", "settings.json"), "w", encoding="utf-8") as f:
        json.dump(sandbox_settings(hook_path, invoked_path), f)
    return [m["name"] for m in manifest]


def link_all_skills(skills_dir):
    """Symlink every git-tracked skill subdir (config.SKILLS_DIR/<name>/SKILL.md) into skills_dir.
    Returns the names linked. DEPLOY discovers ALL authored/promoted skills (unlike the eval catalog,
    which links only gate-ACTIVE induced skills via _link_promoted)."""
    linked = []
    if not config.SKILLS_DIR.exists():
        return linked
    for child in sorted(config.SKILLS_DIR.iterdir()):
        if not (child / "SKILL.md").exists():
            continue
        dst = os.path.join(skills_dir, child.name)
        if os.path.lexists(dst):
            continue
        try:
            os.symlink(os.path.abspath(str(child)), dst, target_is_directory=True)
        except OSError:
            shutil.copytree(str(child), dst)
        linked.append(child.name)
    return linked


def assemble_deploy_catalog():
    """DEPLOY assembly: make config.CLAUDE_SKILLS_LINK a REAL dir that Claude Code natively discovers,
    holding (a) a symlink to every authored/promoted skill in config.SKILLS_DIR and (b) the generated
    mem-*/ex-* memory skills from the current store. Replaces the legacy `.claude/skills -> ../skills`
    symlink with this richer catalog. Idempotent + regenerates the memory part each call, so a
    SessionStart hook keeps the catalog fresh as memory grows. Returns the manifest."""
    link = config.CLAUDE_SKILLS_LINK
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink():
        link.unlink()                      # drop the legacy ../skills symlink; we own a real dir now
    link.mkdir(parents=True, exist_ok=True)
    # prune stale authored-skill symlinks (engine/skills may have changed); mem-*/ex- are real dirs
    # cleared by materialize_into below.
    for child in os.listdir(str(link)):
        p = os.path.join(str(link), child)
        if os.path.islink(p):
            os.unlink(p)
    man = materialize_into(str(link), include_promoted=False)   # mem-*/ex- from the current store
    man += [{"name": n, "kind": "skill", "id": n} for n in link_all_skills(str(link))]
    return man


def invoked_to_bullet_ids(invoked_names):
    """Reverse-map invoked skill names -> distilled-bullet ids (only mem-* are credited).

    Episodic (ex-*) and promoted skills are NOT credited to bullets — matching today's behavior
    (episodic uncredited; promoted skills have their own skill_state lifecycle)."""
    ids = []
    for nm in invoked_names or []:
        if nm and nm.startswith(MEM_PREFIX):
            bid = nm[len(MEM_PREFIX):]
            if bid:
                ids.append(bid)
    return ids


def match_invoked(text, known_names):
    """Given the raw text the PostToolUse hook logged (one JSON event per line) and the set of
    skill names we materialized, return the names that were actually invoked. Substring match on
    the distinctive names is robust to the exact Skill tool-input schema."""
    if not text:
        return []
    found = []
    for nm in known_names or []:
        if nm and nm in text and nm not in found:
            found.append(nm)
    return found
