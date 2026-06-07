---
name: dyck-bracket-stack-completion
description: Correct Dyck language completion by implementing a stack-based algorithm that tracks opening bracket types/positions, then emits closing brackets in LIFO order (last-opened-first-closed) for all remaining unclosed opens.
---

## When to use
- Dyck language completion or bracket balancing tasks with mixed bracket types (<>, [], {}, ())
- Problems requiring nested bracket pairs to be closed in reverse order of opening
- Sequences needing systematic validation or completion of bracket pairs

## Steps
1. Initialize a stack to store (bracket_type, position) for each unmatched opening bracket encountered
2. Process the input sequence left-to-right: push opening brackets onto stack; when closing bracket encountered, pop from stack and verify types match
3. After input exhausted, emit closing brackets for all remaining stack entries in LIFO order (pop until empty), matching bracket type of each entry exactly
4. Return only the completion fragment (closing brackets to append), not the full balanced string; preserve input token spacing/formatting
