---
description: Quick DAX snippet search from your snippet library
argument-hint: [search-query]
allowed-tools: Bash(python *)
---

## Context
- Snippet storage: data/dax_snippets.json
- Manager script: scripts/dax_manager.py

## Instructions
1. Run: `python scripts/dax_manager.py search $ARGUMENTS`
2. Show matching snippets with full DAX code
3. If no results found, suggest similar categories or tags
4. If query is empty, run `python scripts/dax_manager.py list` instead
