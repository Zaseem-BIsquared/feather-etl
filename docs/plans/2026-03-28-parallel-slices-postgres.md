# Parallel Slices + PostgreSQL Source Implementation Plan

Created: 2026-03-28
Status: VERIFIED
Approved: Yes
Iterations: 0
Worktree: No
Type: Feature

## Summary

**Goal:** Implement 6 low-hanging-fruit features from the PRD in 3 parallel groups, plus establish a documented dual-agent (Sonnet + Haiku) verification protocol for all future slices.

**Architecture:** 3 independent task groups executed by parallel agents, each in a worktree-isolated branch. After all merge, documentation is updated and the Sonnet+Haiku verification protocol runs.

**Tech Stack:** psycopg2-binary (PostgreSQL), openpyxl (Excel, already in deps), DuckDB extensions (json, excel readers), Typer (CLI)

## Scope

### In Scope

- **PostgreSQL source** — `PostgresSource` extending `DatabaseSource`, psycopg2-binary driver, real local postgres testing via mise, change detection via COUNT + md5(string_agg(row_to_json)) with PK-based ordering
- **Excel source** — `ExcelSource` extending `FileSource`, DuckDB `ST_READ` or openpyxl-based, `.xlsx`/`.xls` support
- **JSON source** — `JsonSource` extending `FileSource`, DuckDB `read_json_auto`, `.json`/`.jsonl` support
- **`feather run --table`** — single-table extraction filter (V5a from PRD)
- **`feather history`** — run history CLI command querying `_runs` table (V5b from PRD)
- **Append strategy** — insert-only load for compliance/audit trail tables (V12 from PRD)
- **Documentation** — update `docs/testing-feather-etl.md`, `README.md`, `.claude/rules/feather-etl-project.md`
- **Verification protocol** — documented Sonnet + Haiku dual-agent testing procedure

### Out of Scope

- Multi-file CSV (glob patterns) — requires config schema changes (V6 separate)
- PostgreSQL → MotherDuck sync (V13)
- Connection pooling / retry (V14)
- Schema drift detection (V10)
- DQ checks (V9)

## Approach

**Chosen:** 3 parallel agent groups with worktree isolation

**Why:** Avoids file conflicts while maximizing parallelism. Each group only touches non-overlapping files. Merge is sequential and conflict-free.

**Alternatives considered:**
- 6 individual agents: more parallelism but 6 merge steps with conflicts in registry.py/config.py — rejected
- Sequential (1 agent): no conflicts but 3x slower — rejected

### Group File Ownership

| File | Group A (Sources) | Group B (CLI) | Group C (Pipeline) |
|------|:-:|:-:|:-:|
| `sources/postgres.py` | NEW | | |
| `sources/excel.py` | NEW | | |
| `sources/json_source.py` | NEW | | |
| `sources/registry.py` | MODIFY | | |
| `sources/database_source.py` | MODIFY | | |
| `config.py` | MODIFY | | |
| `pyproject.toml` | MODIFY | | |
| `cli.py` | | MODIFY | |
| `state.py` | | MODIFY | |
| `pipeline.py` | | MODIFY | |
| `destinations/duckdb.py` | | | MODIFY |

## Context for Implementer

> Write for an implementer who has never seen the codebase.

### Patterns to Follow

- **New file source** — see `src/feather/sources/csv.py` (60 lines): extend `FileSource`, implement `check()`, `discover()`, `extract()`, `get_schema()`. Use DuckDB reader functions for extraction.
- **New DB source** — see `src/feather/sources/sqlserver.py` (258 lines): extend `DatabaseSource`, implement all 5 protocol methods. Chunked fetchmany → PyArrow batch conversion.
- **Registry** — see `src/feather/sources/registry.py`: add type → class mapping, `create_source()` dispatches based on `FILE_SOURCE_TYPES`.
- **Destination** — see `src/feather/destinations/duckdb.py`: `load_full()` (swap pattern), `load_incremental()` (partition overwrite). Append follows the same INSERT pattern without DELETE.
- **CLI** — see `src/feather/cli.py`: each command is a `@app.command()` decorated function. Uses `_load_and_validate()` helper.

### Conventions

- **Imports:** `from __future__ import annotations` at top of every module
- **Type hints:** Modern syntax (`list[str]`, `str | None`)
- **Testing:** Real fixtures, no mocking (except for DB sources that need pyodbc/psycopg2 — but PostgreSQL uses real local DB)
- **Config validation:** Add to `_validate()` in config.py for source-specific rules

### Key Files

| File | Purpose |
|------|---------|
| `src/feather/sources/__init__.py` | `Source` protocol, `ChangeResult`, `StreamSchema` dataclasses |
| `src/feather/sources/file_source.py` | `FileSource` base with change detection (mtime + MD5) |
| `src/feather/sources/database_source.py` | `DatabaseSource` base with `_build_where_clause()` |
| `src/feather/sources/registry.py` | Type → class registry, `create_source()` factory |
| `src/feather/config.py` | `FILE_SOURCE_TYPES`, `VALID_STRATEGIES`, config validation |
| `src/feather/pipeline.py` | `run_table()` dispatches to `load_full` or `load_incremental` based on strategy |
| `src/feather/destinations/duckdb.py` | `load_full()`, `load_incremental()` — append goes here |
| `src/feather/state.py` | `StateManager` with `_runs` + `_watermarks` tables |

### Gotchas

- **DatabaseSource._build_where_clause** has SQL Server-specific datetime formatting (replace `T` with space, truncate to 3ms). PostgreSQL handles ISO timestamps natively — either override this method or refactor the base to have a `_format_watermark` hook.
- **FILE_SOURCE_TYPES** in `config.py` controls whether `create_source()` passes `path` or `connection_string`. New file sources MUST be added here.
- **`append` is already in VALID_STRATEGIES** but pipeline only dispatches to `load_full` and `load_incremental`. Append needs a new code path.
- **DuckDB excel extension** must be installed/loaded: `INSTALL excel; LOAD excel;` before `read_xlsx()` works.
- **PostgreSQL via mise** — postgres@17.6 is at `~/.local/share/mise/installs/postgres/17.6/`. Data dir exists at `$(mise where postgres@17.6)/data`. Server must be started before tests.
- **Config validation for postgres** — should require `connection_string`, not `path` (same as sqlserver).

### Domain Context

- **Append strategy** is for compliance/audit trail tables where rows are never deleted or updated — only new rows are inserted. Each run appends new data. Duplicates are the caller's responsibility.
- **PostgreSQL** is a new source type — the first DB source besides SQL Server. It validates that `DatabaseSource` abstraction works for multiple databases.

## Runtime Environment

No running service needed. All tests run locally. PostgreSQL server started via `pg_ctl` for integration tests.

```bash
# Start PostgreSQL for testing
PG_DIR="$(mise where postgres@17.6)"
export PATH="$PG_DIR/bin:$PATH"
pg_ctl -D "$PG_DIR/data" -l "$PG_DIR/data/logfile" start

# Verify
pg_isready -h localhost

# Stop after tests
pg_ctl -D "$PG_DIR/data" stop
```

## Assumptions

- PostgreSQL 17.6 data directory at `$(mise where postgres@17.6)/data` is initialized and usable — supported by `ls` showing `pg_hba.conf`, `PG_VERSION`, etc. Tasks 1, 4 depend on this.
- DuckDB can `INSTALL excel; LOAD excel;` in the test environment — supported by DuckDB >= 1.0 in deps. Task 2 depends on this.
- DuckDB `read_json_auto` works without extension install — it's built-in since DuckDB 0.8. Task 3 depends on this.
- `_runs` table in state DB has enough columns for `feather history` output — supported by `state.py:get_status()` already querying this table. Task 6 depends on this.

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| PostgreSQL data dir not properly initialized | Low | Blocks postgres tests | Script will `initdb` if `PG_VERSION` missing |
| DuckDB excel extension not available | Low | Blocks Excel source | Fall back to openpyxl-based reading |
| Parallel merge conflicts despite grouping | Low | Delays integration | Groups designed with zero file overlap; worst case is sequential merge |
| Append strategy creates duplicates on re-run | Medium | Data quality | Document clearly: append = caller responsibility for dedup. This matches PRD V12 design |

## Goal Verification

### Truths

1. `feather run` with `type: postgres` extracts data from a real PostgreSQL database into DuckDB
2. `feather run` with `type: excel` extracts data from `.xlsx` files into DuckDB
3. `feather run` with `type: json` extracts data from `.json` files into DuckDB
4. `feather run --table sales` extracts only the `sales` table, skipping others
5. `feather history` displays a formatted table of past runs from the state DB
6. `feather run` with `strategy: append` inserts rows without deleting existing data
7. All 6 features have passing tests (`uv run pytest -q`)
8. `bash scripts/hands_on_test.sh` still passes (no regressions)
9. `docs/testing-feather-etl.md` has test sections for all 6 new features

### Artifacts

- `src/feather/sources/postgres.py` — PostgreSQL source implementation
- `src/feather/sources/excel.py` — Excel source implementation
- `src/feather/sources/json_source.py` — JSON source implementation
- `tests/test_postgres.py` — PostgreSQL integration tests
- `tests/test_excel.py` — Excel source tests
- `tests/test_json.py` — JSON source tests
- `tests/test_append.py` — Append strategy tests

## Progress Tracking

- [x] Task 1: PostgreSQL source
- [x] Task 2: Excel source
- [x] Task 3: JSON source
- [x] Task 4: Source registry + config integration
- [x] Task 5: --table filter for feather run
- [x] Task 6: feather history command
- [x] Task 7: Append strategy
- [x] Task 8: Documentation updates
- [x] Task 9: Dual-agent verification protocol

**Total Tasks:** 9 | **Completed:** 9 | **Remaining:** 0

---

## Implementation Tasks

### Task 1: PostgreSQL source

**Objective:** Create `PostgresSource` extending `DatabaseSource` with psycopg2-binary, testable against real local PostgreSQL.
**Dependencies:** None
**Group:** A (Sources)

**Files:**

- Create: `src/feather/sources/postgres.py`
- Modify: `src/feather/sources/database_source.py` (add `_format_watermark` hook)
- Modify: `src/feather/sources/sqlserver.py` (override `_format_watermark` for SQL Server datetime)
- Create: `tests/test_postgres.py`
- Create: `scripts/create_postgres_test_fixture.py`

**Key Decisions / Notes:**

- Follow `sqlserver.py` pattern exactly for the class structure: `check()`, `discover()`, `get_schema()`, `extract()`, `detect_changes()`
- `psycopg2.connect()` for connection. Use `cursor.fetchmany(batch_size)` → PyArrow conversion (same chunked pattern as SQL Server)
- discover/get_schema via `INFORMATION_SCHEMA.TABLES` / `INFORMATION_SCHEMA.COLUMNS` — nearly identical SQL to SQL Server but with `table_schema NOT IN ('pg_catalog', 'information_schema')` filter
- Change detection: `SELECT COUNT(*), md5(string_agg(row_to_json(t)::text, '' ORDER BY {pk_cols})) FROM {table} t` — uses primary key columns for stable ordering (discovered via `pg_index`/`INFORMATION_SCHEMA`). Fallback to `ORDER BY 1,2,...` (all columns) if no PK. Avoids `ctid` which changes after VACUUM FULL.
- Refactor `DatabaseSource._build_where_clause` to call a `_format_watermark(value)` hook method. Default returns value as-is (works for PostgreSQL). SqlServerSource overrides to do the T→space and 3ms truncation.
- `_PSYCOPG2_TYPE_MAP` mapping Python types from cursor.description to PyArrow types (similar to `_PYODBC_TYPE_MAP`)
- `_PG_TYPE_MAP` for INFORMATION_SCHEMA `data_type` → PyArrow (varchar→string, integer→int64, timestamp→timestamp("us"), etc.)
- Test fixture script creates a `feather_test` database with `erp` schema and 3 tables matching `sample_erp.duckdb` schema (sales, customers, products)
- Tests marked with `@pytest.mark.postgres` — skip if postgres isn't running

**Definition of Done:**

- [ ] `PostgresSource.check()` connects to local postgres and returns True
- [ ] `PostgresSource.discover()` returns schemas with correct column types
- [ ] `PostgresSource.extract()` returns PyArrow Table with correct row counts
- [ ] `PostgresSource.detect_changes()` detects row count/checksum changes
- [ ] Incremental extraction with watermark works
- [ ] All tests pass: `uv run pytest tests/test_postgres.py -q`
- [ ] No regressions: `uv run pytest -q`

**Verify:**

```bash
uv run pytest tests/test_postgres.py -q
uv run pytest -q
```

---

### Task 2: Excel source

**Objective:** Create `ExcelSource` extending `FileSource` to read `.xlsx` files using DuckDB's excel extension.
**Dependencies:** None
**Group:** A (Sources)

**Files:**

- Create: `src/feather/sources/excel.py`
- Create: `tests/test_excel.py`
- Create: `tests/fixtures/excel_data/` (test Excel files)
- Create: `scripts/create_excel_fixture.py`

**Key Decisions / Notes:**

- Follow `csv.py` pattern exactly: extend `FileSource`, use DuckDB reader function
- DuckDB approach: `INSTALL excel; LOAD excel;` then `SELECT * FROM read_xlsx('path.xlsx', sheet='Sheet1')`
- `check()`: verify path is a directory
- `discover()`: glob for `*.xlsx` + `*.xls` files, DESCRIBE each via DuckDB
- `_source_path_for_table()`: `self.path / table` (each table = one Excel file, like CSV)
- `extract()`: DuckDB `read_xlsx()` with optional column selection and WHERE clause
- `get_schema()`: DuckDB DESCRIBE on the Excel file
- Fixture script creates 3 small Excel files (orders.xlsx, customers.xlsx, products.xlsx) matching the CSV fixture data using openpyxl
- Excel `source_table` must include file extension (`.xlsx`) in config — same pattern as CSV requires `.csv`

**Definition of Done:**

- [ ] `ExcelSource.check()` validates directory exists
- [ ] `ExcelSource.discover()` finds .xlsx files with correct schemas
- [ ] `ExcelSource.extract()` returns PyArrow Table with correct data
- [ ] Change detection works (file mtime + MD5 via FileSource base)
- [ ] All tests pass: `uv run pytest tests/test_excel.py -q`

**Verify:**

```bash
uv run pytest tests/test_excel.py -q
```

---

### Task 3: JSON source

**Objective:** Create `JsonSource` extending `FileSource` to read `.json`/`.jsonl` files using DuckDB's built-in `read_json_auto`.
**Dependencies:** None
**Group:** A (Sources)

**Files:**

- Create: `src/feather/sources/json_source.py`
- Create: `tests/test_json.py`
- Create: `tests/fixtures/json_data/` (test JSON files)

**Key Decisions / Notes:**

- Follow `csv.py` pattern exactly: extend `FileSource`, use DuckDB reader function
- DuckDB `read_json_auto('path.json')` — built-in, no extension needed
- `check()`: verify path is a directory
- `discover()`: glob for `*.json` + `*.jsonl` files, DESCRIBE each
- `_source_path_for_table()`: `self.path / table`
- `extract()`: `SELECT ... FROM read_json_auto('path')` with optional WHERE
- `get_schema()`: DESCRIBE
- Create test fixtures: 3 JSON files (orders.json, customers.json, products.json) matching CSV data
- JSON `source_table` must include file extension (`.json` or `.jsonl`)

**Definition of Done:**

- [ ] `JsonSource.check()` validates directory exists
- [ ] `JsonSource.discover()` finds .json files with correct schemas
- [ ] `JsonSource.extract()` returns PyArrow Table with correct data
- [ ] Change detection works via FileSource base
- [ ] All tests pass: `uv run pytest tests/test_json.py -q`

**Verify:**

```bash
uv run pytest tests/test_json.py -q
```

---

### Task 4: Source registry + config integration

**Objective:** Wire all 3 new sources into the registry and config validation, add psycopg2-binary dependency.
**Dependencies:** Task 1, Task 2, Task 3
**Group:** A (Sources)

**Files:**

- Modify: `src/feather/sources/registry.py`
- Modify: `src/feather/config.py`
- Modify: `pyproject.toml`

**Key Decisions / Notes:**

- Add to `SOURCE_REGISTRY`: `"postgres": PostgresSource`, `"excel": ExcelSource`, `"json": JsonSource` — these are the actual gaps
- `FILE_SOURCE_TYPES` in config.py already contains `"excel"` and `"json"` — do NOT re-add (verify at line 14: `FILE_SOURCE_TYPES = {"duckdb", "sqlite", "csv", "excel", "json"}`)
- `postgres` is NOT in `FILE_SOURCE_TYPES` — uses `connection_string` like `sqlserver` (already handled by the generic DB source validation at lines 153-159)
- Config validation for `excel`/`json`: directory check already covered by CSV-style validation — verify path.is_dir() applies
- Add `"psycopg2-binary>=2.9"` to `pyproject.toml` dependencies
- Run `uv sync` to install

**Definition of Done:**

- [ ] `create_source(SourceConfig(type="postgres", connection_string="..."))` returns PostgresSource
- [ ] `create_source(SourceConfig(type="excel", path=Path("...")))` returns ExcelSource
- [ ] `create_source(SourceConfig(type="json", path=Path("...")))` returns JsonSource
- [ ] Config validation catches missing connection_string for postgres
- [ ] Config validation catches non-directory path for excel/json
- [ ] Full test suite passes: `uv run pytest -q`

**Verify:**

```bash
uv run pytest -q
```

---

### Task 5: --table filter for feather run

**Objective:** Add `--table` CLI option to `feather run` to extract a single table instead of all tables.
**Dependencies:** None
**Group:** B (CLI)

**Files:**

- Modify: `src/feather/cli.py` (add `--table` option to `run` command)
- Modify: `src/feather/pipeline.py` (add `table_filter` parameter to `run_all`)
- Modify or create: `tests/test_cli.py` (test --table flag)

**Key Decisions / Notes:**

- Add `table: str | None = typer.Option(None, "--table")` parameter to `run()` command
- Pass `table_filter=table` to `run_all()` in pipeline.py
- In `run_all()`: if `table_filter` is set, filter `config.tables` to only matching name
- If `--table` name doesn't match any configured table, print error and exit 1
- This is a small, clean change — ~10 lines in cli.py, ~5 lines in pipeline.py

**Definition of Done:**

- [ ] `feather run --table sales` extracts only the sales table
- [ ] `feather run --table nonexistent` prints error and exits 1
- [ ] `feather run` (no --table) still extracts all tables
- [ ] Tests pass: `uv run pytest tests/test_cli.py -q`

**Verify:**

```bash
uv run pytest tests/test_cli.py -q
uv run pytest -q
```

---

### Task 6: feather history command

**Objective:** Add `feather history` CLI command showing past run records from the state DB.
**Dependencies:** None
**Group:** B (CLI)

**Files:**

- Modify: `src/feather/cli.py` (new `history` command)
- Modify: `src/feather/state.py` (add `get_history(table_name, limit)` method)
- Modify or create: `tests/test_cli.py` (test history command)

**Key Decisions / Notes:**

- New `@app.command()` `history` function
- Accept `--config`, optional `--table` filter, optional `--limit` (default 20)
- Query `_runs` table ordered by `started_at DESC`
- Display: run_id, table_name, status, rows_loaded, started_at, ended_at, error_message (truncated)
- Format as a table with headers
- **StateManager needs a new `get_history()` method** (doesn't exist yet — only `get_status()` which returns latest per table):
  ```python
  def get_history(self, table_name: str | None = None, limit: int = 20) -> list[dict]:
      """Return recent runs ordered by started_at DESC. Optionally filter by table."""
  ```
  Returns dicts with keys matching `_runs` columns: `run_id`, `table_name`, `started_at`, `ended_at`, `status`, `rows_loaded`, `error_message`
- See `state.py:get_status()` for the query pattern

**Definition of Done:**

- [ ] `feather history` shows last 20 runs in a formatted table
- [ ] `feather history --table sales` filters to sales table only
- [ ] `feather history --limit 5` shows only 5 most recent runs
- [ ] Empty state DB shows "No runs recorded yet."
- [ ] Tests pass

**Verify:**

```bash
uv run pytest tests/test_cli.py -q
uv run pytest -q
```

---

### Task 7: Append strategy

**Objective:** Implement `append` load strategy — insert-only without deleting existing rows.
**Dependencies:** None
**Group:** C (Pipeline)

**Files:**

- Modify: `src/feather/destinations/duckdb.py` (new `load_append` method)
- Modify: `src/feather/pipeline.py` (dispatch to `load_append` for append strategy)
- Create: `tests/test_append.py`

**Key Decisions / Notes:**

- `append` is already in `VALID_STRATEGIES` in config.py — no config changes needed
- New `load_append(table, data, run_id) -> int` method on `DuckDBDestination`
- Pattern: `CREATE TABLE IF NOT EXISTS {final} AS SELECT ... FROM _arrow_data WHERE 1=0` (create if not exists with schema), then `INSERT INTO {final} SELECT *, CURRENT_TIMESTAMP AS _etl_loaded_at, '{run_id}' AS _etl_run_id FROM _arrow_data`
- In `pipeline.py run_table()`: add `elif table.strategy == "append":` branch that calls `dest.load_append()`
- **Change detection + append interaction (resolved):** Change detection stays on for append. If source is unchanged, skip (no new data to append = no duplicate rows). If source changed, append new data alongside existing. This prevents accidental duplicate appends from repeated runs against the same source file. The pipeline's early-exit at line ~80-96 already handles this correctly — no modification needed.
- Add `pipeline.py` to Task 7's file list (already listed in Modify)
- Test: extract with append, modify source, extract again → both sets of rows exist. Extract a third time without modification → skip (change detection)

**Definition of Done:**

- [ ] `DuckDBDestination.load_append()` inserts rows without deleting
- [ ] Pipeline dispatches to `load_append` for `strategy: append`
- [ ] Running append, then modifying source and running again, results in both datasets present in target
- [ ] Running append twice with unchanged source skips the second run (change detection prevents duplicate append)
- [ ] Metadata columns `_etl_loaded_at` and `_etl_run_id` present on appended rows
- [ ] Tests pass: `uv run pytest tests/test_append.py -q`

**Verify:**

```bash
uv run pytest tests/test_append.py -q
uv run pytest -q
```

---

### Task 8: Documentation updates

**Objective:** Update all documentation to reflect the 6 new features.
**Dependencies:** Tasks 1-7
**Group:** Post-implementation (sequential)

**Files:**

- Modify: `docs/testing-feather-etl.md`
- Modify: `README.md`
- Modify: `.claude/rules/feather-etl-project.md`

**Key Decisions / Notes:**

- `docs/testing-feather-etl.md` — add 6 new sections:
  - **Section 12: PostgreSQL Source** — test extraction from real postgres, change detection, incremental
  - **Section 13: Excel Source** — test extraction from .xlsx files
  - **Section 14: JSON Source** — test extraction from .json files
  - **Section 15: Single-Table Extraction** — test `--table` flag
  - **Section 16: Run History** — test `feather history` command
  - **Section 17: Append Strategy** — test append-only loading
- `README.md` — update source types table, CLI commands table, add postgres/excel/json examples
- `.claude/rules/feather-etl-project.md` — update directory structure, tech stack, current state table

**Definition of Done:**

- [ ] `docs/testing-feather-etl.md` has test instructions for all 6 new features
- [ ] `README.md` documents new source types and CLI commands
- [ ] `.claude/rules/feather-etl-project.md` reflects new files and state

**Verify:**

Review documentation for completeness and accuracy.

---

### Task 9: Dual-agent verification protocol

**Objective:** Document and execute the Sonnet + Haiku dual-agent verification protocol. This protocol should be reusable for all future slices.
**Dependencies:** Task 8

**Files:**

- The protocol itself is executed via Agent tool calls, not code files

**Key Decisions / Notes:**

**Protocol (record for future use):**

1. **After implementation completes**, update `docs/testing-feather-etl.md` with test sections for all new features (Task 8)

2. **Launch Agent 1 (Sonnet)** — Comprehensive test execution:
   - Run `uv run pytest -q` (full suite)
   - Run `bash scripts/hands_on_test.sh` (CLI integration)
   - For each new feature: create a temporary test project, configure feather.yaml, run extraction, verify results
   - Report: PASS/FAIL per feature with evidence

3. **Launch Agent 2 (Haiku)** — Independent verification against testing guide:
   - Read `docs/testing-feather-etl.md`
   - For each section: independently attempt the described tests WITHOUT reading source code
   - Report: PASS/FAIL/SKIP per section with observations
   - Flag any unclear test instructions (these become doc improvements)

4. **Both agents run in parallel** (`run_in_background=true`)

5. **Reconcile results**: if both pass → verified. If either fails → fix and re-run failing agent.

**Agent invocation pattern:**

```
Agent(
  description="Sonnet comprehensive test",
  model="sonnet",
  prompt="Run full test suite and verify all 6 new features...",
  run_in_background=true
)

Agent(
  description="Haiku independent verification",
  model="haiku",
  prompt="Read docs/testing-feather-etl.md and independently verify each section...",
  run_in_background=true
)
```

**Definition of Done:**

- [ ] Both agents report all new features as PASS
- [ ] Full test suite passes (0 failures)
- [ ] hands_on_test.sh passes
- [ ] No documentation gaps flagged by Haiku agent
- [ ] Verification results written to `docs/reviews/2026-03-28-parallel-slices-verification.md` with per-feature PASS/FAIL and evidence

**Verify:**

Review `docs/reviews/2026-03-28-parallel-slices-verification.md` — all features PASS.

---

## Execution Order

```
Phase 1 — Parallel Implementation (3 agents, worktree-isolated):
  ├── Agent A (Sources): Tasks 1, 2, 3, 4
  ├── Agent B (CLI): Tasks 5, 6
  └── Agent C (Pipeline): Task 7

Phase 2 — Sequential Merge:
  Merge Agent A → Merge Agent B → Merge Agent C
  Resolve any unexpected conflicts

Phase 3 — Documentation (Task 8):
  Update all docs after merge

Phase 4 — Dual-Agent Verification (Task 9):
  ├── Agent Sonnet: full test suite + feature verification
  └── Agent Haiku: independent testing-guide verification
```

## Open Questions

None — all design decisions resolved during planning.

### Deferred Ideas

- **Multi-file CSV** (V6): glob patterns like `sales_*.csv` → single table. Requires config schema changes.
- **PostgreSQL LISTEN/NOTIFY** for real-time change detection — could replace polling.
- **Connection pooling** for PostgreSQL (V14) — not needed for batch ETL but useful for scheduled runs.
