---
name: arc-family-procedure-not-grid-specific
description: Prevent per-grid pattern-matching; implement the family-level procedure uniformly across training and held-out instances.
---

## When to use
- Writing solve() for an ARC task that is part of a documented family
- Testing on held-out instances reveals failures not seen on training instances
- Tempted to add conditional logic, task-specific rules, or per-grid pattern-matching

## Steps
1. Extract the family-level procedure before coding. Example for group_by_shape: (1) 4-connectivity flood-fill to extract colored objects, (2) filter by family criteria, (3) apply transformation per-object, (4) redraw on blank grid.
2. Code as parameterized, data-driven logic, not task-specific branches. Replace `if task_id == X: ...` with parameterization by family attributes (color, size, spatial relations).
3. Verify the same solve() code works on both training and held-out instances. If different instances require different branches in solve(), you have reverted to per-grid solving — refactor into family logic.
4. If a task instance fails, debug the family procedure itself (selection criteria, transformation logic), not the grid. Do not add task-specific exceptions.
