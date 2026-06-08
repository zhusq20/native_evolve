---
name: arc-family-abstraction
description: Implement family-level procedures for ARC tasks instead of task-specific hacks to ensure generalization to held-out tests.
---

## When to use
- ARC task is labeled as part of a family with multiple related variants
- Implementing a solution that works on training instances but needs to generalize
- Multiple puzzle instances share a common underlying procedure

## Steps
1. Identify the family-level PROCEDURE, not task-specific hacks. Ask: what are the invariant steps across ALL instances in this family?
2. For ARC group_by_shape: (1) Extract connected colored objects via 4-connectivity flood fill, (2) Select target objects by family criteria (not per-grid detail), (3) Apply transformation uniformly per-object, (4) Redraw on blank grid.
3. Implement the procedure once as a reusable function. Do NOT add per-grid conditionals or task-specific rules.
4. Validate on multiple family instances (training + held-out) to confirm the procedure generalizes.
5. If tests fail, revise the family procedure itself, not by adding per-task workarounds. Trace WHY the procedure was incomplete.
