---
name: dyck-language-stack-algorithm
description: Prevent bracket-balancing failures in Dyck language tasks by systematically using a stack-based algorithm, tracking bracket types, outputting completion fragments only (not full strings), and closing brackets in LIFO order while preserving spacing.
---

## When to use
- When given a partial bracket sequence to complete and must output only the completion fragment
- When verifying or balancing sequences with multiple bracket types ({}, [], <>, ())
- When spacing or token structure in input must be preserved in output

## Steps
1. Iterate through input systematically: push each opening bracket ({, [, <, () onto a stack with its type; pop and verify the type matches when encountering closing brackets (}, ], >, ))
2. For completion tasks: after parsing, emit ONLY the closing brackets needed to close remaining opens, in LIFO order (reverse stack-pop order), matching each bracket's type
3. Never output the full balanced string — output only the completion suffix to append to the input
4. Preserve all spacing and token structure from input when constructing the output fragment
