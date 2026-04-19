# feather-etl — agent context

Config-driven Python ETL for heterogeneous ERP sources → local DuckDB.

**Full project context:** `.claude/rules/feather-etl-project.md`
**Requirements:** `docs/prd.md`
**Architecture:** `README.md`
**Work conventions:** `docs/CONTRIBUTING.md`

## Before you write a single line of code

Run the test suite and confirm green:

```bash
uv run pytest -q               # currently: 720 tests
```

If anything is red before you touch anything, report immediately.
