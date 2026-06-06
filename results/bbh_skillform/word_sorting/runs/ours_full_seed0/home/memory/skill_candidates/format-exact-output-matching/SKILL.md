---
name: format-exact-output-matching
description: In graded/evaluated tasks, match reference output format exactly (space-separated vs comma-separated, newline vs inline, etc.); format-sensitive graders reject semantically equivalent alternatives.
---

## When to use
- Task output is evaluated by an external grader or automated checker
- Problem statement or examples show reference output format
- Output format could vary (space vs comma vs newline separation, trailing punctuation, case sensitivity, JSON structure, etc.)

## Steps
1. Before producing final output, extract format specification from problem statement and examples
2. Identify format properties: delimiter (space/comma/newline/tab), item ordering, trailing punctuation, case sensitivity, JSON/YAML structure, etc.
3. Verify your output matches ALL format properties of the reference; do not assume semantic equivalence (e.g., 'a b c' ≠ 'a,b,c' even if they represent the same items)
4. If format is ambiguous, prioritize the format from the clearest or most recent example in the problem statement
