# CSV and SQLite Source Implementations Plan

Created: 2026-03-26
Status: VERIFIED
Approved: Yes
Iterations: 0
Worktree: Yes
Type: Feature

## Summary

**Goal:** Add CsvSource and SqliteSource implementations, introduce a FileSource base class, and refactor DuckDBFileSource to extend it — completing Slice 1's source type coverage per PRD §1688.

**Architecture:** Thin `FileSource` base class provides shared `__init__(path)`, `check()`, and `detect_changes()`. Three concrete subclasses (`DuckDBFileSource`, `CsvSource`, `SqliteSource`) each implement `discover()`, `extract()`, and `get_schema()` using their own DuckDB reader mechanism (ATTACH, `read_csv()`, `sqlite_scan()`).

**Tech Stack:** Python 3.12, DuckDB (native readers + sqlite_scanner extension), PyArrow

## Scope

### In Scope

- `FileSource` abstract base class with shared behavior
- Refactor `DuckDBFileSource` to extend `FileSource`
- `CsvSource` implementation (directory of CSV files)
- `SqliteSource` implementation (SQLite database file)
- Test fixture generation (CSV + SQLite versions of sample_erp data)
- Registry updates for both new sources
- Config validation updates (CSV directory path vs file path)
- Graduate `test_csv_source_type_rejected_at_validate` (was BUG-2)
- Integration tests for both new source types
- Shell test updates in `hands_on_test.sh`

### Out of Scope

- Change detection (`detect_changes()` returns "always extract" — Slice 2)
- Incremental strategy support (Slice 3)
- Excel/JSON sources (Slice 6 per PRD V6)
- `FileSource.reader_function` abstraction (premature — each source has different reader semantics)

## Approach

**Chosen:** Thin FileSource base class with independent subclass implementations

**Why:** Maximizes code reuse for the genuinely shared parts (path storage, existence check, detect_changes stub) without forcing an artificial abstraction over fundamentally different reader mechanisms (ATTACH vs read_csv vs sqlite_scan). Low risk — DuckDBFileSource refactor is mechanical, and CsvSource/SqliteSource are ~40 LOC each.

**Alternatives considered:**
- *Reader function base class* — FileSource provides generic `extract()` using a `reader_function` attribute. Rejected because DuckDB ATTACH doesn't fit the reader function pattern, forcing DuckDBFileSource to override everything. Would create coupling for no current benefit.
- *Standalone sources (no base)* — Each source is independent. Rejected per user preference for FileSource base class. Would also duplicate `detect_changes()` logic across 3+ sources when Slice 2 adds mtime+hash checking.

## Context for Implementer

> Write for an implementer who has never seen the codebase.

- **Patterns to follow:** `DuckDBFileSource` at `src/feather/sources/duckdb_file.py` is the reference implementation. Every source implements the `Source` Protocol defined in `src/feather/sources/__init__.py:30-50`.
- **Conventions:** Sources return `pyarrow.Table` from `extract()`. `discover()` returns `list[StreamSchema]`. `check()` returns `bool`. All use DuckDB in-memory connections for reading.
- **Key files:**
  - `src/feather/sources/__init__.py` — Protocol + dataclasses (`StreamSchema`, `ChangeResult`)
  - `src/feather/sources/registry.py` — `SOURCE_REGISTRY` dict + `create_source()` factory
  - `src/feather/config.py:14` — `FILE_SOURCE_TYPES` set, `_validate()` function
  - `src/feather/config.py:141` — path existence validation (needs update for CSV directories)
  - `tests/test_sources.py` — unit tests for sources
  - `tests/test_integration.py:462-477` — `test_csv_source_type_rejected_at_validate` (must graduate)
  - `scripts/create_sample_erp_fixture.py` — reference for fixture generation pattern
- **Gotchas:**
  - DuckDB's `sqlite_scanner` extension must be installed+loaded before use: `con.execute("INSTALL sqlite_scanner; LOAD sqlite_scanner")`
  - CSV `source_table` is a filename (e.g., `orders.csv`), resolved against `source.path` directory
  - SQLite `source_table` is a table name in the SQLite DB (no schema prefix — SQLite has no schemas)
  - Config validation currently checks `SOURCE_REGISTRY` keys at `config.py:135`. Once registered, new types pass validation automatically.
  - The `_validate()` function checks `config.source.path.exists()` for all file sources — for CSV, this must check `is_dir()` instead.
- **Domain context:** `source_table` field in `feather.yaml` has different semantics per source type: for DuckDB it's `schema.table_name`, for SQLite it's `table_name`, for CSV it's `filename.csv`.

## Assumptions

- DuckDB's `sqlite_scanner` extension is available and auto-installable in all target environments — supported by DuckDB ≥1.0 bundling it as a core extension. Tasks 4, 6 depend on this.
- CSV files are UTF-8 encoded with headers in the first row — supported by DuckDB `read_csv()` defaults with `auto_detect=true`. Task 3 depends on this.
- `source_table` for CSV is the filename with extension (e.g., `orders.csv`) — supported by PRD §1566 example. Tasks 3, 5, 6 depend on this.
- `source_table` for SQLite is the unqualified table name (e.g., `orders`) — SQLite has no schema concept. Tasks 4, 5, 6 depend on this.

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| sqlite_scanner extension not available in CI | Low | High | Test in Task 4 explicitly installs + loads extension; fail fast with clear error in `check()` |
| CSV auto-detect misidentifies types | Low | Medium | Test with sample_erp data that has known types (INTEGER, DECIMAL, VARCHAR, DATE, TIMESTAMP, NULL) |
| Refactoring DuckDBFileSource breaks existing tests | Low | High | Task 1 runs full test suite before and after refactor |

## Goal Verification

### Truths

1. `feather validate` accepts `type: csv` configs pointing at a directory of CSV files
2. `feather validate` accepts `type: sqlite` configs pointing at a `.sqlite` file
3. `feather discover` lists tables from CSV directories (one per .csv file) and SQLite databases
4. `feather run` with CSV source extracts all rows from CSV files into bronze tables
5. `feather run` with SQLite source extracts all rows from SQLite tables into bronze tables
6. Row counts and NULL values match between DuckDB, CSV, and SQLite extractions of the same data
7. All existing DuckDB-based tests continue to pass after FileSource refactor

### Artifacts

1. `src/feather/sources/file_source.py` — FileSource base class
2. `src/feather/sources/csv.py` — CsvSource implementation
3. `src/feather/sources/sqlite.py` — SqliteSource implementation
4. `src/feather/sources/duckdb_file.py` — refactored to extend FileSource
5. `src/feather/sources/registry.py` — updated with csv + sqlite entries
6. `tests/fixtures/csv_data/` — CSV test fixture directory
7. `tests/fixtures/sample_erp.sqlite` — SQLite test fixture

## Progress Tracking

- [x] Task 1: FileSource base class + DuckDBFileSource refactor
- [x] Task 2: Test fixture generation (CSV + SQLite)
- [x] Task 3: CsvSource implementation + unit tests
- [x] Task 4: SqliteSource implementation + unit tests
- [x] Task 5: Registry, config validation, integration tests + graduated tests

**Total Tasks:** 5 | **Completed:** 5 | **Remaining:** 0

## Implementation Tasks

### Task 1: FileSource Base Class + DuckDBFileSource Refactor

**Objective:** Create `FileSource` base class with shared behavior, refactor `DuckDBFileSource` to extend it. Zero behavior change — all existing tests must pass identically.

**Dependencies:** None

**Files:**

- Create: `src/feather/sources/file_source.py`
- Modify: `src/feather/sources/duckdb_file.py`
- Test: `tests/test_sources.py` (add FileSource tests, existing DuckDB tests unchanged)

**Key Decisions / Notes:**

- `FileSource` is a concrete class (not ABC) — provides `__init__(path)`, `check()`, `detect_changes()`
- `check()` default: `self.path.exists()` — DuckDBFileSource overrides to also try connecting (existing behavior at `duckdb_file.py:29-37`)
- `detect_changes()` default: returns `ChangeResult(changed=True, reason="first_run")` — Slice 1 stub
- DuckDBFileSource keeps `_connect_direct()`, `_connect_attached()`, `discover()`, `extract()`, `get_schema()` unchanged
- DuckDBFileSource calls `super().__init__(path)` and overrides `check()` to add connection validation

**Definition of Done:**

- [ ] `FileSource` class exists with `__init__`, `check()`, `detect_changes()`
- [ ] `DuckDBFileSource` extends `FileSource`, passes `super().__init__(path)`
- [ ] All 92 existing tests pass (0 regressions)
- [ ] New unit test confirms `FileSource.check()` and `detect_changes()` defaults

**Verify:**

- `uv run pytest tests/ -q`

---

### Task 2: Test Fixture Generation (CSV + SQLite)

**Objective:** Create a script that generates CSV and SQLite versions of the sample_erp data, then run it to produce the fixtures.

**Dependencies:** None (independent of Task 1)

**Files:**

- Create: `scripts/create_csv_sqlite_fixtures.py`
- Create: `tests/fixtures/csv_data/orders.csv` (generated)
- Create: `tests/fixtures/csv_data/customers.csv` (generated)
- Create: `tests/fixtures/csv_data/products.csv` (generated)
- Create: `tests/fixtures/sample_erp.sqlite` (generated)

**Key Decisions / Notes:**

- Follow the pattern of `scripts/create_sample_erp_fixture.py` — idempotent, prints summary
- CSV: export from `sample_erp.duckdb` using DuckDB `COPY ... TO ... (FORMAT CSV, HEADER)`
- SQLite: create via Python `sqlite3` module with same schema and data as sample_erp
- SQLite table names: `orders`, `customers`, `products` (no schema prefix — SQLite doesn't have schemas)
- CSV filenames: `orders.csv`, `customers.csv`, `products.csv`
- Preserve NULL in products.stock_qty for both formats
- Add fixtures to git (small files — 12 rows total)

**Definition of Done:**

- [ ] Script runs without error and produces all 4 fixture files
- [ ] CSV files have headers and correct row counts (5/4/3)
- [ ] SQLite DB has 3 tables with correct row counts
- [ ] NULL preserved in products.stock_qty for both formats
- [ ] Script is idempotent (re-running recreates from scratch)

**Verify:**

- `uv run python scripts/create_csv_sqlite_fixtures.py`
- `wc -l tests/fixtures/csv_data/*.csv` (expect 6/5/4 lines including header)

---

### Task 3: CsvSource Implementation + Unit Tests

**Objective:** Implement `CsvSource` that reads CSV files from a directory using DuckDB's `read_csv()`, register it, and add unit tests.

**Dependencies:** Task 1 (FileSource base), Task 2 (CSV fixtures)

**Files:**

- Create: `src/feather/sources/csv.py`
- Modify: `src/feather/sources/registry.py` (add `"csv": CsvSource`)
- Test: `tests/test_sources.py` (add `TestCsvSource` class)

**Key Decisions / Notes:**

- `CsvSource` extends `FileSource`
- `__init__(path)`: calls `super().__init__(path)` — path is a directory
- `check()`: override to `self.path.is_dir()` (directory must exist, not just "exists")
- `discover()`: list `.csv` files in directory, for each file infer schema via DuckDB `read_csv(file, auto_detect=true)` and `DESCRIBE`. Return `StreamSchema` with `name=filename` (e.g., `orders.csv`)
- `extract(table)`: `table` is the filename (e.g., `orders.csv`). Read via `con.execute("SELECT * FROM read_csv(?)", [str(self.path / table)])`. Return `.arrow()`
- `extract()` must accept the full Protocol signature (columns, filter, watermark_column, watermark_value as optional kwargs) even though they are unused in Slice 1. Follow the exact signature from `duckdb_file.py:69-76`.
- `get_schema(table)`: same as discover's column inference but for a single file
- All DuckDB operations use in-memory connection (no ATTACH needed)
- `supports_incremental=False` for all CSV tables (PRD §132: "No (full refresh only)")

**Definition of Done:**

- [ ] `CsvSource` implements all 5 Source Protocol methods
- [ ] `check()` returns True for existing directory, False for nonexistent
- [ ] `discover()` lists all 3 CSV files with column metadata
- [ ] `extract("orders.csv")` returns PyArrow Table with 5 rows
- [ ] `extract()` signature matches Source Protocol (all 5 parameters present)
- [ ] NULL preserved in `products.csv` stock_qty column
- [ ] Registered in `SOURCE_REGISTRY` as `"csv"`
- [ ] All tests pass

**Verify:**

- `uv run pytest tests/test_sources.py -q`

---

### Task 4: SqliteSource Implementation + Unit Tests

**Objective:** Implement `SqliteSource` that reads from SQLite databases using DuckDB's `sqlite_scan()`, register it, and add unit tests.

**Dependencies:** Task 1 (FileSource base), Task 2 (SQLite fixture)

**Files:**

- Create: `src/feather/sources/sqlite.py`
- Modify: `src/feather/sources/registry.py` (add `"sqlite": SqliteSource`)
- Test: `tests/test_sources.py` (add `TestSqliteSource` class)

**Key Decisions / Notes:**

- `SqliteSource` extends `FileSource`
- `__init__(path)`: calls `super().__init__(path)` — path is a `.sqlite` file
- `check()`: override to check `self.path.exists()` AND try `sqlite_scan` connection. Must install+load sqlite_scanner extension: `con.execute("INSTALL sqlite_scanner; LOAD sqlite_scanner")`
- `discover()`: use DuckDB's `sqlite_scan` to read SQLite's internal catalog — `SELECT name FROM sqlite_scan(?, 'sqlite_master') WHERE type = 'table'`, then for each table get columns via `DESCRIBE SELECT * FROM sqlite_scan(?, ?)`. Return `StreamSchema` with `name=table_name` (no schema prefix). Note: `sqlite_master(?)` TVF does NOT exist — must scan `sqlite_master` as a table name argument to `sqlite_scan()`.
- `extract(table)`: `con.execute("SELECT * FROM sqlite_scan(?, ?)", [str(self.path), table])`. Return `.arrow()`
- `extract()` must accept the full Protocol signature (columns, filter, watermark_column, watermark_value as optional kwargs) even though they are unused in Slice 1. Follow the exact signature from `duckdb_file.py:69-76`.
- `get_schema(table)`: `DESCRIBE SELECT * FROM sqlite_scan(?, ?)` — extract column names and types
- `supports_incremental=True` for SQLite tables (PRD §131: "Yes (if timestamp column exists)")

**Definition of Done:**

- [ ] `SqliteSource` implements all 5 Source Protocol methods
- [ ] `check()` returns True for valid SQLite file, False for nonexistent
- [ ] `discover()` lists all 3 tables with column metadata
- [ ] `extract("orders")` returns PyArrow Table with 5 rows
- [ ] `extract()` signature matches Source Protocol (all 5 parameters present)
- [ ] NULL preserved in products.stock_qty
- [ ] sqlite_scanner extension installed and loaded in all methods
- [ ] Registered in `SOURCE_REGISTRY` as `"sqlite"`
- [ ] All tests pass

**Verify:**

- `uv run pytest tests/test_sources.py -q`

---

### Task 5: Config Validation, Integration Tests + Graduated Tests

**Objective:** Update config validation for CSV directory paths, add full-pipeline integration tests for both new sources, graduate the BUG-2 test, and update shell tests.

**Dependencies:** Tasks 3, 4

**Files:**

- Modify: `src/feather/config.py` (update `_validate()` path check for CSV)
- Modify: `tests/test_integration.py` (add CSV + SQLite pipeline tests, graduate BUG-2 test)
- Modify: `scripts/hands_on_test.sh` (add CSV + SQLite source test scenarios)
- Modify: `tests/conftest.py` (add CSV + SQLite fixtures)

**Key Decisions / Notes:**

- Config validation change in `_validate()` at `config.py:141`: for `csv` type, check `path.is_dir()` instead of `path.exists()`. Add error message: "CSV source path must be a directory: {path}"
- BUG-2 graduation (3 steps):
  1. DELETE `test_csv_source_type_rejected_at_validate` from `test_integration.py:462` — it is already in `TestValidationGuards`, not `TestKnownBugs`, so there is nowhere to "move" it. Once csv is registered, this test will fail.
  2. ADD a new `test_csv_source_validates_with_valid_directory` in `TestValidationGuards` that creates a real CSV directory and asserts `load_config()` succeeds.
  3. UPDATE `test_csv_source_type_rejected` in `test_config.py:229` — change it to test a truly-unregistered type (e.g., `type='excel'`) so it still validates the rejection path.
- Integration tests follow the `TestSampleErpFullPipeline` pattern: config → `run_all()` → verify row counts in bronze, NULL pass-through, ETL metadata columns
- Add `csv_data_dir` and `sqlite_db` fixtures to `conftest.py` for reuse
- Shell test additions: validate + discover + run for both CSV and SQLite sources

**Definition of Done:**

- [ ] CSV config with valid directory passes validation
- [ ] CSV config with nonexistent directory fails validation with clear error
- [ ] CSV config with file path (not directory) fails validation
- [ ] Full pipeline works for CSV source: extract 3 tables → bronze, correct row counts (5/4/3)
- [ ] Full pipeline works for SQLite source: extract 3 tables → bronze, correct row counts (5/4/3)
- [ ] NULL pass-through verified for both CSV and SQLite sources
- [ ] `test_csv_source_type_rejected_at_validate` deleted from test_integration.py
- [ ] New `test_csv_source_validates_with_valid_directory` added to TestValidationGuards
- [ ] `test_csv_source_type_rejected` in test_config.py updated to test unregistered type (e.g., 'excel')
- [ ] Shell tests pass for CSV and SQLite scenarios
- [ ] All 92+ tests pass (full suite)
- [ ] `hands_on_test.sh` passes all checks

**Verify:**

- `uv run pytest tests/ -q`
- `bash scripts/hands_on_test.sh`

## Open Questions

None — all design decisions resolved during planning.

### Deferred Ideas

- **FileSource.reader_function abstraction:** When Slice 6 adds JsonSource and ExcelSource, evaluate whether a generic reader_function pattern in FileSource would reduce boilerplate. Currently premature — each source has different reader semantics.
- **CSV auto-detect configuration:** DuckDB `read_csv()` has many options (delimiter, quoting, encoding). Currently using defaults. May need config options for non-standard CSVs in future.
