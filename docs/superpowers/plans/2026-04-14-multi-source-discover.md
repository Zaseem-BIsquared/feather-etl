# Multi-source `discover` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `sources:` list YAML schema and make `feather discover` iterate every source, auto-enumerate SQL Server / Postgres databases, persist resumable state across runs, and detect source renames without losing prior history.

**Architecture:** Five sequential commits, each green-on-its-own:
1. **C2 refactor** — each `Source` subclass owns its own YAML parsing (`from_yaml`) and identifier rules (`validate_source_table`). `registry.py` becomes a lazy `type→class` import map. `SourceConfig` dataclass is deleted; `FeatherConfig.source` becomes a live `Source` instance. Singular `source:` still works so the suite stays green.
2. **Schema flip** — top-level YAML changes from `source:` to `sources:` (list). `FeatherConfig.sources: list[Source]`. Singular `source:` raises a hard migration error. All inline test configs, `pipeline.py`, `init_wizard.py`, and non-discover commands updated; non-discover commands gain a multi-source guard (exit 2 when `len > 1`).
3. **Discover iterates** — rewrite `commands/discover.py` to loop over `cfg.sources`, auto-enumerate databases when a DB source lacks `database`/`databases`, write one `schema_<name>.json` per source, continue on per-source failure, exit 2 if any failed.
4. **State + flags** — new `src/feather_etl/discover_state.py` owns `feather_discover_state.json` I/O and entry classification (`ok` / `failed` / `removed`). Discover gains `--refresh`, `--retry-failed`, `--prune`. Default = resume.
5. **Rename detection** — fingerprint per state entry (`type+host+port+database` for DB, `type+abs_path` for file). On YAML rename, TTY prompts `[Y/n]`; non-TTY exits 3. Flags `--yes` / `--no-renames`. Migration moves state entries and renames JSON files on disk (including auto-enumerated children).

**Tech Stack:** Python ≥3.10, `dataclasses`, `pathlib.Path`, `typing.Protocol` / `ClassVar`, `importlib`, `json`, `yaml`, Typer + `typer.testing.CliRunner`, pytest. SQL Server via `pyodbc`, Postgres via `psycopg2`. `pg_ctl` is the integration-test stand-in for SQL Server multi-database scenarios (Postgres has the equivalent `pg_database` concept).

**Source spec:** [docs/superpowers/specs/2026-04-14-multi-source-discover-design.md](../specs/2026-04-14-multi-source-discover-design.md).

**Naming notes:**
- File source types in the codebase are `{"duckdb", "sqlite", "csv", "excel", "json"}`. CSV/Excel/JSON `path` is a **directory**; `sqlite`/`duckdb` `path` is a **file** (validated at [config.py:233-240](../../../src/feather_etl/config.py#L233-L240)).
- Inline test configs (no `tests/fixtures/*.yaml` files exist — every config is built in-Python via `yaml.dump`). Migration touches Python source, not YAML files on disk.
- `pg_ctl` is started in [tests/conftest.py:11-20](../../../tests/conftest.py#L11-L20). Multi-database Postgres tests can `CREATE DATABASE` on the running cluster.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `src/feather_etl/sources/__init__.py` | `Source` Protocol, `StreamSchema`, `ChangeResult` | Add `from_yaml`, `validate_source_table` to Protocol; add `type: ClassVar[str]` and `name: str` attrs. |
| `src/feather_etl/sources/registry.py` | Type→class map | Replace `create_source()` with lazy `get_source_class()` (string-path imports). |
| `src/feather_etl/sources/sqlserver.py` | SQL Server source | Add `from_yaml`, `validate_source_table`, `databases: list[str] \| None` ctor param, `list_databases()`. |
| `src/feather_etl/sources/postgres.py` | Postgres source | Same shape as sqlserver. |
| `src/feather_etl/sources/{csv,sqlite,duckdb_file,excel,json_source}.py` | File sources | Each gains `from_yaml`, `validate_source_table`. |
| `src/feather_etl/config.py` | YAML loader + dataclasses | Delete `SourceConfig`, `DB_CONNECTION_BUILDERS`, `FILE_SOURCE_TYPES`. `FeatherConfig.sources: list[Source]`. Singular `source:` → migration error. Name-uniqueness + auto-derive rules. |
| `src/feather_etl/commands/discover.py` | `feather discover` | Full rewrite: iterate sources, classify via state, auto-enumerate, format output, handle exit codes 0/2/3. |
| `src/feather_etl/discover_state.py` (**new**) | State file I/O + classification + rename inference | Pure-Python module — no Typer, no I/O on imports. |
| `src/feather_etl/commands/{validate,run,status,history,setup,init}.py` | Single-source commands | Multi-source guard (exit 2 with migration message) + `cfg.sources[0]` reads. |
| `src/feather_etl/pipeline.py` | `run_all` orchestration | Read `cfg.sources[0]` until B2 ships. |
| `src/feather_etl/init_wizard.py` | `feather init` template | Emit `sources:` list (single entry). |
| `tests/test_config.py` | Config tests | Migration-error test, name-uniqueness, XOR rules. |
| `tests/test_sqlserver.py` | SQL Server tests | `from_yaml`, `list_databases`, XOR validation, `validate_source_table`. |
| `tests/test_postgres.py` | Postgres tests | Same shape. |
| `tests/test_csv_glob.py` / `test_excel.py` / `test_json.py` / `test_sources.py` | File-source tests | `from_yaml` + `validate_source_table` per source. |
| `tests/test_discover_state.py` (**new**) | Unit tests for `discover_state` module | Read/write, classify, fingerprint, rename inference. |
| `tests/commands/test_discover.py` | Discover command tests | Edge cases per [spec §8.3](../specs/2026-04-14-multi-source-discover-design.md#83-edge-cases-—-in-per-code-unit-files): state I/O, flags, rename UX. |
| `tests/commands/test_discover_multi_source.py` (**new**) | Happy-path E2E | The 8 scenarios in [spec §8.2](../specs/2026-04-14-multi-source-discover-design.md#82-new-file-—-testscommandstest_discover_multi_sourcepy). |
| `tests/commands/conftest.py` | Shared CLI fixtures | Add `multi_source_yaml(tmp_path, sources=[...])` helper. |
| `tests/conftest.py` | Suite-wide fixtures | Update `config_path` fixture to emit `sources:` list (Phase 2). |
| `docs/CONTRIBUTING.md` | Conventions | Add §8.1 testing-co-location principle. |
| `README.md`, `docs/prd.md` | Examples | `source:` → `sources:` in every example. |

---

# Phase 1 — Source class self-description (commit 1)

After this phase: every source class self-describes via `from_yaml`. `registry.py` is lazy. `config.py` shrinks. `SourceConfig` is gone. **Singular `source:` still parses** so the entire existing suite stays green.

## Task 1.1 — Extend `Source` Protocol

**Files:**
- Modify: [src/feather_etl/sources/__init__.py:30-50](../../../src/feather_etl/sources/__init__.py#L30-L50)
- Modify: [tests/test_sources.py](../../../tests/test_sources.py)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sources.py` (create a new class at the bottom of the file):

```python
from typing import get_type_hints


class TestSourceProtocol:
    def test_protocol_has_from_yaml_and_validate_source_table(self):
        from feather_etl.sources import Source

        assert hasattr(Source, "from_yaml")
        assert hasattr(Source, "validate_source_table")

    def test_each_source_class_declares_type_attr(self):
        from feather_etl.sources.csv import CsvSource
        from feather_etl.sources.duckdb_file import DuckDBFileSource
        from feather_etl.sources.excel import ExcelSource
        from feather_etl.sources.json_source import JsonSource
        from feather_etl.sources.postgres import PostgresSource
        from feather_etl.sources.sqlite import SqliteSource
        from feather_etl.sources.sqlserver import SqlServerSource

        assert CsvSource.type == "csv"
        assert DuckDBFileSource.type == "duckdb"
        assert ExcelSource.type == "excel"
        assert JsonSource.type == "json"
        assert PostgresSource.type == "postgres"
        assert SqliteSource.type == "sqlite"
        assert SqlServerSource.type == "sqlserver"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_sources.py::TestSourceProtocol -v`
Expected: FAIL — `Source` has no `from_yaml`; classes have no `type`.

- [ ] **Step 3: Update the Protocol**

Replace `src/feather_etl/sources/__init__.py:30-50` with:

```python
from typing import ClassVar, Protocol


class Source(Protocol):
    """Any class with these methods is a valid feather-etl source."""

    name: str
    type: ClassVar[str]

    @classmethod
    def from_yaml(cls, entry: dict, config_dir: Path) -> "Source":
        """Parse one `sources:` list entry and return a configured instance.

        All per-type rules live here: port defaults, connection-string template,
        path resolution, database/databases XOR validation. Side-effect free —
        does not open connections.
        """
        ...

    def validate_source_table(self, source_table: str) -> list[str]:
        """Return error messages for this source_table string. Empty list = valid."""
        ...

    def check(self) -> bool: ...

    def discover(self) -> list[StreamSchema]: ...

    def extract(
        self,
        table: str,
        columns: list[str] | None = None,
        filter: str | None = None,
        watermark_column: str | None = None,
        watermark_value: str | None = None,
    ) -> pa.Table: ...

    def detect_changes(
        self, table: str, last_state: dict[str, object] | None = None
    ) -> ChangeResult: ...

    def get_schema(self, table: str) -> list[tuple[str, str]]: ...
```

Add `from pathlib import Path` to the import block at the top of the file.

The `type` ClassVar and `from_yaml`/`validate_source_table` are added concretely on each subclass in Tasks 1.2–1.6 — Step 2 here only fails because no class declares `type` yet.

- [ ] **Step 4: Stop. Tests still fail until Tasks 1.2–1.6 land. Continue to Task 1.2.**

---

## Task 1.2 — `SqlServerSource.from_yaml` + `databases` param + `validate_source_table`

**Files:**
- Modify: [src/feather_etl/sources/sqlserver.py](../../../src/feather_etl/sources/sqlserver.py)
- Modify: [tests/test_sqlserver.py](../../../tests/test_sqlserver.py)

- [ ] **Step 1: Write failing tests**

Append a new class to `tests/test_sqlserver.py`:

```python
class TestSqlServerFromYaml:
    def test_minimal_db_entry_builds_connection_string(self):
        from feather_etl.sources.sqlserver import SqlServerSource

        entry = {
            "name": "erp",
            "type": "sqlserver",
            "host": "db.example.com",
            "user": "u",
            "password": "p",
            "database": "SALES",
        }
        src = SqlServerSource.from_yaml(entry, Path("."))
        assert src.name == "erp"
        assert src.host == "db.example.com"
        assert src.port == 1433
        assert src.database == "SALES"
        assert src.databases is None
        assert "SERVER=db.example.com,1433" in src.connection_string
        assert "DATABASE=SALES" in src.connection_string

    def test_explicit_port(self):
        from feather_etl.sources.sqlserver import SqlServerSource

        entry = {"name": "erp", "type": "sqlserver", "host": "h",
                 "port": 1444, "user": "u", "password": "p", "database": "X"}
        src = SqlServerSource.from_yaml(entry, Path("."))
        assert src.port == 1444
        assert "SERVER=h,1444" in src.connection_string

    def test_databases_list(self):
        from feather_etl.sources.sqlserver import SqlServerSource

        entry = {"name": "erp", "type": "sqlserver", "host": "h",
                 "user": "u", "password": "p", "databases": ["A", "B"]}
        src = SqlServerSource.from_yaml(entry, Path("."))
        assert src.database is None
        assert src.databases == ["A", "B"]

    def test_database_xor_databases_both(self):
        from feather_etl.sources.sqlserver import SqlServerSource

        entry = {"name": "erp", "type": "sqlserver", "host": "h",
                 "user": "u", "password": "p", "database": "A",
                 "databases": ["B"]}
        with pytest.raises(ValueError, match="mutually exclusive"):
            SqlServerSource.from_yaml(entry, Path("."))

    def test_databases_empty_list(self):
        from feather_etl.sources.sqlserver import SqlServerSource

        entry = {"name": "erp", "type": "sqlserver", "host": "h",
                 "user": "u", "password": "p", "databases": []}
        with pytest.raises(ValueError, match="non-empty"):
            SqlServerSource.from_yaml(entry, Path("."))

    def test_explicit_connection_string_overrides(self):
        from feather_etl.sources.sqlserver import SqlServerSource

        entry = {"name": "erp", "type": "sqlserver",
                 "connection_string": "DRIVER={X};SERVER=raw"}
        src = SqlServerSource.from_yaml(entry, Path("."))
        assert src.connection_string == "DRIVER={X};SERVER=raw"


class TestSqlServerValidateSourceTable:
    def test_schema_dot_table_ok(self):
        from feather_etl.sources.sqlserver import SqlServerSource

        src = SqlServerSource(connection_string="dummy", name="x")
        assert src.validate_source_table("dbo.MyTable") == []

    def test_plain_table_ok(self):
        from feather_etl.sources.sqlserver import SqlServerSource

        src = SqlServerSource(connection_string="dummy", name="x")
        assert src.validate_source_table("MyTable") == []
```

Add `from pathlib import Path` and `import pytest` to the test module imports if not already present.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_sqlserver.py::TestSqlServerFromYaml tests/test_sqlserver.py::TestSqlServerValidateSourceTable -v`
Expected: FAIL — `from_yaml` and `validate_source_table` don't exist.

- [ ] **Step 3: Implement**

Edit `src/feather_etl/sources/sqlserver.py`:

Add at the top of the module (under existing imports):

```python
from pathlib import Path
from typing import ClassVar
```

Replace the `class SqlServerSource(DatabaseSource):` definition's `__init__` and add `type` / `from_yaml` / `list_databases` (stub) / `validate_source_table`:

```python
_SQLSERVER_CONN_TEMPLATE = (
    "DRIVER={{ODBC Driver 18 for SQL Server}};"
    "SERVER={host},{port};DATABASE={database};UID={user};PWD={password};"
    "TrustServerCertificate=yes"
)


class SqlServerSource(DatabaseSource):
    """Source that reads tables from SQL Server via pyodbc."""

    type: ClassVar[str] = "sqlserver"

    def __init__(
        self,
        connection_string: str,
        *,
        name: str = "",
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str | None = None,
        databases: list[str] | None = None,
        batch_size: int = 120_000,
    ) -> None:
        super().__init__(connection_string)
        self.name = name
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.databases = databases
        self.batch_size = batch_size
        self._last_error: str | None = None

    @classmethod
    def from_yaml(cls, entry: dict, config_dir: Path) -> "SqlServerSource":
        name = entry.get("name", "")
        explicit_conn = entry.get("connection_string")
        host = entry.get("host")
        port = entry.get("port", 1433)
        user = entry.get("user")
        password = entry.get("password")
        database = entry.get("database")
        databases = entry.get("databases")

        if database is not None and databases is not None:
            raise ValueError(
                "database and databases are mutually exclusive; use one."
            )
        if databases is not None and not databases:
            raise ValueError("databases list must be non-empty.")

        if explicit_conn:
            conn_str = explicit_conn
        elif host:
            conn_str = _SQLSERVER_CONN_TEMPLATE.format(
                host=host,
                port=port,
                database=database or "",
                user=user or "",
                password=password or "",
            )
        else:
            raise ValueError(
                "sqlserver source requires either 'connection_string' or "
                "'host' (with user/password/database)."
            )

        return cls(
            connection_string=conn_str,
            name=name,
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            databases=databases,
        )

    def validate_source_table(self, source_table: str) -> list[str]:
        # SQL Server: lenient — allow 'schema.table' or 'table'. Real
        # validation happens at extract time when the server rejects bad SQL.
        return []

    def list_databases(self) -> list[str]:
        """Stub — implemented in Task 1.3."""
        raise NotImplementedError
```

Then leave the existing `_format_watermark`, `check`, `discover`, `get_schema`, `extract`, `detect_changes` methods untouched.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_sqlserver.py -v`
Expected: PASS for new classes; existing `TestDatabaseSourceFormatWatermark` and other classes also still pass.

- [ ] **Step 5: Commit**

```bash
git add src/feather_etl/sources/sqlserver.py tests/test_sqlserver.py
git commit -m "refactor(sources): SqlServerSource self-describes via from_yaml"
```

---

## Task 1.3 — `SqlServerSource.list_databases()`

**Files:**
- Modify: [src/feather_etl/sources/sqlserver.py](../../../src/feather_etl/sources/sqlserver.py)
- Modify: [tests/test_sqlserver.py](../../../tests/test_sqlserver.py)

- [ ] **Step 1: Write failing test**

Append to `tests/test_sqlserver.py`:

```python
class TestSqlServerListDatabases:
    def test_query_filters_system_dbs(self, monkeypatch):
        """Should run a query against sys.databases excluding master/tempdb/model/msdb."""
        from feather_etl.sources import sqlserver as ss

        captured_sql: list[str] = []

        class FakeCursor:
            def execute(self, sql, *_):
                captured_sql.append(sql)

            def fetchall(self):
                return [("SALES",), ("INVENTORY",), ("HR",)]

            def close(self):
                pass

        class FakeConn:
            def cursor(self):
                return FakeCursor()

            def close(self):
                pass

        monkeypatch.setattr(ss.pyodbc, "connect", lambda *a, **k: FakeConn())

        src = ss.SqlServerSource(connection_string="dummy", name="x")
        result = src.list_databases()

        assert result == ["SALES", "INVENTORY", "HR"]
        assert "sys.databases" in captured_sql[0]
        for sysdb in ("master", "tempdb", "model", "msdb"):
            assert f"'{sysdb}'" in captured_sql[0]

    def test_propagates_pyodbc_error(self, monkeypatch):
        from feather_etl.sources import sqlserver as ss

        def raise_(*a, **k):
            raise ss.pyodbc.Error("Login failed")

        monkeypatch.setattr(ss.pyodbc, "connect", raise_)
        src = ss.SqlServerSource(connection_string="dummy", name="x")
        with pytest.raises(ss.pyodbc.Error):
            src.list_databases()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_sqlserver.py::TestSqlServerListDatabases -v`
Expected: FAIL — `NotImplementedError`.

- [ ] **Step 3: Implement**

Replace the `list_databases` stub in `src/feather_etl/sources/sqlserver.py` with:

```python
    def list_databases(self) -> list[str]:
        """Return user databases on the server (excludes master, tempdb, model, msdb)."""
        con = pyodbc.connect(self.connection_string, timeout=10)
        try:
            cursor = con.cursor()
            cursor.execute(
                "SELECT name FROM sys.databases "
                "WHERE name NOT IN ('master', 'tempdb', 'model', 'msdb') "
                "ORDER BY name"
            )
            rows = cursor.fetchall()
            cursor.close()
            return [r[0] for r in rows]
        finally:
            con.close()
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_sqlserver.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/feather_etl/sources/sqlserver.py tests/test_sqlserver.py
git commit -m "feat(sources): SqlServerSource.list_databases enumerates non-system DBs"
```

---

## Task 1.4 — `PostgresSource.from_yaml` + `databases` param + `validate_source_table`

**Files:**
- Modify: [src/feather_etl/sources/postgres.py](../../../src/feather_etl/sources/postgres.py)
- Modify: [tests/test_postgres.py](../../../tests/test_postgres.py)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_postgres.py`:

```python
class TestPostgresFromYaml:
    def test_minimal_entry_builds_conn_string(self):
        from pathlib import Path

        from feather_etl.sources.postgres import PostgresSource

        entry = {"name": "wh", "type": "postgres", "host": "db.example.com",
                 "user": "u", "password": "p", "database": "warehouse"}
        src = PostgresSource.from_yaml(entry, Path("."))
        assert src.name == "wh"
        assert src.host == "db.example.com"
        assert src.port == 5432
        assert src.database == "warehouse"
        assert "host=db.example.com" in src.connection_string
        assert "port=5432" in src.connection_string
        assert "dbname=warehouse" in src.connection_string

    def test_explicit_port(self):
        from pathlib import Path

        from feather_etl.sources.postgres import PostgresSource

        entry = {"name": "wh", "type": "postgres", "host": "h", "port": 5499,
                 "user": "u", "password": "p", "database": "X"}
        src = PostgresSource.from_yaml(entry, Path("."))
        assert src.port == 5499
        assert "port=5499" in src.connection_string

    def test_databases_list_and_xor_rules(self):
        from pathlib import Path

        from feather_etl.sources.postgres import PostgresSource

        ok = {"name": "wh", "type": "postgres", "host": "h",
              "user": "u", "password": "p", "databases": ["A", "B"]}
        src = PostgresSource.from_yaml(ok, Path("."))
        assert src.databases == ["A", "B"]

        with pytest.raises(ValueError, match="mutually exclusive"):
            PostgresSource.from_yaml(
                {**ok, "database": "C"}, Path(".")
            )

        with pytest.raises(ValueError, match="non-empty"):
            PostgresSource.from_yaml(
                {**ok, "databases": []}, Path(".")
            )


class TestPostgresValidateSourceTable:
    def test_schema_dot_table_ok(self):
        from feather_etl.sources.postgres import PostgresSource

        src = PostgresSource(connection_string="dummy", name="x")
        assert src.validate_source_table("public.orders") == []

    def test_plain_table_ok(self):
        from feather_etl.sources.postgres import PostgresSource

        src = PostgresSource(connection_string="dummy", name="x")
        assert src.validate_source_table("orders") == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_postgres.py::TestPostgresFromYaml tests/test_postgres.py::TestPostgresValidateSourceTable -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

Edit `src/feather_etl/sources/postgres.py`. Add at top:

```python
from pathlib import Path
from typing import ClassVar
```

Add module-level template:

```python
_PG_CONN_TEMPLATE = (
    "host={host} port={port} dbname={database} user={user} password={password}"
)
```

Replace the `class PostgresSource(DatabaseSource):` definition's `__init__` and add the new pieces (other methods stay unchanged):

```python
class PostgresSource(DatabaseSource):
    """Source that reads tables from PostgreSQL via psycopg2."""

    type: ClassVar[str] = "postgres"

    def __init__(
        self,
        connection_string: str,
        *,
        name: str = "",
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str | None = None,
        databases: list[str] | None = None,
        batch_size: int = 120_000,
    ) -> None:
        super().__init__(connection_string)
        self.name = name
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.databases = databases
        self.batch_size = batch_size
        self._last_error: str | None = None

    @classmethod
    def from_yaml(cls, entry: dict, config_dir: Path) -> "PostgresSource":
        name = entry.get("name", "")
        explicit_conn = entry.get("connection_string")
        host = entry.get("host")
        port = entry.get("port", 5432)
        user = entry.get("user")
        password = entry.get("password")
        database = entry.get("database")
        databases = entry.get("databases")

        if database is not None and databases is not None:
            raise ValueError(
                "database and databases are mutually exclusive; use one."
            )
        if databases is not None and not databases:
            raise ValueError("databases list must be non-empty.")

        if explicit_conn:
            conn_str = explicit_conn
        elif host:
            conn_str = _PG_CONN_TEMPLATE.format(
                host=host,
                port=port,
                database=database or "",
                user=user or "",
                password=password or "",
            )
        else:
            raise ValueError(
                "postgres source requires either 'connection_string' or 'host'."
            )

        return cls(
            connection_string=conn_str,
            name=name,
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            databases=databases,
        )

    def validate_source_table(self, source_table: str) -> list[str]:
        return []
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_postgres.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/feather_etl/sources/postgres.py tests/test_postgres.py
git commit -m "refactor(sources): PostgresSource self-describes via from_yaml"
```

---

## Task 1.5 — `PostgresSource.list_databases()`

**Files:**
- Modify: [src/feather_etl/sources/postgres.py](../../../src/feather_etl/sources/postgres.py)
- Modify: [tests/test_postgres.py](../../../tests/test_postgres.py)

- [ ] **Step 1: Write failing test**

Append to `tests/test_postgres.py`:

```python
class TestPostgresListDatabases:
    def test_query_filters_template_dbs(self, monkeypatch):
        from feather_etl.sources import postgres as pg

        captured_sql: list[str] = []

        class FakeCursor:
            def execute(self, sql, *_):
                captured_sql.append(sql)

            def fetchall(self):
                return [("warehouse",), ("analytics",)]

            def close(self):
                pass

        class FakeConn:
            def cursor(self):
                return FakeCursor()

            def close(self):
                pass

        monkeypatch.setattr(pg.psycopg2, "connect", lambda *a, **k: FakeConn())

        src = pg.PostgresSource(connection_string="dummy", name="x")
        result = src.list_databases()

        assert result == ["warehouse", "analytics"]
        sql = captured_sql[0]
        assert "pg_database" in sql
        assert "datistemplate" in sql or "template" in sql
        assert "postgres" in sql  # 'postgres' default DB filtered out
```

- [ ] **Step 2: Run test**

Run: `uv run pytest tests/test_postgres.py::TestPostgresListDatabases -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

Add to `src/feather_etl/sources/postgres.py` inside `class PostgresSource`:

```python
    def list_databases(self) -> list[str]:
        """Return user databases on the cluster (excludes templates and 'postgres')."""
        conn = psycopg2.connect(self.connection_string, connect_timeout=10)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT datname FROM pg_database "
                "WHERE datistemplate = false "
                "AND datname NOT IN ('postgres') "
                "ORDER BY datname"
            )
            rows = cursor.fetchall()
            cursor.close()
            return [r[0] for r in rows]
        finally:
            conn.close()
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_postgres.py -v`
Expected: PASS (the integration test class still skips when pg_ctl unavailable).

- [ ] **Step 5: Commit**

```bash
git add src/feather_etl/sources/postgres.py tests/test_postgres.py
git commit -m "feat(sources): PostgresSource.list_databases enumerates non-template DBs"
```

---

## Task 1.6 — File source `from_yaml` + `validate_source_table` (csv, sqlite, duckdb, excel, json)

All five file sources share a near-identical pattern. Implement in one commit so the suite shifts coherently.

**Files (all modified):**
- `src/feather_etl/sources/csv.py`
- `src/feather_etl/sources/sqlite.py`
- `src/feather_etl/sources/duckdb_file.py`
- `src/feather_etl/sources/excel.py`
- `src/feather_etl/sources/json_source.py`
- `tests/test_sources.py`
- `tests/test_csv_glob.py`
- `tests/test_excel.py`
- `tests/test_json.py`

- [ ] **Step 1: Write failing tests**

Append a new class to `tests/test_sources.py`:

```python
class TestFileSourceFromYaml:
    @pytest.fixture
    def csv_dir(self, tmp_path):
        d = tmp_path / "data"
        d.mkdir()
        (d / "orders.csv").write_text("id,amt\n1,10\n")
        return d

    @pytest.fixture
    def sqlite_file(self, tmp_path):
        f = tmp_path / "src.sqlite"
        f.write_bytes(b"")  # presence is enough for from_yaml; no connection
        return f

    def test_csv_from_yaml(self, csv_dir):
        from feather_etl.sources.csv import CsvSource

        entry = {"name": "sheets", "type": "csv", "path": str(csv_dir)}
        src = CsvSource.from_yaml(entry, csv_dir.parent)
        assert src.name == "sheets"
        assert src.path == csv_dir

    def test_csv_relative_path_resolves_against_config_dir(self, tmp_path):
        from feather_etl.sources.csv import CsvSource

        d = tmp_path / "rel" / "csvs"
        d.mkdir(parents=True)
        entry = {"name": "x", "type": "csv", "path": "rel/csvs"}
        src = CsvSource.from_yaml(entry, tmp_path)
        assert src.path == d.resolve()

    def test_csv_path_required(self, tmp_path):
        from feather_etl.sources.csv import CsvSource

        with pytest.raises(ValueError, match="path"):
            CsvSource.from_yaml({"name": "x", "type": "csv"}, tmp_path)

    def test_csv_rejects_database_field(self, csv_dir):
        from feather_etl.sources.csv import CsvSource

        entry = {"name": "x", "type": "csv", "path": str(csv_dir),
                 "database": "BAD"}
        with pytest.raises(ValueError, match="not supported for source type csv"):
            CsvSource.from_yaml(entry, csv_dir.parent)

    def test_sqlite_from_yaml(self, sqlite_file):
        from feather_etl.sources.sqlite import SqliteSource

        entry = {"name": "db", "type": "sqlite", "path": str(sqlite_file)}
        src = SqliteSource.from_yaml(entry, sqlite_file.parent)
        assert src.path == sqlite_file

    def test_duckdb_from_yaml(self, tmp_path):
        from feather_etl.sources.duckdb_file import DuckDBFileSource

        f = tmp_path / "src.duckdb"
        f.write_bytes(b"")
        entry = {"name": "d", "type": "duckdb", "path": str(f)}
        src = DuckDBFileSource.from_yaml(entry, tmp_path)
        assert src.path == f

    def test_excel_from_yaml(self, tmp_path):
        from feather_etl.sources.excel import ExcelSource

        d = tmp_path / "xlsx"
        d.mkdir()
        src = ExcelSource.from_yaml(
            {"name": "e", "type": "excel", "path": str(d)}, tmp_path
        )
        assert src.path == d

    def test_json_from_yaml(self, tmp_path):
        from feather_etl.sources.json_source import JsonSource

        d = tmp_path / "json"
        d.mkdir()
        src = JsonSource.from_yaml(
            {"name": "j", "type": "json", "path": str(d)}, tmp_path
        )
        assert src.path == d


class TestFileSourceValidateSourceTable:
    def test_csv_accepts_filename(self, tmp_path):
        from feather_etl.sources.csv import CsvSource

        src = CsvSource(path=tmp_path, name="x")
        assert src.validate_source_table("orders.csv") == []

    def test_csv_accepts_glob(self, tmp_path):
        from feather_etl.sources.csv import CsvSource

        src = CsvSource(path=tmp_path, name="x")
        assert src.validate_source_table("sales_*.csv") == []

    def test_sqlite_rejects_dotted(self, tmp_path):
        from feather_etl.sources.sqlite import SqliteSource

        src = SqliteSource(path=tmp_path / "x.sqlite", name="x")
        errs = src.validate_source_table("schema.table")
        assert errs and "identifier" in errs[0].lower()

    def test_duckdb_requires_dotted(self, tmp_path):
        from feather_etl.sources.duckdb_file import DuckDBFileSource

        src = DuckDBFileSource(path=tmp_path / "x.duckdb", name="x")
        errs = src.validate_source_table("plain")
        assert errs and "schema.table" in errs[0]
```

Add `import pytest` at the top of `tests/test_sources.py` if not already there.

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/test_sources.py::TestFileSourceFromYaml tests/test_sources.py::TestFileSourceValidateSourceTable -v`
Expected: FAIL — methods don't exist.

- [ ] **Step 3: Implement file-source pattern**

Each file source needs the same shape. First, edit `src/feather_etl/sources/file_source.py` to add a shared helper at module bottom (does **not** modify `FileSource` itself — it's a free function callable from each subclass's `from_yaml`):

```python
import re
from typing import ClassVar


_SQL_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _resolve_file_path(entry: dict, config_dir: Path) -> Path:
    if "path" not in entry:
        raise ValueError(
            f"source type '{entry.get('type', '?')}' requires 'path'."
        )
    p = Path(entry["path"])
    if not p.is_absolute():
        p = (config_dir / p).resolve()
    return p


def _reject_db_fields(entry: dict, source_type: str) -> None:
    for field in ("database", "databases", "host", "port", "user", "password",
                  "connection_string"):
        if field in entry:
            raise ValueError(
                f"field '{field}' not supported for source type {source_type}."
            )
```

Then update each file source. Pattern for **`src/feather_etl/sources/csv.py`** — add `type` ClassVar, replace `__init__` with a `name` kwarg, and append `from_yaml` + `validate_source_table`:

```python
from typing import ClassVar

from feather_etl.sources.file_source import (
    FileSource,
    _reject_db_fields,
    _resolve_file_path,
)


class CsvSource(FileSource):
    type: ClassVar[str] = "csv"

    def __init__(self, path: Path, *, name: str = "") -> None:
        super().__init__(path)
        self.name = name

    @classmethod
    def from_yaml(cls, entry: dict, config_dir: Path) -> "CsvSource":
        _reject_db_fields(entry, cls.type)
        path = _resolve_file_path(entry, config_dir)
        if not path.is_dir():
            raise ValueError(f"CSV source path must be a directory: {path}")
        return cls(path=path, name=entry.get("name", ""))

    def validate_source_table(self, source_table: str) -> list[str]:
        # CSV: filename or glob pattern; no SQL identifier rule.
        return []

    # ... existing methods unchanged ...
```

Apply the same pattern to **`sqlite.py`**, **`duckdb_file.py`**, **`excel.py`**, **`json_source.py`** with these per-type rules:

| Source | `type` | path must be | `validate_source_table` |
|---|---|---|---|
| `sqlite` | `"sqlite"` | file path (existence checked at `check()` time, not in `from_yaml`) | identifier regex; reject dots — return `["..."]` if `not _SQL_IDENTIFIER_RE.match(source_table)` |
| `duckdb` | `"duckdb"` | file path | require `"."`; both halves must match identifier regex; otherwise return error string mentioning "schema.table format" |
| `excel` | `"excel"` | directory | accept anything (filename) |
| `json` | `"json"` | directory | accept anything (filename) |

Concrete `validate_source_table` for `sqlite.py`:

```python
    def validate_source_table(self, source_table: str) -> list[str]:
        from feather_etl.sources.file_source import _SQL_IDENTIFIER_RE

        if not _SQL_IDENTIFIER_RE.match(source_table):
            return [
                f"source_table '{source_table}' contains invalid identifier "
                f"characters. Use letters, digits, and underscores only."
            ]
        return []
```

Concrete `validate_source_table` for `duckdb_file.py`:

```python
    def validate_source_table(self, source_table: str) -> list[str]:
        from feather_etl.sources.file_source import _SQL_IDENTIFIER_RE

        if "." not in source_table:
            return [
                f"source_table '{source_table}' must be in schema.table "
                f"format for DuckDB sources."
            ]
        st_schema, st_table = source_table.split(".", 1)
        if not _SQL_IDENTIFIER_RE.match(st_schema) or not _SQL_IDENTIFIER_RE.match(st_table):
            return [
                f"source_table '{source_table}' contains invalid identifier "
                f"characters. Use letters, digits, and underscores only."
            ]
        return []
```

For `sqlite.py`, `from_yaml` skips the `is_dir()` check — sqlite is a file:

```python
    @classmethod
    def from_yaml(cls, entry: dict, config_dir: Path) -> "SqliteSource":
        _reject_db_fields(entry, cls.type)
        path = _resolve_file_path(entry, config_dir)
        return cls(path=path, name=entry.get("name", ""))
```

(No `path.exists()` check here — `check()` already handles that. Matches the no-side-effect rule from spec §5.2.)

`duckdb_file.py` mirrors `sqlite.py` (file path, no dir check). `excel.py` and `json_source.py` mirror `csv.py` (dir check).

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_sources.py tests/test_csv_glob.py tests/test_excel.py tests/test_json.py -v`
Expected: PASS — new tests pass; existing tests untouched (file sources still accept positional `path`).

- [ ] **Step 5: Commit**

```bash
git add src/feather_etl/sources/file_source.py \
        src/feather_etl/sources/csv.py \
        src/feather_etl/sources/sqlite.py \
        src/feather_etl/sources/duckdb_file.py \
        src/feather_etl/sources/excel.py \
        src/feather_etl/sources/json_source.py \
        tests/test_sources.py
git commit -m "refactor(sources): file sources self-describe via from_yaml"
```

---

## Task 1.7 — Lazy registry (`get_source_class`)

**Files:**
- Modify: [src/feather_etl/sources/registry.py](../../../src/feather_etl/sources/registry.py)
- Modify: [tests/test_sources.py](../../../tests/test_sources.py)

- [ ] **Step 1: Write failing test**

Append to `tests/test_sources.py`:

```python
class TestLazyRegistry:
    def test_get_source_class_returns_class_by_name(self):
        from feather_etl.sources.csv import CsvSource
        from feather_etl.sources.registry import get_source_class

        assert get_source_class("csv") is CsvSource

    def test_get_source_class_unknown_raises(self):
        from feather_etl.sources.registry import get_source_class

        with pytest.raises(ValueError, match="not implemented"):
            get_source_class("oracle")

    def test_only_referenced_modules_imported(self):
        """Importing the registry alone must NOT import every source connector.

        This is the closing condition for issue #4 — pyodbc / psycopg2 stay
        unimported until a sqlserver/postgres source is requested.
        """
        import importlib
        import sys

        # Drop any cached source modules so the test sees a fresh import graph.
        for mod_name in list(sys.modules):
            if mod_name.startswith("feather_etl.sources"):
                del sys.modules[mod_name]

        importlib.import_module("feather_etl.sources.registry")
        loaded = {m for m in sys.modules if m.startswith("feather_etl.sources")}

        assert "feather_etl.sources.sqlserver" not in loaded
        assert "feather_etl.sources.postgres" not in loaded
        assert "feather_etl.sources.csv" not in loaded
```

- [ ] **Step 2: Run test**

Run: `uv run pytest tests/test_sources.py::TestLazyRegistry -v`
Expected: FAIL — registry eagerly imports everything; `get_source_class` doesn't exist.

- [ ] **Step 3: Replace `registry.py`**

Overwrite `src/feather_etl/sources/registry.py`:

```python
"""Source registry — lazy type→class map.

Each entry stores the dotted module path so importing the registry itself
does NOT import optional connector dependencies (pyodbc, psycopg2). The
target module is imported on first lookup. Closes issue #4.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from feather_etl.sources import Source


SOURCE_CLASSES: dict[str, str] = {
    "duckdb": "feather_etl.sources.duckdb_file.DuckDBFileSource",
    "csv": "feather_etl.sources.csv.CsvSource",
    "sqlite": "feather_etl.sources.sqlite.SqliteSource",
    "sqlserver": "feather_etl.sources.sqlserver.SqlServerSource",
    "postgres": "feather_etl.sources.postgres.PostgresSource",
    "excel": "feather_etl.sources.excel.ExcelSource",
    "json": "feather_etl.sources.json_source.JsonSource",
}


def get_source_class(type_name: str) -> type["Source"]:
    """Resolve the source class for a YAML `type:` value, importing lazily."""
    if type_name not in SOURCE_CLASSES:
        raise ValueError(
            f"Source type '{type_name}' is not implemented. "
            f"Registered: {sorted(SOURCE_CLASSES)}"
        )
    module_path, cls_name = SOURCE_CLASSES[type_name].rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, cls_name)
```

`create_source()` and `SOURCE_REGISTRY` are removed. Their last callers (`config.py:_validate`, `commands/discover.py`, `commands/validate.py`, `pipeline.py`) are updated in Task 1.8.

- [ ] **Step 4: Don't run pytest yet — Task 1.8 is the matching caller change. Continue.**

---

## Task 1.8 — `config.py` delegates to `from_yaml`; delete `SourceConfig`

**Files:**
- Modify: [src/feather_etl/config.py](../../../src/feather_etl/config.py)
- Modify: [src/feather_etl/commands/discover.py](../../../src/feather_etl/commands/discover.py)
- Modify: [src/feather_etl/commands/validate.py](../../../src/feather_etl/commands/validate.py)
- Modify: [src/feather_etl/pipeline.py](../../../src/feather_etl/pipeline.py)

This task does not have a TDD step of its own — every existing test in `tests/test_config.py`, `tests/commands/test_discover.py`, `tests/commands/test_validate.py`, `tests/test_integration.py`, `tests/test_e2e.py` is the test. After this task, `uv run pytest -q` must be fully green.

- [ ] **Step 1: Rewrite `config.py` source parsing**

Edit `src/feather_etl/config.py`:

1. Delete `FILE_SOURCE_TYPES`, `DB_CONNECTION_BUILDERS`, and the entire `SourceConfig` dataclass.
2. Update `resolved_source_name` and `schema_output_path` to take a `Source` instance instead of `SourceConfig`. Their bodies still work — both helpers only read `name`, `type`, `path`, `host`, `database`, all of which now live on the `Source` instance.
3. Replace lines 382-410 (the source-parsing block) with:

```python
    from feather_etl.sources.registry import get_source_class

    source_raw = raw["source"]
    src_type = source_raw["type"]
    source_cls = get_source_class(src_type)
    source = source_cls.from_yaml(source_raw, config_dir)
```

4. Replace `_validate`'s source checks (lines 223-249) with:

```python
    # Source validation lives on each Source class via from_yaml; once we
    # have an instance it has already passed structural validation. We only
    # check destination + table-level rules here.
```

(Delete the source-type, file-source-path, and connection-string checks. Each `from_yaml` already raised on bad input. `path.exists()` for sqlite/duckdb is intentionally not checked at config load — `source.check()` covers it at runtime.)

5. Update the per-table `source_table` validation block (lines 302-326). Replace the type-conditional branches with:

```python
        # Source-type-aware source_table validation
        for err in config.source.validate_source_table(table.source_table):
            errors.append(f"Table '{table.name}': {err}")
```

6. Update `FeatherConfig`:

```python
@dataclass
class FeatherConfig:
    source: "Source"  # forward ref — see TYPE_CHECKING import
    destination: DestinationConfig
    tables: list[TableConfig]
    defaults: DefaultsConfig = field(default_factory=DefaultsConfig)
    config_dir: Path = field(default_factory=lambda: Path("."))
    mode: str = "dev"
    alerts: AlertsConfig | None = None
```

Add at the top of `config.py`:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from feather_etl.sources import Source
```

7. Update `write_validation_json` to read `config.source.path` only when the attribute is truthy (file sources have it, DB sources don't — `getattr(config.source, "path", None)`).

- [ ] **Step 2: Update callers of `create_source(cfg.source)`**

In `src/feather_etl/commands/discover.py`, replace:

```python
    from feather_etl.sources.registry import create_source
    ...
    source = create_source(cfg.source)
```

with:

```python
    source = cfg.source
```

(Same replacement in `src/feather_etl/commands/validate.py:22` and `src/feather_etl/pipeline.py:209`.)

In `src/feather_etl/commands/validate.py:39`, the source-label expression needs adjustment because `cfg.source.host` only exists on DB sources and `cfg.source.path` only on file sources:

```python
        source_label = (
            getattr(cfg.source, "path", None)
            or getattr(cfg.source, "host", None)
            or "configured"
        )
```

In `src/feather_etl/commands/validate.py:30`, change `cfg.source.type` to use the class attribute (still works — the spec adds it as `ClassVar[str]`).

- [ ] **Step 3: Run the full suite**

Run: `uv run pytest -q`
Expected: ALL PASS. If anything fails, the failure points to a caller that still expected `SourceConfig` shape — fix it before continuing.

- [ ] **Step 4: Run hands_on_test.sh**

Run: `bash scripts/hands_on_test.sh`
Expected: ALL 61 checks pass.

- [ ] **Step 5: Commit**

```bash
git add src/feather_etl/sources/registry.py \
        src/feather_etl/sources/__init__.py \
        src/feather_etl/config.py \
        src/feather_etl/commands/discover.py \
        src/feather_etl/commands/validate.py \
        src/feather_etl/pipeline.py
git commit -m "refactor(config): delegate source parsing to Source.from_yaml; lazy registry"
```

---

# Phase 2 — `sources:` list YAML schema (commit 2)

After this phase: `feather.yaml` requires `sources:` (list). Singular `source:` raises a hard error. `FeatherConfig.sources: list[Source]`. All commands except `discover` operate on `cfg.sources[0]` and exit 2 with a guard message when `len > 1`. Every inline test config is updated.

## Task 2.1 — Parse `sources:` list; hard error on `source:`

**Files:**
- Modify: [src/feather_etl/config.py](../../../src/feather_etl/config.py)
- Modify: [tests/test_config.py](../../../tests/test_config.py)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_config.py`:

```python
class TestSourcesList:
    def test_sources_list_with_single_entry(self, tmp_path: Path):
        from feather_etl.config import load_config

        cfg_dict = {
            "sources": [{"type": "duckdb", "path": str(tmp_path / "s.duckdb")}],
            "destination": {"path": str(tmp_path / "out.duckdb")},
            "tables": [],
        }
        (tmp_path / "s.duckdb").write_bytes(b"")
        config_file = tmp_path / "feather.yaml"
        config_file.write_text(yaml.dump(cfg_dict))
        cfg = load_config(config_file, validate=False)
        assert len(cfg.sources) == 1
        assert cfg.sources[0].type == "duckdb"

    def test_sources_list_multi_entry_requires_names(self, tmp_path: Path):
        from feather_etl.config import load_config

        cfg_dict = {
            "sources": [
                {"type": "duckdb", "path": str(tmp_path / "a.duckdb")},
                {"type": "duckdb", "path": str(tmp_path / "b.duckdb")},
            ],
            "destination": {"path": str(tmp_path / "out.duckdb")},
            "tables": [],
        }
        for f in ("a.duckdb", "b.duckdb"):
            (tmp_path / f).write_bytes(b"")
        config_file = tmp_path / "feather.yaml"
        config_file.write_text(yaml.dump(cfg_dict))
        with pytest.raises(ValueError, match="name.*required"):
            load_config(config_file, validate=False)

    def test_sources_list_multi_entry_with_names_ok(self, tmp_path: Path):
        from feather_etl.config import load_config

        cfg_dict = {
            "sources": [
                {"name": "a", "type": "duckdb", "path": str(tmp_path / "a.duckdb")},
                {"name": "b", "type": "duckdb", "path": str(tmp_path / "b.duckdb")},
            ],
            "destination": {"path": str(tmp_path / "out.duckdb")},
            "tables": [],
        }
        for f in ("a.duckdb", "b.duckdb"):
            (tmp_path / f).write_bytes(b"")
        config_file = tmp_path / "feather.yaml"
        config_file.write_text(yaml.dump(cfg_dict))
        cfg = load_config(config_file, validate=False)
        assert [s.name for s in cfg.sources] == ["a", "b"]

    def test_sources_list_duplicate_name_raises(self, tmp_path: Path):
        from feather_etl.config import load_config

        cfg_dict = {
            "sources": [
                {"name": "x", "type": "duckdb", "path": str(tmp_path / "a.duckdb")},
                {"name": "x", "type": "duckdb", "path": str(tmp_path / "b.duckdb")},
            ],
            "destination": {"path": str(tmp_path / "out.duckdb")},
            "tables": [],
        }
        for f in ("a.duckdb", "b.duckdb"):
            (tmp_path / f).write_bytes(b"")
        config_file = tmp_path / "feather.yaml"
        config_file.write_text(yaml.dump(cfg_dict))
        with pytest.raises(ValueError, match="duplicate.*'x'"):
            load_config(config_file, validate=False)

    def test_sources_empty_list_raises(self, tmp_path: Path):
        from feather_etl.config import load_config

        cfg_dict = {
            "sources": [],
            "destination": {"path": str(tmp_path / "out.duckdb")},
            "tables": [],
        }
        config_file = tmp_path / "feather.yaml"
        config_file.write_text(yaml.dump(cfg_dict))
        with pytest.raises(ValueError, match="non-empty"):
            load_config(config_file, validate=False)


class TestSingularSourceMigrationError:
    def test_singular_source_raises_with_guidance(self, tmp_path: Path):
        from feather_etl.config import load_config

        cfg_dict = {
            "source": {"type": "duckdb", "path": str(tmp_path / "s.duckdb")},
            "destination": {"path": str(tmp_path / "out.duckdb")},
            "tables": [],
        }
        (tmp_path / "s.duckdb").write_bytes(b"")
        config_file = tmp_path / "feather.yaml"
        config_file.write_text(yaml.dump(cfg_dict))
        with pytest.raises(ValueError) as exc:
            load_config(config_file, validate=False)
        msg = str(exc.value)
        assert "sources:" in msg
        assert "Wrap your existing source in a list" in msg
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/test_config.py::TestSourcesList tests/test_config.py::TestSingularSourceMigrationError -v`
Expected: FAIL — config still expects singular `source:`.

- [ ] **Step 3: Rewrite parsing**

Replace the `for key in ("source", "destination"):` block in `load_config` (was config.py:378-380) and the source-parsing block immediately after with:

```python
    if "source" in raw and "sources" not in raw:
        raise ValueError(
            "feather.yaml now uses 'sources:' (list). Wrap your existing source in a list:\n"
            "  sources:\n"
            "    - name: ...\n"
            "      type: ...\n"
        )

    if "sources" not in raw or "destination" not in raw:
        missing = "sources" if "sources" not in raw else "destination"
        raise ValueError(f"Missing required config section: '{missing}'")

    sources_raw = raw["sources"]
    if not isinstance(sources_raw, list) or not sources_raw:
        raise ValueError("'sources' must be a non-empty list.")

    from feather_etl.sources.registry import get_source_class

    sources: list = []
    seen_names: set[str] = set()
    multi = len(sources_raw) > 1
    for idx, entry in enumerate(sources_raw):
        if "type" not in entry:
            raise ValueError(f"sources[{idx}] missing required field 'type'.")
        if multi and not entry.get("name"):
            raise ValueError(
                f"sources[{idx}]: 'name' is required when multiple sources are configured."
            )
        src_cls = get_source_class(entry["type"])
        src = src_cls.from_yaml(entry, config_dir)
        # Resolve display name when single-entry + name omitted.
        if not src.name and not multi:
            src.name = resolved_source_name(src)
        if src.name in seen_names:
            raise ValueError(
                f"duplicate source name '{src.name}'; names must be unique."
            )
        seen_names.add(src.name)
        sources.append(src)
```

Update `FeatherConfig`:

```python
@dataclass
class FeatherConfig:
    sources: list                  # list[Source] — forward ref
    destination: DestinationConfig
    tables: list[TableConfig]
    defaults: DefaultsConfig = field(default_factory=DefaultsConfig)
    config_dir: Path = field(default_factory=lambda: Path("."))
    mode: str = "dev"
    alerts: AlertsConfig | None = None
```

Update the `FeatherConfig(...)` constructor call near the bottom of `load_config`:

```python
    config = FeatherConfig(
        sources=sources,
        destination=dest,
        tables=tables,
        defaults=defaults,
        config_dir=config_dir,
        mode=mode,
        alerts=alerts,
    )
```

Update `_validate` to iterate `config.sources` for any per-source rule, and update `write_validation_json` to read `config.sources[0]` (single-source mode) or summarize all (`[str(s.path) if hasattr(s, "path") else s.host for s in config.sources]`).

For per-table `validate_source_table`, the rule is "validate against `cfg.sources[0]`" until B2 ships:

```python
    primary = config.sources[0]
    for table in config.tables:
        ...
        for err in primary.validate_source_table(table.source_table):
            errors.append(f"Table '{table.name}': {err}")
```

- [ ] **Step 4: Don't run the suite yet — fixtures break next.** Continue to Task 2.2.

---

## Task 2.2 — Update inline test configs

Every test file that builds a config dict in-Python uses singular `source:`. They all need `sources: [...]`.

**Files (all modified — `source: {...}` → `sources: [{...}]`):**
- `tests/conftest.py` (1 fixture: `config_path`)
- `tests/commands/conftest.py` (3 fixtures: `cli_env`, `two_table_env`, `cli_config`)
- `tests/commands/test_discover.py` (3 inline configs)
- `tests/commands/test_run.py`
- `tests/commands/test_validate.py`
- `tests/commands/test_status.py`
- `tests/commands/test_history.py`
- `tests/commands/test_setup.py`
- `tests/commands/test_init.py` (if any)
- `tests/test_config.py` (every existing test that builds a config dict)
- `tests/test_csv_glob.py`
- `tests/test_excel.py`
- `tests/test_json.py`
- `tests/test_sources.py`
- `tests/test_discover_io.py`
- `tests/test_integration.py`
- `tests/test_e2e.py`
- `tests/test_alerts.py`, `test_dq.py`, `test_schema_drift.py` — only if they build configs (most use the shared `config_path` fixture)

- [ ] **Step 1: Mechanical migration**

For each file, find every `"source": {...}` entry and replace with `"sources": [{...}]`:

```python
# Before
"source": {"type": "duckdb", "path": str(client_db)},

# After
"sources": [{"type": "duckdb", "path": str(client_db)}],
```

The single-entry list keeps `name` optional — derived names work as before.

- [ ] **Step 2: Update assertion-side references**

Any test that asserts `cfg.source.X` becomes `cfg.sources[0].X`:

```bash
# Search-and-find — DO NOT auto-replace; review each match.
grep -rn "cfg\.source\.\|config\.source\." tests/
```

Update each call site.

- [ ] **Step 3: Run the suite**

Run: `uv run pytest -q`
Expected: most tests pass; any remaining failures point to a missed config dict — fix and re-run until green.

- [ ] **Step 4: Don't commit yet — the production code in pipeline/commands still reads `cfg.source`.** Move to Task 2.3.

---

## Task 2.3 — `pipeline.py` reads `cfg.sources[0]`

**Files:**
- Modify: [src/feather_etl/pipeline.py:209](../../../src/feather_etl/pipeline.py#L209)

- [ ] **Step 1: Edit pipeline.py**

Replace `source = create_source(config.source)` (already changed in Task 1.8 to `source = config.source`) with:

```python
    source = config.sources[0]
```

Also search for any other `config.source` reference in `pipeline.py` and update to `config.sources[0]`.

- [ ] **Step 2: Run integration tests**

Run: `uv run pytest tests/test_integration.py tests/test_e2e.py tests/test_pipeline.py -v`
Expected: PASS.

- [ ] **Step 3: Don't commit yet — commands still read `cfg.source`.**

---

## Task 2.4 — Single-source commands read `cfg.sources[0]` + multi-source guard

**Files:**
- Modify: [src/feather_etl/commands/validate.py](../../../src/feather_etl/commands/validate.py)
- Modify: [src/feather_etl/commands/run.py](../../../src/feather_etl/commands/run.py)
- Modify: [src/feather_etl/commands/status.py](../../../src/feather_etl/commands/status.py)
- Modify: [src/feather_etl/commands/history.py](../../../src/feather_etl/commands/history.py)
- Modify: [src/feather_etl/commands/setup.py](../../../src/feather_etl/commands/setup.py)
- Modify: [src/feather_etl/commands/_common.py](../../../src/feather_etl/commands/_common.py) (add helper)

- [ ] **Step 1: Write failing test for the guard**

Append a new file `tests/commands/test_multi_source_guard.py`:

```python
"""Multi-source guard for non-discover commands (B2 deferral)."""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from tests.conftest import FIXTURES_DIR


def _multi_source_yaml(tmp_path: Path) -> Path:
    src1 = tmp_path / "a.duckdb"
    src2 = tmp_path / "b.duckdb"
    shutil.copy2(FIXTURES_DIR / "client.duckdb", src1)
    shutil.copy2(FIXTURES_DIR / "client.duckdb", src2)
    cfg = {
        "sources": [
            {"name": "a", "type": "duckdb", "path": str(src1)},
            {"name": "b", "type": "duckdb", "path": str(src2)},
        ],
        "destination": {"path": str(tmp_path / "out.duckdb")},
        "tables": [
            {"name": "ig", "source_table": "icube.InventoryGroup",
             "target_table": "bronze.ig", "strategy": "full"},
        ],
    }
    p = tmp_path / "feather.yaml"
    p.write_text(yaml.dump(cfg))
    return p


class TestMultiSourceGuard:
    def test_validate_exits_2_with_guidance(self, runner, tmp_path):
        from feather_etl.cli import app
        cfg = _multi_source_yaml(tmp_path)
        r = runner.invoke(app, ["validate", "--config", str(cfg)])
        assert r.exit_code == 2
        assert "single-source" in r.output
        assert "discover" in r.output

    def test_run_exits_2(self, runner, tmp_path):
        from feather_etl.cli import app
        cfg = _multi_source_yaml(tmp_path)
        r = runner.invoke(app, ["run", "--config", str(cfg)])
        assert r.exit_code == 2

    def test_status_exits_2(self, runner, tmp_path):
        from feather_etl.cli import app
        cfg = _multi_source_yaml(tmp_path)
        r = runner.invoke(app, ["status", "--config", str(cfg)])
        assert r.exit_code == 2

    def test_history_exits_2(self, runner, tmp_path):
        from feather_etl.cli import app
        cfg = _multi_source_yaml(tmp_path)
        r = runner.invoke(app, ["history", "--config", str(cfg)])
        assert r.exit_code == 2

    def test_setup_exits_2(self, runner, tmp_path):
        from feather_etl.cli import app
        cfg = _multi_source_yaml(tmp_path)
        r = runner.invoke(app, ["setup", "--config", str(cfg)])
        assert r.exit_code == 2
```

- [ ] **Step 2: Run test**

Run: `uv run pytest tests/commands/test_multi_source_guard.py -v`
Expected: FAIL — guard not implemented.

- [ ] **Step 3: Add the guard helper to `_common.py`**

Append to `src/feather_etl/commands/_common.py`:

```python
def _enforce_single_source(cfg, command_name: str) -> None:
    """Exit 2 if cfg has multiple sources. Used by every non-discover command."""
    if len(cfg.sources) > 1:
        typer.echo(
            f"Command '{command_name}' is single-source for now (issue #8). "
            f"Use `feather discover` to enumerate multi-source schemas, or "
            f"split into one feather.yaml per source for non-discover operations.",
            err=True,
        )
        raise typer.Exit(code=2)
```

- [ ] **Step 4: Wire the guard into each command**

In each of `validate.py`, `run.py`, `status.py`, `history.py`, `setup.py`, immediately after `cfg = _load_and_validate(...)`:

```python
    from feather_etl.commands._common import _enforce_single_source
    _enforce_single_source(cfg, "<command>")  # e.g. "validate", "run", ...
```

Then update the body to read `cfg.sources[0]`:

- `validate.py:22`: `source = cfg.sources[0]` (the source instance — already-resolved). Remove the `create_source` line.
- `validate.py:30`: `"source_type": cfg.sources[0].type`
- `validate.py:39`: `cfg.sources[0]` in source_label expression
- `validate.py:41`: `cfg.sources[0].type` in echo

`run.py`, `status.py`, `history.py`, `setup.py` don't need to read `cfg.source` directly — they use `cfg.config_dir`, `cfg.destination`, etc. The guard alone suffices.

`init.py` does NOT need the guard — it scaffolds a fresh project, doesn't load an existing config.

- [ ] **Step 5: Run suite**

Run: `uv run pytest -q`
Expected: ALL PASS.

- [ ] **Step 6: Run hands_on_test.sh**

Run: `bash scripts/hands_on_test.sh`
Expected: ALL 61 checks pass (every check uses single-source configs).

---

## Task 2.5 — `init_wizard.py` template emits `sources:` list

**Files:**
- Modify: [src/feather_etl/init_wizard.py](../../../src/feather_etl/init_wizard.py)
- Modify: [tests/commands/test_init.py](../../../tests/commands/test_init.py)

- [ ] **Step 1: Write failing test**

Append to `tests/commands/test_init.py`:

```python
class TestInitTemplateUsesSourcesList:
    def test_scaffolded_yaml_uses_sources_list(self, tmp_path: Path):
        from feather_etl.init_wizard import scaffold_project

        scaffold_project(tmp_path / "proj")
        content = (tmp_path / "proj" / "feather.yaml").read_text()
        assert "sources:" in content
        assert "\nsource:" not in content  # must not emit singular form

    def test_scaffolded_yaml_loads_clean(self, tmp_path: Path):
        from feather_etl.config import load_config
        from feather_etl.init_wizard import scaffold_project

        proj = tmp_path / "proj"
        scaffold_project(proj)
        # The default template references ./source.duckdb which doesn't exist;
        # validate=False skips source existence checks while still parsing.
        cfg = load_config(proj / "feather.yaml", validate=False)
        assert len(cfg.sources) == 1
```

- [ ] **Step 2: Run test**

Run: `uv run pytest tests/commands/test_init.py::TestInitTemplateUsesSourcesList -v`
Expected: FAIL.

- [ ] **Step 3: Update template**

In `src/feather_etl/init_wizard.py`, replace the active `source:` block (lines 44-46) with:

```python
sources:
  - type: duckdb
    path: ./source.duckdb
```

Also update the example comments in the docstring header so the multi-source example is shown:

```python
# Multi-source example:
#
# sources:
#   - name: erp
#     type: sqlserver
#     host: ${SQLSERVER_HOST}
#     user: ${SQLSERVER_USER}
#     password: ${SQLSERVER_PASSWORD}
#   - name: spreadsheets
#     type: csv
#     path: ./data/csv/
```

- [ ] **Step 4: Run test**

Run: `uv run pytest tests/commands/test_init.py -v`
Expected: PASS.

---

## Task 2.6 — Phase 2 commit + docs sync

**Files:**
- Modify: `README.md` — every `source:` example → `sources: [...]`
- Modify: `docs/prd.md` — same
- Modify: [docs/CONTRIBUTING.md](../../../docs/CONTRIBUTING.md) — add §8.1 testing-co-location principle

- [ ] **Step 1: Sweep docs**

```bash
# Identify candidates — review each manually before editing.
grep -rn "^source:" README.md docs/prd.md docs/CONTRIBUTING.md
```

For each match, rewrite to `sources:` list form using the template:

```yaml
sources:
  - type: <type>
    path: <path>            # or host/user/password/database
```

In `docs/CONTRIBUTING.md`, append a new section:

```markdown
## Testing co-location

Tests track with the **module of origin**, not with the feature that
motivated them. When you edit `SqlServerSource`, every constraint on your
change lives in `tests/test_sqlserver.py`. When you edit the discover
command, every flag combo lives in `tests/commands/test_discover.py`.

The one exception: happy-path E2E tests stand alone as "how does a user
actually use this end-to-end." They live in
`tests/commands/test_<workflow>.py`.

Do **not** create feature-named test files (e.g. `test_multi_source.py`) —
tests belong with the code they exercise.
```

- [ ] **Step 2: Run full suite + hands_on_test.sh**

```bash
uv run pytest -q
bash scripts/hands_on_test.sh
```

Both green.

- [ ] **Step 3: Commit Phase 2 as one commit**

```bash
git add -A
git commit -m "feat(config): YAML schema flips to 'sources:' list; multi-source guard for non-discover commands"
```

(Phase 2 is one logical change — schema flip — but touches many files. The atomic commit captures it together.)

---

# Phase 3 — `discover` iterates sources + auto-enumerate (commit 3)

After this phase: `feather discover` writes one schema JSON per source. SQL Server / Postgres sources without `database`/`databases` auto-enumerate via `list_databases()`. Per-source failures don't abort the run; exit 2 if any failed.

No state file yet — every run discovers everything from scratch.

## Task 3.1 — `multi_source_yaml` test helper

**Files:**
- Modify: [tests/commands/conftest.py](../../../tests/commands/conftest.py)

- [ ] **Step 1: Append helper**

```python
def multi_source_yaml(tmp_path: Path, sources: list[dict],
                      destination_path: str | None = None,
                      tables: list[dict] | None = None) -> Path:
    """Build a feather.yaml with arbitrary sources/destinations/tables."""
    cfg = {
        "sources": sources,
        "destination": {
            "path": destination_path or str(tmp_path / "feather_data.duckdb")
        },
        "tables": tables or [],
    }
    p = tmp_path / "feather.yaml"
    p.write_text(yaml.dump(cfg, default_flow_style=False))
    return p
```

No test — this is a helper. Validated indirectly by Task 3.5.

---

## Task 3.2 — Discover iterates `cfg.sources` and writes per-source files

**Files:**
- Modify: [src/feather_etl/commands/discover.py](../../../src/feather_etl/commands/discover.py)
- Create: `tests/commands/test_discover_multi_source.py`

- [ ] **Step 1: Create the new E2E test file with the first scenario**

Create `tests/commands/test_discover_multi_source.py`:

```python
"""Happy-path E2E for `feather discover` over multiple sources.

Per docs/CONTRIBUTING.md (testing co-location): edge cases for the
discover command live in tests/commands/test_discover.py. This file holds
end-to-end workflow tests — what a user actually does at the keyboard.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from tests.commands.conftest import multi_source_yaml
from tests.conftest import FIXTURES_DIR


class TestDiscoverHeterogeneousSources:
    def test_single_csv_source_writes_one_file(self, runner, tmp_path, monkeypatch):
        from feather_etl.cli import app

        csvs = tmp_path / "csv"
        shutil.copytree(FIXTURES_DIR / "csv_data", csvs)
        cfg = multi_source_yaml(tmp_path, [
            {"name": "sheets", "type": "csv", "path": str(csvs)},
        ])
        monkeypatch.chdir(tmp_path)

        r = runner.invoke(app, ["discover", "--config", str(cfg)])
        assert r.exit_code == 0, r.output
        files = sorted(tmp_path.glob("schema_*.json"))
        assert [f.name for f in files] == ["schema_sheets.json"]
        payload = json.loads(files[0].read_text())
        assert isinstance(payload, list)
        assert len(payload) == 3  # csv_data has 3 files

    def test_heterogeneous_sources_write_one_file_per_source(
        self, runner, tmp_path, monkeypatch
    ):
        from feather_etl.cli import app

        csvs = tmp_path / "csv"
        shutil.copytree(FIXTURES_DIR / "csv_data", csvs)
        sqlite = tmp_path / "src.sqlite"
        shutil.copy2(FIXTURES_DIR / "sample_erp.sqlite", sqlite)
        duckdb_f = tmp_path / "src.duckdb"
        shutil.copy2(FIXTURES_DIR / "sample_erp.duckdb", duckdb_f)

        cfg = multi_source_yaml(tmp_path, [
            {"name": "sheets", "type": "csv", "path": str(csvs)},
            {"name": "sqlite_db", "type": "sqlite", "path": str(sqlite)},
            {"name": "duck", "type": "duckdb", "path": str(duckdb_f)},
        ])
        monkeypatch.chdir(tmp_path)

        r = runner.invoke(app, ["discover", "--config", str(cfg)])
        assert r.exit_code == 0, r.output
        names = {p.name for p in tmp_path.glob("schema_*.json")}
        assert names == {"schema_sheets.json", "schema_sqlite_db.json",
                         "schema_duck.json"}
```

- [ ] **Step 2: Run test**

Run: `uv run pytest tests/commands/test_discover_multi_source.py -v`
Expected: FAIL — current discover only handles one source.

- [ ] **Step 3: Rewrite `commands/discover.py`**

Replace the entire file with:

```python
"""`feather discover` command — iterates every source in feather.yaml."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from feather_etl.commands._common import _load_and_validate


def _sanitised_filename(name: str) -> str:
    import re
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)


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


def discover(config: Path = typer.Option("feather.yaml", "--config")) -> None:
    """Save source schema (tables + columns) per source to JSON files."""
    cfg = _load_and_validate(config)
    target_dir = cfg.config_dir

    succeeded = 0
    failed: list[tuple[str, str]] = []
    total = len(cfg.sources)

    for idx, source in enumerate(cfg.sources, start=1):
        prefix = f"  [{idx}/{total}] {source.name}"
        if not source.check():
            err = getattr(source, "_last_error", "connection failed")
            failed.append((source.name, err))
            typer.echo(f"{prefix}  → FAILED: {err}", err=True)
            continue
        try:
            out, count = _write_schema(source, target_dir)
        except Exception as e:  # pragma: no cover — surfaces in tests
            failed.append((source.name, str(e)))
            typer.echo(f"{prefix}  → FAILED: {e}", err=True)
            continue
        succeeded += 1
        typer.echo(f"{prefix}  → {count} tables → ./{out.name}")

    typer.echo(f"\n{succeeded} succeeded, {len(failed)} failed.")
    if failed:
        raise typer.Exit(code=2)


def register(app: typer.Typer) -> None:
    app.command(name="discover")(discover)
```

- [ ] **Step 4: Run new tests**

Run: `uv run pytest tests/commands/test_discover_multi_source.py -v`
Expected: PASS.

- [ ] **Step 5: Run existing discover tests**

Run: `uv run pytest tests/commands/test_discover.py -v`
Expected: PASS — old single-source assertions still match (filename derivation lives on `Source.name`, set by `resolved_source_name` in single-entry case from Task 2.1).

- [ ] **Step 6: Don't commit yet — auto-enumeration in next task.**

---

## Task 3.3 — Auto-enumerate DB sources without `database`/`databases`

When a sqlserver/postgres source has neither `database` nor `databases`, `discover` calls `source.list_databases()` and treats each enumerated database as a child source named `<parent>__<db>`.

**Files:**
- Modify: [src/feather_etl/commands/discover.py](../../../src/feather_etl/commands/discover.py)
- Modify: `tests/commands/test_discover_multi_source.py`

- [ ] **Step 1: Append failing tests**

Append two more tests to `tests/commands/test_discover_multi_source.py`. Mark with `@pytest.mark.postgres` so they skip when `pg_ctl` isn't available.

```python
import pytest

CONN_STR = "dbname=feather_test host=localhost"


def _postgres_available() -> bool:
    try:
        import psycopg2
        psycopg2.connect(CONN_STR).close()
        return True
    except Exception:
        return False


postgres = pytest.mark.skipif(
    not _postgres_available(), reason="PostgreSQL not available"
)


@postgres
class TestDiscoverPostgresMultiDatabase:
    def _create_databases(self, names):
        import psycopg2
        conn = psycopg2.connect(CONN_STR)
        conn.autocommit = True
        cur = conn.cursor()
        for n in names:
            cur.execute(f"DROP DATABASE IF EXISTS {n}")
            cur.execute(f"CREATE DATABASE {n}")
        cur.close()
        conn.close()

    def _drop_databases(self, names):
        import psycopg2
        conn = psycopg2.connect(CONN_STR)
        conn.autocommit = True
        cur = conn.cursor()
        for n in names:
            cur.execute(f"DROP DATABASE IF EXISTS {n}")
        cur.close()
        conn.close()

    def test_explicit_databases(self, runner, tmp_path, monkeypatch):
        from feather_etl.cli import app

        names = ["feather_a", "feather_b"]
        self._create_databases(names)
        try:
            cfg = multi_source_yaml(tmp_path, [
                {"name": "wh", "type": "postgres", "host": "localhost",
                 "user": "", "password": "", "databases": names},
            ])
            monkeypatch.chdir(tmp_path)
            r = runner.invoke(app, ["discover", "--config", str(cfg)])
            assert r.exit_code == 0, r.output
            files = {p.name for p in tmp_path.glob("schema_*.json")}
            assert files == {"schema_wh__feather_a.json",
                             "schema_wh__feather_b.json"}
        finally:
            self._drop_databases(names)

    def test_auto_enumerate(self, runner, tmp_path, monkeypatch):
        from feather_etl.cli import app

        names = ["feather_x", "feather_y"]
        self._create_databases(names)
        try:
            cfg = multi_source_yaml(tmp_path, [
                {"name": "wh", "type": "postgres", "host": "localhost",
                 "user": "", "password": ""},
            ])
            monkeypatch.chdir(tmp_path)
            r = runner.invoke(app, ["discover", "--config", str(cfg)])
            assert r.exit_code == 0, r.output
            files = {p.name for p in tmp_path.glob("schema_*.json")}
            for n in names:
                assert f"schema_wh__{n}.json" in files
        finally:
            self._drop_databases(names)
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/commands/test_discover_multi_source.py::TestDiscoverPostgresMultiDatabase -v`
Expected: FAIL — discover doesn't expand DB sources yet.

- [ ] **Step 3: Implement expansion in discover.py**

Add a helper that takes the configured sources and expands DB sources into child instances:

```python
def _expand_db_sources(sources: list) -> list:
    """Expand sqlserver/postgres sources without explicit database into child sources.

    For each parent source:
      - If it has `database` set → keep as-is.
      - If it has `databases: [...]` set → produce one child per entry, named
        `<parent_name>__<db>`, with `database` set on the child.
      - Otherwise (DB source, neither set) → call list_databases() and
        produce one child per result.
      - File sources → keep as-is.
    """
    from feather_etl.sources.postgres import PostgresSource
    from feather_etl.sources.sqlserver import SqlServerSource

    expanded: list = []
    for src in sources:
        is_db = isinstance(src, (SqlServerSource, PostgresSource))
        if not is_db:
            expanded.append(src)
            continue
        if src.database is not None:
            expanded.append(src)
            continue
        databases = src.databases
        if databases is None:
            # Auto-enumerate. Failures bubble up to the caller, which
            # records a single 'failed' entry for the parent source.
            try:
                databases = src.list_databases()
            except Exception as e:
                src._last_error = (
                    f"Found 0 databases on host {src.host}. Either grant "
                    f"VIEW ANY DATABASE to this login, or specify "
                    f"`database:` / `databases: [...]` explicitly. ({e})"
                )
                expanded.append(src)  # surfaces as failed during the loop
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
            expanded.append(child)
    return expanded
```

In `discover()`, call `_expand_db_sources(cfg.sources)` instead of iterating `cfg.sources` directly:

```python
    sources = _expand_db_sources(cfg.sources)
    total = len(sources)
    for idx, source in enumerate(sources, start=1):
        ...
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/commands/test_discover_multi_source.py -v
uv run pytest tests/commands/test_discover.py -v
```

Both green.

- [ ] **Step 5: Run full suite**

```bash
uv run pytest -q
bash scripts/hands_on_test.sh
```

Green.

- [ ] **Step 6: Commit Phase 3**

```bash
git add -A
git commit -m "feat(discover): iterate cfg.sources and auto-enumerate DB sources"
```

---

# Phase 4 — State file + flags (commit 4)

After this phase: `feather_discover_state.json` records every attempt. Default re-runs skip cached and retry failed. Flags: `--refresh`, `--retry-failed`, `--prune`. Permission errors emit a remediation hint per spec §6.5.

## Task 4.1 — New module `discover_state.py` with `DiscoverState` class

**Files:**
- Create: `src/feather_etl/discover_state.py`
- Create: `tests/test_discover_state.py`

- [ ] **Step 1: Write failing tests for the data model**

Create `tests/test_discover_state.py`:

```python
"""Unit tests for discover_state.py — state file I/O + classification."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


class TestDiscoverStateRoundTrip:
    def test_load_returns_empty_when_file_missing(self, tmp_path: Path):
        from feather_etl.discover_state import DiscoverState

        s = DiscoverState.load(tmp_path)
        assert s.sources == {}
        assert s.auto_enumeration == {}

    def test_save_then_load(self, tmp_path: Path):
        from feather_etl.discover_state import DiscoverState

        s = DiscoverState.load(tmp_path)
        s.record_ok(
            name="a",
            type_="duckdb",
            fingerprint="duckdb:/tmp/x.duckdb",
            table_count=3,
            output_path=Path("./schema_a.json"),
        )
        s.save()

        reloaded = DiscoverState.load(tmp_path)
        assert "a" in reloaded.sources
        assert reloaded.sources["a"]["status"] == "ok"
        assert reloaded.sources["a"]["table_count"] == 3
        assert reloaded.sources["a"]["fingerprint"] == "duckdb:/tmp/x.duckdb"

    def test_record_failed_stores_error_and_increments_attempt(self, tmp_path: Path):
        from feather_etl.discover_state import DiscoverState

        s = DiscoverState.load(tmp_path)
        s.record_failed(name="a", type_="sqlserver",
                        fingerprint="sqlserver:h:1433:DB", error="Login failed")
        s.record_failed(name="a", type_="sqlserver",
                        fingerprint="sqlserver:h:1433:DB", error="Login failed")
        assert s.sources["a"]["attempt_count"] == 2

    def test_schema_version_in_payload(self, tmp_path: Path):
        from feather_etl.discover_state import DiscoverState

        s = DiscoverState.load(tmp_path)
        s.record_ok(name="a", type_="csv", fingerprint="csv:/tmp",
                    table_count=0, output_path=Path("./schema_a.json"))
        s.save()
        payload = json.loads((tmp_path / "feather_discover_state.json").read_text())
        assert payload["schema_version"] == 1


class TestClassify:
    def test_new_source_classified_new(self, tmp_path: Path):
        from feather_etl.discover_state import DiscoverState, classify

        s = DiscoverState.load(tmp_path)
        decisions = classify(state=s, current_names=["a", "b"], flag=None)
        assert decisions["a"] == "new"
        assert decisions["b"] == "new"

    def test_cached_source_classified_cached(self, tmp_path: Path):
        from feather_etl.discover_state import DiscoverState, classify

        s = DiscoverState.load(tmp_path)
        s.record_ok(name="a", type_="csv", fingerprint="csv:/x",
                    table_count=1, output_path=Path("./schema_a.json"))
        decisions = classify(state=s, current_names=["a"], flag=None)
        assert decisions["a"] == "cached"

    def test_failed_classified_retry_default(self, tmp_path: Path):
        from feather_etl.discover_state import DiscoverState, classify

        s = DiscoverState.load(tmp_path)
        s.record_failed(name="a", type_="csv", fingerprint="csv:/x",
                        error="oops")
        decisions = classify(state=s, current_names=["a"], flag=None)
        assert decisions["a"] == "retry"

    def test_refresh_forces_rerun(self, tmp_path: Path):
        from feather_etl.discover_state import DiscoverState, classify

        s = DiscoverState.load(tmp_path)
        s.record_ok(name="a", type_="csv", fingerprint="csv:/x",
                    table_count=1, output_path=Path("./schema_a.json"))
        decisions = classify(state=s, current_names=["a"], flag="refresh")
        assert decisions["a"] == "rerun"

    def test_retry_failed_skips_cached(self, tmp_path: Path):
        from feather_etl.discover_state import DiscoverState, classify

        s = DiscoverState.load(tmp_path)
        s.record_ok(name="a", type_="csv", fingerprint="csv:/x",
                    table_count=1, output_path=Path("./schema_a.json"))
        s.record_failed(name="b", type_="csv", fingerprint="csv:/y", error="x")
        decisions = classify(state=s, current_names=["a", "b"], flag="retry-failed")
        assert decisions["a"] == "skip"
        assert decisions["b"] == "retry"

    def test_removed_when_state_has_name_not_in_current(self, tmp_path: Path):
        from feather_etl.discover_state import DiscoverState, classify

        s = DiscoverState.load(tmp_path)
        s.record_ok(name="a", type_="csv", fingerprint="csv:/x",
                    table_count=1, output_path=Path("./schema_a.json"))
        decisions = classify(state=s, current_names=[], flag=None)
        assert decisions["a"] == "removed"
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/test_discover_state.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement `discover_state.py`**

Create `src/feather_etl/discover_state.py`:

```python
"""Persistent state for `feather discover` — feather_discover_state.json."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
STATE_FILENAME = "feather_discover_state.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DiscoverState:
    config_dir: Path
    sources: dict[str, dict] = field(default_factory=dict)
    auto_enumeration: dict[str, dict] = field(default_factory=dict)
    last_run_at: str | None = None

    @classmethod
    def load(cls, config_dir: Path) -> "DiscoverState":
        path = config_dir / STATE_FILENAME
        if not path.is_file():
            return cls(config_dir=config_dir)
        raw = json.loads(path.read_text())
        return cls(
            config_dir=config_dir,
            sources=raw.get("sources", {}),
            auto_enumeration=raw.get("auto_enumeration", {}),
            last_run_at=raw.get("last_run_at"),
        )

    def save(self) -> None:
        self.last_run_at = _now_iso()
        payload = {
            "schema_version": SCHEMA_VERSION,
            "last_run_at": self.last_run_at,
            "sources": self.sources,
            "auto_enumeration": self.auto_enumeration,
        }
        (self.config_dir / STATE_FILENAME).write_text(
            json.dumps(payload, indent=2)
        )

    def record_ok(self, *, name: str, type_: str, fingerprint: str,
                  table_count: int, output_path: Path,
                  host: str | None = None,
                  database: str | None = None) -> None:
        self.sources[name] = {
            "type": type_,
            "host": host,
            "database": database,
            "fingerprint": fingerprint,
            "status": "ok",
            "discovered_at": _now_iso(),
            "table_count": table_count,
            "output_path": str(output_path),
        }

    def record_failed(self, *, name: str, type_: str, fingerprint: str,
                      error: str, host: str | None = None,
                      database: str | None = None) -> None:
        prev = self.sources.get(name, {})
        attempts = int(prev.get("attempt_count", 0)) + 1
        self.sources[name] = {
            "type": type_,
            "host": host,
            "database": database,
            "fingerprint": fingerprint,
            "status": "failed",
            "attempted_at": _now_iso(),
            "error": error,
            "attempt_count": attempts,
        }

    def record_removed(self, name: str) -> None:
        if name in self.sources:
            self.sources[name]["status"] = "removed"
            self.sources[name]["removed_detected_at"] = _now_iso()

    def record_orphaned(self, name: str, note: str = "") -> None:
        if name in self.sources:
            self.sources[name]["status"] = "orphaned"
            self.sources[name]["orphaned_detected_at"] = _now_iso()
            if note:
                self.sources[name]["note"] = note

    def record_auto_enum(self, *, parent_name: str, type_: str,
                         host: str | None, databases_seen: list[str]) -> None:
        self.auto_enumeration[parent_name] = {
            "type": type_,
            "host": host,
            "last_enumerated_at": _now_iso(),
            "databases_seen": list(databases_seen),
        }


# --- classification ---------------------------------------------------------

# Decision values returned by classify():
#   "new"     — not in state, must discover
#   "cached"  — in state with status=ok, skip
#   "rerun"   — re-run (refresh forces this)
#   "retry"   — last attempt failed, retry
#   "skip"    — present but flag-skipped (e.g. cached entry under --retry-failed)
#   "removed" — was in state but no longer in current sources

def classify(*, state: DiscoverState, current_names: list[str],
             flag: str | None) -> dict[str, str]:
    """Return per-name decision for this run.

    flag: None, "refresh", "retry-failed", "prune".
    """
    decisions: dict[str, str] = {}
    state_names = set(state.sources)
    current = list(current_names)

    for name in current:
        entry = state.sources.get(name)
        if entry is None:
            decisions[name] = "new"
            continue
        status = entry.get("status", "ok")
        if flag == "refresh":
            decisions[name] = "rerun"
        elif flag == "retry-failed":
            decisions[name] = "retry" if status == "failed" else "skip"
        elif flag == "prune":
            decisions[name] = "skip"
        else:
            if status == "ok":
                decisions[name] = "cached"
            elif status == "failed":
                decisions[name] = "retry"
            else:  # removed/orphaned coming back into config
                decisions[name] = "rerun"

    for name in state_names - set(current):
        decisions[name] = "removed"
    return decisions
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_discover_state.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/feather_etl/discover_state.py tests/test_discover_state.py
git commit -m "feat(discover): DiscoverState manages feather_discover_state.json"
```

---

## Task 4.2 — Wire `DiscoverState` into `discover.py` (resume default)

**Files:**
- Modify: [src/feather_etl/commands/discover.py](../../../src/feather_etl/commands/discover.py)
- Modify: `tests/commands/test_discover_multi_source.py`

- [ ] **Step 1: Append failing test**

Append to `tests/commands/test_discover_multi_source.py`:

```python
class TestDiscoverResume:
    def test_second_run_skips_cached(self, runner, tmp_path, monkeypatch):
        from feather_etl.cli import app

        sqlite = tmp_path / "src.sqlite"
        shutil.copy2(FIXTURES_DIR / "sample_erp.sqlite", sqlite)
        cfg = multi_source_yaml(tmp_path, [
            {"name": "db", "type": "sqlite", "path": str(sqlite)},
        ])
        monkeypatch.chdir(tmp_path)

        r1 = runner.invoke(app, ["discover", "--config", str(cfg)])
        assert r1.exit_code == 0
        first_mtime = (tmp_path / "schema_db.json").stat().st_mtime_ns

        # Touch the schema JSON so we can detect whether it was rewritten.
        import time
        time.sleep(0.05)

        r2 = runner.invoke(app, ["discover", "--config", str(cfg)])
        assert r2.exit_code == 0
        assert "cached" in r2.output
        # Cached run does NOT rewrite the schema file.
        assert (tmp_path / "schema_db.json").stat().st_mtime_ns == first_mtime

    def test_state_file_written(self, runner, tmp_path, monkeypatch):
        from feather_etl.cli import app

        sqlite = tmp_path / "src.sqlite"
        shutil.copy2(FIXTURES_DIR / "sample_erp.sqlite", sqlite)
        cfg = multi_source_yaml(tmp_path, [
            {"name": "db", "type": "sqlite", "path": str(sqlite)},
        ])
        monkeypatch.chdir(tmp_path)

        r = runner.invoke(app, ["discover", "--config", str(cfg)])
        assert r.exit_code == 0
        state_path = tmp_path / "feather_discover_state.json"
        assert state_path.is_file()
        payload = json.loads(state_path.read_text())
        assert payload["schema_version"] == 1
        assert "db" in payload["sources"]
        assert payload["sources"]["db"]["status"] == "ok"
```

- [ ] **Step 2: Run test**

Run: `uv run pytest tests/commands/test_discover_multi_source.py::TestDiscoverResume -v`
Expected: FAIL.

- [ ] **Step 3: Wire state into discover**

Edit `src/feather_etl/commands/discover.py`. Add at top:

```python
from feather_etl.discover_state import DiscoverState, classify
```

Update `discover()` to load state, classify, act:

```python
def discover(
    config: Path = typer.Option("feather.yaml", "--config"),
) -> None:
    """Save source schema (tables + columns) per source to JSON files."""
    cfg = _load_and_validate(config)
    target_dir = cfg.config_dir
    state = DiscoverState.load(target_dir)

    sources = _expand_db_sources(cfg.sources)
    names = [s.name for s in sources]
    decisions = classify(state=state, current_names=names, flag=None)

    succeeded = 0
    failed_count = 0
    cached_count = 0
    total = len(sources)

    if state.last_run_at:
        typer.echo(
            f"Discovering from {config.name} (state file found, "
            f"last run {state.last_run_at})..."
        )
    else:
        typer.echo(f"Discovering from {config.name}...")

    for idx, source in enumerate(sources, start=1):
        prefix = f"  [{idx}/{total}] {source.name}"
        decision = decisions.get(source.name, "new")
        fingerprint = _fingerprint_for(source)

        if decision == "cached":
            entry = state.sources[source.name]
            cached_count += 1
            typer.echo(f"{prefix}  (cached, {entry.get('table_count', 0)} tables)")
            continue
        if decision == "skip":
            typer.echo(f"{prefix}  (skipped)")
            continue

        # "new", "retry", "rerun" — actually discover.
        if not source.check():
            err = getattr(source, "_last_error", "connection failed")
            failed_count += 1
            state.record_failed(
                name=source.name, type_=source.type, fingerprint=fingerprint,
                error=err, host=getattr(source, "host", None),
                database=getattr(source, "database", None),
            )
            typer.echo(f"{prefix}  → FAILED: {err}", err=True)
            continue
        try:
            out, count = _write_schema(source, target_dir)
        except Exception as e:
            failed_count += 1
            state.record_failed(
                name=source.name, type_=source.type, fingerprint=fingerprint,
                error=str(e), host=getattr(source, "host", None),
                database=getattr(source, "database", None),
            )
            typer.echo(f"{prefix}  → FAILED: {e}", err=True)
            continue
        succeeded += 1
        state.record_ok(
            name=source.name, type_=source.type, fingerprint=fingerprint,
            table_count=count, output_path=out,
            host=getattr(source, "host", None),
            database=getattr(source, "database", None),
        )
        label = "new" if decision == "new" else decision
        typer.echo(f"{prefix}  ({label})  → {count} tables → ./{out.name}")

    # Mark state-only entries as removed.
    for name, dec in decisions.items():
        if dec == "removed":
            state.record_removed(name)

    state.save()

    parts = [f"{succeeded + cached_count} succeeded"]
    if cached_count:
        parts.append(f"{cached_count} cached")
    if failed_count:
        parts.append(f"{failed_count} failed")
    typer.echo(f"\n{', '.join(parts)}.")

    if failed_count > 0:
        raise typer.Exit(code=2)


def _fingerprint_for(source) -> str:
    """Composition per spec §6.7.

    DB sources: '<type>:<host>:<port>:<database>'. File sources: '<type>:<absolute_path>'.
    """
    if hasattr(source, "host"):
        return (
            f"{source.type}:{source.host}:{source.port or ''}:"
            f"{source.database or ''}"
        )
    return f"{source.type}:{Path(source.path).resolve()}"
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/commands/test_discover_multi_source.py -v`
Expected: PASS.

---

## Task 4.3 — Flags `--refresh`, `--retry-failed`, `--prune`

**Files:**
- Modify: [src/feather_etl/commands/discover.py](../../../src/feather_etl/commands/discover.py)
- Modify: `tests/commands/test_discover_multi_source.py`

- [ ] **Step 1: Append failing tests**

```python
class TestDiscoverFlags:
    def test_refresh_rewrites_schema_files(self, runner, tmp_path, monkeypatch):
        from feather_etl.cli import app

        sqlite = tmp_path / "src.sqlite"
        shutil.copy2(FIXTURES_DIR / "sample_erp.sqlite", sqlite)
        cfg = multi_source_yaml(tmp_path, [
            {"name": "db", "type": "sqlite", "path": str(sqlite)},
        ])
        monkeypatch.chdir(tmp_path)

        runner.invoke(app, ["discover", "--config", str(cfg)])
        first_mtime = (tmp_path / "schema_db.json").stat().st_mtime_ns

        import time; time.sleep(0.05)
        r = runner.invoke(app, ["discover", "--config", str(cfg), "--refresh"])
        assert r.exit_code == 0
        assert (tmp_path / "schema_db.json").stat().st_mtime_ns > first_mtime

    def test_retry_failed_only_retries_failures(
        self, runner, tmp_path, monkeypatch
    ):
        """Simulate a failed source then verify --retry-failed retries only it."""
        from feather_etl.cli import app
        from feather_etl.discover_state import DiscoverState

        sqlite = tmp_path / "src.sqlite"
        shutil.copy2(FIXTURES_DIR / "sample_erp.sqlite", sqlite)
        bogus = tmp_path / "missing.sqlite"  # doesn't exist → check() fails

        cfg = multi_source_yaml(tmp_path, [
            {"name": "ok", "type": "sqlite", "path": str(sqlite)},
            {"name": "bad", "type": "sqlite", "path": str(bogus)},
        ])
        monkeypatch.chdir(tmp_path)

        r1 = runner.invoke(app, ["discover", "--config", str(cfg)])
        assert r1.exit_code == 2  # one failed
        ok_mtime = (tmp_path / "schema_ok.json").stat().st_mtime_ns

        # Make the bogus path valid.
        shutil.copy2(sqlite, bogus)

        import time; time.sleep(0.05)
        r2 = runner.invoke(
            app, ["discover", "--config", str(cfg), "--retry-failed"]
        )
        assert r2.exit_code == 0
        # ok was not re-discovered.
        assert (tmp_path / "schema_ok.json").stat().st_mtime_ns == ok_mtime
        # bad now has a schema file.
        assert (tmp_path / "schema_bad.json").is_file()

    def test_prune_removes_orphaned_state_and_file(
        self, runner, tmp_path, monkeypatch
    ):
        from feather_etl.cli import app

        a = tmp_path / "a.sqlite"; b = tmp_path / "b.sqlite"
        shutil.copy2(FIXTURES_DIR / "sample_erp.sqlite", a)
        shutil.copy2(FIXTURES_DIR / "sample_erp.sqlite", b)
        cfg = multi_source_yaml(tmp_path, [
            {"name": "a", "type": "sqlite", "path": str(a)},
            {"name": "b", "type": "sqlite", "path": str(b)},
        ])
        monkeypatch.chdir(tmp_path)
        runner.invoke(app, ["discover", "--config", str(cfg)])
        assert (tmp_path / "schema_a.json").exists()
        assert (tmp_path / "schema_b.json").exists()

        # Remove 'b' from feather.yaml.
        cfg2 = multi_source_yaml(tmp_path, [
            {"name": "a", "type": "sqlite", "path": str(a)},
        ])
        runner.invoke(app, ["discover", "--config", str(cfg2)])
        # 'b' marked removed in state, file still exists.
        assert (tmp_path / "schema_b.json").exists()

        r = runner.invoke(app, ["discover", "--config", str(cfg2), "--prune"])
        assert r.exit_code == 0
        assert not (tmp_path / "schema_b.json").exists()
        state = json.loads(
            (tmp_path / "feather_discover_state.json").read_text()
        )
        assert "b" not in state["sources"]
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/commands/test_discover_multi_source.py::TestDiscoverFlags -v`
Expected: FAIL.

- [ ] **Step 3: Add flags + handling**

Update the `discover()` signature to:

```python
def discover(
    config: Path = typer.Option("feather.yaml", "--config"),
    refresh: bool = typer.Option(False, "--refresh",
        help="Re-run discovery for every source, ignoring cached state."),
    retry_failed: bool = typer.Option(False, "--retry-failed",
        help="Only retry sources that previously failed."),
    prune: bool = typer.Option(False, "--prune",
        help="Delete state entries and JSON files for removed/orphaned sources."),
) -> None:
    ...
```

Resolve the active flag (only one is meaningful — if multiple are passed, last-write-wins per Typer convention):

```python
    flag: str | None = None
    if refresh:
        flag = "refresh"
    elif retry_failed:
        flag = "retry-failed"
    elif prune:
        flag = "prune"
```

Pass `flag=flag` into `classify()` and add a `--prune` post-pass that deletes state entries + files:

```python
    if flag == "prune":
        for name, dec in list(decisions.items()):
            entry = state.sources.get(name)
            if dec == "removed" or (entry and entry.get("status") == "orphaned"):
                if entry and entry.get("output_path"):
                    target = target_dir / Path(entry["output_path"]).name
                    if target.is_file():
                        target.unlink()
                state.sources.pop(name, None)
        state.save()
        typer.echo(f"Pruned removed/orphaned entries.")
        return
```

(The `--prune` branch happens before the discovery loop and short-circuits.)

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/commands/test_discover_multi_source.py::TestDiscoverFlags -v`
Expected: PASS.

---

## Task 4.4 — Permission-error path (E1)

**Files:**
- Modify: [src/feather_etl/commands/discover.py](../../../src/feather_etl/commands/discover.py)
- Modify: [tests/commands/test_discover.py](../../../tests/commands/test_discover.py)

- [ ] **Step 1: Append failing test to `tests/commands/test_discover.py`**

```python
class TestDiscoverAutoEnumPermissionError:
    def test_empty_enumeration_records_failed_with_hint(
        self, runner, tmp_path, monkeypatch
    ):
        """If list_databases() returns [], record FAILED with remediation hint (E1)."""
        from feather_etl.cli import app
        from feather_etl.sources.sqlserver import SqlServerSource

        # Patch list_databases to return [] regardless of connection.
        monkeypatch.setattr(SqlServerSource, "list_databases", lambda self: [])
        # Patch check() so it reports OK (irrelevant; expansion runs first).
        monkeypatch.setattr(SqlServerSource, "check", lambda self: True)

        cfg_text = """
sources:
  - name: erp
    type: sqlserver
    host: db.example.com
    user: u
    password: p
destination:
  path: ./out.duckdb
tables: []
"""
        (tmp_path / "feather.yaml").write_text(cfg_text)
        monkeypatch.chdir(tmp_path)

        r = runner.invoke(
            app, ["discover", "--config", str(tmp_path / "feather.yaml")]
        )
        assert r.exit_code == 2
        assert "Found 0 databases" in r.output or "Found 0 databases" in r.stdout
        assert "VIEW ANY DATABASE" in (r.output + (r.stdout or ""))
```

(Already partially handled by Task 3.3's `_expand_db_sources` — this test verifies the message reaches the user via the discover loop's "FAILED" branch.)

- [ ] **Step 2: Run test**

Run: `uv run pytest tests/commands/test_discover.py::TestDiscoverAutoEnumPermissionError -v`
Expected: PASS if Task 3.3's `_last_error` plumbing is wired through; FAIL otherwise. If FAIL, ensure the discover loop reads `getattr(source, "_last_error", ...)` for the error message.

- [ ] **Step 3: Run hands_on_test.sh + full suite**

```bash
uv run pytest -q
bash scripts/hands_on_test.sh
```

Both green.

- [ ] **Step 4: Commit Phase 4**

```bash
git add -A
git commit -m "feat(discover): state file with --refresh/--retry-failed/--prune flags"
```

---

# Phase 5 — Rename detection (commit 5)

After this phase: when a user renames a source in `feather.yaml`, discover infers it via fingerprint match. TTY: prompt `[Y/n]`. Non-TTY: exit 3 with guidance. Flags: `--yes` (auto-accept), `--no-renames` (orphan rejected entries).

## Task 5.1 — Fingerprint + rename inference in `discover_state.py`

**Files:**
- Modify: [src/feather_etl/discover_state.py](../../../src/feather_etl/discover_state.py)
- Modify: [tests/test_discover_state.py](../../../tests/test_discover_state.py)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_discover_state.py`:

```python
class TestRenameInference:
    def test_unambiguous_match_proposes_rename(self, tmp_path: Path):
        from feather_etl.discover_state import (
            DiscoverState,
            detect_renames,
        )

        s = DiscoverState.load(tmp_path)
        s.record_ok(name="erp", type_="sqlserver",
                    fingerprint="sqlserver:h:1433:SALES",
                    table_count=3, output_path=Path("./schema_erp.json"))
        proposals, ambiguous = detect_renames(
            state=s,
            current=[("erp_main", "sqlserver:h:1433:SALES")],
        )
        assert proposals == [("erp", "erp_main")]
        assert ambiguous == []

    def test_no_match_no_proposal(self, tmp_path: Path):
        from feather_etl.discover_state import (
            DiscoverState,
            detect_renames,
        )

        s = DiscoverState.load(tmp_path)
        s.record_ok(name="erp", type_="sqlserver",
                    fingerprint="sqlserver:h:1433:SALES",
                    table_count=3, output_path=Path("./schema_erp.json"))
        proposals, ambiguous = detect_renames(
            state=s,
            current=[("brand_new", "sqlserver:other:1433:OTHER")],
        )
        assert proposals == []
        assert ambiguous == []

    def test_ambiguous_two_state_entries_one_fingerprint(self, tmp_path: Path):
        from feather_etl.discover_state import (
            DiscoverState,
            detect_renames,
        )

        s = DiscoverState.load(tmp_path)
        s.record_ok(name="a", type_="csv", fingerprint="csv:/x",
                    table_count=1, output_path=Path("./schema_a.json"))
        s.record_ok(name="b", type_="csv", fingerprint="csv:/x",
                    table_count=1, output_path=Path("./schema_b.json"))
        proposals, ambiguous = detect_renames(
            state=s,
            current=[("c", "csv:/x")],
        )
        assert proposals == []
        assert ambiguous == [("c", ["a", "b"])]

    def test_apply_renames_moves_state_entries(self, tmp_path: Path):
        from feather_etl.discover_state import (
            DiscoverState,
            apply_renames,
        )

        s = DiscoverState.load(tmp_path)
        s.record_ok(name="erp", type_="sqlserver",
                    fingerprint="sqlserver:h:1433:SALES",
                    table_count=3, output_path=Path("./schema_erp.json"))
        # Auto-enumerated children
        s.record_ok(name="erp__SALES", type_="sqlserver",
                    fingerprint="sqlserver:h:1433:SALES",
                    table_count=3,
                    output_path=Path("./schema_erp__SALES.json"))

        # Pretend the schema files exist.
        (tmp_path / "schema_erp.json").write_text("[]")
        (tmp_path / "schema_erp__SALES.json").write_text("[]")

        apply_renames(state=s, renames=[("erp", "erp_main")],
                      config_dir=tmp_path)
        assert "erp_main" in s.sources
        assert "erp_main__SALES" in s.sources
        assert "erp" not in s.sources
        assert "erp__SALES" not in s.sources
        assert (tmp_path / "schema_erp_main.json").exists()
        assert (tmp_path / "schema_erp_main__SALES.json").exists()
        assert not (tmp_path / "schema_erp.json").exists()
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/test_discover_state.py::TestRenameInference -v`
Expected: FAIL — functions don't exist.

- [ ] **Step 3: Implement**

Append to `src/feather_etl/discover_state.py`:

```python
def detect_renames(
    *, state: DiscoverState, current: list[tuple[str, str]]
) -> tuple[list[tuple[str, str]], list[tuple[str, list[str]]]]:
    """Identify likely rename pairs by matching fingerprints.

    Args:
        state: existing DiscoverState.
        current: list of (name, fingerprint) tuples for sources currently in feather.yaml.

    Returns:
        (proposals, ambiguous) where:
          proposals = [(old_name, new_name), ...] for each unambiguous match
          ambiguous = [(new_name, [candidate_old_names, ...]), ...] for cases
                      where a single new fingerprint matches multiple state entries
    """
    current_names = {n for n, _ in current}
    state_only = {
        name: entry["fingerprint"]
        for name, entry in state.sources.items()
        if name not in current_names
        and entry.get("status") in ("ok", "removed", "failed")
    }

    proposals: list[tuple[str, str]] = []
    ambiguous: list[tuple[str, list[str]]] = []
    for new_name, fp in current:
        if new_name in state.sources:
            continue
        candidates = [old for old, old_fp in state_only.items() if old_fp == fp]
        if len(candidates) == 1:
            proposals.append((candidates[0], new_name))
        elif len(candidates) > 1:
            ambiguous.append((new_name, candidates))
    return proposals, ambiguous


def apply_renames(*, state: DiscoverState,
                  renames: list[tuple[str, str]],
                  config_dir: Path) -> None:
    """Move state entries (incl. auto-enumerated children) and rename JSON files."""
    for old, new in renames:
        # Move the parent.
        if old in state.sources:
            state.sources[new] = state.sources.pop(old)
        # Move auto-enum metadata.
        if old in state.auto_enumeration:
            state.auto_enumeration[new] = state.auto_enumeration.pop(old)
        # Move children: any name starting with old + "__".
        prefix = f"{old}__"
        for child_old in [n for n in state.sources if n.startswith(prefix)]:
            child_new = new + "__" + child_old[len(prefix):]
            state.sources[child_new] = state.sources.pop(child_old)
        # Rename JSON files on disk.
        for src_path in list(config_dir.glob(f"schema_{old}*.json")):
            suffix = src_path.name[len(f"schema_{old}"):]
            dst = config_dir / f"schema_{new}{suffix}"
            src_path.rename(dst)
            # Update output_path in any moved entry.
            for entry in state.sources.values():
                op = entry.get("output_path")
                if op and Path(op).name == src_path.name:
                    entry["output_path"] = str(dst)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_discover_state.py -v`
Expected: PASS.

---

## Task 5.2 — Discover prompts (TTY) / exits 3 (non-TTY); `--yes` / `--no-renames`

**Files:**
- Modify: [src/feather_etl/commands/discover.py](../../../src/feather_etl/commands/discover.py)
- Modify: `tests/commands/test_discover_multi_source.py`
- Modify: [tests/commands/test_discover.py](../../../tests/commands/test_discover.py)

- [ ] **Step 1: Append failing tests**

To `tests/commands/test_discover_multi_source.py`:

```python
class TestRenameNonTtyExit3:
    def test_rename_in_yaml_first_invocation_exits_3(
        self, runner, tmp_path, monkeypatch
    ):
        """First run with old name; second run with renamed config exits 3 in non-TTY."""
        from feather_etl.cli import app

        sqlite = tmp_path / "src.sqlite"
        shutil.copy2(FIXTURES_DIR / "sample_erp.sqlite", sqlite)
        monkeypatch.chdir(tmp_path)

        cfg1 = multi_source_yaml(tmp_path, [
            {"name": "erp", "type": "sqlite", "path": str(sqlite)},
        ])
        r1 = runner.invoke(app, ["discover", "--config", str(cfg1)])
        assert r1.exit_code == 0

        cfg2 = multi_source_yaml(tmp_path, [
            {"name": "erp_main", "type": "sqlite", "path": str(sqlite)},
        ])
        # CliRunner is non-TTY by default.
        r2 = runner.invoke(app, ["discover", "--config", str(cfg2)])
        assert r2.exit_code == 3
        assert "rename" in r2.output.lower()
        assert "--yes" in r2.output
        assert "--no-renames" in r2.output

    def test_yes_flag_migrates_state_and_files(
        self, runner, tmp_path, monkeypatch
    ):
        from feather_etl.cli import app

        sqlite = tmp_path / "src.sqlite"
        shutil.copy2(FIXTURES_DIR / "sample_erp.sqlite", sqlite)
        monkeypatch.chdir(tmp_path)

        cfg1 = multi_source_yaml(tmp_path, [
            {"name": "erp", "type": "sqlite", "path": str(sqlite)},
        ])
        runner.invoke(app, ["discover", "--config", str(cfg1)])
        assert (tmp_path / "schema_erp.json").exists()

        cfg2 = multi_source_yaml(tmp_path, [
            {"name": "erp_main", "type": "sqlite", "path": str(sqlite)},
        ])
        r = runner.invoke(
            app, ["discover", "--config", str(cfg2), "--yes"]
        )
        assert r.exit_code == 0
        assert (tmp_path / "schema_erp_main.json").exists()
        assert not (tmp_path / "schema_erp.json").exists()
        state = json.loads(
            (tmp_path / "feather_discover_state.json").read_text()
        )
        assert "erp_main" in state["sources"]
        assert "erp" not in state["sources"]

    def test_no_renames_orphans_old_entry(self, runner, tmp_path, monkeypatch):
        from feather_etl.cli import app

        sqlite = tmp_path / "src.sqlite"
        shutil.copy2(FIXTURES_DIR / "sample_erp.sqlite", sqlite)
        monkeypatch.chdir(tmp_path)

        cfg1 = multi_source_yaml(tmp_path, [
            {"name": "erp", "type": "sqlite", "path": str(sqlite)},
        ])
        runner.invoke(app, ["discover", "--config", str(cfg1)])

        cfg2 = multi_source_yaml(tmp_path, [
            {"name": "erp_main", "type": "sqlite", "path": str(sqlite)},
        ])
        r = runner.invoke(
            app, ["discover", "--config", str(cfg2), "--no-renames"]
        )
        assert r.exit_code == 0
        state = json.loads(
            (tmp_path / "feather_discover_state.json").read_text()
        )
        assert state["sources"]["erp"]["status"] == "orphaned"
        assert state["sources"]["erp_main"]["status"] == "ok"
```

To `tests/commands/test_discover.py`, add the ambiguous-match unit-style test:

```python
class TestRenameAmbiguousMatch:
    def test_ambiguous_fingerprint_match_errors(
        self, runner, tmp_path, monkeypatch
    ):
        """Two state entries pointing at same fingerprint → cannot infer rename."""
        from feather_etl.cli import app
        from feather_etl.discover_state import DiscoverState

        sqlite = tmp_path / "src.sqlite"
        shutil.copy2(FIXTURES_DIR / "sample_erp.sqlite", sqlite)
        monkeypatch.chdir(tmp_path)

        # Manually seed an ambiguous state.
        st = DiscoverState.load(tmp_path)
        fp = f"sqlite:{sqlite.resolve()}"
        st.record_ok(name="a", type_="sqlite", fingerprint=fp,
                     table_count=1, output_path=Path("./schema_a.json"))
        st.record_ok(name="b", type_="sqlite", fingerprint=fp,
                     table_count=1, output_path=Path("./schema_b.json"))
        st.save()

        cfg = multi_source_yaml(tmp_path, [
            {"name": "c", "type": "sqlite", "path": str(sqlite)},
        ])
        r = runner.invoke(app, ["discover", "--config", str(cfg)])
        assert r.exit_code != 0
        out = r.output + (r.stderr or "")
        assert "ambiguous" in out.lower()
        assert "a" in out and "b" in out
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/commands/test_discover.py::TestRenameAmbiguousMatch tests/commands/test_discover_multi_source.py::TestRenameNonTtyExit3 -v`
Expected: FAIL.

- [ ] **Step 3: Add flags + rename detection to discover.py**

Update the `discover()` signature:

```python
def discover(
    config: Path = typer.Option("feather.yaml", "--config"),
    refresh: bool = typer.Option(False, "--refresh"),
    retry_failed: bool = typer.Option(False, "--retry-failed"),
    prune: bool = typer.Option(False, "--prune"),
    yes: bool = typer.Option(False, "--yes",
        help="Auto-accept inferred renames."),
    no_renames: bool = typer.Option(False, "--no-renames",
        help="Reject inferred renames; old entries become orphaned."),
) -> None:
    ...
```

After loading state and expanding sources, before classify, run rename detection:

```python
import sys
from feather_etl.discover_state import (
    DiscoverState, classify, detect_renames, apply_renames,
)

    current_pairs = [(s.name, _fingerprint_for(s)) for s in sources]
    proposals, ambiguous = detect_renames(state=state, current=current_pairs)

    if ambiguous:
        for new_name, candidates in ambiguous:
            typer.echo(
                f"Ambiguous rename: '{new_name}' matches multiple state "
                f"entries: {', '.join(candidates)}. Resolve by editing "
                f"feather_discover_state.json or run with --no-renames.",
                err=True,
            )
        raise typer.Exit(code=2)

    if proposals:
        if no_renames:
            for old, _new in proposals:
                state.record_orphaned(
                    old, note="rename rejected via --no-renames"
                )
        elif yes:
            apply_renames(state=state, renames=proposals,
                          config_dir=target_dir)
            for old, new in proposals:
                typer.echo(f"Renamed '{old}' → '{new}'.")
        elif sys.stdin.isatty():
            for old, new in proposals:
                typer.echo(f"Detected likely rename: {old} → {new}")
            ans = typer.prompt("Accept all? [Y/n]", default="Y")
            if ans.strip().lower() in ("", "y", "yes"):
                apply_renames(state=state, renames=proposals,
                              config_dir=target_dir)
            else:
                for old, _new in proposals:
                    state.record_orphaned(old, note="rename rejected at prompt")
        else:
            for old, new in proposals:
                fp = _fingerprint_for(next(s for s in sources if s.name == new))
                cached_children = sum(
                    1 for n in state.sources if n.startswith(f"{old}__")
                )
                typer.echo(
                    f"\nDetected likely rename:\n"
                    f"  {old} → {new}\n"
                    f"  fingerprint: {fp}\n"
                    f"  cached schemas that would carry forward: "
                    f"{1 + cached_children}\n",
                    err=True,
                )
            typer.echo(
                "Interactive input not available. Pass one of:\n"
                "  --yes           accept rename, migrate state, continue\n"
                "  --no-renames    treat old name as orphaned (status: orphaned)",
                err=True,
            )
            raise typer.Exit(code=3)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/commands/test_discover_multi_source.py -v
uv run pytest tests/commands/test_discover.py -v
```

Both green.

- [ ] **Step 5: Run full suite + hands_on_test.sh**

```bash
uv run pytest -q
bash scripts/hands_on_test.sh
```

Both green.

- [ ] **Step 6: Commit Phase 5**

```bash
git add -A
git commit -m "feat(discover): rename detection via fingerprint with --yes/--no-renames"
```

---

# Phase 6 — Open the PR

- [ ] **Step 1: Confirm green from main**

```bash
git log --oneline main..HEAD
uv run pytest -q
bash scripts/hands_on_test.sh
ruff format .
ruff check .
```

If `ruff format` rewrote anything, commit the formatting in a separate commit before opening the PR (per the auto-memory `feedback_format_all_before_push`).

- [ ] **Step 2: Open PR**

```bash
git push -u origin <branch>
gh pr create --title "Multi-source discover (issue #8)" --body "$(cat <<'EOF'
## Summary
- `feather.yaml` now uses `sources:` (list); singular `source:` raises a hard migration error
- Each `Source` subclass owns its own `from_yaml` + `validate_source_table`; lazy registry closes #4
- `feather discover` iterates every source, auto-enumerates SQL Server/Postgres databases, and resumes via `feather_discover_state.json`
- Flags: `--refresh`, `--retry-failed`, `--prune`, `--yes`, `--no-renames`
- Rename detection via fingerprint (DB: type+host+port+database; file: type+abs_path)

Spec: `docs/superpowers/specs/2026-04-14-multi-source-discover-design.md`
Plan: `docs/superpowers/plans/2026-04-14-multi-source-discover.md`

## Test plan
- [ ] `uv run pytest -q` — all green (target: previous count + ~30)
- [ ] `bash scripts/hands_on_test.sh` — 61 checks pass
- [ ] Manual: heterogeneous YAML (sqlserver + csv + sqlite) writes one schema JSON per source
- [ ] Manual: rename a source in `feather.yaml` and verify the non-TTY exit-3 path prints `--yes` / `--no-renames` guidance
EOF
)"
```

---

# Self-review notes

Coverage cross-check (spec §3 decision table → tasks):

| Spec decision | Implemented in |
|---|---|
| `sources:` list required, non-empty | Task 2.1 |
| Singular `source:` → hard error | Task 2.1 |
| `database` XOR `databases` | Tasks 1.2, 1.4 |
| Auto-enumerate when neither | Task 3.3 |
| Name derivation (single) / required (multi) / unique | Task 2.1 |
| `tables[].source` deferred | Out of scope (spec D1) |
| C2 refactor — `from_yaml` per class | Tasks 1.1–1.6 |
| Lazy registry | Task 1.7 |
| Discover failure handling — exit 2 after all | Tasks 3.2 |
| Permission error E1 — empty enumeration → failed entry | Tasks 3.3, 4.4 |
| Discover `--json` dropped | Implicit — Task 3.2 rewrite removes ctx use |
| Default = resume | Tasks 4.2, 4.3 |
| `--prune` deletes state + JSON | Task 4.3 |
| Rename: fingerprint composition | Task 5.1 |
| Rename: TTY prompt / non-TTY exit 3 | Task 5.2 |
| `--yes` / `--no-renames` | Task 5.2 |
| Hard migration (BC1) | Task 2.1 |
| Co-location convention added to CONTRIBUTING | Task 2.6 |
| Per-code-unit edge-case tests + one E2E file | Throughout (test files in each task) |

All §3 decisions have a task. No placeholders remain — every "TBD"-shaped step in the original draft was either expanded inline or moved to a deferral noted by the spec.

---

# Post-#17 Compatibility Baseline

**Added:** 2026-04-15, after rebasing `phase-2-yaml-schema-flip` onto upstream/main at `89ff463` (issue #17 — "feat(discover): auto-open schema viewer and add view command").

Issue #17 merged to upstream `main` while Phase 1 + Phase 2 were in flight on a fork branch. Rebase was clean at the git level (all 8 Phase 2 commits replayed without merge conflicts), but one hidden semantic conflict surfaced at test time: `tests/commands/test_discover.py::test_invokes_shared_viewer_runtime_after_writing_json` was a new test introduced by #17 that wrote an inline singular `source: {...}` YAML — which Phase 2 Task 2.1's new parser rejects with a hard error. Fixed by flipping the inline fixture to `sources: [{...}]` during the rebase cleanup commit.

The rebase preserved the full contract from #17. Phase 3 — which rewrites `commands/discover.py` to iterate over `cfg.sources` and write one `schema_<name>.json` per source — **must not regress** any of the following behaviors from #17:

## Behavior contracts Phase 3 must preserve

1. **`feather discover --help` mentions both outputs.** The docstring must name *"schema JSON"* (the file on disk) **and** *"serve/open the schema viewer"* (the runtime side-effect). Phase 3's multi-source docstring should read something like "Save each source's schema to an auto-named JSON file, then serve/open the schema viewer" — plural but structurally identical.

2. **`discover` still calls the viewer runtime.** After writing schema JSON(s), `discover` calls `serve_and_open(viewer_target_dir, preferred_port=8000)` as its last side-effect. Default behavior is to serve + open (not headless). Phase 3 must keep this call at the end of the command — after the loop that writes per-source JSONs — with `viewer_target_dir` resolving to the directory containing the new JSON files.

3. **`serve_and_open` is monkeypatchable from `feather_etl.commands.discover`.** Existing tests (`test_invokes_shared_viewer_runtime_after_writing_json`, `test_runtime_emitted_output_line_is_surfaced`) use `monkeypatch.setattr(discover_cmd, "serve_and_open", ...)` to stub the viewer in non-blocking E2E flows. Phase 3 must keep `serve_and_open` imported at module level (not inside the function) so the monkeypatch keeps working. The stub pattern allows `fake_serve_and_open(target_dir, preferred_port=8000)` — Phase 3 must call with the same signature.

4. **`feather view --port` accepts 1–65535 with default 8000.** Unaffected by Phase 3 (Phase 3 only touches `discover`, not `view`), but noting it so the next implementer does not casually change `viewer_server.serve_and_open`'s signature — `view.py` shares the same underlying primitive.

5. **Viewer fallback on port conflict.** `viewer_server.py` has port-fallback logic when the preferred port is taken. Phase 3 must not reach into `viewer_server.py` to "simplify" anything; only `commands/discover.py` is in-scope.

6. **Non-blocking E2E test comment in `tests/test_e2e.py`.** #17 added a monkeypatch of `serve_and_open` in the E2E suite with a comment explaining why (so CI does not open a browser). Phase 3 must not delete that comment when it adds new E2E tests — if anything, Phase 3's new multi-source E2E tests need the same monkeypatch pattern.

## Rebase-cleanup checklist for any future Phase 3 implementer

When you start Phase 3 on a freshly-rebased branch, run these checks **before writing any code**:

```bash
uv run feather discover --help        # expect: "schema JSON" + "serve/open the schema viewer"
uv run feather view --help             # expect: --port 1-65535, default 8000
uv run pytest -q tests/commands/test_discover.py tests/commands/test_view.py tests/test_viewer_server.py
```

All three must be green before Task 3.1 begins. If any of them is red, the rebase was not clean — do NOT paper over the failure by editing the #17 test; instead, read the Phase 3 task body against what #17 expects and reconcile at the plan level first.

## Lesson for future cross-branch migrations

Git rebase can be clean while the **semantic contract** is broken. The failing test in this cleanup was created *after* Phase 2 started, so it never appeared in any Phase 2 diff — it was a landmine only the test suite could find. **Always run `uv run pytest -q` before trusting a "clean" rebase**, even when `git rebase` reports zero conflicts. The actual conflict surface is "files both sides touched" *plus* "files the other side created that reference contracts you changed." Git only sees the first half.
