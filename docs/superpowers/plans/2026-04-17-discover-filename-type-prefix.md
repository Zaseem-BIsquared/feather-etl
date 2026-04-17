# Discover Filename Type Prefix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `feather discover` write JSON filenames that include the source type when the user explicitly named the source in `feather.yaml`, so multi-source projects can be navigated at a glance.

**Architecture:** Add a runtime flag `_explicit_name` on every `Source` instance, set by each `from_yaml` classmethod based on whether `entry.get("name")` was present. The single filename helper `schema_output_path(cfg)` in `config.py` prepends `<type>_` iff the flag is `True`. Multi-database expansion propagates the parent's flag to its children. The helper becomes the only place that constructs discover filenames; `commands/discover.py:_write_schema` and `discover_state.py`'s rename path both call it.

**Tech Stack:** Python 3.10+, `uv`, pytest, DuckDB fixtures, Typer CLI. No new dependencies.

**Spec:** [docs/superpowers/specs/2026-04-17-discover-filename-type-prefix-design.md](../specs/2026-04-17-discover-filename-type-prefix-design.md)

---

## File Structure

| File | Role | Change |
|---|---|---|
| `src/feather_etl/sources/csv.py` | CSV source | Set `_explicit_name` in `from_yaml` |
| `src/feather_etl/sources/duckdb_file.py` | DuckDB file source | Set `_explicit_name` in `from_yaml` |
| `src/feather_etl/sources/sqlite.py` | SQLite source | Set `_explicit_name` in `from_yaml` |
| `src/feather_etl/sources/excel.py` | Excel source | Set `_explicit_name` in `from_yaml` |
| `src/feather_etl/sources/json_source.py` | JSON source | Set `_explicit_name` in `from_yaml` |
| `src/feather_etl/sources/postgres.py` | Postgres source | Set `_explicit_name` in `from_yaml` |
| `src/feather_etl/sources/sqlserver.py` | SQL Server source | Set `_explicit_name` in `from_yaml` |
| `src/feather_etl/config.py` | Config loader + `schema_output_path` | Rewrite `schema_output_path` body to use the flag |
| `src/feather_etl/commands/discover.py` | `discover` command | Propagate flag in `_expand_db_sources`; replace inline filename f-string with `schema_output_path`; pass sources into `apply_renames` |
| `src/feather_etl/discover_state.py` | State + rename helpers | `apply_renames` takes `sources` and routes rename filename through `schema_output_path` |
| `tests/test_discover_io.py` | Existing filename unit tests | Update 5 `schema_output_path` assertions; add new cases |
| `tests/test_discover_expansion.py` | New | `_expand_db_sources` flag propagation tests |
| `tests/test_discover_state_rename.py` | Existing rename tests (or equivalent) | Update rename assertions to new filenames |

No files are deleted. No files are moved.

---

## Task 0: Verify baseline is green

Confirm the repo is clean before touching anything. If anything is red, stop and report.

- [ ] **Step 1: Run the Python suite**

Run: `uv run pytest -q`
Expected: all pass (per CLAUDE.md, currently 460 tests).

- [ ] **Step 2: Run the CLI integration suite**

Run: `bash scripts/hands_on_test.sh`
Expected: all pass (currently 61 checks).

- [ ] **Step 3: Confirm clean working tree**

Run: `git status`
Expected: `nothing to commit, working tree clean`.

---

## Task 1: Introduce `_explicit_name` flag on all Source classes

Each `Source.from_yaml` sets `self._explicit_name = bool(entry.get("name"))` after constructing the instance. The loader's single-source name backfill at `config.py:337-338` does not touch the flag (it only sets `.name`).

**Files:**
- Create: `tests/test_explicit_name_flag.py`
- Modify: `src/feather_etl/sources/csv.py:45`
- Modify: `src/feather_etl/sources/duckdb_file.py:33`
- Modify: `src/feather_etl/sources/sqlite.py:33`
- Modify: `src/feather_etl/sources/excel.py:34`
- Modify: `src/feather_etl/sources/json_source.py:34`
- Modify: `src/feather_etl/sources/postgres.py` (end of `from_yaml`)
- Modify: `src/feather_etl/sources/sqlserver.py` (end of `from_yaml`)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_explicit_name_flag.py`:

```python
"""Verify `_explicit_name` is set correctly on Source instances loaded from yaml."""

from pathlib import Path

import pytest
import yaml

from feather_etl.config import FeatherConfig


def _write_yaml(tmp_path: Path, body: dict) -> Path:
    cfg_path = tmp_path / "feather.yaml"
    cfg_path.write_text(yaml.safe_dump(body))
    return cfg_path


@pytest.fixture
def csv_dir(tmp_path: Path) -> Path:
    d = tmp_path / "data"
    d.mkdir()
    (d / "orders.csv").write_text("id,name\n1,a\n")
    return d


def test_explicit_name_flag_true_when_yaml_has_name(tmp_path, csv_dir):
    cfg_path = _write_yaml(
        tmp_path,
        {
            "sources": [{"name": "orders", "type": "csv", "path": str(csv_dir)}],
            "destination": {"path": str(tmp_path / "out.duckdb")},
            "tables": [],
        },
    )
    cfg = FeatherConfig.load_yaml(cfg_path)
    assert cfg.sources[0]._explicit_name is True


def test_explicit_name_flag_false_when_yaml_omits_name(tmp_path, csv_dir):
    cfg_path = _write_yaml(
        tmp_path,
        {
            "sources": [{"type": "csv", "path": str(csv_dir)}],
            "destination": {"path": str(tmp_path / "out.duckdb")},
            "tables": [],
        },
    )
    cfg = FeatherConfig.load_yaml(cfg_path)
    src = cfg.sources[0]
    # loader backfills .name for single-source configs
    assert src.name != ""
    assert src._explicit_name is False


def test_explicit_name_flag_for_sqlite(tmp_path):
    sqlite_file = tmp_path / "db.sqlite"
    sqlite_file.touch()
    cfg_path = _write_yaml(
        tmp_path,
        {
            "sources": [{"name": "mydb", "type": "sqlite", "path": str(sqlite_file)}],
            "destination": {"path": str(tmp_path / "out.duckdb")},
            "tables": [],
        },
    )
    cfg = FeatherConfig.load_yaml(cfg_path)
    assert cfg.sources[0]._explicit_name is True


def test_explicit_name_flag_for_postgres(tmp_path):
    cfg_path = _write_yaml(
        tmp_path,
        {
            "sources": [
                {
                    "name": "prod",
                    "type": "postgres",
                    "host": "localhost",
                    "database": "sales",
                }
            ],
            "destination": {"path": str(tmp_path / "out.duckdb")},
            "tables": [],
        },
    )
    cfg = FeatherConfig.load_yaml(cfg_path)
    assert cfg.sources[0]._explicit_name is True


def test_explicit_name_flag_for_sqlserver_auto(tmp_path):
    cfg_path = _write_yaml(
        tmp_path,
        {
            "sources": [
                {
                    "type": "sqlserver",
                    "host": "db.internal",
                    "database": "X",
                }
            ],
            "destination": {"path": str(tmp_path / "out.duckdb")},
            "tables": [],
        },
    )
    cfg = FeatherConfig.load_yaml(cfg_path)
    src = cfg.sources[0]
    assert src._explicit_name is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_explicit_name_flag.py -v`
Expected: 5 failures, all with `AttributeError: ... object has no attribute '_explicit_name'`.

- [ ] **Step 3: Add the flag to `CsvSource.from_yaml`**

Edit [src/feather_etl/sources/csv.py](../../src/feather_etl/sources/csv.py) lines 40-45:

```python
    @classmethod
    def from_yaml(cls, entry: dict, config_dir: Path) -> "CsvSource":
        _reject_db_fields(entry, cls.type)
        path = _resolve_file_path(entry, config_dir)
        if not path.is_dir():
            raise ValueError(f"CSV source path must be a directory: {path}")
        src = cls(path=path, name=entry.get("name", ""))
        src._explicit_name = bool(entry.get("name"))
        return src
```

- [ ] **Step 4: Add the flag to `DuckDBFileSource.from_yaml`**

Edit [src/feather_etl/sources/duckdb_file.py](../../src/feather_etl/sources/duckdb_file.py) around line 33:

```python
    @classmethod
    def from_yaml(cls, entry: dict, config_dir: Path) -> "DuckDBFileSource":
        _reject_db_fields(entry, cls.type)
        path = _resolve_file_path(entry, config_dir)
        src = cls(path=path, name=entry.get("name", ""))
        src._explicit_name = bool(entry.get("name"))
        return src
```

- [ ] **Step 5: Add the flag to `SqliteSource.from_yaml`**

Edit [src/feather_etl/sources/sqlite.py](../../src/feather_etl/sources/sqlite.py) around line 33:

```python
    @classmethod
    def from_yaml(cls, entry: dict, config_dir: Path) -> "SqliteSource":
        _reject_db_fields(entry, cls.type)
        path = _resolve_file_path(entry, config_dir)
        src = cls(path=path, name=entry.get("name", ""))
        src._explicit_name = bool(entry.get("name"))
        return src
```

- [ ] **Step 6: Add the flag to `ExcelSource.from_yaml`**

Edit [src/feather_etl/sources/excel.py](../../src/feather_etl/sources/excel.py) around line 34:

```python
    @classmethod
    def from_yaml(cls, entry: dict, config_dir: Path) -> "ExcelSource":
        _reject_db_fields(entry, cls.type)
        path = _resolve_file_path(entry, config_dir)
        if not path.is_dir():
            raise ValueError(f"Excel source path must be a directory: {path}")
        src = cls(path=path, name=entry.get("name", ""))
        src._explicit_name = bool(entry.get("name"))
        return src
```

- [ ] **Step 7: Add the flag to `JsonSource.from_yaml`**

Edit [src/feather_etl/sources/json_source.py](../../src/feather_etl/sources/json_source.py) around line 34:

```python
    @classmethod
    def from_yaml(cls, entry: dict, config_dir: Path) -> "JsonSource":
        _reject_db_fields(entry, cls.type)
        path = _resolve_file_path(entry, config_dir)
        if not path.is_dir():
            raise ValueError(f"JSON source path must be a directory: {path}")
        src = cls(path=path, name=entry.get("name", ""))
        src._explicit_name = bool(entry.get("name"))
        return src
```

- [ ] **Step 8: Add the flag to `PostgresSource.from_yaml`**

Open [src/feather_etl/sources/postgres.py](../../src/feather_etl/sources/postgres.py) and find the end of `from_yaml` (where the final `return cls(...)` or `return src` happens). Replace the final return so the flag is set on the returned instance:

```python
        # (existing logic that builds the connection_string and decides database/databases) ...
        src = cls(
            connection_string=conn_str,
            name=name,
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            databases=databases,
        )
        src._explicit_name = bool(entry.get("name"))
        return src
```

If the existing code has a single `return cls(...)` expression, convert it to `src = cls(...)`, set the flag, then `return src`. Do not change any other logic.

- [ ] **Step 9: Add the flag to `SqlServerSource.from_yaml`**

Same pattern as Step 8, applied to [src/feather_etl/sources/sqlserver.py](../../src/feather_etl/sources/sqlserver.py):

```python
        src = cls(
            connection_string=conn_str,
            name=name,
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            databases=databases,
        )
        src._explicit_name = bool(entry.get("name"))
        return src
```

- [ ] **Step 10: Run the new tests to verify they pass**

Run: `uv run pytest tests/test_explicit_name_flag.py -v`
Expected: all 5 pass.

- [ ] **Step 11: Run the full Python suite to confirm no regressions**

Run: `uv run pytest -q`
Expected: all pass (460 original + 5 new = 465).

- [ ] **Step 12: Commit**

```bash
git add src/feather_etl/sources/csv.py src/feather_etl/sources/duckdb_file.py \
        src/feather_etl/sources/sqlite.py src/feather_etl/sources/excel.py \
        src/feather_etl/sources/json_source.py src/feather_etl/sources/postgres.py \
        src/feather_etl/sources/sqlserver.py tests/test_explicit_name_flag.py
git commit -m "feat(sources): record _explicit_name flag from yaml (#21)"
```

---

## Task 2: Propagate `_explicit_name` through `_expand_db_sources`

When `_expand_db_sources` builds child sources for `databases: [...]` expansion, it currently always passes `"name"` in the synthesized entry dict. Under Task 1's rule that would force `_explicit_name = True` on every child. Instead, children inherit from the parent.

**Files:**
- Create: `tests/test_discover_expansion.py`
- Modify: `src/feather_etl/commands/discover.py:85-98`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_discover_expansion.py`:

```python
"""Verify `_expand_db_sources` copies parent's `_explicit_name` onto children."""

from __future__ import annotations

from pathlib import Path

import pytest

from feather_etl.commands.discover import _expand_db_sources
from feather_etl.sources.postgres import PostgresSource


def _make_postgres(name: str, *, explicit: bool, databases=None) -> PostgresSource:
    src = PostgresSource(
        connection_string="",
        name=name,
        host="localhost",
        port=5432,
        user="u",
        password="p",
        database=None,
        databases=databases,
    )
    src._explicit_name = explicit
    return src


def test_children_inherit_explicit_true_from_parent():
    parent = _make_postgres("prod", explicit=True, databases=["sales", "hr"])
    children = _expand_db_sources([parent])
    assert len(children) == 2
    for child in children:
        assert child._explicit_name is True
        assert child.name.startswith("prod__")


def test_children_inherit_explicit_false_from_parent():
    parent = _make_postgres("postgres-localhost", explicit=False, databases=["sales", "hr"])
    children = _expand_db_sources([parent])
    assert len(children) == 2
    for child in children:
        assert child._explicit_name is False
        assert child.name.startswith("postgres-localhost__")


def test_parent_without_expansion_is_unchanged():
    src = PostgresSource(
        connection_string="",
        name="prod",
        host="localhost",
        port=5432,
        user="u",
        password="p",
        database="sales",  # explicit database -> no expansion
    )
    src._explicit_name = True
    expanded = _expand_db_sources([src])
    assert expanded == [src]
    assert expanded[0]._explicit_name is True
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_discover_expansion.py -v`
Expected: `test_children_inherit_explicit_false_from_parent` fails because children currently get `_explicit_name = True` from `from_yaml` (since the synthetic entry dict has `"name"`). The other two may already pass — that's fine.

- [ ] **Step 3: Add flag propagation in `_expand_db_sources`**

Edit [src/feather_etl/commands/discover.py](../../src/feather_etl/commands/discover.py) lines 85-98. Add one line immediately after `child = type(src).from_yaml(...)`:

```python
        for db in databases:
            child = type(src).from_yaml(
                {
                    "name": f"{src.name}__{db}",
                    "type": src.type,
                    "host": src.host,
                    "port": src.port,
                    "user": src.user,
                    "password": src.password,
                    "database": db,
                },
                Path("."),
            )
            child._explicit_name = src._explicit_name
            expanded.append(child)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_discover_expansion.py -v`
Expected: all 3 pass.

- [ ] **Step 5: Run the full Python suite**

Run: `uv run pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/feather_etl/commands/discover.py tests/test_discover_expansion.py
git commit -m "feat(discover): propagate _explicit_name to expanded db children (#21)"
```

---

## Task 3: Rewrite `schema_output_path` to use the flag

Replace the body so the helper prepends `<type>_` when `_explicit_name` is truthy, and does NOT append `_<database>` (db name is already embedded in child `name` via `__<db>` when expansion happens).

**Files:**
- Modify: `src/feather_etl/config.py:53-64`
- Modify: `tests/test_discover_io.py:127-179` (the 5 existing assertions)

- [ ] **Step 1: Write new unit tests**

Append to `tests/test_discover_io.py` (at the bottom of the existing `TestSchemaOutputPath` test class, or a new class next to it):

```python
class TestSchemaOutputPathTypePrefix:
    """Tests for the type-prefix rule (#21)."""

    def test_explicit_name_csv_gets_type_prefix(self, tmp_path):
        from pathlib import Path

        from feather_etl.config import schema_output_path
        from feather_etl.sources.csv import CsvSource

        d = tmp_path / "data"
        d.mkdir()
        src = CsvSource(path=d, name="orders")
        src._explicit_name = True
        assert schema_output_path(src) == Path("schema_csv_orders.json")

    def test_explicit_name_sqlite_gets_type_prefix(self, tmp_path):
        from pathlib import Path

        from feather_etl.config import schema_output_path
        from feather_etl.sources.sqlite import SqliteSource

        sqlite_file = tmp_path / "source.sqlite"
        sqlite_file.touch()
        src = SqliteSource(path=sqlite_file, name="mydb")
        src._explicit_name = True
        assert schema_output_path(src) == Path("schema_sqlite_mydb.json")

    def test_explicit_name_postgres_no_database_in_filename(self):
        from pathlib import Path

        from feather_etl.config import schema_output_path
        from feather_etl.sources.postgres import PostgresSource

        src = PostgresSource(
            connection_string="x",
            name="prod",
            host="localhost",
            database="sales",
        )
        src._explicit_name = True
        # database is NOT appended; db embedding only happens via expansion (__<db>)
        assert schema_output_path(src) == Path("schema_postgres_prod.json")

    def test_explicit_name_sqlserver_gets_type_prefix(self):
        from pathlib import Path

        from feather_etl.config import schema_output_path
        from feather_etl.sources.sqlserver import SqlServerSource

        src = SqlServerSource(
            connection_string="x",
            name="prod-erp",
            host="db",
            database="ZAKYA",
        )
        src._explicit_name = True
        assert schema_output_path(src) == Path("schema_sqlserver_prod-erp.json")

    def test_auto_name_has_no_type_prefix(self):
        from pathlib import Path

        from feather_etl.config import schema_output_path
        from feather_etl.sources.sqlserver import SqlServerSource

        src = SqlServerSource(
            connection_string="x", host="db.internal", database="ZAKYA"
        )
        src.name = "sqlserver-db.internal"  # simulate loader backfill
        src._explicit_name = False
        assert schema_output_path(src) == Path("schema_sqlserver-db.internal.json")

    def test_expanded_child_explicit_parent(self):
        from pathlib import Path

        from feather_etl.config import schema_output_path
        from feather_etl.sources.postgres import PostgresSource

        # simulate a child produced by _expand_db_sources with explicit parent
        child = PostgresSource(
            connection_string="x",
            name="prod__sales",
            host="localhost",
            database="sales",
        )
        child._explicit_name = True
        assert schema_output_path(child) == Path("schema_postgres_prod__sales.json")

    def test_expanded_child_auto_parent(self):
        from pathlib import Path

        from feather_etl.config import schema_output_path
        from feather_etl.sources.postgres import PostgresSource

        child = PostgresSource(
            connection_string="x",
            name="postgres-localhost__sales",
            host="localhost",
            database="sales",
        )
        child._explicit_name = False
        assert schema_output_path(child) == Path("schema_postgres-localhost__sales.json")
```

- [ ] **Step 2: Update the existing 5 assertions at `tests/test_discover_io.py:127-179`**

The existing tests build sources by calling the class constructor directly. They do NOT set `_explicit_name`, so the new helper will treat them as auto-named. Expected filenames change to drop the `_<database>` suffix (since the new helper never appends database). Update exactly the five `assert` values:

1. `test_db_source_with_database` (sqlserver host=192.168.2.62, database=ZAKYA, no name)
   - Old expected: `Path("schema_sqlserver-192.168.2.62_ZAKYA.json")`
   - New expected: `Path("schema_sqlserver-192.168.2.62.json")`

2. `test_db_source_sanitizes_database` (sqlserver host=db.internal, database=My DB, no name)
   - Old expected: `Path("schema_sqlserver-db.internal_My_DB.json")`
   - New expected: `Path("schema_sqlserver-db.internal.json")`
   - Rename this test to `test_db_source_without_explicit_name_has_no_db_suffix` for clarity.

3. `test_db_source_without_database` (sqlserver host=db.internal, no database, no name)
   - Old expected: `Path("schema_sqlserver-db.internal.json")`
   - New expected: unchanged.

4. `test_file_source_has_no_database_suffix` (sqlite path=source.sqlite, no name)
   - Old expected: `Path("schema_sqlite-source.json")`
   - New expected: unchanged.

5. `test_user_name_used_in_path` (sqlserver, name=prod-erp, host=db, database=ZAKYA)
   - Old expected: `Path("schema_prod-erp_ZAKYA.json")`
   - New expected: `Path("schema_sqlserver_prod-erp.json")`
   - This test now must set `src._explicit_name = True` before the assertion (since the test constructs the source directly instead of going through the yaml loader).

Full rewrite of `test_user_name_used_in_path`:

```python
    def test_user_name_used_in_path(self):
        from pathlib import Path

        from feather_etl.config import schema_output_path
        from feather_etl.sources.sqlserver import SqlServerSource

        src = SqlServerSource(
            connection_string="x", name="prod-erp", host="db", database="ZAKYA"
        )
        src._explicit_name = True
        assert schema_output_path(src) == Path("schema_sqlserver_prod-erp.json")
```

- [ ] **Step 3: Run the tests to verify failures are in the expected places**

Run: `uv run pytest tests/test_discover_io.py -v`
Expected: existing 4 `TestSchemaOutputPath` tests PASS only after test expectations are updated; new `TestSchemaOutputPathTypePrefix` tests FAIL with assertion mismatches because the helper still has the old body.

- [ ] **Step 4: Rewrite `schema_output_path`**

Edit [src/feather_etl/config.py:53-64](../../src/feather_etl/config.py#L53-L64). Replace the existing body:

```python
def schema_output_path(cfg: "Source") -> Path:
    """Return the filename for `feather discover` JSON output.

    - If the user explicitly set `name:` in yaml (tracked via cfg._explicit_name),
      the filename is prepended with `<type>_` for at-a-glance source typing.
    - Otherwise the auto-derived name is used as-is; it already carries the
      type (e.g. 'csv-orders', 'postgres-localhost').

    Database name is NOT appended here — when `databases: [...]` expansion
    happens in `_expand_db_sources`, the db is already embedded in `cfg.name`
    via `__<db>`.
    """
    stem = resolved_source_name(cfg)
    if getattr(cfg, "_explicit_name", False):
        stem = f"{cfg.type}_{stem}"
    return Path(f"schema_{stem}.json")
```

- [ ] **Step 5: Run `test_discover_io.py` to verify all pass**

Run: `uv run pytest tests/test_discover_io.py -v`
Expected: all old and new cases pass.

- [ ] **Step 6: Run the full Python suite**

Run: `uv run pytest -q`
Expected: all pass. If any existing test elsewhere pinned the old `schema_<name>_<db>.json` format, it must be updated with the same logic (explicit name → prefix; no database suffix in filename).

- [ ] **Step 7: Commit**

```bash
git add src/feather_etl/config.py tests/test_discover_io.py
git commit -m "feat(config): schema_output_path prepends type for explicit names (#21)"
```

---

## Task 4: Wire `schema_output_path` into `_write_schema`

`commands/discover.py:_write_schema` currently constructs the filename inline via `f"schema_{_sanitised_filename(source.name)}.json"`. Route it through the helper instead so the typed filenames actually land on disk.

**Files:**
- Modify: `src/feather_etl/commands/discover.py:26-38`
- Verify: `tests/` (any existing tests that assert output filenames from the full discover flow)

- [ ] **Step 1: Write a failing integration-style test**

Append to `tests/test_explicit_name_flag.py`:

```python
def test_discover_writes_typed_filename_for_explicit_name(tmp_path, csv_dir):
    """End-to-end: discover with explicit name writes schema_<type>_<name>.json."""
    from feather_etl.commands.discover import discover
    import typer

    cfg_path = _write_yaml(
        tmp_path,
        {
            "sources": [{"name": "orders", "type": "csv", "path": str(csv_dir)}],
            "destination": {"path": str(tmp_path / "out.duckdb")},
            "tables": [],
        },
    )

    # Run discover by invoking the Typer command directly
    from typer.testing import CliRunner
    from feather_etl.cli import app

    runner = CliRunner()
    result = runner.invoke(
        app, ["discover", "--config", str(cfg_path), "--yes"]
    )
    assert result.exit_code == 0, result.output

    expected = tmp_path / "schema_csv_orders.json"
    assert expected.is_file(), f"expected {expected} to exist. Files: {list(tmp_path.iterdir())}"


def test_discover_writes_untyped_filename_for_auto_name(tmp_path, csv_dir):
    """End-to-end: discover without explicit name keeps the auto-derived filename."""
    from typer.testing import CliRunner
    from feather_etl.cli import app

    cfg_path = _write_yaml(
        tmp_path,
        {
            "sources": [{"type": "csv", "path": str(csv_dir)}],
            "destination": {"path": str(tmp_path / "out.duckdb")},
            "tables": [],
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        app, ["discover", "--config", str(cfg_path), "--yes"]
    )
    assert result.exit_code == 0, result.output

    # auto-name is csv-<dirname>
    expected_prefix = "schema_csv-"
    matches = [p for p in tmp_path.iterdir() if p.name.startswith(expected_prefix) and p.suffix == ".json"]
    assert len(matches) == 1, f"expected one file starting with {expected_prefix}; found {[m.name for m in tmp_path.iterdir()]}"
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_explicit_name_flag.py::test_discover_writes_typed_filename_for_explicit_name -v`
Expected: FAIL — the inline f-string at `_write_schema` does not apply the type prefix, so the file is written as `schema_orders.json` instead of `schema_csv_orders.json`.

- [ ] **Step 3: Replace the inline filename construction**

Edit [src/feather_etl/commands/discover.py:26-38](../../src/feather_etl/commands/discover.py#L26-L38). Replace:

```python
def _write_schema(source, target_dir: Path) -> tuple[Path, int]:
    """Discover `source` and write JSON. Returns (path, table_count)."""
    schemas = source.discover()
    payload = [
        {
            "table_name": s.name,
            "columns": [{"name": c[0], "type": c[1]} for c in s.columns],
        }
        for s in schemas
    ]
    out = target_dir / f"schema_{_sanitised_filename(source.name)}.json"
    out.write_text(json.dumps(payload, indent=2))
    return out, len(schemas)
```

With:

```python
def _write_schema(source, target_dir: Path) -> tuple[Path, int]:
    """Discover `source` and write JSON. Returns (path, table_count)."""
    from feather_etl.config import schema_output_path

    schemas = source.discover()
    payload = [
        {
            "table_name": s.name,
            "columns": [{"name": c[0], "type": c[1]} for c in s.columns],
        }
        for s in schemas
    ]
    out = target_dir / schema_output_path(source)
    out.write_text(json.dumps(payload, indent=2))
    return out, len(schemas)
```

The local `_sanitised_filename` helper at lines 22-23 may still be used elsewhere in this file (check with `grep _sanitised_filename src/feather_etl/commands/discover.py`). If no other references remain, delete the helper; otherwise leave it.

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `uv run pytest tests/test_explicit_name_flag.py -v`
Expected: all pass.

- [ ] **Step 5: Run the full Python suite**

Run: `uv run pytest -q`
Expected: all pass.

- [ ] **Step 6: Run the CLI integration suite**

Run: `bash scripts/hands_on_test.sh`
Expected: all pass. (A quick grep confirms the script does not assert any specific `schema_*.json` filenames; if a previously-green check now fails due to a filename assertion, update the expected value in the script.)

- [ ] **Step 7: Commit**

```bash
git add src/feather_etl/commands/discover.py tests/test_explicit_name_flag.py
git commit -m "feat(discover): route _write_schema through schema_output_path (#21)"
```

---

## Task 5: Route the rename path through `schema_output_path`

`discover_state.apply_renames` currently reconstructs the new filename via string replacement on the old path. That cannot handle the new rule correctly (the new filename may need a type prefix that the old filename lacked, or vice versa). Pass the current `sources` list into `apply_renames` and look up the renamed source to call `schema_output_path` on it.

**Files:**
- Modify: `src/feather_etl/discover_state.py:209-263` (`apply_renames`, `_rename_schema_file`)
- Modify: `src/feather_etl/commands/discover.py:181, 184` (two `apply_renames` call sites)
- Create: `tests/test_discover_rename_filenames.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_discover_rename_filenames.py`:

```python
"""Verify rename produces new-format (type-prefixed) filenames."""

from pathlib import Path

import pytest
import yaml

from feather_etl.commands.discover import _expand_db_sources
from feather_etl.config import FeatherConfig, schema_output_path
from feather_etl.discover_state import DiscoverState, apply_renames


@pytest.fixture
def csv_dir(tmp_path: Path) -> Path:
    d = tmp_path / "data"
    d.mkdir()
    (d / "orders.csv").write_text("id,name\n1,a\n")
    return d


def test_rename_produces_typed_filename(tmp_path, csv_dir):
    """Rename from 'orders_old' -> 'orders_new' yields schema_csv_orders_new.json."""
    # Simulate prior discovery: state file references old typed filename.
    old_schema = tmp_path / "schema_csv_orders_old.json"
    old_schema.write_text("[]")

    state = DiscoverState(path=tmp_path / "feather_discover_state.json")
    state.sources["orders_old"] = {
        "status": "discovered",
        "output_path": str(old_schema),
    }

    # Load yaml with the new name.
    cfg_path = tmp_path / "feather.yaml"
    cfg_path.write_text(
        yaml.safe_dump(
            {
                "sources": [
                    {"name": "orders_new", "type": "csv", "path": str(csv_dir)}
                ],
                "destination": {"path": str(tmp_path / "out.duckdb")},
                "tables": [],
            }
        )
    )
    cfg = FeatherConfig.load_yaml(cfg_path)
    sources = _expand_db_sources(cfg.sources)

    apply_renames(
        state=state,
        renames=[("orders_old", "orders_new")],
        config_dir=tmp_path,
        sources=sources,
    )

    expected_name = schema_output_path(sources[0]).name  # schema_csv_orders_new.json
    new_path = state.sources["orders_new"]["output_path"]
    assert Path(new_path).name == expected_name
    assert (tmp_path / expected_name).is_file()
    assert not old_schema.is_file()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_discover_rename_filenames.py -v`
Expected: FAIL — `apply_renames()` does not accept a `sources` kwarg yet.

- [ ] **Step 3: Update `apply_renames` signature and logic**

Edit [src/feather_etl/discover_state.py:209-245](../../src/feather_etl/discover_state.py#L209-L245). Replace the function:

```python
def apply_renames(
    *,
    state: DiscoverState,
    renames: list[tuple[str, str]],
    config_dir: Path,
    sources: list,
) -> None:
    """Move matched state entries and schema files to their new names.

    `sources` is the current list of expanded sources (post `_expand_db_sources`).
    Used to compute new filenames via `schema_output_path`, so renames land on
    the correct new-format filenames regardless of explicit/auto flag changes.
    """
    from feather_etl.config import schema_output_path

    by_name = {s.name: s for s in sources}

    for old, new in renames:
        if old not in state.sources:
            continue

        old_prefix = f"{old}__"
        new_prefix = f"{new}__"

        parent_entry = state.sources.pop(old)
        state.sources[new] = parent_entry

        if old in state.auto_enumeration:
            state.auto_enumeration[new] = state.auto_enumeration.pop(old)

        child_keys = [
            name for name in list(state.sources) if name.startswith(old_prefix)
        ]
        for child_old in child_keys:
            child_new = new_prefix + child_old[len(old_prefix):]
            child_entry = state.sources.pop(child_old)
            child_src = by_name.get(child_new)
            child_entry["output_path"] = _rename_schema_file(
                config_dir=config_dir,
                output_path=child_entry.get("output_path"),
                new_source=child_src,
            )
            state.sources[child_new] = child_entry

        parent_src = by_name.get(new)
        parent_entry["output_path"] = _rename_schema_file(
            config_dir=config_dir,
            output_path=parent_entry.get("output_path"),
            new_source=parent_src,
        )
```

Replace `_rename_schema_file` (`discover_state.py:248-263`) with a source-aware version:

```python
def _rename_schema_file(
    *,
    config_dir: Path,
    output_path: str | None,
    new_source,
) -> str | None:
    """Rename the on-disk schema file to the name computed from `new_source`.

    If `new_source` is None (renamed to a source not present in the current
    config — shouldn't happen under normal rename flow), leave the path alone.
    """
    if output_path is None or new_source is None:
        return output_path

    from feather_etl.config import schema_output_path

    current = Path(output_path)
    new_name = schema_output_path(new_source).name
    if current.name == new_name:
        return output_path

    source_file = config_dir / current.name
    target_file = config_dir / new_name
    if source_file.is_file():
        source_file.rename(target_file)
    return str(current.with_name(new_name))
```

The old `_renamed_schema_path` helper at `discover_state.py:200-206` is no longer used and can be deleted. Verify with `grep _renamed_schema_path src/ tests/` before deleting.

- [ ] **Step 4: Update the two call sites in `commands/discover.py`**

Edit [src/feather_etl/commands/discover.py:181](../../src/feather_etl/commands/discover.py#L181) and line 184 — both `apply_renames(...)` calls. At this point `sources` is already in scope (the expanded list). Add the new kwarg:

```python
            elif yes:
                apply_renames(
                    state=state,
                    renames=proposals,
                    config_dir=target_dir,
                    sources=sources,
                )
            elif sys.stdin.isatty():
                if typer.confirm("Accept all?", default=True):
                    apply_renames(
                        state=state,
                        renames=proposals,
                        config_dir=target_dir,
                        sources=sources,
                    )
```

- [ ] **Step 5: Run the new test to verify pass**

Run: `uv run pytest tests/test_discover_rename_filenames.py -v`
Expected: PASS.

- [ ] **Step 6: Run any existing rename tests**

Run: `uv run pytest -q -k rename`
Expected: all pass. If a test fails because the old `_rename_schema_file` / `_renamed_schema_path` signature is exercised directly, update that test to use the new signature or delete it if redundant.

- [ ] **Step 7: Run the full Python suite**

Run: `uv run pytest -q`
Expected: all pass.

- [ ] **Step 8: Run the CLI integration suite**

Run: `bash scripts/hands_on_test.sh`
Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add src/feather_etl/discover_state.py src/feather_etl/commands/discover.py \
        tests/test_discover_rename_filenames.py
git commit -m "feat(discover): renames compute new filename via schema_output_path (#21)"
```

---

## Task 6: Final verification and close-out

A final sweep to catch anything the earlier tasks missed.

**Files:** verification only, no code changes unless a regression appears.

- [ ] **Step 1: Confirm `schema_output_path` is the only filename constructor**

Run: `grep -rn 'schema_' src/feather_etl/ --include='*.py' | grep -v 'schema_changes\|_schema_snapshots\|save_schema_snapshot\|get_schema_snapshot\|alert_on_schema_drift\|schema_drift\|schema_prefix\|VALID_SCHEMA_PREFIXES\|schema_version\|schema_dir\|schema_name'`
Expected: results should only be: `schema_output_path` definition + its imports + `_write_schema`'s call to it + the rename path's call to it. No other f-strings starting with `schema_`. If any appear, refactor them to call the helper.

- [ ] **Step 2: Run the full Python suite with coverage**

Run: `uv run pytest -q --cov=src --cov-fail-under=80`
Expected: all pass, coverage >= 80%.

- [ ] **Step 3: Run the CLI integration suite**

Run: `bash scripts/hands_on_test.sh`
Expected: all pass.

- [ ] **Step 4: Lint and format check**

Run: `ruff check . && ruff format --check .`
Expected: clean. If not, run `ruff format .` and re-commit.

- [ ] **Step 5: Manual smoke test**

Create a scratch `feather.yaml` in a temp directory with one explicitly-named CSV source and one auto-named sqlite source, run `feather discover`, verify:

```bash
TMP=$(mktemp -d)
mkdir "$TMP/orders_dir"
echo "id,name" > "$TMP/orders_dir/a.csv"
echo "1,alice" >> "$TMP/orders_dir/a.csv"
cp tests/fixtures/sample_erp.sqlite "$TMP/sample.sqlite"
cat > "$TMP/feather.yaml" <<YAML
sources:
  - name: orders
    type: csv
    path: $TMP/orders_dir
  - type: sqlite
    path: $TMP/sample.sqlite
    name: legacy
destination:
  path: $TMP/out.duckdb
tables: []
YAML
cd "$TMP"
uv run --project "$OLDPWD" feather discover --yes
ls schema_*.json
```

Expected output:
```
schema_csv_orders.json
schema_sqlite_legacy.json
```

(Both sources have explicit names, so both get the type prefix.)

- [ ] **Step 6: Update CLAUDE.md test count if it changed**

Check `CLAUDE.md`'s "currently: 460 tests" line. If the number shifted by more than the expected additions (Task 1: +5, Task 2: +3, Task 3: +7, Task 4: +2, Task 5: +1 = +18 → 478), investigate. If the number is exactly the expected delta, update the line:

```
uv run pytest -q               # currently: 478 tests
```

- [ ] **Step 7: Commit final cleanup**

If CLAUDE.md was updated or any stragglers were fixed:

```bash
git add CLAUDE.md
git commit -m "docs(claude): bump test count for #21"
```

Otherwise skip this step.

---

## Verification checklist (from spec)

- [ ] Explicit-name sources produce `schema_<type>_<name>.json`
- [ ] Auto-derived sources produce unchanged `schema_<type>-<basename|host>.json`
- [ ] Expanded DB children inherit parent's explicitness (prefix when parent explicit, no prefix when parent auto)
- [ ] `schema_output_path` is the only filename constructor
- [ ] Rename flow produces the correct new-format filename
- [ ] No file migration code — testers are expected to delete stale `schema_*.json` + `feather_discover_state.json` manually if upgrading across this change
- [ ] `uv run pytest -q` all green
- [ ] `bash scripts/hands_on_test.sh` all green
- [ ] `ruff check .` clean
