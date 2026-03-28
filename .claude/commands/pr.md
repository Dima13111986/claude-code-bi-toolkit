---
description: Generate PR description for current branch
allowed-tools: Bash(git log:*), Bash(git diff:*)
---

## Context
- Branch: !`git branch --show-current`
- Commits since main: !`git log main..HEAD --oneline`
- Files changed: !`git diff main --stat`

## Instructions
Generate PR description with these sections:
1. **Summary** — what this PR does (2-3 sentences)
2. **Changes** — bulleted list of changes
3. **Type** — feat/fix/docs/refactor/test
4. **Testing** — how to verify
5. **Checklist** — [ ] tests pass, [ ] docs updated, [ ] no .env committed