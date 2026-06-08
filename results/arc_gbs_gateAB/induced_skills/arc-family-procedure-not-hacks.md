---
name: arc-family-procedure-not-hacks
description: Prevents ARC family task failures by enforcing a generalizable family-level procedure (extract objects → select → transform → redraw) instead of grid-specific pattern matching.
---

## When to use
- When solving an ARC family task with multiple train/test grids sharing the same family structure
- When inferring per-task rules that pass training but fail on held-out tests
- When tempted to add grid-specific branches or hacks to handle edge cases in individual grids

## Steps
1. Before implementing, identify the family type and define the family-level PROCEDURE in pseudocode. Do NOT infer ad-hoc rules from individual grids.
2. For group_by_shape specifically, implement: (a) Extract connected colored objects via 4-connectivity flood fill; (b) Select target objects by family criteria (which objects to include); (c) Apply per-object transformation (size, position, color); (d) Redraw on blank grid.
3. Implement this procedure ONCE, parameterized only by family-specific rules. No branches for individual grid shapes or colors.
4. Test the procedure on ALL training grids. If it fails on any grid, revise the family definition/selection/transformation rules, not the grid-specific logic.
5. Verify the procedure works on held-out test grids without modification. Failures signal an incomplete family abstraction — fix the procedure itself, never add post-hoc patches.
