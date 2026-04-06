# Concerns & Technical Debt

## Technical Debt

### State and data updates are not atomic (FR4.9 violation)
The PRD requires `FR4.9: THE SYSTEM SHALL wrap loading and state update in a single DuckDB transaction.` In practice, `src/feather/pipeline.py` calls `dest.load_full()` / `dest.load_incremental()` / `dest.load_append()` (each in their own transaction on the data DB), then separately calls `state.write_watermark()` and `state.record_run()` on a different DuckDB file (`feather_state.duckdb`). Since data and state live in two separate DuckDB files, there is no cross-file transaction — a crash between load and state update leaves them inconsistent.

### Append strategy lacks partial-failure cleanup (FR4.10 not implemented)
`FR4.10: WHEN retrying an append-strategy table after partial failure THE SYSTEM SHALL first delete rows where _etl_run_id matches the failed run's ID.` The current `load_append()` in `src/feather/destinations/duckdb.py` does a simple INSERT without checking for existing `_etl_run_id` from a failed previous run. A retry after partial failure will duplicate rows.

### `run_id` interpolated directly into SQL
In `src/feather/destinations/duckdb.py` (lines 55, 87, 92, 134), `run_id` is f-string-interpolated into SQL as `'{run_id}' AS _etl_run_id`. While `run_id` is system-generated (`table_name + ISO timestamp`), this is a fragile pattern — a table name containing a single quote would break the SQL.

### `_connect()` called per method in `StateManager`
Every method in `src/feather/state.py` opens and closes its own DuckDB connection. A single `run_table()` call opens 8-12 state DB connections. While DuckDB handles this efficiently for local files, it's unnecessary overhead and makes transactional grouping impossible.

### Duplicate `write_validation_json()` calls (L-1)
`src/feather/cli.py:_load_and_validate()` writes `feather_validation.json`, and it's called on every CLI command. Not harmful, but wasteful on the `run` path.

### `pipeline.py` is a 545-line monolith
`src/feather/pipeline.py` contains the `run_table()` function (~290 lines) with deep nesting (try/except around schema drift, try/except around DQ, three strategy branches). Extraction, loading strategy dispatch, DQ, schema drift, and transform rebuild are all interleaved.

---

## Known Issues

### One known bug in `TestKnownBugs`
`tests/test_integration.py:TestKnownBugs::test_M6_incremental_strategy_silently_does_full_load` — For DuckDB file sources, the first incremental run silently does a full load when there's no prior watermark. This is the expected behavior per code comments ("first incremental run (no watermark yet)"), but the test documents that strategy dispatch doesn't truly differentiate the first run path.

### SQL composition from config fields (M-1 from review)
`src/feather/sources/file_source.py:_build_where_clause()` and `src/feather/sources/database_source.py:_build_where_clause()` interpolate `filter`, `watermark_column`, and `watermark_value` directly into SQL strings via f-strings. The `filter` field comes from YAML config (`filter: "STATUS <> 1"`) and is operator-controlled (not end-user), but there's no sanitization. A config typo or malicious config could produce broken or dangerous SQL.

### Review findings status
Per `docs/reviews/2026-03-27-slice2-3-review-2.md`, findings H-1 (watermark preservation on touch-skip) and H-2 (overlap validation) have been fixed since that review. M-1 (SQL composition) remains open. M-2 (state connection leaks) has been fixed — all state methods now use try/finally.

---

## Security Concerns

### No credential redaction in logs or error messages (NFR8 violation)
The PRD requires `NFR8: Credential redaction in logs. Connection strings and tokens shall never appear in log output or in _runs.error_message.` This is not implemented. When a pyodbc or psycopg2 error occurs, the connection string (potentially containing credentials) appears in the exception message, which is logged via `logger.error()` and stored in `_runs.error_message` by `state.record_run()`.

### No plain-text secret warning (NFR8 violation)
The PRD requires a `[WARNING]` log when known secret fields (e.g., `smtp_password`, `connection_string`) contain literal values instead of `${ENV_VAR}` references. This warning is not implemented in `src/feather/config.py`.

### SQL injection surface in database sources
`src/feather/sources/sqlserver.py:164` and `src/feather/sources/postgres.py:160` construct queries via `f"SELECT {col_clause} FROM {table}{where}"`. The `table` name comes from YAML config's `source_table` field. While config is operator-controlled (not external input), there's no parameterization or quoting for table/column names in database queries. The `columns` list is joined without quoting in SQL Server (`", ".join(columns)`), though DuckDB file sources do quote columns (`f'"{c}"'`).

### File permissions only on creation
`src/feather/state.py` and `src/feather/destinations/duckdb.py` set `0o600` permissions only when the file is newly created. If permissions are changed externally, they won't be re-enforced.

---

## Performance Concerns

### Full-file MD5 hash on every changed-mtime check
`src/feather/sources/file_source.py:_compute_file_hash()` reads the entire file to compute MD5 when mtime changes. For large source files (500MB+), this adds seconds of I/O before extraction even begins. The 8KB chunk size is adequate but the hash computation is sequential.

### PostgreSQL change detection reads all rows
`src/feather/sources/postgres.py:237` computes change detection via `md5(string_agg(row_to_json(t)::text, '' ORDER BY {order_by}))` — this serializes every row to JSON, sorts, concatenates, and hashes. For large tables, this is a full table scan with significant memory and CPU usage on the PostgreSQL server.

### No connection pooling for database sources
`src/feather/sources/sqlserver.py` and `src/feather/sources/postgres.py` create a new connection for every operation (extract, discover, detect_changes, get_schema). For SQL Server over VPN (common in Indian SMB deployments), connection establishment can take 2-5 seconds each time.

### Boundary dedup row-by-row Python loop
`src/feather/pipeline.py:_filter_boundary_rows()` iterates row-by-row in Python to check SHA-256 hashes of PK values at the watermark boundary. For tables with many rows at the boundary timestamp, this is O(n) in Python rather than vectorized.

### No pagination or limit on state queries
`src/feather/state.py:get_status()` joins `_runs` with `_watermarks` without any limit. Over months of operation with hundreds of tables, the `_runs` table grows unbounded with no pruning mechanism.

---

## Fragile Areas

### `run_table()` strategy branching
`src/feather/pipeline.py:run_table()` has three deeply nested strategy branches (incremental with watermark, append, full/first-incremental) with different code paths for column_map, dedup, DQ, and state updates. Adding a new strategy or modifying extraction logic requires understanding all branches.

### Database source `extract()` methods lack try/finally
`src/feather/sources/sqlserver.py:extract()` (line 157) and `src/feather/sources/sqlserver.py:discover()` (line 93) open pyodbc connections without try/finally. An exception during extraction (e.g., network timeout mid-batch, type coercion failure) leaks the database connection. Same applies to `SqlServerSource.get_schema()` and `SqlServerSource.detect_changes()` (the pyodbc.Error catch only covers the execute, not cursor.close/con.close).

### Tight coupling between `DuckDBDestination._connect()` and pipeline
`src/feather/pipeline.py` calls `dest._connect()` directly (a private method) for schema drift ALTER TABLE and DQ checks, bypassing the `Destination` Protocol interface. This makes the pipeline dependent on the DuckDB destination implementation.

### Transform execution order is recalculated on every run
`src/feather/pipeline.py:run_all()` calls `discover_transforms()` + `build_execution_order()` on every pipeline run, re-parsing all SQL files and rebuilding the dependency graph.

---

## Missing Features / Gaps

### MotherDuck sync not implemented (FR6)
The `Destination` Protocol in `src/feather/destinations/__init__.py` declares `sync_to_remote()`, but `DuckDBDestination` doesn't implement it. The pipeline has no sync step. The `sync` config section is parsed in the README examples but not consumed by any code.

### Scheduling not implemented (FR10)
There is no `feather schedule` command, no APScheduler integration, and no `--tier` flag on `feather run`. The `apscheduler` dependency is listed in `pyproject.toml` but unused. The `schedule` field on `TableConfig` is parsed but never consumed.

### No `--tier` flag on `feather run` (FR11.5)
The CLI has `--table` but not `--tier`. Schedule tiers are referenced in config examples but have no runtime effect.

### No `_quarantine` schema usage (FR4.14)
The `_quarantine` schema is created by `DuckDBDestination.setup_schemas()` but never used. Schema drift type changes that fail casting are supposed to route rows to `_quarantine.{table_name}` per FR4.14, but this is not implemented.

### No `partial_success` run status
The PRD references `partial_success` as a run status (FR4.14), but the code only records `success`, `failure`, or `skipped`.

### Custom extract queries (`extracts/` directory) not implemented
The `extracts/` directory is scaffolded by `feather init` but there's no code to discover or use custom extraction SQL files.

### `primary_key` not required by validation (FR2.11)
The PRD says `FR2.11: WHEN primary_key is not configured for a table THE SYSTEM SHALL raise a validation error.` But `src/feather/config.py:_validate()` doesn't check for missing `primary_key`. The field defaults to `None` in `TableConfig`.

### Structured JSONL log rotation not implemented (NFR7)
`src/feather/pipeline.py:_setup_jsonl_logging()` creates a plain `FileHandler` that appends to `feather_log.jsonl` without rotation. NFR7 requires rotation at 10MB with 5 retained files (`RotatingFileHandler`).

### `Destination` Protocol methods not fully implemented
`DuckDBDestination` doesn't implement `execute_sql()` or `sync_to_remote()` from the `Destination` Protocol in `src/feather/destinations/__init__.py`.

---

## Dependency Risks

### `apscheduler` is an unused dependency
Listed in `pyproject.toml` but no code imports it. Adds to install size and attack surface for no benefit until scheduling is implemented.

### `pytz` is a legacy dependency
`pytz` is listed in `pyproject.toml` dependencies. Modern Python (3.9+) uses `zoneinfo` from stdlib. The codebase uses `datetime.timezone.utc` throughout — `pytz` appears unused.

### `psycopg2-binary` bundles libpq
`psycopg2-binary` is convenient but ships a bundled libpq that may not match the system's PostgreSQL version. The `-binary` suffix is fine for development but production deployments should use `psycopg2` with system libpq.

### `pyodbc` requires system ODBC driver
`pyodbc>=5.0` requires the Microsoft ODBC Driver for SQL Server to be installed at the OS level. This is not documented in `pyproject.toml` or README as a system dependency.

### Broad version ranges
Dependencies use minimum version pins (`duckdb>=1.0`, `pyarrow>=15.0`) with no upper bounds. A breaking change in DuckDB 2.0 or PyArrow 20.0 could break the package silently.

---

## Code Quality Hotspots

### `src/feather/pipeline.py` (545 lines)
The largest source file. `run_table()` alone is ~290 lines with 4 levels of nesting. Handles extraction, loading, DQ, schema drift, boundary dedup, and state management in a single function. Prime candidate for decomposition.

### `src/feather/state.py` (509 lines)
Every method opens and closes a connection. The class has grown to handle watermarks, run recording, DQ results, schema snapshots, retry state, and boundary hashes — all in one class with no separation of concerns.

### `src/feather/sources/sqlserver.py` (265 lines) and `src/feather/sources/postgres.py` (275 lines)
Near-identical structure and logic (extract with chunked fetch, discover via INFORMATION_SCHEMA, detect_changes). Significant code duplication between the two — the `DatabaseSource` base class only provides `_build_where_clause()`. The shared chunked-fetch-to-Arrow pattern should be in the base class.

### `src/feather/config.py` (400 lines)
Mixes parsing, validation, path resolution, env var substitution, and JSON output. The `_validate()` function is a long sequential chain of if-checks.

### `src/feather/cli.py` (427 lines)
The `init` command handler has 3 duplicate code paths (non-interactive explicit, non-interactive via flags, interactive) that all call the same underlying functions.
