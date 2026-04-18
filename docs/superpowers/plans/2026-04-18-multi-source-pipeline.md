# Multi-Source Pipeline + Curation-Driven Extraction — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `feather run` extract tables from multiple sources using `discovery/curation.json` as the table manifest, replacing the YAML `tables:` section.

**Architecture:** Config-layer resolution — `load_config()` reads curation.json, filters to `include` entries, resolves each entry's `source_db` to the correct source instance, and produces `TableConfig` objects with resolved source references. Pipeline receives a source per table instead of hardcoding `sources[0]`.

**Tech Stack:** Python, DuckDB, PyArrow, pytest (file-based fixtures only — no database server deps)

**Spec:** `docs/superpowers/specs/2026-04-18-multi-source-pipeline-design.md`

---

## File Structure

| File | Responsibility | Status |
|---|---|---|
| `src/feather_etl/sources/expand.py` | Shared `expand_db_sources()` using `DatabaseSource` base class | **New** |
| `src/feather_etl/curation.py` | Load curation.json, filter to includes, resolve source_db, produce TableConfig list | **New** |
| `tests/test_expand_db_sources.py` | Tests for extracted expand utility | **New** |
| `tests/test_curation.py` | Tests for curation loader + source resolution | **New** |
| `tests/test_multi_source_e2e.py` | End-to-end multi-source extraction with file-based sources | **New** |
| `src/feather_etl/config.py` | Add `source`/`database` to TableConfig, wire curation loader | **Modify** |
| `src/feather_etl/pipeline.py` | `run_table()` accepts source param | **Modify** |
| `src/feather_etl/commands/_common.py` | Remove `_enforce_single_source()` | **Modify** |
| `src/feather_etl/commands/run.py` | Remove gate, pass source to pipeline | **Modify** |
| `src/feather_etl/commands/setup.py` | Remove gate | **Modify** |
| `src/feather_etl/commands/status.py` | Remove gate | **Modify** |
| `src/feather_etl/commands/validate.py` | Remove gate, iterate all sources for check | **Modify** |
| `src/feather_etl/commands/history.py` | Remove gate | **Modify** |
| `src/feather_etl/commands/discover.py` | Import from shared expand utility | **Modify** |

---

### Task 1: Extract `_expand_db_sources` to shared utility

**Files:**
- Create: `src/feather_etl/sources/expand.py`
- Create: `tests/test_expand_db_sources.py`
- Modify: `src/feather_etl/commands/discover.py:37-97`

- [ ] **Step 1: Write the failing test**

Create `tests/test_expand_db_sources.py`:

```python
"""Tests for the shared expand_db_sources utility."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest


class TestExpandDbSources:
    def test_file_sources_pass_through(self):
        """File sources are returned unchanged."""
        from feather_etl.sources.expand import expand_db_sources

        mock_src = MagicMock()
        mock_src.database = None
        mock_src.databases = None
        # Not a DatabaseSource subclass — simulate a FileSource
        result = expand_db_sources([mock_src])
        assert result == [mock_src]

    def test_db_source_with_single_database_passes_through(self):
        """DB source with database set is returned unchanged."""
        from feather_etl.sources.expand import expand_db_sources
        from feather_etl.sources.database_source import DatabaseSource

        mock_src = MagicMock(spec=DatabaseSource)
        mock_src.database = "mydb"
        mock_src.databases = None
        result = expand_db_sources([mock_src])
        assert result == [mock_src]

    def test_db_source_with_databases_list_expands(self):
        """DB source with databases: [a, b] produces one child per db."""
        from feather_etl.sources.expand import expand_db_sources
        from feather_etl.sources.database_source import DatabaseSource

        mock_src = MagicMock(spec=DatabaseSource)
        mock_src.database = None
        mock_src.databases = ["db_a", "db_b"]
        mock_src.name = "test_server"
        mock_src.type = "sqlserver"
        mock_src.host = "localhost"
        mock_src.port = 1433
        mock_src.user = "sa"
        mock_src.password = "pass"
        mock_src._explicit_name = False

        child_a = MagicMock(spec=DatabaseSource)
        child_b = MagicMock(spec=DatabaseSource)
        type(mock_src).from_yaml = MagicMock(side_effect=[child_a, child_b])

        result = expand_db_sources([mock_src])
        assert len(result) == 2
        calls = type(mock_src).from_yaml.call_args_list
        assert calls[0][0][0]["database"] == "db_a"
        assert calls[0][0][0]["name"] == "test_server__db_a"
        assert calls[1][0][0]["database"] == "db_b"
        assert calls[1][0][0]["name"] == "test_server__db_b"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_expand_db_sources.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'feather_etl.sources.expand'`

- [ ] **Step 3: Write the shared expand utility**

Create `src/feather_etl/sources/expand.py`:

```python
"""Shared database source expansion — used by discover and pipeline."""

from __future__ import annotations

from pathlib import Path

from feather_etl.sources.database_source import DatabaseSource


def expand_db_sources(sources: list) -> list:
    """Expand database sources without explicit database into child sources.

    For each source:
      - File sources → keep as-is.
      - DB source with `database` set → keep as-is.
      - DB source with `databases: [...]` → one child per entry.
      - DB source with neither → call list_databases() and expand.
    """
    expanded: list = []
    for src in sources:
        if not isinstance(src, DatabaseSource):
            expanded.append(src)
            continue
        if src.database is not None:
            expanded.append(src)
            continue
        databases = src.databases
        if databases is None:
            try:
                databases = src.list_databases()
            except Exception as e:
                src._last_error = (
                    f"Found 0 databases on host {src.host}. Either grant "
                    f"VIEW ANY DATABASE to this login, or specify "
                    f"`database:` / `databases: [...]` explicitly. ({e})"
                )
                expanded.append(src)
                continue
            if not databases:
                src._last_error = (
                    f"Found 0 databases on host {src.host}. Either grant "
                    f"VIEW ANY DATABASE to this login, or specify "
                    f"`database:` / `databases: [...]` explicitly."
                )
                expanded.append(src)
                continue
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
            child._explicit_name = getattr(src, "_explicit_name", False)
            expanded.append(child)
    return expanded
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_expand_db_sources.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: Update discover.py to import from shared utility**

In `src/feather_etl/commands/discover.py`, replace the `_expand_db_sources` function (lines 37–97) with an import:

```python
from feather_etl.sources.expand import expand_db_sources
```

Update the call site at line 139 from `_expand_db_sources(cfg.sources)` to `expand_db_sources(cfg.sources)`.

Delete the old `_expand_db_sources` function and its three `from feather_etl.sources.*` imports at lines 48–51.

- [ ] **Step 6: Run full test suite to confirm no regressions**

Run: `uv run pytest -q`
Expected: All tests pass (currently 597)

- [ ] **Step 7: Commit**

```bash
git add src/feather_etl/sources/expand.py tests/test_expand_db_sources.py src/feather_etl/commands/discover.py
git commit -m "refactor: extract expand_db_sources to shared utility, use DatabaseSource base class (#27)"
```

---

### Task 2: Add `source` and `database` fields to `TableConfig`

**Files:**
- Modify: `src/feather_etl/config.py:85-99`

- [ ] **Step 1: Add fields to TableConfig**

In `src/feather_etl/config.py`, add two fields to the `TableConfig` dataclass after `dedup_columns`:

```python
@dataclass
class TableConfig:
    name: str
    source_table: str
    strategy: str
    target_table: str = ""
    primary_key: list[str] | None = None
    timestamp_column: str | None = None
    checksum_columns: list[str] | None = None
    filter: str | None = None
    quality_checks: dict | None = None
    column_map: dict[str, str] | None = None
    schedule: str | None = None
    dedup: bool = False
    dedup_columns: list[str] | None = None
    source_name: str | None = None    # resolved source name from curation
    database: str | None = None       # resolved database from curation
```

- [ ] **Step 2: Run full test suite to confirm backward compat**

Run: `uv run pytest -q`
Expected: All tests pass — new fields have `None` defaults so nothing breaks.

- [ ] **Step 3: Commit**

```bash
git add src/feather_etl/config.py
git commit -m "feat: add source_name and database fields to TableConfig (#8)"
```

---

### Task 3: Build curation.json loader

**Files:**
- Create: `src/feather_etl/curation.py`
- Create: `tests/test_curation.py`

- [ ] **Step 1: Write tests for curation loader**

Create `tests/test_curation.py`:

```python
"""Tests for curation.json loader and source resolution."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from feather_etl.config import TableConfig


def _write_curation(tmp_path: Path, tables: list[dict], source_systems: dict | None = None) -> Path:
    """Write a minimal curation.json for testing."""
    discovery_dir = tmp_path / "discovery"
    discovery_dir.mkdir(exist_ok=True)
    manifest = {
        "version": 2,
        "updated_at": "2026-04-18T00:00:00Z",
        "notes": "test",
        "source_systems": source_systems or {},
        "policies": {"data_quality": {"default": "flag", "escalations": []}},
        "tables": tables,
    }
    path = discovery_dir / "curation.json"
    path.write_text(json.dumps(manifest, indent=2))
    return path


def _make_include_entry(
    source_db: str = "test_db",
    source_table: str = "dbo.Sales",
    alias: str = "sales",
    strategy: str = "full",
    primary_key: list[str] | None = None,
    timestamp: dict | None = None,
) -> dict:
    return {
        "source_db": source_db,
        "source_table": source_table,
        "decision": "include",
        "table_type": "fact",
        "group": "test",
        "alias": alias,
        "classification_notes": None,
        "strategy": strategy,
        "primary_key": primary_key or ["id"],
        "timestamp": timestamp,
        "grain": None,
        "scd": None,
        "mapping": None,
        "dq_policy": None,
        "load_contract": None,
        "reason": "test entry",
    }


class TestLoadCuration:
    def test_filters_to_include_only(self, tmp_path: Path):
        from feather_etl.curation import load_curation_tables

        tables = [
            _make_include_entry(alias="sales"),
            {**_make_include_entry(alias="excluded"), "decision": "exclude"},
            {**_make_include_entry(alias="review"), "decision": "review"},
        ]
        _write_curation(tmp_path, tables)
        result = load_curation_tables(tmp_path)
        assert len(result) == 1
        assert result[0].name == "test_db_sales"

    def test_derives_bronze_name_from_source_db_and_alias(self, tmp_path: Path):
        from feather_etl.curation import load_curation_tables

        entry = _make_include_entry(source_db="Gofrugal", alias="sales")
        _write_curation(tmp_path, [entry])
        result = load_curation_tables(tmp_path)
        assert result[0].name == "gofrugal_sales"
        assert result[0].target_table == "bronze.gofrugal_sales"

    def test_maps_strategy(self, tmp_path: Path):
        from feather_etl.curation import load_curation_tables

        entry = _make_include_entry(strategy="incremental", timestamp={"column": "SyncDate", "reason": None, "rejected": []})
        _write_curation(tmp_path, [entry])
        result = load_curation_tables(tmp_path)
        assert result[0].strategy == "incremental"
        assert result[0].timestamp_column == "SyncDate"

    def test_maps_primary_key(self, tmp_path: Path):
        from feather_etl.curation import load_curation_tables

        entry = _make_include_entry(primary_key=["record_no", "line_no"])
        _write_curation(tmp_path, [entry])
        result = load_curation_tables(tmp_path)
        assert result[0].primary_key == ["record_no", "line_no"]

    def test_sets_source_name_and_database(self, tmp_path: Path):
        from feather_etl.curation import load_curation_tables

        entry = _make_include_entry(source_db="SAP")
        _write_curation(tmp_path, [entry])
        result = load_curation_tables(tmp_path)
        assert result[0].database == "SAP"

    def test_missing_curation_raises(self, tmp_path: Path):
        from feather_etl.curation import load_curation_tables

        with pytest.raises(FileNotFoundError, match="discovery/curation.json"):
            load_curation_tables(tmp_path)

    def test_no_include_entries_raises(self, tmp_path: Path):
        from feather_etl.curation import load_curation_tables

        entry = {**_make_include_entry(), "decision": "exclude"}
        _write_curation(tmp_path, [entry])
        with pytest.raises(ValueError, match="No tables with decision.*include"):
            load_curation_tables(tmp_path)

    def test_sanitizes_bronze_name(self, tmp_path: Path):
        from feather_etl.curation import load_curation_tables

        entry = _make_include_entry(source_db="My-Source", alias="Sales Data!")
        _write_curation(tmp_path, [entry])
        result = load_curation_tables(tmp_path)
        # Should be lowercased and sanitized
        assert result[0].name == "my_source_sales_data_"


class TestResolveSource:
    def test_resolves_source_by_databases_list(self):
        from feather_etl.curation import resolve_source

        mock_src = MagicMock()
        mock_src.name = "Rama"
        mock_src.database = None
        mock_src.databases = ["Gofrugal", "SAP", "ZAKYA"]
        mock_src.type = "sqlserver"

        result = resolve_source("Gofrugal", [mock_src])
        assert result == mock_src

    def test_resolves_source_by_single_database(self):
        from feather_etl.curation import resolve_source

        mock_src = MagicMock()
        mock_src.name = "erp"
        mock_src.database = "mydb"
        mock_src.databases = None

        result = resolve_source("mydb", [mock_src])
        assert result == mock_src

    def test_resolves_file_source_by_name(self):
        from feather_etl.curation import resolve_source

        mock_src = MagicMock()
        mock_src.name = "csv_data"
        mock_src.database = None
        mock_src.databases = None
        # File source — no database attribute logic, matched by name
        del mock_src.database
        del mock_src.databases
        mock_src.name = "csv_data"

        result = resolve_source("csv_data", [mock_src])
        assert result == mock_src

    def test_no_match_raises(self):
        from feather_etl.curation import resolve_source

        mock_src = MagicMock()
        mock_src.name = "Rama"
        mock_src.database = None
        mock_src.databases = ["Gofrugal"]

        with pytest.raises(ValueError, match="does not match any declared source"):
            resolve_source("NonExistent", [mock_src])

    def test_ambiguous_match_raises(self):
        from feather_etl.curation import resolve_source

        src_a = MagicMock()
        src_a.name = "ServerA"
        src_a.database = None
        src_a.databases = ["sales"]

        src_b = MagicMock()
        src_b.name = "ServerB"
        src_b.database = None
        src_b.databases = ["sales"]

        with pytest.raises(ValueError, match="ambiguous.*matches multiple sources"):
            resolve_source("sales", [src_a, src_b])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_curation.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'feather_etl.curation'`

- [ ] **Step 3: Implement the curation loader**

Create `src/feather_etl/curation.py`:

```python
"""Curation manifest loader — reads discovery/curation.json as the table manifest."""

from __future__ import annotations

import json
import re
from pathlib import Path

from feather_etl.config import TableConfig

_UNSAFE_CHARS = re.compile(r"[^a-z0-9_]")


def _sanitize_bronze_name(source_db: str, alias: str) -> str:
    """Derive a sanitized bronze table name from source_db and alias.

    Format: <source_db>_<alias>, lowercased, non-alphanum replaced with underscore.
    """
    raw = f"{source_db}_{alias}".lower()
    return _UNSAFE_CHARS.sub("_", raw)


def resolve_source(source_db: str, sources: list) -> object:
    """Find the source that owns the given database name.

    Resolution order:
    1. source.database == source_db (single-database source)
    2. source_db in source.databases (multi-database source)
    3. source.name == source_db (file sources — no database concept)

    Raises ValueError if no match or ambiguous match.
    """
    matches = []
    for src in sources:
        db = getattr(src, "database", None)
        dbs = getattr(src, "databases", None)
        if db is not None and db == source_db:
            matches.append(src)
        elif dbs is not None and source_db in dbs:
            matches.append(src)
        elif src.name == source_db:
            matches.append(src)

    if len(matches) == 0:
        available = ", ".join(s.name for s in sources)
        raise ValueError(
            f"source_db '{source_db}' does not match any declared source. "
            f"Available sources: {available}"
        )
    if len(matches) > 1:
        names = ", ".join(s.name for s in matches)
        raise ValueError(
            f"source_db '{source_db}' is ambiguous — matches multiple sources: {names}"
        )
    return matches[0]


def load_curation_tables(config_dir: Path) -> list[TableConfig]:
    """Load discovery/curation.json and produce TableConfig list from include entries.

    Raises FileNotFoundError if curation.json does not exist.
    Raises ValueError if no tables have decision 'include'.
    """
    curation_path = config_dir / "discovery" / "curation.json"
    if not curation_path.exists():
        raise FileNotFoundError(
            f"discovery/curation.json not found in {config_dir}. "
            f"Run 'feather discover' and curate tables first."
        )

    manifest = json.loads(curation_path.read_text())
    raw_tables = manifest.get("tables", [])
    includes = [t for t in raw_tables if t.get("decision") == "include"]

    if not includes:
        raise ValueError(
            "No tables with decision 'include' in discovery/curation.json. "
            "Curate at least one table before running."
        )

    tables: list[TableConfig] = []
    for entry in includes:
        source_db = entry["source_db"]
        alias = entry.get("alias") or entry["source_table"].split(".")[-1]
        bronze_name = _sanitize_bronze_name(source_db, alias)

        timestamp_column = None
        ts = entry.get("timestamp")
        if ts and isinstance(ts, dict):
            timestamp_column = ts.get("column")

        tables.append(
            TableConfig(
                name=bronze_name,
                source_table=entry["source_table"],
                strategy=entry["strategy"],
                target_table=f"bronze.{bronze_name}",
                primary_key=entry.get("primary_key"),
                timestamp_column=timestamp_column,
                source_name=source_db,
                database=source_db,
            )
        )

    return tables
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_curation.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/feather_etl/curation.py tests/test_curation.py
git commit -m "feat: add curation.json loader with source resolution (#8, #15)"
```

---

### Task 4: Wire curation loader into `load_config()`

**Files:**
- Modify: `src/feather_etl/config.py:274-418`
- Create: `tests/test_curation_config_integration.py`

- [ ] **Step 1: Write the integration test**

Create `tests/test_curation_config_integration.py`:

```python
"""Tests for curation.json integration with load_config."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest
import yaml


def _write_feather_yaml(tmp_path: Path, sources: list[dict]) -> Path:
    """Write a feather.yaml with sources and destination, no tables."""
    config = {
        "sources": sources,
        "destination": {"path": str(tmp_path / "feather_data.duckdb")},
    }
    config_file = tmp_path / "feather.yaml"
    config_file.write_text(yaml.dump(config, default_flow_style=False))
    return config_file


def _write_curation(tmp_path: Path, tables: list[dict]) -> None:
    """Write discovery/curation.json."""
    discovery_dir = tmp_path / "discovery"
    discovery_dir.mkdir(exist_ok=True)
    manifest = {
        "version": 2,
        "updated_at": "2026-04-18T00:00:00Z",
        "notes": "test",
        "source_systems": {},
        "policies": {"data_quality": {"default": "flag", "escalations": []}},
        "tables": tables,
    }
    (discovery_dir / "curation.json").write_text(json.dumps(manifest))


def _make_include(source_db: str, source_table: str, alias: str, strategy: str = "full") -> dict:
    return {
        "source_db": source_db,
        "source_table": source_table,
        "decision": "include",
        "table_type": "fact",
        "group": "test",
        "alias": alias,
        "classification_notes": None,
        "strategy": strategy,
        "primary_key": ["id"],
        "timestamp": None,
        "grain": None,
        "scd": None,
        "mapping": None,
        "dq_policy": None,
        "load_contract": None,
        "reason": "test",
    }


class TestLoadConfigWithCuration:
    def test_loads_tables_from_curation_json(self, tmp_path: Path):
        """When curation.json exists, tables come from it."""
        from feather_etl.config import load_config

        # Create a DuckDB source file
        src_db = tmp_path / "source.duckdb"
        con = duckdb.connect(str(src_db))
        con.execute("CREATE SCHEMA erp")
        con.execute("CREATE TABLE erp.orders (id INT, amount DOUBLE)")
        con.execute("INSERT INTO erp.orders VALUES (1, 100.0)")
        con.close()

        config_file = _write_feather_yaml(tmp_path, [
            {"type": "duckdb", "name": "erp", "path": str(src_db)},
        ])
        _write_curation(tmp_path, [
            _make_include("erp", "erp.orders", "orders"),
        ])

        cfg = load_config(config_file, validate=False)
        assert len(cfg.tables) == 1
        assert cfg.tables[0].name == "erp_orders"
        assert cfg.tables[0].target_table == "bronze.erp_orders"
        assert cfg.tables[0].source_table == "erp.orders"
        assert cfg.tables[0].database == "erp"

    def test_multi_source_loads_from_curation(self, tmp_path: Path):
        """Two sources, curation entries from each, all resolve."""
        from feather_etl.config import load_config

        # Create two DuckDB source files
        src_a = tmp_path / "source_a.duckdb"
        con = duckdb.connect(str(src_a))
        con.execute("CREATE SCHEMA main")
        con.execute("CREATE TABLE main.items (id INT)")
        con.close()

        src_b = tmp_path / "source_b.duckdb"
        con = duckdb.connect(str(src_b))
        con.execute("CREATE SCHEMA main")
        con.execute("CREATE TABLE main.users (id INT)")
        con.close()

        config_file = _write_feather_yaml(tmp_path, [
            {"type": "duckdb", "name": "inventory", "path": str(src_a)},
            {"type": "duckdb", "name": "crm", "path": str(src_b)},
        ])
        _write_curation(tmp_path, [
            _make_include("inventory", "main.items", "items"),
            _make_include("crm", "main.users", "users"),
        ])

        cfg = load_config(config_file, validate=False)
        assert len(cfg.tables) == 2
        names = {t.name for t in cfg.tables}
        assert names == {"inventory_items", "crm_users"}

    def test_no_curation_no_tables_raises(self, tmp_path: Path):
        """When neither curation.json nor tables: exists, error."""
        from feather_etl.config import load_config

        src_db = tmp_path / "source.duckdb"
        src_db.touch()
        config_file = _write_feather_yaml(tmp_path, [
            {"type": "duckdb", "name": "erp", "path": str(src_db)},
        ])

        with pytest.raises(FileNotFoundError, match="curation.json"):
            load_config(config_file, validate=False)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_curation_config_integration.py -v`
Expected: FAIL — load_config still expects tables: in YAML

- [ ] **Step 3: Modify load_config to use curation loader**

In `src/feather_etl/config.py`, update `load_config()`:

1. Remove `_parse_tables` and `_merge_tables_dir` calls (lines 374–376).
2. Replace with curation loader import and call:

```python
from feather_etl.curation import load_curation_tables

# ... after sources and destination are parsed ...

# Tables come from curation.json
tables = load_curation_tables(config_dir)
```

3. Remove the `if "tables" not in raw` check — tables no longer come from YAML.

4. Update `_validate()` — remove the `primary.validate_source_table()` check that uses `config.sources[0]` (line 249). Source-table validation for curation entries will be handled by the curation validator (#29).

- [ ] **Step 4: Run the integration tests**

Run: `uv run pytest tests/test_curation_config_integration.py -v`
Expected: All PASS

- [ ] **Step 5: Run the full test suite, fix broken tests**

Run: `uv run pytest -q`

Many existing tests will fail because they use `tables:` in their YAML configs. These tests need a `discovery/curation.json` fixture instead. Update test helpers:

In `tests/helpers.py`, add a function:

```python
import json


def write_curation(tmp_path: Path, tables: list[dict]) -> Path:
    """Write a discovery/curation.json for testing."""
    discovery_dir = tmp_path / "discovery"
    discovery_dir.mkdir(exist_ok=True)
    manifest = {
        "version": 2,
        "updated_at": "2026-04-18T00:00:00Z",
        "notes": "test fixture",
        "source_systems": {},
        "policies": {"data_quality": {"default": "flag", "escalations": []}},
        "tables": tables,
    }
    path = discovery_dir / "curation.json"
    path.write_text(json.dumps(manifest))
    return path
```

Update existing test fixtures across `test_config.py`, `test_pipeline.py`, `test_e2e.py`, `test_mode.py`, and others to use `write_curation()` alongside `write_config()`. Each test that currently puts `tables:` in feather.yaml needs to instead write a curation.json with equivalent entries.

This is the largest step — work through test files one at a time until `uv run pytest -q` passes.

- [ ] **Step 6: Commit**

```bash
git add src/feather_etl/config.py tests/helpers.py tests/test_curation_config_integration.py
git add tests/  # all updated test files
git commit -m "feat: wire curation.json as sole table manifest in load_config (#8, #15)"
```

---

### Task 5: Update `run_table()` to accept source as parameter

**Files:**
- Modify: `src/feather_etl/pipeline.py:168-209` and `518-546`

- [ ] **Step 1: Write the test**

In `tests/test_pipeline.py`, add (or update existing test) to confirm source is passed through:

```python
def test_run_table_uses_provided_source(self, tmp_path: Path):
    """run_table extracts from the source passed as argument, not sources[0]."""
    # Setup: create a config with one source, but pass a different source to run_table
    # The test confirms the passed source is used for extract, not config.sources[0]
    from feather_etl.pipeline import run_table
    from feather_etl.config import FeatherConfig, TableConfig, DestinationConfig, DefaultsConfig

    # Create a real DuckDB source with data
    import duckdb
    src_path = tmp_path / "real_source.duckdb"
    con = duckdb.connect(str(src_path))
    con.execute("CREATE SCHEMA erp; CREATE TABLE erp.orders (id INT); INSERT INTO erp.orders VALUES (1), (2)")
    con.close()

    from feather_etl.sources.duckdb_file import DuckDBFileSource
    real_source = DuckDBFileSource(path=src_path, name="real")

    table = TableConfig(
        name="erp_orders",
        source_table="erp.orders",
        strategy="full",
        target_table="bronze.erp_orders",
        primary_key=["id"],
        source_name="real",
        database="real",
    )

    config = FeatherConfig(
        sources=[real_source],
        destination=DestinationConfig(path=tmp_path / "dest.duckdb"),
        tables=[table],
        config_dir=tmp_path,
    )

    result = run_table(config, table, tmp_path, source=real_source)
    assert result.status == "success"
    assert result.rows_loaded == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_pipeline.py::test_run_table_uses_provided_source -v`
Expected: FAIL — `run_table() got an unexpected keyword argument 'source'`

- [ ] **Step 3: Update run_table signature**

In `src/feather_etl/pipeline.py`, change `run_table`:

```python
def run_table(
    config: FeatherConfig,
    table: TableConfig,
    working_dir: Path,
    source: object | None = None,
) -> RunResult:
```

Replace line 208 (`source = config.sources[0]`) with:

```python
    if source is None:
        source = config.sources[0]
```

- [ ] **Step 4: Update `run_all()` to pass source per table**

In `run_all()` (line 544), update the loop to resolve and pass the source:

```python
    from feather_etl.curation import resolve_source

    results: list[RunResult] = []
    for table in tables:
        table_source = resolve_source(table.database, config.sources) if table.database else config.sources[0]
        result = run_table(config, table, working_dir, source=table_source)
        results.append(result)
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/feather_etl/pipeline.py tests/test_pipeline.py
git commit -m "feat: run_table accepts source param, run_all resolves per table (#8)"
```

---

### Task 6: Remove `_enforce_single_source` from all commands

**Files:**
- Modify: `src/feather_etl/commands/_common.py:19-28`
- Modify: `src/feather_etl/commands/run.py:10,27`
- Modify: `src/feather_etl/commands/setup.py:10,27`
- Modify: `src/feather_etl/commands/status.py:10,24`
- Modify: `src/feather_etl/commands/validate.py:10,22`
- Modify: `src/feather_etl/commands/history.py:10,27`

- [ ] **Step 1: Delete `_enforce_single_source` from _common.py**

In `src/feather_etl/commands/_common.py`, delete lines 19–28 (the entire function).

- [ ] **Step 2: Remove import and call from each command**

In each of these files, remove `_enforce_single_source` from the import and delete the call line:

- `commands/run.py`: remove from import (line 10), delete call (line 27)
- `commands/setup.py`: remove from import (line 10), delete call (line 27)
- `commands/status.py`: remove from import (line 10), delete call (line 24)
- `commands/validate.py`: remove from import (line 10), delete call (line 22)
- `commands/history.py`: remove from import (line 10), delete call (line 27)

- [ ] **Step 3: Update validate command for multi-source**

In `commands/validate.py`, update the source check section (lines 24–58) to iterate all sources:

```python
    # Test source connections
    all_ok = True
    for source in cfg.sources:
        source_ok = source.check()
        if not source_ok:
            all_ok = False
        if not _is_json(ctx):
            source_label = (
                getattr(source, "path", None)
                or getattr(source, "host", None)
                or "configured"
            )
            conn_status = "connected" if source_ok else "FAILED"
            typer.echo(f"  Source: {source.type} ({source_label}) — {conn_status}")
            if not source_ok:
                err = getattr(source, "_last_error", None)
                if err:
                    typer.echo(f"    Details: {err}", err=True)

    if not all_ok:
        raise typer.Exit(code=2)
```

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest -q`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add src/feather_etl/commands/_common.py src/feather_etl/commands/run.py \
  src/feather_etl/commands/setup.py src/feather_etl/commands/status.py \
  src/feather_etl/commands/validate.py src/feather_etl/commands/history.py
git commit -m "feat: remove _enforce_single_source gate from all commands (#8)"
```

---

### Task 7: End-to-end multi-source extraction test

**Files:**
- Create: `tests/test_multi_source_e2e.py`

- [ ] **Step 1: Write the e2e test**

Create `tests/test_multi_source_e2e.py`:

```python
"""End-to-end test: multi-source extraction via curation.json."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest
import yaml

from feather_etl.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def _setup_multi_source_project(tmp_path: Path) -> Path:
    """Create a project with 2 DuckDB sources + curation.json."""
    # Source A: ERP with orders and customers
    src_a = tmp_path / "erp.duckdb"
    con = duckdb.connect(str(src_a))
    con.execute("CREATE SCHEMA erp")
    con.execute("CREATE TABLE erp.orders (id INT, amount DOUBLE)")
    con.execute("INSERT INTO erp.orders VALUES (1, 100.0), (2, 200.0), (3, 300.0)")
    con.execute("CREATE TABLE erp.customers (id INT, name VARCHAR)")
    con.execute("INSERT INTO erp.customers VALUES (1, 'Alice'), (2, 'Bob')")
    con.close()

    # Source B: SQLite-like DuckDB with products
    src_b = tmp_path / "inventory.duckdb"
    con = duckdb.connect(str(src_b))
    con.execute("CREATE SCHEMA inv")
    con.execute("CREATE TABLE inv.products (id INT, sku VARCHAR, price DOUBLE)")
    con.execute("INSERT INTO inv.products VALUES (1, 'SKU001', 9.99), (2, 'SKU002', 19.99)")
    con.close()

    # feather.yaml — two sources, no tables
    config = {
        "sources": [
            {"type": "duckdb", "name": "erp", "path": str(src_a)},
            {"type": "duckdb", "name": "inventory", "path": str(src_b)},
        ],
        "destination": {"path": str(tmp_path / "feather_data.duckdb")},
    }
    config_file = tmp_path / "feather.yaml"
    config_file.write_text(yaml.dump(config, default_flow_style=False))

    # discovery/curation.json — 3 include entries across 2 sources
    discovery_dir = tmp_path / "discovery"
    discovery_dir.mkdir()
    curation = {
        "version": 2,
        "updated_at": "2026-04-18T00:00:00Z",
        "notes": "test",
        "source_systems": {},
        "policies": {"data_quality": {"default": "flag", "escalations": []}},
        "tables": [
            {
                "source_db": "erp",
                "source_table": "erp.orders",
                "decision": "include",
                "table_type": "fact",
                "group": "erp",
                "alias": "orders",
                "classification_notes": None,
                "strategy": "full",
                "primary_key": ["id"],
                "timestamp": None,
                "grain": "one row per order",
                "scd": None,
                "mapping": None,
                "dq_policy": None,
                "load_contract": None,
                "reason": "test",
            },
            {
                "source_db": "erp",
                "source_table": "erp.customers",
                "decision": "include",
                "table_type": "dimension",
                "group": "erp",
                "alias": "customers",
                "classification_notes": None,
                "strategy": "full",
                "primary_key": ["id"],
                "timestamp": None,
                "grain": None,
                "scd": None,
                "mapping": None,
                "dq_policy": None,
                "load_contract": None,
                "reason": "test",
            },
            {
                "source_db": "inventory",
                "source_table": "inv.products",
                "decision": "include",
                "table_type": "dimension",
                "group": "inventory",
                "alias": "products",
                "classification_notes": None,
                "strategy": "full",
                "primary_key": ["id"],
                "timestamp": None,
                "grain": None,
                "scd": None,
                "mapping": None,
                "dq_policy": None,
                "load_contract": None,
                "reason": "test",
            },
            {
                "source_db": "erp",
                "source_table": "erp.audit_log",
                "decision": "exclude",
                "table_type": "audit",
                "group": "erp",
                "alias": None,
                "classification_notes": None,
                "strategy": None,
                "primary_key": None,
                "timestamp": None,
                "grain": None,
                "scd": None,
                "mapping": None,
                "dq_policy": None,
                "load_contract": None,
                "reason": "not needed",
            },
        ],
    }
    (discovery_dir / "curation.json").write_text(json.dumps(curation))

    return config_file


class TestMultiSourceE2E:
    def test_feather_run_extracts_from_multiple_sources(self, tmp_path: Path, monkeypatch):
        """feather run extracts tables from 2 DuckDB sources via curation.json."""
        monkeypatch.chdir(tmp_path)
        config_file = _setup_multi_source_project(tmp_path)

        result = runner.invoke(app, ["run", "--config", str(config_file)])
        assert result.exit_code == 0, f"stdout: {result.stdout}\nstderr: {result.stderr if hasattr(result, 'stderr') else ''}"

        # Verify data landed in bronze
        dest = duckdb.connect(str(tmp_path / "feather_data.duckdb"), read_only=True)
        tables = [
            row[0]
            for row in dest.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'bronze'"
            ).fetchall()
        ]
        dest.close()

        assert "erp_orders" in tables
        assert "erp_customers" in tables
        assert "inventory_products" in tables
        assert len(tables) == 3  # excluded table not present

    def test_row_counts_correct(self, tmp_path: Path, monkeypatch):
        """Verify row counts match source data."""
        monkeypatch.chdir(tmp_path)
        config_file = _setup_multi_source_project(tmp_path)
        runner.invoke(app, ["run", "--config", str(config_file)])

        dest = duckdb.connect(str(tmp_path / "feather_data.duckdb"), read_only=True)
        orders = dest.execute("SELECT COUNT(*) FROM bronze.erp_orders").fetchone()[0]
        customers = dest.execute("SELECT COUNT(*) FROM bronze.erp_customers").fetchone()[0]
        products = dest.execute("SELECT COUNT(*) FROM bronze.inventory_products").fetchone()[0]
        dest.close()

        assert orders == 3
        assert customers == 2
        assert products == 2

    def test_table_filter_works_with_bronze_name(self, tmp_path: Path, monkeypatch):
        """--table flag filters by curation-derived bronze name."""
        monkeypatch.chdir(tmp_path)
        config_file = _setup_multi_source_project(tmp_path)

        result = runner.invoke(app, ["run", "--config", str(config_file), "--table", "erp_orders"])
        assert result.exit_code == 0

        dest = duckdb.connect(str(tmp_path / "feather_data.duckdb"), read_only=True)
        tables = [
            row[0]
            for row in dest.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'bronze'"
            ).fetchall()
        ]
        dest.close()

        assert "erp_orders" in tables
        assert "erp_customers" not in tables  # not extracted — filtered out
```

- [ ] **Step 2: Run e2e tests**

Run: `uv run pytest tests/test_multi_source_e2e.py -v`
Expected: All 3 tests PASS

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest -q`
Expected: All tests pass

- [ ] **Step 4: Run ruff format**

Run: `ruff format .`

- [ ] **Step 5: Commit**

```bash
git add tests/test_multi_source_e2e.py
git commit -m "test: add multi-source e2e extraction tests (#8, #15)"
```

---

Plan complete and saved to `docs/superpowers/plans/2026-04-18-multi-source-pipeline.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?