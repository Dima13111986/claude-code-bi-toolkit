---
description: Code review of a file or directory
argument-hint: [file-or-directory]
---

Review $ARGUMENTS for:
1. **Correctness** — logic errors, edge cases
2. **Style** — matches CLAUDE.md conventions
3. **Security** — hardcoded secrets, injection
4. **Performance** — O(n²), missing caching
5. **Tests** — coverage, edge cases

Output as table: | Issue | Severity | Line | Suggestion |