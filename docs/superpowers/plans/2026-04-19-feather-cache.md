# `feather cache` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `feather cache` — a dev-only CLI command that pulls curated source tables into `bronze.*` using isolated cache state, skipping unchanged sources on re-run, never touching production state.

**Architecture:** Dedicated `run_cache()` orchestrator in `src/feather_etl/cache.py` with its own loop — does not modify `pipeline.run_all`/`run_table`. State isolation is enforced by the API surface: a new `_cache_watermarks` table plus sibling `read_cache_watermark` / `write_cache_watermark` methods on `StateManager`. The CLI wrapper `src/feather_etl/commands/cache.py` handles selector parsing, prod-mode rejection, and grouped human output. No transforms, no DQ, no schema drift, no run-history tracking.

**Tech Stack:** Python 3.10+, Typer (CLI), DuckDB (destination + state), PyArrow (interchange), pytest + `typer.testing.CliRunner` (tests), `uv` for dep management.

**Spec:** `docs/superpowers/specs/2026-04-19-feather-cache-design.md`
**Issue:** [#15](https://github.com/siraj-samsudeen/feather-etl/issues/15)

---

## Preconditions

- [ ] **Run the existing test suite and confirm green before any edits.**

Run: `uv run pytest -q`
Expected: all tests pass (should be ~597, matching `CLAUDE.md`).

If anything is red before you start, stop and surface it — do not proceed.

---

## File structure

**New files:**

| Path | Responsibility |
|---|---|
| `src/feather_etl/cache.py` | `run_cache()` orchestrator + `CacheResult` dataclass. One function, one dataclass, no CLI code. |
| `src/feather_etl/commands/cache.py` | Typer command. Flag parsing, mode guard, selector resolution, dispatch to `run_cache`, grouped output formatting. |
| `tests/test_cache.py` | Unit tests for `run_cache`. Uses real DuckDB fixtures per project convention. |
| `tests/commands/test_cache.py` | CLI tests via `CliRunner`. Follows pattern of `tests/commands/test_run.py`. |

**Modified files:**

| Path | Change |
|---|---|
| `src/feather_etl/state.py` | Add `_cache_watermarks` CREATE TABLE to `init_state()`; add `read_cache_watermark` and `write_cache_watermark` methods. |
| `tests/test_state.py` | Add `TestCacheWatermarks` class covering the new table + methods. |
| `src/feather_etl/cli.py` | Register cache command. |
| `README.md` | Add "Dev cache" subsection. |
| `docs/prd.md` | §499 — one-line pointer to `feather cache`. |
| `CLAUDE.md` | Bump pytest count after new tests land. |

---

## Task 1: Add `_cache_watermarks` table to `StateManager.init_state()`

**Files:**
- Modify: `src/feather_etl/state.py` — add CREATE TABLE block inside `init_state()`
- Test: `tests/test_state.py` — extend `TestStateInit.test_creates_all_tables`

- [ ] **Step 1: Write the failing test**

Open `tests/test_state.py`. Find `TestStateInit.test_creates_all_tables`. Update the `expected` set to include the new table:

```python
    def test_creates_all_tables(self, tmp_path: Path):
        from feather_etl.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()

        con = duckdb.connect(str(sm.path), read_only=True)
        tables = {
            r[0]
            for r in con.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'main'"
            ).fetchall()
        }
        con.close()
        expected = {
            "_state_meta",
            "_watermarks",
            "_runs",
            "_run_steps",
            "_dq_results",
            "_schema_snapshots",
            "_cache_watermarks",
        }
        assert tables == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_state.py::TestStateInit::test_creates_all_tables -v`
Expected: FAIL with `AssertionError` — actual set is missing `_cache_watermarks`.

- [ ] **Step 3: Write the failing idempotency test**

Add a new test to the `TestStateInit` class in `tests/test_state.py`:

```python
    def test_cache_watermarks_table_schema(self, tmp_path: Path):
        """_cache_watermarks has exactly the columns we need, no more."""
        from feather_etl.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()

        con = duckdb.connect(str(sm.path), read_only=True)
        rows = con.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = '_cache_watermarks' ORDER BY ordinal_position"
        ).fetchall()
        con.close()

        expected = [
            ("table_name", "VARCHAR"),
            ("source_db", "VARCHAR"),
            ("last_file_mtime", "DOUBLE"),
            ("last_file_hash", "VARCHAR"),
            ("last_checksum", "VARCHAR"),
            ("last_row_count", "INTEGER"),
            ("last_run_at", "TIMESTAMP"),
        ]
        assert rows == expected
```

- [ ] **Step 4: Run the schema test to verify it fails**

Run: `uv run pytest tests/test_state.py::TestStateInit::test_cache_watermarks_table_schema -v`
Expected: FAIL — table does not exist.

- [ ] **Step 5: Implement the new table in `init_state()`**

Open `src/feather_etl/state.py`. Find the `init_state` method. Add this CREATE TABLE block right after the `_schema_snapshots` block (before the version check/insert):

```python
            con.execute("""
                CREATE TABLE IF NOT EXISTS _cache_watermarks (
                    table_name VARCHAR PRIMARY KEY,
                    source_db VARCHAR,
                    last_file_mtime DOUBLE,
                    last_file_hash VARCHAR,
                    last_checksum VARCHAR,
                    last_row_count INTEGER,
                    last_run_at TIMESTAMP
                )
            """)
```

- [ ] **Step 6: Run both new tests to verify they pass**

Run: `uv run pytest tests/test_state.py::TestStateInit -v`
Expected: all tests in `TestStateInit` pass, including `test_creates_all_tables` and `test_cache_watermarks_table_schema`.

- [ ] **Step 7: Run the full state test suite to confirm no regression**

Run: `uv run pytest tests/test_state.py -v`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add src/feather_etl/state.py tests/test_state.py
git commit -m "feat(state): add _cache_watermarks table (#15)

Additive schema change to StateManager.init_state(). Creates
_cache_watermarks with a primary key on table_name plus fields for
change-detection fingerprints (file_mtime/hash for file sources,
checksum/row_count for DB sources).

No schema_version bump — purely additive. Existing state DBs
auto-upgrade on next init_state() call."
```

---

## Task 2: Add `read_cache_watermark` + `write_cache_watermark` to `StateManager`

**Files:**
- Modify: `src/feather_etl/state.py` — add two new methods
- Test: `tests/test_state.py` — new `TestCacheWatermarks` class

- [ ] **Step 1: Write failing test for `read_cache_watermark` empty case**

Add to `tests/test_state.py` at the end of the file (after existing classes):

```python
class TestCacheWatermarks:
    """Cache-scoped watermark methods — fully isolated from _watermarks."""

    def test_read_returns_none_when_absent(self, tmp_path: Path):
        from feather_etl.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()
        assert sm.read_cache_watermark("nonexistent") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_state.py::TestCacheWatermarks::test_read_returns_none_when_absent -v`
Expected: FAIL — `AttributeError: 'StateManager' object has no attribute 'read_cache_watermark'`.

- [ ] **Step 3: Implement `read_cache_watermark`**

Open `src/feather_etl/state.py`. Add this method inside the `StateManager` class (put it right after `read_watermark`):

```python
    def read_cache_watermark(self, table_name: str) -> dict[str, object] | None:
        """Read a row from _cache_watermarks. Returns None if absent.

        Hardcoded to _cache_watermarks — this method cannot read from
        _watermarks under any circumstances.
        """
        con = self._connect()
        try:
            row = con.execute(
                "SELECT * FROM _cache_watermarks WHERE table_name = ?",
                [table_name],
            ).fetchone()
            if row is None:
                return None
            columns = [desc[0] for desc in con.description]
            return dict(zip(columns, row))
        finally:
            con.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_state.py::TestCacheWatermarks::test_read_returns_none_when_absent -v`
Expected: PASS.

- [ ] **Step 5: Write failing test for `write_cache_watermark` insert + `read_cache_watermark` round-trip**

Append to `TestCacheWatermarks` in `tests/test_state.py`:

```python
    def test_write_then_read_roundtrip(self, tmp_path: Path):
        from datetime import datetime, timezone
        from feather_etl.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()
        now = datetime.now(timezone.utc)
        sm.write_cache_watermark(
            table_name="afans_sales",
            source_db="afans",
            last_run_at=now,
            last_file_mtime=1234567890.5,
            last_file_hash="deadbeef",
            last_checksum="abc123",
            last_row_count=42,
        )
        row = sm.read_cache_watermark("afans_sales")
        assert row is not None
        assert row["table_name"] == "afans_sales"
        assert row["source_db"] == "afans"
        assert row["last_file_mtime"] == 1234567890.5
        assert row["last_file_hash"] == "deadbeef"
        assert row["last_checksum"] == "abc123"
        assert row["last_row_count"] == 42
```

- [ ] **Step 6: Run test to verify it fails**

Run: `uv run pytest tests/test_state.py::TestCacheWatermarks::test_write_then_read_roundtrip -v`
Expected: FAIL — `AttributeError: 'StateManager' object has no attribute 'write_cache_watermark'`.

- [ ] **Step 7: Implement `write_cache_watermark`**

Open `src/feather_etl/state.py`. Add this method inside the `StateManager` class (put it right after `read_cache_watermark`):

```python
    def write_cache_watermark(
        self,
        table_name: str,
        source_db: str,
        last_run_at: datetime,
        last_file_mtime: float | None = None,
        last_file_hash: str | None = None,
        last_checksum: str | None = None,
        last_row_count: int | None = None,
    ) -> None:
        """Upsert a row into _cache_watermarks.

        Hardcoded to _cache_watermarks — this method cannot touch
        _watermarks under any circumstances.
        """
        con = self._connect()
        try:
            existing = con.execute(
                "SELECT COUNT(*) FROM _cache_watermarks WHERE table_name = ?",
                [table_name],
            ).fetchone()[0]
            if existing:
                con.execute(
                    "UPDATE _cache_watermarks SET source_db = ?, "
                    "last_file_mtime = ?, last_file_hash = ?, "
                    "last_checksum = ?, last_row_count = ?, last_run_at = ? "
                    "WHERE table_name = ?",
                    [
                        source_db,
                        last_file_mtime,
                        last_file_hash,
                        str(last_checksum) if last_checksum is not None else None,
                        last_row_count,
                        last_run_at,
                        table_name,
                    ],
                )
            else:
                con.execute(
                    "INSERT INTO _cache_watermarks "
                    "(table_name, source_db, last_file_mtime, last_file_hash, "
                    "last_checksum, last_row_count, last_run_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [
                        table_name,
                        source_db,
                        last_file_mtime,
                        last_file_hash,
                        str(last_checksum) if last_checksum is not None else None,
                        last_row_count,
                        last_run_at,
                    ],
                )
        finally:
            con.close()
```

Note: `last_checksum` is stored as VARCHAR because the checksum source (SQL Server CHECKSUM_AGG returns int, Postgres md5 returns hex string) varies. We normalize to string at the boundary.

- [ ] **Step 8: Run test to verify it passes**

Run: `uv run pytest tests/test_state.py::TestCacheWatermarks::test_write_then_read_roundtrip -v`
Expected: PASS.

- [ ] **Step 9: Write failing test for upsert (overwrite existing row)**

Append to `TestCacheWatermarks`:

```python
    def test_write_upserts_existing_row(self, tmp_path: Path):
        from datetime import datetime, timezone
        from feather_etl.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()
        t1 = datetime(2026, 4, 1, tzinfo=timezone.utc)
        t2 = datetime(2026, 4, 2, tzinfo=timezone.utc)

        sm.write_cache_watermark(
            table_name="t",
            source_db="db",
            last_run_at=t1,
            last_file_hash="old",
        )
        sm.write_cache_watermark(
            table_name="t",
            source_db="db",
            last_run_at=t2,
            last_file_hash="new",
        )
        row = sm.read_cache_watermark("t")
        assert row["last_file_hash"] == "new"
        # Only one row
        import duckdb
        con = duckdb.connect(str(sm.path), read_only=True)
        count = con.execute(
            "SELECT COUNT(*) FROM _cache_watermarks WHERE table_name = 't'"
        ).fetchone()[0]
        con.close()
        assert count == 1
```

- [ ] **Step 10: Run test to verify it passes**

Run: `uv run pytest tests/test_state.py::TestCacheWatermarks::test_write_upserts_existing_row -v`
Expected: PASS (the method already handles UPDATE vs INSERT).

- [ ] **Step 11: Write failing test for isolation — write_cache_watermark does not touch _watermarks**

Append to `TestCacheWatermarks`:

```python
    def test_write_cache_watermark_does_not_touch_watermarks(self, tmp_path: Path):
        """Cache writes must never land in the prod _watermarks table."""
        from datetime import datetime, timezone
        import duckdb
        from feather_etl.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()
        sm.write_cache_watermark(
            table_name="isolated",
            source_db="db",
            last_run_at=datetime.now(timezone.utc),
            last_file_hash="h",
        )
        con = duckdb.connect(str(sm.path), read_only=True)
        prod_count = con.execute("SELECT COUNT(*) FROM _watermarks").fetchone()[0]
        cache_count = con.execute(
            "SELECT COUNT(*) FROM _cache_watermarks"
        ).fetchone()[0]
        con.close()
        assert prod_count == 0
        assert cache_count == 1
```

- [ ] **Step 12: Run test to verify it passes**

Run: `uv run pytest tests/test_state.py::TestCacheWatermarks::test_write_cache_watermark_does_not_touch_watermarks -v`
Expected: PASS.

- [ ] **Step 13: Run the full state test suite**

Run: `uv run pytest tests/test_state.py -v`
Expected: all pass, including existing tests.

- [ ] **Step 14: Commit**

```bash
git add src/feather_etl/state.py tests/test_state.py
git commit -m "feat(state): add read_cache_watermark + write_cache_watermark (#15)

Cache-scoped sibling methods to read_watermark/write_watermark.
Hardcoded to _cache_watermarks — no scope parameter means there is
no code path from these methods to the production _watermarks table.

State isolation is a property of the API surface: code that only
calls *_cache_* methods cannot corrupt prod state."
```

---

## Task 3: Build `run_cache()` orchestrator in `src/feather_etl/cache.py`

**Files:**
- Create: `src/feather_etl/cache.py`
- Test: `tests/test_cache.py`

Each test builds on the same `_cache_project` fixture pattern — we define it as the first step.

- [ ] **Step 1: Write failing test for successful full extraction**

Create `tests/test_cache.py`:

```python
"""Unit tests for feather_etl.cache.run_cache()."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pytest
import yaml

from tests.conftest import FIXTURES_DIR
from tests.helpers import make_curation_entry, write_curation


def _make_project(tmp_path: Path) -> Path:
    """Build a minimal feather project: 1 DuckDB source, 1 curated table."""
    client_db = tmp_path / "client.duckdb"
    shutil.copy2(FIXTURES_DIR / "client.duckdb", client_db)
    config = {
        "sources": [{"type": "duckdb", "name": "icube", "path": str(client_db)}],
        "destination": {"path": str(tmp_path / "feather_data.duckdb")},
    }
    (tmp_path / "feather.yaml").write_text(yaml.dump(config))
    write_curation(
        tmp_path,
        [make_curation_entry("icube", "icube.InventoryGroup", "inventory_group")],
    )
    return tmp_path / "feather.yaml"


class TestRunCacheBasic:
    def test_extracts_all_columns_into_bronze(self, tmp_path: Path):
        from feather_etl.cache import run_cache
        from feather_etl.config import load_config

        config_path = _make_project(tmp_path)
        cfg = load_config(config_path)
        results = run_cache(cfg, cfg.tables, tmp_path)

        assert len(results) == 1
        assert results[0].status == "success"
        assert results[0].table_name == "icube_inventory_group"
        assert results[0].rows_loaded > 0

        # Verify bronze table exists with all source columns
        con = duckdb.connect(str(cfg.destination.path), read_only=True)
        cols = {
            r[0]
            for r in con.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'bronze' "
                "AND table_name = 'icube_inventory_group'"
            ).fetchall()
        }
        con.close()
        # Must include _etl_* metadata columns + source columns
        assert "_etl_loaded_at" in cols
        assert "_etl_run_id" in cols
        assert len(cols) > 2  # more than just the metadata columns
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cache.py::TestRunCacheBasic::test_extracts_all_columns_into_bronze -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'feather_etl.cache'`.

- [ ] **Step 3: Create the minimal `cache.py` module to make the test pass**

Create `src/feather_etl/cache.py`:

```python
"""`feather cache` orchestrator — dev-only bronze pull, isolated state."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from feather_etl.config import FeatherConfig, TableConfig
from feather_etl.curation import resolve_source
from feather_etl.destinations.duckdb import DuckDBDestination
from feather_etl.state import StateManager

logger = logging.getLogger(__name__)


@dataclass
class CacheResult:
    """Result of caching one table."""

    table_name: str
    source_db: str
    status: str  # "success" | "cached" | "failure"
    rows_loaded: int = 0
    error_message: str | None = None


def run_cache(
    config: FeatherConfig,
    tables: list[TableConfig],
    working_dir: Path,
    refresh: bool = False,
) -> list[CacheResult]:
    """Pull curated tables into bronze. Dev-only. No transforms, no DQ, no drift."""
    state = StateManager(working_dir / "feather_state.duckdb")
    state.init_state()
    dest = DuckDBDestination(path=config.destination.path)
    dest.setup_schemas()

    results: list[CacheResult] = []
    for table in tables:
        source_db = table.database or (table.source_name or "")
        try:
            source = resolve_source(source_db, config.sources)
        except ValueError as e:
            results.append(
                CacheResult(
                    table_name=table.name,
                    source_db=source_db,
                    status="failure",
                    error_message=str(e),
                )
            )
            continue

        now = datetime.now(timezone.utc)
        run_id = f"cache_{table.name}_{now.isoformat()}"

        wm = state.read_cache_watermark(table.name)
        change = source.detect_changes(table.source_table, last_state=wm)

        if not change.changed and not refresh:
            results.append(
                CacheResult(
                    table_name=table.name,
                    source_db=source_db,
                    status="cached",
                )
            )
            continue

        try:
            data = source.extract(table.source_table)
            rows = dest.load_full(f"bronze.{table.name}", data, run_id)
            state.write_cache_watermark(
                table_name=table.name,
                source_db=source_db,
                last_run_at=now,
                last_file_mtime=change.metadata.get("file_mtime"),
                last_file_hash=change.metadata.get("file_hash"),
                last_checksum=change.metadata.get("checksum"),
                last_row_count=change.metadata.get("row_count"),
            )
            results.append(
                CacheResult(
                    table_name=table.name,
                    source_db=source_db,
                    status="success",
                    rows_loaded=rows,
                )
            )
        except Exception as e:
            logger.error("Cache failed for %s: %s", table.name, e)
            results.append(
                CacheResult(
                    table_name=table.name,
                    source_db=source_db,
                    status="failure",
                    error_message=str(e),
                )
            )

    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cache.py::TestRunCacheBasic::test_extracts_all_columns_into_bronze -v`
Expected: PASS.

- [ ] **Step 5: Write failing test for state isolation**

Append to `tests/test_cache.py`:

```python
class TestRunCacheStateIsolation:
    def test_writes_only_to_cache_watermarks(self, tmp_path: Path):
        """After run_cache, _watermarks must be empty and _cache_watermarks populated."""
        from feather_etl.cache import run_cache
        from feather_etl.config import load_config

        config_path = _make_project(tmp_path)
        cfg = load_config(config_path)
        run_cache(cfg, cfg.tables, tmp_path)

        state_db = tmp_path / "feather_state.duckdb"
        con = duckdb.connect(str(state_db), read_only=True)
        prod = con.execute("SELECT COUNT(*) FROM _watermarks").fetchone()[0]
        cache = con.execute(
            "SELECT COUNT(*) FROM _cache_watermarks"
        ).fetchone()[0]
        runs = con.execute("SELECT COUNT(*) FROM _runs").fetchone()[0]
        con.close()

        assert prod == 0, "run_cache must not write to _watermarks"
        assert runs == 0, "run_cache must not write to _runs"
        assert cache == 1, "run_cache must write to _cache_watermarks"
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_cache.py::TestRunCacheStateIsolation -v`
Expected: PASS (the method-hardcoding in Tasks 1 & 2 enforces this structurally).

- [ ] **Step 7: Write failing test for smart skip on second run**

Append to `tests/test_cache.py`:

```python
class TestRunCacheSkip:
    def test_skips_unchanged_on_second_run(self, tmp_path: Path):
        from feather_etl.cache import run_cache
        from feather_etl.config import load_config

        config_path = _make_project(tmp_path)
        cfg = load_config(config_path)

        first = run_cache(cfg, cfg.tables, tmp_path)
        assert first[0].status == "success"

        second = run_cache(cfg, cfg.tables, tmp_path)
        assert second[0].status == "cached"
        assert second[0].rows_loaded == 0

    def test_refresh_forces_repull(self, tmp_path: Path):
        from feather_etl.cache import run_cache
        from feather_etl.config import load_config

        config_path = _make_project(tmp_path)
        cfg = load_config(config_path)

        run_cache(cfg, cfg.tables, tmp_path)
        second = run_cache(cfg, cfg.tables, tmp_path, refresh=True)

        assert second[0].status == "success"
        assert second[0].rows_loaded > 0
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/test_cache.py::TestRunCacheSkip -v`
Expected: PASS for both.

- [ ] **Step 9: Write failing test for partial failure**

Append to `tests/test_cache.py`:

```python
class TestRunCachePartialFailure:
    def test_one_failure_does_not_block_others(self, tmp_path: Path):
        """One bad table should not prevent other tables from being cached."""
        from feather_etl.cache import run_cache
        from feather_etl.config import load_config

        client_db = tmp_path / "client.duckdb"
        shutil.copy2(FIXTURES_DIR / "client.duckdb", client_db)
        config = {
            "sources": [
                {"type": "duckdb", "name": "icube", "path": str(client_db)}
            ],
            "destination": {"path": str(tmp_path / "feather_data.duckdb")},
        }
        (tmp_path / "feather.yaml").write_text(yaml.dump(config))
        write_curation(
            tmp_path,
            [
                make_curation_entry(
                    "icube", "icube.InventoryGroup", "good_table"
                ),
                make_curation_entry("icube", "icube.DOES_NOT_EXIST", "bad_table"),
            ],
        )

        cfg = load_config(tmp_path / "feather.yaml")
        results = run_cache(cfg, cfg.tables, tmp_path)

        statuses = {r.table_name: r.status for r in results}
        assert statuses["icube_good_table"] == "success"
        assert statuses["icube_bad_table"] == "failure"
```

- [ ] **Step 10: Run test to verify it passes**

Run: `uv run pytest tests/test_cache.py::TestRunCachePartialFailure -v`
Expected: PASS (the try/except around the extract/load path in `run_cache` handles this).

- [ ] **Step 11: Run the full `test_cache.py` suite**

Run: `uv run pytest tests/test_cache.py -v`
Expected: all pass.

- [ ] **Step 12: Commit**

```bash
git add src/feather_etl/cache.py tests/test_cache.py
git commit -m "feat(cache): add run_cache() orchestrator (#15)

New src/feather_etl/cache.py with run_cache(config, tables,
working_dir, refresh=False) -> list[CacheResult]. Loop: resolve
source → detect_changes against cache watermark → extract all
columns → load_full to bronze.<name> → write cache watermark.

No DQ, no transforms, no schema drift, no overlap windows, no retry
backoff, no column mapping. One pass per table.

State isolation verified: _watermarks and _runs remain empty after
run_cache completes; only _cache_watermarks gets rows."
```

---

## Task 4: Build `commands/cache.py` CLI

**Files:**
- Create: `src/feather_etl/commands/cache.py`
- Test: `tests/commands/test_cache.py`

This task is subdivided by behavior because there are many CLI behaviors. Each sub-step is its own test → impl → commit cycle.

### Task 4a: Bare CLI that dispatches to `run_cache`

- [ ] **Step 1: Write failing test for happy path**

Create `tests/commands/test_cache.py`:

```python
"""Tests for the `feather cache` command."""

from __future__ import annotations

import shutil
from pathlib import Path

import duckdb
import pytest
import yaml
from typer.testing import CliRunner

from tests.conftest import FIXTURES_DIR
from tests.helpers import make_curation_entry, write_curation


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _project(tmp_path: Path) -> Path:
    """Minimal project: 1 DuckDB source, 1 curated table. Returns config path."""
    client_db = tmp_path / "client.duckdb"
    shutil.copy2(FIXTURES_DIR / "client.duckdb", client_db)
    config = {
        "sources": [{"type": "duckdb", "name": "icube", "path": str(client_db)}],
        "destination": {"path": str(tmp_path / "feather_data.duckdb")},
    }
    cp = tmp_path / "feather.yaml"
    cp.write_text(yaml.dump(config))
    write_curation(
        tmp_path,
        [make_curation_entry("icube", "icube.InventoryGroup", "inventory_group")],
    )
    return cp


class TestCacheBasic:
    def test_cold_run_extracts_tables(self, runner, tmp_path: Path):
        from feather_etl.cli import app

        config_path = _project(tmp_path)
        result = runner.invoke(app, ["cache", "--config", str(config_path)])
        assert result.exit_code == 0
        assert "extracted" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/commands/test_cache.py::TestCacheBasic::test_cold_run_extracts_tables -v`
Expected: FAIL with `No such command 'cache'` (the command is not registered yet) or `ModuleNotFoundError`.

- [ ] **Step 3: Create minimal `commands/cache.py`**

Create `src/feather_etl/commands/cache.py`:

```python
"""`feather cache` command — dev-only local bronze pull."""

from __future__ import annotations

from pathlib import Path

import typer

from feather_etl.commands._common import _load_and_validate


def cache(
    config: Path = typer.Option("feather.yaml", "--config"),
    table: str | None = typer.Option(
        None,
        "--table",
        help="Comma-separated bronze table names to cache. "
        "Default: all curated tables.",
    ),
    source: str | None = typer.Option(
        None,
        "--source",
        help="Comma-separated source_db values to cache. "
        "Default: all sources in curation.",
    ),
    refresh: bool = typer.Option(
        False,
        "--refresh",
        help="Force re-pull even if source is unchanged.",
    ),
) -> None:
    """Pull curated source tables into bronze (dev-only)."""
    from feather_etl.cache import run_cache

    cfg = _load_and_validate(config)

    if cfg.mode == "prod":
        typer.echo(
            "feather cache is a dev-only tool. "
            "Remove 'mode: prod' or unset FEATHER_MODE=prod to use it.",
            err=True,
        )
        raise typer.Exit(code=2)

    tables = cfg.tables
    results = run_cache(cfg, tables, cfg.config_dir, refresh=refresh)

    # Grouped-by-source_db output
    from collections import defaultdict
    groups: dict[str, list] = defaultdict(list)
    for r in results:
        groups[r.source_db].append(r)

    typer.echo("Mode: dev (cache)")
    total_success = 0
    total_cached = 0
    total_failed = 0
    for source_db, rs in groups.items():
        succ = sum(1 for r in rs if r.status == "success")
        cach = sum(1 for r in rs if r.status == "cached")
        fail = sum(1 for r in rs if r.status == "failure")
        total_success += succ
        total_cached += cach
        total_failed += fail

        parts = []
        if succ:
            parts.append(f"{succ} extracted")
        if cach:
            parts.append(f"{cach} cached")
        if fail:
            parts.append(f"{fail} failed")
        # Look up the source 'name' for the parenthetical. For file sources,
        # source_db == source.name, so fall back to source_db.
        src_name = _lookup_source_name(cfg, source_db)
        line = f"  {source_db:<12} ({src_name}): {', '.join(parts) or '0 tables'}"
        typer.echo(line)
        for r in rs:
            if r.status == "failure":
                err = (r.error_message or "").splitlines()[0][:120]
                typer.echo(f"    ✗ {r.table_name} — {err}")

    total = len(results)
    summary_parts = []
    if total_success:
        summary_parts.append(f"{total_success} extracted")
    if total_cached:
        summary_parts.append(f"{total_cached} cached")
    if total_failed:
        summary_parts.append(f"{total_failed} failed")
    typer.echo(f"\n{total} tables: {', '.join(summary_parts) or '0 tables'}.")

    if total_failed:
        raise typer.Exit(code=1)


def _lookup_source_name(cfg, source_db: str) -> str:
    """Find the YAML source 'name' corresponding to a source_db."""
    from feather_etl.curation import resolve_source
    try:
        src = resolve_source(source_db, cfg.sources)
        return src.name
    except ValueError:
        return source_db


def register(app: typer.Typer) -> None:
    app.command(name="cache")(cache)
```

- [ ] **Step 4: Register the command in `cli.py`**

Open `src/feather_etl/cli.py`. Add the import and registration:

```python
from feather_etl.commands.cache import register as register_cache
```

And add `register_cache(app)` after `register_status(app)`:

```python
register_cache(app)
```

(Full file after the edit ends with the block of `register_*` calls — the order does not matter to Typer.)

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/commands/test_cache.py::TestCacheBasic::test_cold_run_extracts_tables -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/feather_etl/commands/cache.py src/feather_etl/cli.py tests/commands/test_cache.py
git commit -m "feat(cli): add bare feather cache command (#15)

Minimum viable CLI: invokes run_cache with the full curated table
list and prints grouped-by-source output. Exits 1 if any table
failed, 0 otherwise."
```

### Task 4b: Hard-error when effective mode is prod

- [ ] **Step 1: Write failing test for YAML `mode: prod`**

Append to `tests/commands/test_cache.py`:

```python
class TestCacheProdModeGuard:
    def test_rejects_yaml_mode_prod(self, runner, tmp_path: Path):
        from feather_etl.cli import app

        client_db = tmp_path / "client.duckdb"
        shutil.copy2(FIXTURES_DIR / "client.duckdb", client_db)
        config = {
            "mode": "prod",
            "sources": [{"type": "duckdb", "name": "icube", "path": str(client_db)}],
            "destination": {"path": str(tmp_path / "feather_data.duckdb")},
        }
        cp = tmp_path / "feather.yaml"
        cp.write_text(yaml.dump(config))
        write_curation(
            tmp_path,
            [make_curation_entry("icube", "icube.InventoryGroup", "inv")],
        )

        result = runner.invoke(app, ["cache", "--config", str(cp)])
        assert result.exit_code == 2
        assert "dev-only" in result.output

    def test_rejects_feather_mode_env_prod(self, runner, tmp_path: Path, monkeypatch):
        from feather_etl.cli import app

        monkeypatch.setenv("FEATHER_MODE", "prod")
        config_path = _project(tmp_path)
        result = runner.invoke(app, ["cache", "--config", str(config_path)])
        assert result.exit_code == 2
        assert "dev-only" in result.output
```

- [ ] **Step 2: Run tests — verify they already pass**

Run: `uv run pytest tests/commands/test_cache.py::TestCacheProdModeGuard -v`
Expected: PASS — the guard is already in place from Step 3 of Task 4a.

If one fails, fix the logic in `commands/cache.py` (usually a message wording issue) and rerun.

- [ ] **Step 3: Commit**

```bash
git add tests/commands/test_cache.py
git commit -m "test(cache): verify prod-mode hard-error guard (#15)"
```

### Task 4c: Error cleanly when `discovery/curation.json` is missing

Context: the shared `_load_and_validate` helper in `commands/_common.py` swallows the curation-specific error message when `curation.json` is missing (it prints a generic `"Config file not found: <feather.yaml>"` with exit 1). That's misleading for users — `feather.yaml` exists; it's `curation.json` that's missing. Rather than modifying shared code (out of scope), `commands/cache.py` will pre-check for `curation.json` with a clear message and exit 2.

- [ ] **Step 1: Write failing test**

Append to `tests/commands/test_cache.py`:

```python
class TestCacheMissingCuration:
    def test_errors_with_curation_path_when_missing(
        self, runner, tmp_path: Path
    ):
        from feather_etl.cli import app

        client_db = tmp_path / "client.duckdb"
        shutil.copy2(FIXTURES_DIR / "client.duckdb", client_db)
        config = {
            "sources": [
                {"type": "duckdb", "name": "icube", "path": str(client_db)}
            ],
            "destination": {"path": str(tmp_path / "feather_data.duckdb")},
        }
        cp = tmp_path / "feather.yaml"
        cp.write_text(yaml.dump(config))
        # Intentionally no write_curation() call — curation.json does not exist.

        result = runner.invoke(app, ["cache", "--config", str(cp)])
        assert result.exit_code == 2
        assert "curation.json" in result.output
        assert "feather discover" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/commands/test_cache.py::TestCacheMissingCuration -v`
Expected: FAIL — either a generic "Config file not found" message (exit 1) or a stack trace. The test wants curation-specific wording and exit 2.

- [ ] **Step 3: Add the pre-check in `commands/cache.py`**

Open `src/feather_etl/commands/cache.py`. Add this block at the **top** of the `cache()` function body, before any other work:

```python
    curation_path = Path(config).resolve().parent / "discovery" / "curation.json"
    if not curation_path.exists():
        typer.echo(
            f"discovery/curation.json not found in {curation_path.parent.parent}. "
            f"Run 'feather discover' and curate tables first.",
            err=True,
        )
        raise typer.Exit(code=2)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/commands/test_cache.py::TestCacheMissingCuration -v`
Expected: PASS.

- [ ] **Step 5: Run the full cache CLI suite to confirm no regression**

Run: `uv run pytest tests/commands/test_cache.py -v`
Expected: all previous tests still pass — the pre-check only fires when `curation.json` is missing, and our other tests all call `write_curation()`.

- [ ] **Step 6: Commit**

```bash
git add src/feather_etl/commands/cache.py tests/commands/test_cache.py
git commit -m "feat(cache): pre-check curation.json with clear message + exit 2 (#15)

_load_and_validate emits a generic 'Config file not found' message
for missing curation.json (pre-existing shared-code behavior,
out of scope to fix here). The cache command pre-checks for
curation.json existence and emits a curation-specific message with
exit 2 before invoking the shared loader."
```

### Task 4d: `--table` and `--source` selectors

- [ ] **Step 1: Write failing test for `--table` filter**

Append to `tests/commands/test_cache.py`:

```python
class TestCacheSelectors:
    def _two_table_project(self, tmp_path: Path) -> Path:
        client_db = tmp_path / "client.duckdb"
        shutil.copy2(FIXTURES_DIR / "client.duckdb", client_db)
        config = {
            "sources": [
                {"type": "duckdb", "name": "icube", "path": str(client_db)}
            ],
            "destination": {"path": str(tmp_path / "feather_data.duckdb")},
        }
        cp = tmp_path / "feather.yaml"
        cp.write_text(yaml.dump(config))
        write_curation(
            tmp_path,
            [
                make_curation_entry("icube", "icube.InventoryGroup", "inv"),
                make_curation_entry("icube", "icube.CUSTOMERMASTER", "cust"),
            ],
        )
        return cp

    def test_table_filter_restricts_extraction(self, runner, tmp_path: Path):
        from feather_etl.cli import app

        cp = self._two_table_project(tmp_path)
        result = runner.invoke(
            app, ["cache", "--config", str(cp), "--table", "icube_inv"]
        )
        assert result.exit_code == 0

        data_db = tmp_path / "feather_data.duckdb"
        con = duckdb.connect(str(data_db), read_only=True)
        tables = {
            r[0]
            for r in con.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'bronze'"
            ).fetchall()
        }
        con.close()
        assert "icube_inv" in tables
        assert "icube_cust" not in tables
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/commands/test_cache.py::TestCacheSelectors::test_table_filter_restricts_extraction -v`
Expected: FAIL — `--table` flag isn't being applied; both tables get cached.

- [ ] **Step 3: Implement selector logic**

In `src/feather_etl/commands/cache.py`, replace the line `tables = cfg.tables` with this selector block:

```python
    # Parse selectors
    requested_tables = (
        [t.strip() for t in table.split(",") if t.strip()] if table else None
    )
    requested_sources = (
        [s.strip() for s in source.split(",") if s.strip()] if source else None
    )

    all_tables = cfg.tables
    all_table_names = [t.name for t in all_tables]
    all_source_dbs = sorted({t.database for t in all_tables if t.database})

    if requested_tables:
        unknown = [t for t in requested_tables if t not in all_table_names]
        if unknown:
            typer.echo(
                f"Unknown --table value(s): {', '.join(unknown)}. "
                f"Valid: {', '.join(all_table_names)}",
                err=True,
            )
            raise typer.Exit(code=2)

    if requested_sources:
        unknown = [s for s in requested_sources if s not in all_source_dbs]
        if unknown:
            typer.echo(
                f"Unknown --source value(s): {', '.join(unknown)}. "
                f"Valid: {', '.join(all_source_dbs)}",
                err=True,
            )
            raise typer.Exit(code=2)

    tables = all_tables
    if requested_tables:
        tables = [t for t in tables if t.name in requested_tables]
    if requested_sources:
        tables = [t for t in tables if t.database in requested_sources]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/commands/test_cache.py::TestCacheSelectors::test_table_filter_restricts_extraction -v`
Expected: PASS.

- [ ] **Step 5: Write failing test for `--source` filter**

Append to `TestCacheSelectors`:

```python
    def test_source_filter_restricts_extraction(self, runner, tmp_path: Path):
        from feather_etl.cli import app

        cp = self._two_table_project(tmp_path)
        # Only one source_db here (icube); this also confirms the filter accepts it.
        result = runner.invoke(
            app, ["cache", "--config", str(cp), "--source", "icube"]
        )
        assert result.exit_code == 0

        data_db = tmp_path / "feather_data.duckdb"
        con = duckdb.connect(str(data_db), read_only=True)
        tables = {
            r[0]
            for r in con.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'bronze'"
            ).fetchall()
        }
        con.close()
        assert "icube_inv" in tables
        assert "icube_cust" in tables
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/commands/test_cache.py::TestCacheSelectors::test_source_filter_restricts_extraction -v`
Expected: PASS.

- [ ] **Step 7: Write failing test for intersect (both given)**

Append to `TestCacheSelectors`:

```python
    def test_table_and_source_intersect(self, runner, tmp_path: Path):
        from feather_etl.cli import app

        cp = self._two_table_project(tmp_path)
        result = runner.invoke(
            app,
            [
                "cache",
                "--config",
                str(cp),
                "--table",
                "icube_inv",
                "--source",
                "icube",
            ],
        )
        assert result.exit_code == 0

        data_db = tmp_path / "feather_data.duckdb"
        con = duckdb.connect(str(data_db), read_only=True)
        tables = {
            r[0]
            for r in con.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'bronze'"
            ).fetchall()
        }
        con.close()
        assert tables == {"icube_inv"}
```

- [ ] **Step 8: Run test to verify it passes**

Run: `uv run pytest tests/commands/test_cache.py::TestCacheSelectors::test_table_and_source_intersect -v`
Expected: PASS.

- [ ] **Step 9: Write failing test for unknown-table error message**

Append to `TestCacheSelectors`:

```python
    def test_unknown_table_errors_with_valid_list(self, runner, tmp_path: Path):
        from feather_etl.cli import app

        cp = self._two_table_project(tmp_path)
        result = runner.invoke(
            app, ["cache", "--config", str(cp), "--table", "no_such_table"]
        )
        assert result.exit_code == 2
        assert "no_such_table" in result.output
        assert "icube_inv" in result.output
        assert "icube_cust" in result.output

    def test_unknown_source_errors_with_valid_list(self, runner, tmp_path: Path):
        from feather_etl.cli import app

        cp = self._two_table_project(tmp_path)
        result = runner.invoke(
            app, ["cache", "--config", str(cp), "--source", "nope"]
        )
        assert result.exit_code == 2
        assert "nope" in result.output
        assert "icube" in result.output
```

- [ ] **Step 10: Run tests to verify they pass**

Run: `uv run pytest tests/commands/test_cache.py::TestCacheSelectors -v`
Expected: all PASS.

- [ ] **Step 11: Commit**

```bash
git add src/feather_etl/commands/cache.py tests/commands/test_cache.py
git commit -m "feat(cache): --table and --source selectors with intersect (#15)

--table matches on TableConfig.name (sanitized bronze name).
--source matches on TableConfig.database (source_db).
Both given → intersect. Unknown values error with valid options."
```

### Task 4e: `--refresh` flag propagates to `run_cache`

- [ ] **Step 1: Write failing test**

Append to `tests/commands/test_cache.py`:

```python
class TestCacheRefresh:
    def test_refresh_forces_re_extraction(self, runner, tmp_path: Path):
        from feather_etl.cli import app

        config_path = _project(tmp_path)
        # Cold run
        r1 = runner.invoke(app, ["cache", "--config", str(config_path)])
        assert r1.exit_code == 0
        assert "1 extracted" in r1.output

        # Warm run — should be cached
        r2 = runner.invoke(app, ["cache", "--config", str(config_path)])
        assert r2.exit_code == 0
        assert "1 cached" in r2.output

        # Refresh — should re-extract
        r3 = runner.invoke(
            app, ["cache", "--config", str(config_path), "--refresh"]
        )
        assert r3.exit_code == 0
        assert "1 extracted" in r3.output
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run pytest tests/commands/test_cache.py::TestCacheRefresh -v`
Expected: PASS — `--refresh` is already wired through from Task 4a.

- [ ] **Step 3: Commit**

```bash
git add tests/commands/test_cache.py
git commit -m "test(cache): verify --refresh flag forces re-extraction (#15)"
```

### Task 4f: Grouped output format with expanded failures

- [ ] **Step 1: Write failing test**

Append to `tests/commands/test_cache.py`:

```python
class TestCacheOutputFormat:
    def test_grouped_output_with_failure_expansion(
        self, runner, tmp_path: Path
    ):
        from feather_etl.cli import app

        client_db = tmp_path / "client.duckdb"
        shutil.copy2(FIXTURES_DIR / "client.duckdb", client_db)
        config = {
            "sources": [
                {"type": "duckdb", "name": "icube", "path": str(client_db)}
            ],
            "destination": {"path": str(tmp_path / "feather_data.duckdb")},
        }
        cp = tmp_path / "feather.yaml"
        cp.write_text(yaml.dump(config))
        write_curation(
            tmp_path,
            [
                make_curation_entry("icube", "icube.InventoryGroup", "good"),
                make_curation_entry("icube", "icube.NOPE", "bad"),
            ],
        )

        result = runner.invoke(app, ["cache", "--config", str(cp)])
        # Non-zero exit because of the failed table
        assert result.exit_code == 1
        out = result.output

        assert "Mode: dev (cache)" in out
        # Grouped: a line starts with "icube" (source_db), has counts
        assert "icube" in out
        # Summary: totals across groups
        assert "2 tables:" in out
        # Failure details expanded
        assert "✗ icube_bad" in out
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run pytest tests/commands/test_cache.py::TestCacheOutputFormat -v`
Expected: PASS — the grouped output logic was implemented in Task 4a.

If the test fails because the `✗` character or "Mode: dev (cache)" wording differs, reconcile the test's assertion with the actual implementation output. Either loosen the test (use case-insensitive `in` checks) or adjust the format string in `commands/cache.py` to match. Prefer keeping the format string stable.

- [ ] **Step 3: Commit**

```bash
git add tests/commands/test_cache.py
git commit -m "test(cache): verify grouped output format (#15)"
```

### Task 4g: End-to-end sanity — full command flow

- [ ] **Step 1: Run the entire cache test suite**

Run: `uv run pytest tests/test_cache.py tests/commands/test_cache.py -v`
Expected: all PASS.

- [ ] **Step 2: Run the full project test suite**

Run: `uv run pytest -q`
Expected: all PASS. New test count = previous total + number of new tests.

Record the new test count; you'll use it in Task 6.

---

## Task 5: Final `cli.py` wiring verification

The registration was added during Task 4a. This task only verifies that the command renders correctly and appears in `--help`.

- [ ] **Step 1: Write failing test**

Open `tests/test_cli_structure.py`. Add a new test (or add to the existing class that covers command registration):

```python
class TestCacheCommandRegistered:
    def test_feather_help_lists_cache(self):
        from typer.testing import CliRunner
        from feather_etl.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "cache" in result.output

    def test_feather_cache_help_renders(self):
        from typer.testing import CliRunner
        from feather_etl.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["cache", "--help"])
        assert result.exit_code == 0
        assert "--table" in result.output
        assert "--source" in result.output
        assert "--refresh" in result.output
        assert "--config" in result.output
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli_structure.py::TestCacheCommandRegistered -v`
Expected: PASS for both.

- [ ] **Step 3: Commit**

```bash
git add tests/test_cli_structure.py
git commit -m "test(cli): verify feather cache is registered and --help renders (#15)"
```

---

## Task 6: Documentation updates

### Task 6a: `README.md` — add "Dev cache" subsection

- [ ] **Step 1: Locate the CLI reference section of README.md**

Run: `grep -n "feather run\|## CLI\|### " README.md | head -30`

Identify where `feather run` is documented — the "Dev cache" subsection should sit alongside it.

- [ ] **Step 2: Add the "Dev cache" subsection**

Immediately after the `feather run` documentation block, add:

````markdown
### Dev cache — `feather cache`

Pull curated source tables into local `bronze.*` for offline development. Skips unchanged sources on re-run. Isolated state — never touches `feather run`'s watermarks.

```bash
feather cache                                  # all curated tables, skip unchanged
feather cache --table sales,customer           # comma-separated, by bronze name
feather cache --source afans,nimbalyst         # comma-separated, by source_db
feather cache --table sales --source afans     # intersect
feather cache --refresh                        # force re-pull of all tables
feather cache --refresh --table sales          # force re-pull of specific tables
```

`feather cache` requires `discovery/curation.json`. Run `feather discover` first to generate it.

`feather cache` never runs silver/gold transforms. After a fresh cache, run `feather run` or `feather setup` to create silver views and materialize gold tables.

`feather cache` is dev-only. It will refuse to run when the effective mode is `prod` (via `mode: prod` in `feather.yaml` or `FEATHER_MODE=prod`).
````

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(readme): add feather cache to CLI reference (#15)"
```

### Task 6b: `docs/prd.md` §499 — point to `feather cache`

- [ ] **Step 1: Locate §499**

Run: `grep -n "Development cache\|§499\|## 499" docs/prd.md | head -5`

- [ ] **Step 2: Add the pointer sentence**

Immediately after the existing §499 paragraph that begins "During active development, the operator extracts all columns...", add a new sentence as the final line of that paragraph (or as a new paragraph if the section is multi-paragraph):

> The canonical command for this workflow is `feather cache` — see the README "Dev cache" section.

- [ ] **Step 3: Commit**

```bash
git add docs/prd.md
git commit -m "docs(prd): point §499 at feather cache as canonical command (#15)"
```

### Task 6c: `CLAUDE.md` — bump pytest count

- [ ] **Step 1: Run the final test count**

Run: `uv run pytest -q 2>&1 | tail -5`

Note the pass count (e.g., `627 passed`).

- [ ] **Step 2: Update `CLAUDE.md`**

Open `CLAUDE.md`. Find the line:

```
uv run pytest -q               # currently: 597 tests
```

Replace `597` with the new total.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude): bump pytest count after feather cache tests (#15)"
```

---

## Task 7: File follow-up GH issue (post-merge, non-code)

**Files:** No code. This task is for after the PR lands.

- [ ] **Step 1: Open the `feather-etl` repo on GitHub and create a new issue**

Title: `Thin-CLI pattern sweep: extract core from all command modules`

Body:

````markdown
## Problem

The pattern `commands/<name>.py` (Typer CLI) → `<name>.py` (top-level core module) is already used for `commands/run.py` ↔ `pipeline.py`. It gives us:

- Testable core logic without Typer runtime.
- Clean separation between "what the command does" and "how the CLI exposes it."
- Reusable cores (e.g., an eventual MCP/HTTP layer can call the core without reimplementing).

Most command modules don't yet follow this pattern. They interleave orchestration, `typer.echo`, and `typer.Exit` inline. Examples:

- `commands/discover.py` — 274 lines mixing rename detection, prune logic, state writes, per-source loop, and viewer serving.
- `commands/setup.py`, `commands/validate.py`, `commands/status.py`, etc.

## Proposal

Refactor each command module into two layers:

| Layer | Responsibility |
|---|---|
| `commands/<name>.py` | Flag parsing, prompts, output formatting, exit-code translation. Stays Typer-dependent. |
| `<name>.py` (top-level) | Orchestration, data flow, IO. No Typer imports. Returns values / raises domain exceptions. |

Scope:

- [ ] `commands/discover.py` → `src/feather_etl/discover.py`
- [ ] `commands/run.py` — already follows the pattern; verify no further extraction needed.
- [ ] `commands/setup.py`
- [ ] `commands/validate.py`
- [ ] `commands/status.py`
- [ ] `commands/history.py`
- [ ] `commands/init.py`
- [ ] `commands/view.py`

Constraints:

- Each refactor is behavior-preserving — existing tests must stay green.
- Do not expand scope (no new features during the refactor).
- Each command's refactor can be its own commit.

## Context

Spun out of #15 (`feather cache`) which established the target pattern.
````

- [ ] **Step 2: Cross-link from the cache PR**

When creating the cache PR, reference the new issue in the PR body:

> Follow-up tracked in #NN (thin-CLI pattern sweep).

---

## Final verification

- [ ] **Step 1: Run the full test suite one last time**

Run: `uv run pytest -q`
Expected: all tests pass.

- [ ] **Step 2: Try the command end-to-end**

Run the done-signal scenario from the spec:

```bash
cd /tmp && mkdir -p feather-cache-smoke && cd feather-cache-smoke
# Copy a test fixture
cp -r /path/to/feather-etl/test_duckdb_project/* .

uv run feather cache                   # cold run
uv run feather cache                   # warm run: all cached
uv run feather cache --refresh         # force re-pull

# Isolation proof
duckdb feather_state.duckdb "SELECT COUNT(*) FROM _watermarks"            # 0
duckdb feather_state.duckdb "SELECT COUNT(*) FROM _cache_watermarks"      # N

# Prod-mode guard
FEATHER_MODE=prod uv run feather cache  # exits with code 2
```

Verify each step matches the expected output from § 7 of the spec.

- [ ] **Step 3: Review the full git log for this feature**

Run: `git log --oneline main..HEAD`

Confirm the commit chain is clean:
- Each task's commits are atomic and appropriately scoped.
- Commit messages reference `#15`.
- No "WIP" or "fix typo" commits — squash before merge if there are.

- [ ] **Step 4: Open PR**

Title: `feat: feather cache — dev-ergonomic local bronze cache (#15)`

PR body: point at the spec, summarize the 6 implementation tasks, list the CLI surface, and include the "done signal" output as proof of working software.

Reference the follow-up issue created in Task 7.

---

## Notes for the implementing engineer

- **TDD discipline:** Every code step is preceded by a failing test. If a step says "write the minimal code to make the test pass," resist the urge to add extra features. YAGNI.
- **No `print()` calls in core modules.** Use `logger.info`/`logger.error` in `cache.py`. User-facing output belongs in `commands/cache.py` via `typer.echo`.
- **Isolation invariant:** If at any point you find yourself thinking "just this once, cache will write to `_watermarks`…" — stop. That's the invariant Task 2 is explicitly designed to make impossible. If you need prod-state writes, you've misread the spec.
- **Fixture reuse:** The `_project()` and `_two_table_project()` helpers in `tests/commands/test_cache.py` follow the same pattern as `tests/commands/conftest.py::cli_env`. If you find yourself rewriting these, consider promoting to `conftest.py` — but only after the third duplication.
- **`tests/fixtures/client.duckdb`** already exists (~14K rows across 6 tables in `icube.*`). No new fixtures needed.
- **Don't touch `pipeline.py`, `run_all`, or `run_table`.** Cache is a separate module. If a test seems to require changing `run_table`, you've gone down the wrong path — back out and reread § 5 of the spec.
- **Commit cadence:** Each atomic test → implementation → pass cycle is a commit. Do not accumulate multiple commits of work before testing.

---

## Spec coverage check (engineer: do not need to do this — verifier only)

| Spec section | Task(s) |
|---|---|
| § 2 In — `feather cache` command | Tasks 3, 4, 5 |
| § 2 In — Per-table change detection, cache watermarks | Tasks 1, 2, 3 |
| § 2 In — `--table`, `--source`, `--refresh` | Task 4d, 4e |
| § 2 In — Hard error on prod mode | Task 4b |
| § 2 In — Grouped output | Task 4a, 4f |
| § 2 In — Docs | Task 6 |
| § 4.1 CLI surface | Task 4 |
| § 4.2 Workflow resolution | Task 4 |
| § 4.3 Human output | Task 4a, 4f |
| § 4.4 State shape (`_cache_watermarks`) | Task 1 |
| § 4.5 Interaction with `feather run` | Task 3 (state isolation test) |
| § 5 New files | Tasks 3, 4 |
| § 5 Files that change | Tasks 1, 2, 4a, 6 |
| § 5 StateManager API | Task 2 |
| § 5 `run_cache` signature | Task 3 |
| § 7 Done signal | Final verification |
| § 8 Follow-up issue | Task 7 |
