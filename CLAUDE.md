# BI Toolkit — Project Guide for Claude

## What is this?
CLI tools for Power BI developers: data quality checks, DAX documentation,
deployment notes, naming conventions, star schema validation.

## Tech Stack
- Python 3.10+ (scripts, CLI tools)
- Node.js 18+ (deployment notes generator)
- pytest (Python tests), Jest (Node.js tests)

## Project Structure
- /scripts — Python CLI tools
- /scripts/deployment-notes — Node.js deployment notes generator
- /data — sample datasets and configs
- /tests — Python tests (mirror scripts/ structure)
- /docs — project documentation

## Commands
- python -m pytest tests/ — run Python tests
- cd scripts/deployment-notes && npm test — run Node.js tests
- ruff check scripts/ — lint Python
- ruff format scripts/ — format Python

## Code Style
- Python: type hints, docstrings, no hardcoded paths
- Commits: conventional (feat:, fix:, docs:, refactor:, test:)
- Branches: feature/day-XX-topic

## Rules
- NEVER commit .env files or credentials
- ALWAYS add tests for new features
- Use argparse for CLI tools (not click or typer)
- CSV/JSON data files go in /data, never in /scripts
- When compacting, preserve modified files list and test status