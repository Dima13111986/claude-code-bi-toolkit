# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is this?

CLI tools for Power BI developers: data quality checks, DAX documentation, deployment notes, naming conventions, star schema validation.

## Tech Stack

- Python 3.10+ (`/scripts` — CLI tools)
- Node.js 18+ (`/scripts/deployment-notes` — deployment notes generator)
- pytest (Python tests), Jest (Node.js tests)

## Project Structure

- `/scripts` — Python CLI tools (each file is a standalone tool using argparse)
- `/scripts/deployment-notes` — Node.js deployment notes generator
- `/data` — sample datasets and configs (CSV/JSON only, never put data in /scripts)
- `/tests` — Python tests mirroring `/scripts` structure
- `/docs` — project documentation

## Commands

```bash
# Python
python -m pytest tests/                          # run all Python tests
python -m pytest tests/path/to/test_foo.py       # run a single test file
python -m pytest tests/ -k "test_name"           # run tests matching a name
ruff check scripts/                              # lint
ruff format scripts/                             # format

# Node.js (deployment notes)
cd scripts/deployment-notes && npm test          # run Node.js tests
```

## Code Style

- Python: type hints and docstrings on all public functions, no hardcoded paths
- Use `argparse` for all CLI tools — not click or typer
- Commits: conventional format (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`)
- Branches: `feature/day-XX-topic`

## Custom Slash Commands

Defined in `.claude/commands/`:

- `/commit` — smart commit: stages relevant files, writes a conventional message, and commits
- `/review [file-or-dir]` — code review with severity table (correctness, style, security, performance, tests)
- `/pr` — generates a PR description from the branch diff against `main`

## Skills

Defined in `.claude/skills/`, auto-applied when relevant:

- `bi-code-style` — Python/DAX/SQL/YAML conventions for this project
- `dax-patterns` — DAX measure patterns library

## Hooks

Configured in `.claude/settings.json`:

- **PostToolUse** (`Edit|Write` on `*.py`) — runs `ruff format` then `ruff check --fix` automatically after any Python file is written or edited

## Permissions

- **Allow:** `Read`, `Write`, `Bash` (git, python, node, npm, ruff, pytest)
- **Deny:** `.env` files (read and write)
