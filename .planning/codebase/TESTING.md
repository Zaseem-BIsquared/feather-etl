# Testing

## Framework & Tools

| Tool | Version | Purpose |
|------|---------|---------|
| pytest | `>=8.0` | Test runner |
| pytest-cov | `>=5.0` | Coverage reporting |
| ruff | `0.14.4` | Linting/formatting (not test-specific, but runs pre-merge) |
| typer.testing.CliRunner | (bundled with typer) | CLI integration testing |
| unittest.mock | (stdlib) | Mocking external services only |

Defined in `pyproject.toml` under `[dependency-groups] dev`.

No `pytest.ini` or `[tool.pytest.ini_options]` in `pyproject.toml` — pytest uses default configuration.

## Test Structure

### Directory Layout
```
tests/
  __init__.py
  conftest.py               # Shared fixtures: client_db, config_path, csv_data_dir, sqlite_db, sample_erp_db
  fixtures/
    client.duckdb            # 6 tables, ~14K rows — real Icube ERP data
    client_update.duckdb     # 3 tables, ~12K rows — for incremental update tests
    sample_erp.duckdb        # 3 tables, 12 rows — fast synthetic data
    sample_erp.sqlite        # 3 tables, 12 rows — SQLite source tests
    csv_data/                # 3 CSV files (orders, customers, products)
    csv_glob/                # 2 CSV files (sales_jan.csv, sales_feb.csv) — glob pattern tests
    excel_data/              # 3 .xlsx files (orders, customers, products)
    json_data/               # 3 JSON files (orders, customers, products)
  test_alerts.py             # SMTP alerting (mocked)
  test_append.py             # Append strategy (feature)
  test_boundary_dedup.py     # Boundary dedup (feature)
  test_cli.py                # CLI commands via CliRunner
  test_config.py             # Config parsing & validation
  test_csv_glob.py           # CSV glob pattern support
  test_dedup.py              # Dedup (feature)
  test_destinations.py       # DuckDB destination load methods
  test_dq.py                 # Data quality checks
  test_e2e.py                # End-to-end: init→validate→discover→setup→run→status
  test_excel.py              # Excel source
  test_incremental.py        # Incremental extraction (feature)
  test_init_wizard.py        # Project scaffolding wizard
  test_integration.py        # Multi-component integration tests
  test_json.py               # JSON source
  test_json_output.py        # --json NDJSON output mode
  test_mode.py               # Dev/prod/test mode system
  test_pipeline.py           # Pipeline orchestration
  test_postgres.py           # PostgreSQL source (mocked + optional real DB)
  test_retry.py              # Retry + backoff state management
  test_schema_drift.py       # Schema drift detection
  test_sources.py            # Source protocol, FileSource, DuckDBFileSource, CsvSource, SqliteSource, registry
  test_sqlserver.py          # SQL Server source (fully mocked)
  test_state.py              # StateManager (watermarks, runs, schema snapshots)
  test_table_filter_and_history.py  # --table filter + history/status commands
  test_transforms.py         # Silver/gold transform engine
```

**Total:** ~341 tests across 28 test files (~8,160 lines of test code)

### Naming Conventions

**Test files:** `test_<module>.py` for unit tests of a single module, `test_<feature>.py` for cross-module feature tests.

**Test classes:** Group related tests with descriptive PascalCase names:
```python
class TestRunTable:           # Tests for run_table() function
class TestIncrementRetry:     # Tests for increment_retry() behavior
class TestNotNull:            # Tests for not_null DQ check
class TestSampleErpFixture:   # Tests validating fixture data
class TestKnownBugs:          # Bugs from reviews (graduated when fixed)
```

**Test functions:** Describe the behavior being verified:
```python
def test_first_run_always_extracts():
def test_unchanged_source_skips():
def test_full_load_swap_replaces_data():
def test_not_null_fails_on_nulls():
def test_smtp_error_caught_and_logged():
```

## Test Categories

### 1. Unit Tests (~100 tests)
Single function/class behavior. No pipeline orchestration needed.

| File | Tests |
|------|-------|
| `tests/test_config.py` | Config parsing, validation, env vars, mode resolution, path resolution |
| `tests/test_state.py` | StateManager: init, watermarks, run recording, schema snapshots |
| `tests/test_destinations.py` | DuckDB load_full, load_append, load_incremental, setup_schemas |
| `tests/test_dq.py` | DQ checks: not_null, unique, duplicate, row_count |
| `tests/test_schema_drift.py` | Drift detection: added, removed, type_changed columns |
| `tests/test_alerts.py` | SMTP alerting: send_alert, alert hooks (fully mocked) |
| `tests/test_sources.py` | Source protocol, FileSource change detection, source registry |

### 2. Feature Tests (~200 tests)
Single feature exercised through the pipeline. Each file tests one cross-cutting concern.

| File | Feature |
|------|---------|
| `tests/test_incremental.py` | Incremental extraction with watermarks + overlap window |
| `tests/test_boundary_dedup.py` | Boundary dedup via PK hashes |
| `tests/test_retry.py` | Retry + backoff state management |
| `tests/test_mode.py` | Dev/prod/test mode system with column_map, target resolution, transforms |
| `tests/test_append.py` | Append strategy (insert-only) |
| `tests/test_dedup.py` | Row dedup and column-based dedup |
| `tests/test_csv_glob.py` | CSV glob pattern support |
| `tests/test_transforms.py` | Silver/gold transform parsing, ordering, execution, materialization |
| `tests/test_excel.py` | Excel source (`.xlsx` and `.xls`) |
| `tests/test_json.py` | JSON source (`.json` and `.jsonl`) |
| `tests/test_json_output.py` | `--json` NDJSON output for all CLI commands |
| `tests/test_init_wizard.py` | `feather init` wizard (interactive + non-interactive) |

### 3. Integration Tests (~30 tests)
Multi-component composition: pipeline + source + destination + state.

| File | Scope |
|------|-------|
| `tests/test_integration.py` | Fixture validation, multi-table pipeline, error isolation, path resolution |
| `tests/test_pipeline.py` | Pipeline orchestration: extract→load→state, table filter, run_all |
| `tests/test_table_filter_and_history.py` | `--table` filter, history/status commands |

### 4. E2E Tests (1-2 tests)
Full CLI flow exercised end-to-end.

| File | Scope |
|------|-------|
| `tests/test_e2e.py` | `init → validate → discover → setup → run → status → run again` (single comprehensive test) |

### 5. Shell Smoke Tests (72 checks)
CLI exercised as a real user would, via `scripts/hands_on_test.sh`.

| Section | Scenarios |
|---------|-----------|
| S1 | `feather init` scaffold, re-init rejection, `.` path |
| S2–S22+ | validate, discover, setup, run, status, history, mode, transforms, etc. |
| S-INCR | Incremental extraction scenarios |

### 6. External DB Tests (conditional)
- `tests/test_postgres.py` — marked `@pytest.mark.skipif(not _postgres_available())`, skipped when no local PostgreSQL
- `tests/test_sqlserver.py` — all tests use `@pytest.mark.unit` with full pyodbc mocking

## Fixtures & Setup

### Shared Fixtures (`tests/conftest.py`)
All fixtures copy source files to `tmp_path` to avoid cross-test contamination:

| Fixture | Returns | Source |
|---------|---------|--------|
| `client_db(tmp_path)` | `Path` to copied `client.duckdb` | `tests/fixtures/client.duckdb` |
| `config_path(client_db, tmp_path)` | `Path` to `feather.yaml` with 3-table config | Generated YAML |
| `csv_data_dir(tmp_path)` | `Path` to copied `csv_data/` directory | `tests/fixtures/csv_data/` |
| `sqlite_db(tmp_path)` | `Path` to copied `sample_erp.sqlite` | `tests/fixtures/sample_erp.sqlite` |
| `sample_erp_db(tmp_path)` | `Path` to copied `sample_erp.duckdb` | `tests/fixtures/sample_erp.duckdb` |

### Local Fixtures (per test file)
Many test files define their own local fixtures when conftest fixtures don't fit:

```python
# tests/test_sources.py
@pytest.fixture
def client_db(self, tmp_path: Path) -> Path:  # Class-scoped override

# tests/test_dq.py
@pytest.fixture
def dq_db(tmp_path: Path):  # Creates specific DQ test data inline

# tests/test_cli.py
@pytest.fixture
def cli_env(tmp_path: Path) -> tuple[Path, Path]:  # Config + source for CLI tests
```

### Helper Functions (underscore-prefixed)
Test files use module-level helpers for repetitive setup:

| Helper | File(s) | Purpose |
|--------|---------|---------|
| `_write_config()` | `test_config.py`, `test_integration.py`, `test_mode.py` | Write YAML config to tmp_path |
| `_minimal_config()` | `test_config.py` | Generate minimal valid config dict |
| `_sample_arrow_table()` | `test_destinations.py` | Create PyArrow table with N rows |
| `_make_bronze_tables()` | `test_transforms.py` | Set up bronze schema + tables in DuckDB |
| `_write_sql()` | `test_transforms.py` | Write transform .sql files |
| `_ts_arrow_table()` | `test_incremental.py` | Create timestamped PyArrow table |
| `_pk_hash()` | `test_boundary_dedup.py` | Compute SHA-256 hash for PK |
| `_make_broken_config()` | `test_retry.py` | Config pointing to nonexistent source |

### Inline Data Creation
Per testing philosophy, feature tests create data inline for self-containment:
```python
def test_dedup_removes_exact_duplicates(tmp_path):
    csv_dir = tmp_path / "data"
    csv_dir.mkdir()
    (csv_dir / "sales.csv").write_text("id,amount\n1,100\n2,200\n1,100\n")
    # ... configure and run
```

## Mocking Patterns

### When Mocking Is Used
Mocking is **only** used for external services that aren't available in CI:

1. **SMTP (alerts):** `@patch("feather.alerts.smtplib.SMTP")` in `tests/test_alerts.py`
2. **pyodbc (SQL Server):** `@patch("feather.sources.sqlserver.pyodbc")` in `tests/test_sqlserver.py`
3. **psycopg2 (PostgreSQL unit tests):** `@patch("feather.sources.postgres.psycopg2")` in `tests/test_postgres.py`
4. **Time-sensitive operations:** `unittest.mock.patch` on `StateManager._utcnow_naive()` in `tests/test_retry.py` for backoff window tests

### When Mocking Is NOT Used
The **core data path** (source → extract → transform → load → state) always uses **real DuckDB, real CSV, real SQLite**:
> "A test that mocks DuckDB and passes is worse than no test—it gives false confidence." — `docs/TESTING-PHILOSOPHY.md`

### Mock Style
```python
from unittest.mock import MagicMock, patch

@patch("feather.alerts.smtplib.SMTP")
def test_sends_email(self, mock_smtp_cls):
    mock_smtp = MagicMock()
    mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
    # ... test ...
    mock_smtp.sendmail.assert_called_once()
```

### Fake Config Objects
Test-only dataclasses replace real config for external services:
```python
@dataclass
class FakeAlertsConfig:
    smtp_host: str = "smtp.example.com"
    smtp_port: int = 587
    # ...
```

## Running Tests

### Primary Commands
```bash
# Run all pytest tests (expect ~341 tests)
uv run pytest -q

# Run shell smoke tests (expect 72 checks)
bash scripts/hands_on_test.sh

# Both must pass before any merge
```

### Coverage
```bash
uv run pytest -q --cov=src --cov-fail-under=80
```
Coverage target: **80%** minimum (configured via CLI flag, not in config files).

### Selective Runs
```bash
# Single test file
uv run pytest tests/test_config.py -q

# Single test class
uv run pytest tests/test_sources.py::TestFileSource -q

# Single test
uv run pytest tests/test_e2e.py::test_full_onboarding_flow -q

# By marker (SQL Server unit tests)
uv run pytest -m unit -q

# Skip slow tests (PostgreSQL)
uv run pytest -m "not postgres" -q
```

### Pytest Markers
| Marker | Usage |
|--------|-------|
| `@pytest.mark.unit` | SQL Server tests (all mocked) in `tests/test_sqlserver.py` |
| `@pytest.mark.skipif(not _postgres_available())` | PostgreSQL tests skipped without local DB |

No custom markers registered in `pyproject.toml`.

## Coverage

- **Target:** 80% line coverage (`--cov-fail-under=80`)
- **Scope:** `--cov=src` (covers `src/feather/` only)
- **Tool:** pytest-cov
- **Not enforced in CI config** (no CI pipeline file found), but documented in `CLAUDE.md` dev commands
- Coverage is measured per the testing philosophy: "Review test count growth. If tests grew but coverage didn't, we have duplicates."

## Testing Philosophy

Fully documented in `docs/TESTING-PHILOSOPHY.md`. Key principles:

### 1. One Behavior, One Test, One Place
Every behavior tested exactly once. The test lives at the level where the behavior is implemented.

### 2. Test Behaviors, Not Code Paths
Tests describe user-observable behaviors, not implementation details:
```python
# ✅ Good
def test_incremental_captures_new_rows_after_watermark():

# ❌ Bad
def test_build_where_clause_returns_string_with_gte():
```

### 3. Real Fixtures, No Mocking (for Data Path)
The core data path uses real DuckDB, real CSV, real SQLite. Never mock these.

### 4. Fresh Directory Per Test
Every test uses `tmp_path` or a fresh directory. No shared mutable state between tests.

### 5. Assert Specific Values
```python
# ✅ assert row_count == 5
# ❌ assert result is not None
```

### 6. Minimal Setup, Maximum Clarity
Setup visible in the test body. Avoid deep fixture chains. Test should be understandable without reading other files.

### Bug Tracking in Tests
- `TestKnownBugs` class in `tests/test_integration.py` — one test per open bug from reviews
- BUG-N labels in docstrings: `"""BUG-3: current wrong behaviour. After fix: correct behaviour."""`
- When fixed: invert assertion, remove BUG prefix, move to positive test class
- Corresponding BUG labels in `scripts/hands_on_test.sh` check() calls

### Fixture Regeneration
```bash
python scripts/create_sample_erp_fixture.py        # DuckDB fixture
python scripts/create_csv_sqlite_fixtures.py       # CSV + SQLite fixtures
python scripts/create_excel_fixture.py             # Excel fixtures
python scripts/create_postgres_test_fixture.py     # PostgreSQL test data
python scripts/create_test_fixture.py              # Client fixture
```

### Pre-Merge Checklist (from `docs/TESTING-PHILOSOPHY.md`)
- [ ] `uv run pytest -q` — all green
- [ ] `bash scripts/hands_on_test.sh` — all 72 checks pass
- [ ] No new test duplicates what an existing test covers
- [ ] Assertions check specific values, not just existence
- [ ] Each test uses a fresh directory (no shared state)
