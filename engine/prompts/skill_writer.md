You are packaging a proven piece of experience into a reusable Agent Skill.

Output ONLY the full contents of a SKILL.md file. No prose around it, no code fences.

Required format:
---
name: <kebab-case-name, matches the scope>
description: <one line; this is the retrieval key — say WHEN to use this skill and for WHAT>
---

## When to use
<short trigger conditions>

## Steps
<numbered, concrete, tool-aware steps>

## Failure modes (keep — do not delete)
<the specific mistakes this skill prevents>

Rules:
- The `description` must be precise enough that the harness can decide relevance from it alone.
- Preserve the failure modes; they are the most valuable part.
- Keep it self-contained and runnable; reference real tools (Read, Bash, etc.) where relevant.
