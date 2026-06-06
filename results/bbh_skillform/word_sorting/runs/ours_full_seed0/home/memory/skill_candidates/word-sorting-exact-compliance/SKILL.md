---
name: word-sorting-exact-compliance
description: Prevent word-sorting failures by explicitly preserving all input words, sorting with letter-by-letter lexicographic comparison, and matching reference output format exactly (space-separated, no commas).
---

## When to use
- When asked to sort a list of words and output the result
- When the task specifies or shows space-separated output format
- When output will be graded against a reference with specific formatting

## Steps
1. Parse input: Explicitly enumerate all words as a numbered or bulleted list (do not rely on mental tracking of word identity).
2. Sort correctly: Apply letter-by-letter lexicographic comparison. Compare character-by-character; on tie, advance to next character. Shorter words sort before longer words with the same prefix (e.g., 'cat' < 'cats'). Write out the comparison logic step-by-step if order is ambiguous.
3. Validate preservation: Count input and output word counts; confirm they match. Check that every input word appears exactly once in output (no drops, no additions, no duplicates). If counts differ, list input and output side-by-side to identify the discrepancy.
4. Format output: Output space-separated words only (no commas, no other delimiters unless the reference explicitly shows them). Match the reference format exactly: if reference shows 'word1 word2 word3', output must be identical.
