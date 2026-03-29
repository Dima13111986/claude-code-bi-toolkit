---
name: bi-code-style
description: >
  Power BI code style conventions. Use when writing or reviewing Python,
  DAX, SQL, or YAML in this project.
---

# BI Code Style Guide

## Python
- argparse (not click/typer), type hints, Google-style docstrings
- logging (never print()), pathlib.Path (never string paths)

## DAX
- VAR/RETURN, no FORMAT() in measures, comment complex CALCULATE

## SQL
- Explicit JOINs, CTE over subqueries, meaningful aliases, no SELECT *

## YAML
- schema_version field, ISO 8601 dates, no secrets

## File Naming
- Python: snake_case.py | Configs: kebab-case.yaml | Tests: test_module.py
