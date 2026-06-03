"""native_evolve — harness-native self-evolving memory/skill for Claude Code / Codex.

The package is harness-agnostic. Adapters under ../adapters wire it into a
specific CLI harness (Claude Code via hooks, Codex via a wrapper runner).

Only LLM access is through the `claude` / `codex` CLI (see evolve.llm).
Everything else (retrieve / curate / promote bookkeeping) is deterministic.
"""

__version__ = "0.1.0"
