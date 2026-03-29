# Parallel Slices Verification Report

Created: 2026-03-28
Plan: docs/plans/2026-03-28-parallel-slices-postgres.md
Protocol: Sonnet + Haiku dual-agent independent verification

## Test Suite Baseline

| Suite | Result |
|-------|--------|
| `uv run pytest -q` | 341 passed, 0 failures |
| `bash scripts/hands_on_test.sh` | 70 passed, 0 failed |

## Feature Verification Summary

| Feature | Sonnet | Haiku | Final |
|---------|--------|-------|-------|
| PostgreSQL Source | PARTIAL → **PASS** (after fix) | SKIP (no pg access) | **PASS** |
| Excel Source | PASS | PASS | **PASS** |
| JSON Source | PASS | PASS | **PASS** |
| --table Filter | PASS | PASS | **PASS** |
| feather history | PASS | PASS | **PASS** |
| Append Strategy | PASS | PASS | **PASS** |

## Bug Found and Fixed

**BUG: `last_checksum INTEGER` in state.py line 49**

- **Found by:** Sonnet agent during PostgreSQL verification
- **Root cause:** `_watermarks.last_checksum` was `INTEGER` but PostgreSQL `detect_changes()` returns an MD5 hex string (32 chars). DuckDB raised `Conversion Error: Could not convert string to INT32`.
- **Fix:** Changed to `last_checksum VARCHAR` in DDL and `int | str | None` in type hint.
- **Verification:** PostgreSQL extraction now succeeds: 3/3 tables, 10+4+5 rows.

## Detailed Results

### PostgreSQL Source
- `feather discover` lists 3 tables with correct column types (integer, text, double precision, timestamp)
- `feather run` extracts 10+4+5 rows from real PostgreSQL (after checksum fix)
- Change detection via md5(string_agg(row_to_json)) with PK-based ordering

### Excel Source
- `feather discover` finds 3 .xlsx files with correct schemas
- `feather run` extracts 5+4+3 rows
- Column types: DOUBLE (numeric), VARCHAR (text), BOOLEAN
- Change detection via FileSource base (mtime + MD5)

### JSON Source
- `feather discover` finds 3 .json files with correct schemas
- `feather run` extracts 5+4+3 rows
- DuckDB `read_json_auto` infers types correctly (BIGINT, VARCHAR, BOOLEAN)

### --table Filter
- `feather run --table customers` extracts only that table (1/1)
- Other tables not created in destination
- `feather run --table nonexistent` shows error with available table names, exits 1

### feather history
- Shows formatted table: table name, status, rows loaded, timestamp, run ID
- `--table` filter shows only matching runs
- `--limit` caps output
- Empty state shows "No runs recorded yet."

### Append Strategy
- First run: 5 rows inserted with metadata columns
- Source modified (2 rows added), second run: 7 rows appended
- Total after 2 runs: 12 rows (5+7) — confirms accumulation, not replacement
- Unchanged source: skipped (change detection prevents duplicate append)

## Doc Improvement (from Haiku)

Section 12 (PostgreSQL) should add: "Requires PostgreSQL installed locally (via mise, brew, or Docker)" as a prerequisite note.
