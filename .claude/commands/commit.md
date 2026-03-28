---
description: Smart commit — stage, write message, commit
allowed-tools: Bash(git add:*), Bash(git status:*), Bash(git commit:*), Bash(git diff:*)
---

## Context
- Current status: !`git status`
- Current diff: !`git diff HEAD`
- Current branch: !`git branch --show-current`

## Instructions
1. Review the changes above
2. Stage relevant files (skip .env, __pycache__, node_modules)
3. Write a conventional commit message (feat:/fix:/docs:/refactor:/test:)
4. Commit and show hash + summary