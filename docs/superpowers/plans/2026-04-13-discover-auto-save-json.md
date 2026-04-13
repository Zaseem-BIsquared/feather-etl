# `feather discover` Auto-Save JSON — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Change `feather discover` to always save table/column schema to an auto-named JSON file in the current directory, instead of printing to stdout.

**Architecture:** Add an optional `source.name` field to `SourceConfig`. Introduce two pure helpers in `config.py` — `resolved_source_name(cfg)` (computes `name` or derives from type + host/path) and `schema_output_path(cfg)` (builds the full output `Path`). Silently sanitize every filename segment via a single regex. Rewrite `discover()` in `cli.py` to write JSON and print a single summary line. Move discover test coverage from `hands_on_test.sh` to pytest.

**Tech Stack:** Python 3.10+, `dataclasses`, `pathlib.Path`, `re`, `json`, Typer for CLI, `typer.testing.CliRunner` for CLI tests, pytest.

**Source spec:** [docs/superpowers/specs/2026-04-13-discover-auto-save-json-design.md](../specs/2026-04-13-discover-auto-save-json-design.md).

**Naming note:** The spec's recipe table uses `duckdb_file` — in the codebase this source type is named `duckdb`. File source types in `FILE_SOURCE_TYPES` are `{"duckdb", "sqlite", "csv", "excel", "json"}`. CSV is the only file source whose `path` is a directory (validated at [config.py:186-190](../../../src/feather_etl/config.py#L186-L190)); all other file sources have a file path.

---

## File Structure

| File | Purpose | Change |
|---|---|---|
| `src/feather_etl/config.py` | Config dataclasses + load/validate | Add `SourceConfig.name`; add `_sanitize`, `resolved_source_name`, `schema_output_path` helpers |
| `src/feather_etl/cli.py` | Typer commands | Rewrite `discover()` to save file + print path |
| `tests/test_config.py` | Config unit tests | Add test for optional `source.name` field |
| `tests/test_discover_io.py` (new) | Helper unit tests | Unit tests for `_sanitize`, `resolved_source_name`, `schema_output_path` |
| `tests/test_discover.py` (new) | End-to-end CLI tests | CLI invocation tests using `CliRunner` |
| `scripts/hands_on_test.sh` | Shell integration | Delete S4 + S15 + S17 discover assertions |

---

## Task 1 — Add `source.name` field to `SourceConfig`

**Files:**
- Modify: `src/feather_etl/config.py:43-52` (add `name` field to `SourceConfig`)
- Modify: `tests/test_config.py` (add test)

- [ ] **Step 1: Write the failing test**

Append this to `tests/test_config.py` inside the existing `TestConfigParsing` class (or as a new class `TestSourceName` at module bottom if preferred):

```python
class TestSourceName:
    def test_source_name_is_optional(self, tmp_path: Path):
        from feather_etl.config import load_config

        cfg_dict = _minimal_config(tmp_path)
        config_file = write_config(tmp_path, cfg_dict)
        result = load_config(config_file, validate=False)
        assert result.source.name is None

    def test_source_name_is_accepted(self, tmp_path: Path):
        from feather_etl.config import load_config

        cfg_dict = _minimal_config(tmp_path)
        cfg_dict["source"]["name"] = "prod-erp"
        config_file = write_config(tmp_path, cfg_dict)
        result = load_config(config_file, validate=False)
        assert result.source.name == "prod-erp"
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `uv run pytest tests/test_config.py::TestSourceName -v`

Expected: FAIL with `AttributeError: 'SourceConfig' object has no attribute 'name'` (or similar).

- [ ] **Step 3: Add the `name` field to `SourceConfig`**

Edit `src/feather_etl/config.py`. Find the `SourceConfig` dataclass (around line 43-52) and add the new field immediately after `type`:

```python
@dataclass
class SourceConfig:
    type: str
    name: str | None = None
    path: Path | None = None
    connection_string: str | None = None
    host: str | None = None
    port: int | None = None
    database: str | None = None
    user: str | None = None
    password: str | None = None
```

- [ ] **Step 4: Check whether `load_config` needs changes**

`load_config` uses dataclass constructor or dict unpacking. Search how `SourceConfig` is constructed:

Run: `grep -n "SourceConfig(" src/feather_etl/config.py`

If construction uses `SourceConfig(**source_dict)` or `dataclasses.fields(SourceConfig)` filtering, the new `name` field will automatically be picked up from the YAML. If any explicit mapping is present, add a `name=source_dict.get("name")` line there. Do **not** add validation — silent sanitization happens later at `resolved_source_name` call sites.

- [ ] **Step 5: Run the test and verify it passes**

Run: `uv run pytest tests/test_config.py::TestSourceName -v`

Expected: PASS (both tests).

- [ ] **Step 6: Run the full config suite to catch regressions**

Run: `uv run pytest tests/test_config.py -q`

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add src/feather_etl/config.py tests/test_config.py
git commit -m "feat(config): add optional source.name field"
```

---

## Task 2 — Add `_sanitize()` helper

**Files:**
- Modify: `src/feather_etl/config.py` (add helper at module bottom or near top)
- Create: `tests/test_discover_io.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_discover_io.py`:

```python
"""Unit tests for discover I/O helpers in feather_etl.config."""


class TestSanitize:
    def test_keeps_safe_chars(self):
        from feather_etl.config import _sanitize

        assert _sanitize("prod-erp.db_01") == "prod-erp.db_01"

    def test_replaces_unsafe_chars(self):
        from feather_etl.config import _sanitize

        assert _sanitize("prod/erp") == "prod_erp"
        assert _sanitize("192.168.2.62:1433") == "192.168.2.62_1433"
        assert _sanitize("a b c") == "a_b_c"

    def test_preserves_dots_and_hyphens(self):
        from feather_etl.config import _sanitize

        assert _sanitize("db.internal-prod") == "db.internal-prod"
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `uv run pytest tests/test_discover_io.py::TestSanitize -v`

Expected: FAIL with `ImportError: cannot import name '_sanitize'`.

- [ ] **Step 3: Implement `_sanitize` in `config.py`**

Add near the top of `src/feather_etl/config.py`, after the existing imports (check the first ~15 lines for the `import re` and `FILE_SOURCE_TYPES` constant — add this near `FILE_SOURCE_TYPES`):

```python
import re

_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]")


def _sanitize(segment: str) -> str:
    """Replace any char outside [A-Za-z0-9._-] with underscore. Preserves dots and hyphens."""
    return _UNSAFE_CHARS.sub("_", segment)
```

If `import re` is already at the top of the file, skip the import line.

- [ ] **Step 4: Run the test and verify it passes**

Run: `uv run pytest tests/test_discover_io.py::TestSanitize -v`

Expected: PASS (three tests).

- [ ] **Step 5: Commit**

```bash
git add src/feather_etl/config.py tests/test_discover_io.py
git commit -m "feat(config): add _sanitize helper for filename segments"
```

---

## Task 3 — Add `resolved_source_name()` helper

**Files:**
- Modify: `src/feather_etl/config.py` (add helper below `_sanitize`)
- Modify: `tests/test_discover_io.py` (add new test class)

- [ ] **Step 1: Write the failing tests**

Append this class to `tests/test_discover_io.py`:

```python
class TestResolvedSourceName:
    def _cfg(self, **kwargs):
        from feather_etl.config import SourceConfig

        return SourceConfig(**kwargs)

    def test_user_name_wins_over_auto(self):
        from feather_etl.config import resolved_source_name

        cfg = self._cfg(type="sqlserver", name="prod-erp", host="db.internal")
        assert resolved_source_name(cfg) == "prod-erp"

    def test_user_name_is_sanitized(self):
        from feather_etl.config import resolved_source_name

        cfg = self._cfg(type="sqlserver", name="prod/erp", host="db.internal")
        assert resolved_source_name(cfg) == "prod_erp"

    def test_sqlserver_auto_uses_type_and_host(self):
        from feather_etl.config import resolved_source_name

        cfg = self._cfg(type="sqlserver", host="192.168.2.62")
        assert resolved_source_name(cfg) == "sqlserver-192.168.2.62"

    def test_sqlserver_auto_sanitizes_host(self):
        from feather_etl.config import resolved_source_name

        cfg = self._cfg(type="sqlserver", host="192.168.2.62:1433")
        assert resolved_source_name(cfg) == "sqlserver-192.168.2.62_1433"

    def test_postgres_auto_uses_type_and_host(self):
        from feather_etl.config import resolved_source_name

        cfg = self._cfg(type="postgres", host="db.internal")
        assert resolved_source_name(cfg) == "postgres-db.internal"

    def test_csv_auto_uses_directory_basename(self, tmp_path):
        from pathlib import Path

        from feather_etl.config import resolved_source_name

        csv_dir = tmp_path / "csv_data"
        csv_dir.mkdir()
        cfg = self._cfg(type="csv", path=csv_dir)
        assert resolved_source_name(cfg) == "csv-csv_data"

    def test_sqlite_auto_uses_file_basename_without_ext(self, tmp_path):
        from feather_etl.config import resolved_source_name

        sqlite_file = tmp_path / "source.sqlite"
        sqlite_file.touch()
        cfg = self._cfg(type="sqlite", path=sqlite_file)
        assert resolved_source_name(cfg) == "sqlite-source"

    def test_duckdb_auto_uses_file_basename_without_ext(self, tmp_path):
        from feather_etl.config import resolved_source_name

        duck_file = tmp_path / "my_data.duckdb"
        duck_file.touch()
        cfg = self._cfg(type="duckdb", path=duck_file)
        assert resolved_source_name(cfg) == "duckdb-my_data"

    def test_excel_auto_uses_file_basename_without_ext(self, tmp_path):
        from feather_etl.config import resolved_source_name

        xl = tmp_path / "sheet.xlsx"
        xl.touch()
        cfg = self._cfg(type="excel", path=xl)
        assert resolved_source_name(cfg) == "excel-sheet"

    def test_json_auto_uses_file_basename_without_ext(self, tmp_path):
        from feather_etl.config import resolved_source_name

        js = tmp_path / "events.json"
        js.touch()
        cfg = self._cfg(type="json", path=js)
        assert resolved_source_name(cfg) == "json-events"

    def test_db_source_without_host_falls_back_to_unknown(self):
        from feather_etl.config import resolved_source_name

        cfg = self._cfg(type="sqlserver", host=None)
        assert resolved_source_name(cfg) == "sqlserver-unknown"

    def test_file_source_without_path_falls_back_to_unknown(self):
        from feather_etl.config import resolved_source_name

        cfg = self._cfg(type="csv", path=None)
        assert resolved_source_name(cfg) == "csv-unknown"
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `uv run pytest tests/test_discover_io.py::TestResolvedSourceName -v`

Expected: FAIL with `ImportError: cannot import name 'resolved_source_name'`.

- [ ] **Step 3: Implement `resolved_source_name`**

Append to `src/feather_etl/config.py`, immediately below `_sanitize`:

```python
def resolved_source_name(cfg: "SourceConfig") -> str:
    """Return the sanitized identity used in discover output filenames.

    If cfg.name is set, sanitize and return it. Otherwise derive:
      - DB sources (sqlserver, postgres): '<type>-<host>'
      - CSV (path is a directory): 'csv-<dirname>'
      - Other file sources (sqlite, duckdb, excel, json): '<type>-<basename-without-ext>'
    Falls back to '<type>-unknown' when the relevant field is missing.
    """
    if cfg.name:
        return _sanitize(cfg.name)

    if cfg.type in FILE_SOURCE_TYPES:
        if cfg.path is None:
            return _sanitize(f"{cfg.type}-unknown")
        if cfg.type == "csv":
            basename = cfg.path.name
        else:
            basename = cfg.path.stem
        return _sanitize(f"{cfg.type}-{basename}")

    # DB source
    host = cfg.host or "unknown"
    return _sanitize(f"{cfg.type}-{host}")
```

Note: `"SourceConfig"` is quoted because the function sits below `SourceConfig`'s definition within the same module; the string annotation avoids any forward-reference issues.

- [ ] **Step 4: Run the tests and verify they pass**

Run: `uv run pytest tests/test_discover_io.py::TestResolvedSourceName -v`

Expected: PASS (all twelve tests).

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest -q`

Expected: all pass (no regressions from the new field or helper).

- [ ] **Step 6: Commit**

```bash
git add src/feather_etl/config.py tests/test_discover_io.py
git commit -m "feat(config): add resolved_source_name helper"
```

---

## Task 4 — Add `schema_output_path()` helper

**Files:**
- Modify: `src/feather_etl/config.py` (add helper below `resolved_source_name`)
- Modify: `tests/test_discover_io.py` (add new test class)

- [ ] **Step 1: Write the failing tests**

Append this class to `tests/test_discover_io.py`:

```python
class TestSchemaOutputPath:
    def _cfg(self, **kwargs):
        from feather_etl.config import SourceConfig

        return SourceConfig(**kwargs)

    def test_db_source_includes_database_suffix(self):
        from pathlib import Path

        from feather_etl.config import schema_output_path

        cfg = self._cfg(type="sqlserver", host="192.168.2.62", database="ZAKYA")
        assert schema_output_path(cfg) == Path("schema_sqlserver-192.168.2.62_ZAKYA.json")

    def test_db_source_sanitizes_database(self):
        from pathlib import Path

        from feather_etl.config import schema_output_path

        cfg = self._cfg(type="sqlserver", host="db.internal", database="My DB")
        assert schema_output_path(cfg) == Path("schema_sqlserver-db.internal_My_DB.json")

    def test_db_source_without_database(self):
        from pathlib import Path

        from feather_etl.config import schema_output_path

        cfg = self._cfg(type="sqlserver", host="db.internal")
        assert schema_output_path(cfg) == Path("schema_sqlserver-db.internal.json")

    def test_file_source_has_no_database_suffix(self, tmp_path):
        from pathlib import Path

        from feather_etl.config import schema_output_path

        sqlite_file = tmp_path / "source.sqlite"
        sqlite_file.touch()
        cfg = self._cfg(type="sqlite", path=sqlite_file)
        assert schema_output_path(cfg) == Path("schema_sqlite-source.json")

    def test_user_name_used_in_path(self):
        from pathlib import Path

        from feather_etl.config import schema_output_path

        cfg = self._cfg(type="sqlserver", name="prod-erp", host="db", database="ZAKYA")
        assert schema_output_path(cfg) == Path("schema_prod-erp_ZAKYA.json")
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `uv run pytest tests/test_discover_io.py::TestSchemaOutputPath -v`

Expected: FAIL with `ImportError: cannot import name 'schema_output_path'`.

- [ ] **Step 3: Implement `schema_output_path`**

Append to `src/feather_etl/config.py`, immediately below `resolved_source_name`:

```python
def schema_output_path(cfg: "SourceConfig") -> Path:
    """Return the target Path for `feather discover` JSON output.

    Format:
      - DB source:   ./schema_<name>_<database>.json
      - File source: ./schema_<name>.json
    """
    parts = [f"schema_{resolved_source_name(cfg)}"]
    if cfg.database:
        parts.append(_sanitize(cfg.database))
    return Path(f"{'_'.join(parts)}.json")
```

- [ ] **Step 4: Run the tests and verify they pass**

Run: `uv run pytest tests/test_discover_io.py::TestSchemaOutputPath -v`

Expected: PASS (all five tests).

- [ ] **Step 5: Run the full helper suite**

Run: `uv run pytest tests/test_discover_io.py -q`

Expected: all pass (20 tests across the three classes).

- [ ] **Step 6: Commit**

```bash
git add src/feather_etl/config.py tests/test_discover_io.py
git commit -m "feat(config): add schema_output_path helper"
```

---

## Task 5 — Rewrite `discover()` CLI command to save JSON

**Files:**
- Modify: `src/feather_etl/cli.py:114-144` (rewrite `discover()`)
- Create: `tests/test_discover.py`

- [ ] **Step 1: Read the current `discover()` implementation**

Read [src/feather_etl/cli.py:114-144](../../../src/feather_etl/cli.py#L114-L144) to confirm the exact current structure. Expected shape (from the spec):

```python
@app.command()
def discover(ctx: typer.Context, config: Path = typer.Option("feather.yaml", "--config")) -> None:
    """List tables and columns available in the configured source."""
    from feather_etl.sources.registry import create_source

    cfg = _load_and_validate(config)
    source = create_source(cfg.source)

    if not source.check():
        typer.echo("Source connection failed.", err=True)
        raise typer.Exit(code=2)

    schemas = source.discover()
    if _is_json(ctx):
        emit(
            [ {"table_name": s.name, "columns": [{"name": c[0], "type": c[1]} for c in s.columns]} for s in schemas ],
            json_mode=True,
        )
    else:
        typer.echo(f"Found {len(schemas)} table(s):\n")
        for s in schemas:
            typer.echo(f"  {s.name}")
            for col_name, col_type in s.columns:
                typer.echo(f"    {col_name}: {col_type}")
            typer.echo()
```

- [ ] **Step 2: Write the failing end-to-end test**

Create `tests/test_discover.py`:

```python
"""End-to-end tests for `feather discover`."""

import json
import shutil
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from tests.conftest import FIXTURES_DIR

runner = CliRunner()


def _write_sqlite_config(tmp_path: Path, source_name: str | None = None) -> Path:
    """Set up a tmp SQLite feather project. Returns config path."""
    shutil.copy2(FIXTURES_DIR / "sample_erp.sqlite", tmp_path / "source.sqlite")
    source: dict = {"type": "sqlite", "path": "./source.sqlite"}
    if source_name is not None:
        source["name"] = source_name
    cfg = {
        "source": source,
        "destination": {"path": "./feather_data.duckdb"},
        "tables": [
            {
                "name": "orders",
                "source_table": "orders",
                "target_table": "bronze.orders",
                "strategy": "full",
            }
        ],
    }
    config_path = tmp_path / "feather.yaml"
    config_path.write_text(yaml.dump(cfg))
    return config_path


class TestDiscoverSavesJson:
    def test_writes_auto_named_file_for_sqlite(self, tmp_path: Path, monkeypatch):
        from feather_etl.cli import app

        config_path = _write_sqlite_config(tmp_path)
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["discover", "--config", str(config_path)])
        assert result.exit_code == 0, result.output

        expected = tmp_path / "schema_sqlite-source.json"
        assert expected.exists()

    def test_prints_single_summary_line(self, tmp_path: Path, monkeypatch):
        from feather_etl.cli import app

        config_path = _write_sqlite_config(tmp_path)
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["discover", "--config", str(config_path)])
        assert result.exit_code == 0

        # Exactly one non-empty line of output; it mentions the file path.
        lines = [line for line in result.output.splitlines() if line.strip()]
        assert len(lines) == 1
        assert "schema_sqlite-source.json" in lines[0]
        assert "Wrote" in lines[0]

    def test_json_payload_has_expected_shape(self, tmp_path: Path, monkeypatch):
        from feather_etl.cli import app

        config_path = _write_sqlite_config(tmp_path)
        monkeypatch.chdir(tmp_path)

        runner.invoke(app, ["discover", "--config", str(config_path)])

        payload = json.loads((tmp_path / "schema_sqlite-source.json").read_text())
        assert isinstance(payload, list)
        assert len(payload) > 0
        assert set(payload[0].keys()) == {"table_name", "columns"}
        assert isinstance(payload[0]["columns"], list)
        if payload[0]["columns"]:
            assert set(payload[0]["columns"][0].keys()) == {"name", "type"}

    def test_user_name_overrides_auto_derivation(self, tmp_path: Path, monkeypatch):
        from feather_etl.cli import app

        config_path = _write_sqlite_config(tmp_path, source_name="prod-erp")
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["discover", "--config", str(config_path)])
        assert result.exit_code == 0
        assert (tmp_path / "schema_prod-erp.json").exists()
        assert not (tmp_path / "schema_sqlite-source.json").exists()

    def test_user_name_with_unsafe_chars_is_sanitized(self, tmp_path: Path, monkeypatch):
        from feather_etl.cli import app

        config_path = _write_sqlite_config(tmp_path, source_name="prod/erp")
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["discover", "--config", str(config_path)])
        assert result.exit_code == 0
        assert (tmp_path / "schema_prod_erp.json").exists()

    def test_silent_overwrite_on_second_run(self, tmp_path: Path, monkeypatch):
        from feather_etl.cli import app

        config_path = _write_sqlite_config(tmp_path)
        monkeypatch.chdir(tmp_path)

        r1 = runner.invoke(app, ["discover", "--config", str(config_path)])
        assert r1.exit_code == 0
        first_mtime = (tmp_path / "schema_sqlite-source.json").stat().st_mtime_ns

        r2 = runner.invoke(app, ["discover", "--config", str(config_path)])
        assert r2.exit_code == 0
        second_mtime = (tmp_path / "schema_sqlite-source.json").stat().st_mtime_ns
        # File was re-written — mtime should be >= first (typically strictly greater).
        assert second_mtime >= first_mtime

    def test_zero_tables_writes_empty_array(self, tmp_path: Path, monkeypatch):
        """An empty source still produces a valid file with '[]' content."""
        import sqlite3

        from feather_etl.cli import app

        # Create an empty SQLite DB (no tables) at the expected path.
        empty_db = tmp_path / "source.sqlite"
        conn = sqlite3.connect(empty_db)
        conn.close()

        cfg = {
            "source": {"type": "sqlite", "path": "./source.sqlite"},
            "destination": {"path": "./feather_data.duckdb"},
            "tables": [
                {
                    "name": "placeholder",
                    "source_table": "sqlite_master",
                    "target_table": "bronze.placeholder",
                    "strategy": "full",
                }
            ],
        }
        config_path = tmp_path / "feather.yaml"
        config_path.write_text(yaml.dump(cfg))
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["discover", "--config", str(config_path)])
        assert result.exit_code == 0, result.output

        out = tmp_path / "schema_sqlite-source.json"
        assert out.exists()
        assert json.loads(out.read_text()) == []
        assert "Wrote 0 table(s)" in result.output
```

If `source.discover()` on an empty SQLite DB turns out to raise (rather than return an empty list), document that in this task's step and either (a) adjust the test to assert the error is caught and a zero-table file is still written, or (b) skip this test with a `pytest.skip(reason="source.discover() cannot handle zero-table schemas yet")` and file a follow-up issue. Do not fabricate a pass.

- [ ] **Step 3: Run the tests and verify they fail**

Run: `uv run pytest tests/test_discover.py -v`

Expected: FAIL — tests will fail on assertions about the file existing (current `discover` prints to stdout, doesn't write a file).

- [ ] **Step 4: Rewrite `discover()` in `src/feather_etl/cli.py`**

Replace the body of `discover()` (around lines 114-144). The imports at the top of `cli.py` may already include `json` — if not, add it. Also add `schema_output_path` to the existing `from feather_etl.config import ...` line (or add an import near the top of `cli.py` at the top-level imports section). Keep the `from feather_etl.sources.registry import create_source` as a local import inside the function (matches existing style).

```python
@app.command()
def discover(ctx: typer.Context, config: Path = typer.Option("feather.yaml", "--config")) -> None:
    """Save source schema (tables + columns) to an auto-named JSON file in the current directory."""
    import json

    from feather_etl.config import schema_output_path
    from feather_etl.sources.registry import create_source

    cfg = _load_and_validate(config)
    source = create_source(cfg.source)

    if not source.check():
        typer.echo("Source connection failed.", err=True)
        raise typer.Exit(code=2)

    schemas = source.discover()
    payload = [
        {
            "table_name": s.name,
            "columns": [{"name": c[0], "type": c[1]} for c in s.columns],
        }
        for s in schemas
    ]
    out_path = schema_output_path(cfg.source)
    out_path.write_text(json.dumps(payload, indent=2))
    typer.echo(f"Wrote {len(schemas)} table(s) to ./{out_path}")
```

Notes:
- The `ctx` parameter is retained for Typer signature compatibility even though `_is_json(ctx)` is no longer consulted — Typer inspects command signatures so leaving it matches other commands in the file.
- `./{out_path}` keeps the leading `./` for display (matches the spec's example output).
- `out_path` is relative; Python writes to CWD, which matches "current directory" in the spec.

- [ ] **Step 5: Run the discover tests and verify they pass**

Run: `uv run pytest tests/test_discover.py -v`

Expected: PASS (all six tests).

- [ ] **Step 6: Run the full test suite and check for regressions**

Run: `uv run pytest -q`

Expected: all pass. If existing tests in `test_cli.py` or `test_json_output.py` assert on the *old* discover stdout, update them to match the new contract (single summary line) — not by grepping for table names, but by asserting the file was written. If you find such tests, add a `test_cli.py` / `test_json_output.py` edit here as a sub-step and re-run the suite.

- [ ] **Step 7: Commit**

```bash
git add src/feather_etl/cli.py tests/test_discover.py
git commit -m "feat(cli): discover saves JSON to auto-named file (closes #16)"
```

---

## Task 6 — Delete discover assertions from `scripts/hands_on_test.sh`

**Files:**
- Modify: `scripts/hands_on_test.sh` (remove S4 block, S15 discover lines, S17 discover lines)

- [ ] **Step 1: Read the current file around the three targets**

Confirm the line numbers by reading:

```bash
sed -n '213,230p' scripts/hands_on_test.sh    # S4 block
sed -n '631,638p' scripts/hands_on_test.sh    # S15 discover assertion
sed -n '699,706p' scripts/hands_on_test.sh    # S17 discover assertion
```

If line numbers drifted (e.g. prior tasks touched the file), adjust below.

- [ ] **Step 2: Delete S4 entirely**

Remove lines 213-229 (the S4 header comment block, `yellow` banner, and all three `check` assertions plus the trailing `echo ""`):

```
# ---------------------------------------------------------------------------
# S4 — feather discover (client fixture)
# ---------------------------------------------------------------------------
yellow "--- S4: feather discover ---"
out=$("$FEATHER" discover --config "$S2/feather.yaml" 2>&1)
echo "$out" | grep -q "Found 6 table" \
    && check "discover finds 6 icube tables" ok \
    || check "discover finds 6 icube tables" fail
echo "$out" | grep -q "icube.SALESINVOICE" \
    && check "discover shows icube.SALESINVOICE" ok \
    || check "discover shows icube.SALESINVOICE" fail
echo "$out" | grep -q "ModifiedDate" \
    && check "discover shows columns" ok \
    || check "discover shows columns" fail

echo ""
```

Expected line count change: −17 lines (including the blank line after `echo ""`). Subsequent scenario numbers (S5, S6, …) are **not** renumbered — the gap is fine and preserves git blame history.

- [ ] **Step 3: Delete the S15 discover block (4 lines, ~line 633-636 before S4 removal shifted them)**

Remove the 4 lines in the S15 scenario:

```
discover_out=$("$FEATHER" discover --config "$S15/feather.yaml" 2>&1) || true
echo "$discover_out" | grep -q "orders.csv" \
    && check "csv discover finds orders.csv" ok \
    || check "csv discover finds orders.csv" fail
```

Keep the blank line below it (before the `run_out=…` block) so S15 still reads cleanly.

- [ ] **Step 4: Delete the S17 discover block (4 lines, ~line 701-704 before prior removals shifted them)**

Remove the 4 lines in the S17 scenario:

```
discover_out=$("$FEATHER" discover --config "$S17/feather.yaml" 2>&1) || true
echo "$discover_out" | grep -q "orders" \
    && check "sqlite discover finds orders table" ok \
    || check "sqlite discover finds orders table" fail
```

Keep the blank line below it.

- [ ] **Step 5: Update the S15 and S17 scenario header comments**

The S15 banner currently reads:

```
# S15 — CSV source: validate, discover, run
yellow "--- S15: CSV source validate + discover + run ---"
```

Change to (remove "discover" from the scenario description):

```
# S15 — CSV source: validate, run
yellow "--- S15: CSV source validate + run ---"
```

Likewise for S17:

```
# S17 — SQLite source: validate, discover, run
yellow "--- S17: SQLite source validate + discover + run ---"
```

becomes:

```
# S17 — SQLite source: validate, run
yellow "--- S17: SQLite source validate + run ---"
```

- [ ] **Step 6: Run the shell suite to make sure the rest still works**

Run: `bash scripts/hands_on_test.sh`

Expected: runs to completion with a passing summary; check count reduces by 5 (3 from S4 + 1 from S15 + 1 from S17). Old expected: 72 checks. New expected: 67 checks.

If the script errors out because something depended on `$S2/feather.yaml` having been discovered-upon, look upstream — S4 didn't mutate anything, so this should not happen. Investigate before proceeding.

- [ ] **Step 7: Update the file-wide check count reference in the project docs**

Two locations document the current count:

- `CLAUDE.md` — line that mentions "currently: 72 checks" (search with `grep -n "72 checks" CLAUDE.md`).
- `.claude/rules/feather-etl-project.md` — same line.

Update both to the new count (67).

- [ ] **Step 8: Commit**

```bash
git add scripts/hands_on_test.sh CLAUDE.md .claude/rules/feather-etl-project.md
git commit -m "test: migrate discover coverage from hands_on_test.sh to pytest"
```

---

## Task 7 — Final verification

- [ ] **Step 1: Run the full pytest suite**

Run: `uv run pytest -q`

Expected: all pass. New tests added — `test_discover_io.py` (20 cases) and `test_discover.py` (7 cases including zero-tables). Plus 2 new `test_config` name cases. Delta = +29 tests. Starting point was 341; new count should be ~370 (report the exact number).

- [ ] **Step 2: Run the shell integration suite**

Run: `bash scripts/hands_on_test.sh`

Expected: passes with 67 checks.

- [ ] **Step 3: Exercise the CLI by hand**

```bash
cd /tmp && rm -rf /tmp/discover-smoke && mkdir /tmp/discover-smoke && cd /tmp/discover-smoke
cp /Users/siraj/Desktop/NonDropBoxProjects/feather-etl/tests/fixtures/sample_erp.sqlite source.sqlite
cat > feather.yaml <<'YAML'
source:
  type: sqlite
  path: ./source.sqlite
destination:
  path: ./feather_data.duckdb
tables:
  - name: orders
    source_table: orders
    target_table: bronze.orders
    strategy: full
YAML
uv run --directory /Users/siraj/Desktop/NonDropBoxProjects/feather-etl feather discover --config /tmp/discover-smoke/feather.yaml
ls /tmp/discover-smoke/schema_*.json
cat /tmp/discover-smoke/schema_sqlite-source.json | head -20
```

Expected: one-line summary like `Wrote 3 table(s) to ./schema_sqlite-source.json`, file exists, content is pretty-printed JSON with `table_name` / `columns` structure.

- [ ] **Step 4: Final lint check**

Run: `ruff check .` then `ruff format --check .`

Expected: clean on both.

- [ ] **Step 5: Skim the git log for this feature**

Run: `git log --oneline main..HEAD` (or the relevant range)

Expected: 6 commits, each atomic — one per task, readable without reference to the plan.

---

## Out of Scope (from spec's "Follow-ups")

Do **not** do these in this plan — open separate issues:

1. Persist the auto-derived `source.name` back into `feather.yaml` via `feather validate --fix` (or similar config-mutation command).
2. Build the HTML schema viewer that consumes `schema_*.json`.
3. Full removal of `scripts/hands_on_test.sh` — migrate remaining scenarios as they're touched by future work.
