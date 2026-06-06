---
name: word-sorting-completeness-format
description: Prevent word loss during sorting and output format mismatches by explicitly tracking input words, applying systematic lexicographic comparison, and matching reference format exactly.
---

## When to use
- When given a word list to sort alphabetically or lexicographically
- Before returning output, verify it contains identical words to input with no omissions
- Match output format to reference format (space-separated vs comma-separated, etc.) exactly

## Steps
1. Create an explicit enumerated list of all input words; do not rely on informal mental tracking.
2. Sort using systematic letter-by-letter lexicographic comparison: first compare all words' first letters, then second letters among tied words, continuing until sorted.
3. After sorting, verify output contains exactly the same words as input—identical count, no additions, no omissions. Use a checklist to cross-check each word.
4. Inspect the reference output format: space-separated ('word1 word2 word3')? Comma-separated? Newline-delimited? Line-wrapped?
5. Format output to match reference format exactly. If reference shows space-separated, output space-separated; do not substitute with comma-separated or any other delimiter.
6. Perform final validation: re-count words, re-verify lexicographic order letter-by-letter, and re-check format matches reference.
