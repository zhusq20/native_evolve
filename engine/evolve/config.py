"""Central configuration: paths + thresholds + binaries.

All paths are resolved relative to NATIVE_EVOLVE_HOME (the project root where
the harness runs). Resolution order:
  1. env NATIVE_EVOLVE_HOME
  2. env CLAUDE_PROJECT_DIR  (set by Claude Code when running hooks)
  3. the directory that contains this `evolve/` package
"""
import os
import pathlib


def _home():
    # An explicit override is honored unconditionally (the eval runner and the
    # install-claude hooks point this at an isolated dir that has no evolve/ of its own).
    val = os.environ.get("NATIVE_EVOLVE_HOME")
    if val:
        return pathlib.Path(val).resolve()
    # Auto-detect from the harness only when it actually holds the engine.
    val = os.environ.get("CLAUDE_PROJECT_DIR")
    if val and (pathlib.Path(val) / "evolve").is_dir():
        return pathlib.Path(val).resolve()
    return pathlib.Path(__file__).resolve().parent.parent


HOME = _home()

MEMORY_DIR = HOME / "memory"
STORE = MEMORY_DIR / "store.jsonl"
SKILL_STATE = MEMORY_DIR / "skill_state.json"
REPLAY_DIR = MEMORY_DIR / "replay"
CANDIDATE_DIR = MEMORY_DIR / "skill_candidates"
# Promoted skills live in a VISIBLE top-level dir so you can see/edit/git them
# directly. Claude Code natively discovers skills from .claude/skills, so we keep
# .claude/skills as a symlink -> ../skills (see ensure_skill_link()).
SKILLS_DIR = HOME / "skills"
CLAUDE_SKILLS_LINK = HOME / ".claude" / "skills"
PROMPTS_DIR = HOME / "prompts"


def ensure_skill_link():
    """Legacy: make .claude/skills a symlink to the visible ./skills dir (idempotent).

    NOTE (session 19): the NATIVE deploy catalog makes .claude/skills a REAL dir (authored skills +
    materialized memory; see materialize.assemble_deploy_catalog). So if .claude/skills already exists
    as a real dir, this is a NO-OP — it must NOT migrate/clobber the assembled catalog. Only used now
    by the legacy inject-mode path + a fresh-clone fallback (when nothing exists yet).
    """
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    link = CLAUDE_SKILLS_LINK
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink():
        return  # already linked (don't second-guess the target)
    if link.exists():
        return  # a real dir is present (the native catalog) — leave it; do NOT clobber
    try:
        link.symlink_to(pathlib.Path("..") / "skills", target_is_directory=True)
    except OSError:
        # Filesystems without symlinks (rare): fall back to a real dir.
        SKILLS_DIR.mkdir(parents=True, exist_ok=True)

# Binaries (overridable so deployment can point at an absolute path).
CLAUDE_BIN = os.environ.get("NATIVE_EVOLVE_CLAUDE_BIN", "claude")
CODEX_BIN = os.environ.get("NATIVE_EVOLVE_CODEX_BIN", "codex")
MODEL = os.environ.get("NATIVE_EVOLVE_MODEL", "")  # empty -> harness default

# Retrieval
RETRIEVE_TOPK = int(os.environ.get("NATIVE_EVOLVE_TOPK", "8"))

# Promotion gate
PROMOTE_HELPFUL = int(os.environ.get("NATIVE_EVOLVE_PROMOTE_HELPFUL", "5"))
PROMOTE_USES = int(os.environ.get("NATIVE_EVOLVE_PROMOTE_USES", "5"))
GATE_PASS_RATE = float(os.environ.get("NATIVE_EVOLVE_GATE_RATE", "0.8"))
AUTO_PROMOTE = os.environ.get("NATIVE_EVOLVE_AUTO_PROMOTE", "0") == "1"

# Curation
DEDUP_JACCARD = float(os.environ.get("NATIVE_EVOLVE_DEDUP", "0.8"))
DEPRECATE_HARMFUL = int(os.environ.get("NATIVE_EVOLVE_DEPRECATE_HARMFUL", "3"))
