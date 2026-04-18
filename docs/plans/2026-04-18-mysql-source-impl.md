# MySQL Source Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `mysql` source type to feather-etl that extracts tables from MySQL databases into DuckDB, following the established Postgres/SQL Server pattern.

**Architecture:** New `MySQLSource` class extends `DatabaseSource`, implements the full `Source` protocol. Uses `mysql-connector-python` for connectivity. Registered in the lazy-import registry so the dependency is only loaded when a MySQL source is configured.

**Tech Stack:** `mysql-connector-python>=8.0`, PyArrow, DuckDB (test fixtures)

**Spec:** `docs/plans/2026-04-18-mysql-source.md`

---

## File Structure

| File | Responsibility |
|---|---|
| `src/feather_etl/sources/mysql.py` | **New.** `MySQLSource` class — config parsing, connectivity, discovery, extraction, change detection |
| `src/feather_etl/sources/registry.py` | **Modify (1 line).** Add `"mysql"` → lazy import entry |
| `pyproject.toml` | **Modify (1 line).** Add `mysql-connector-python` dependency |
| `tests/test_mysql.py` | **New.** Unit tests (mocked connector) + integration tests (real MySQL, skip-gated) |

---

### Task 1: Add `mysql-connector-python` dependency

**Files:**
- Modify: `pyproject.toml:23-32` (dependencies list)

- [ ] **Step 1: Add dependency to pyproject.toml**

Add `mysql-connector-python>=8.0` to the dependencies list:

```python
dependencies = [
    "duckdb>=1.0",
    "pyarrow>=15.0",
    "pyyaml>=6.0",
    "typer>=0.9",
    "pyodbc>=5.0",
    "psycopg2-binary>=2.9",
    "python-dotenv>=1.0",
    "pytz",  # not imported directly, but DuckDB needs it for timestamp→Python conversion
    "mysql-connector-python>=8.0",
]
```

- [ ] **Step 2: Install**

Run: `uv sync`

- [ ] **Step 3: Verify import works**

Run: `uv run python -c "import mysql.connector; print(mysql.connector.__version__)"`
Expected: prints a version number (e.g., `9.x.x`)

- [ ] **Step 4: Verify existing tests still pass**

Run: `uv run pytest -q`
Expected: 582 passed, 16 skipped

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "feat: add mysql-connector-python dependency for MySQL source (#25)"
```

---

### Task 2: Implement `MySQLSource` core — `from_yaml`, `check`, `validate_source_table`

**Files:**
- Create: `src/feather_etl/sources/mysql.py`
- Test: `tests/test_mysql.py`

- [ ] **Step 1: Write the failing tests for `from_yaml`**

Create `tests/test_mysql.py`:

```python
"""Tests for MySQL source.

Real-database tests are marked with a skip decorator and are skipped when
the local MySQL instance is not reachable.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# MySQLSource.from_yaml — unit tests (no DB needed)
# ---------------------------------------------------------------------------


class TestMySQLFromYaml:
    def test_minimal_entry_builds_connect_kwargs(self):
        from feather_etl.sources.mysql import MySQLSource

        entry = {
            "name": "wh",
            "type": "mysql",
            "host": "db.example.com",
            "user": "u",
            "password": "p",
            "database": "warehouse",
        }
        src = MySQLSource.from_yaml(entry, Path("."))
        assert src.name == "wh"
        assert src.host == "db.example.com"
        assert src.port == 3306
        assert src.database == "warehouse"
        assert src._connect_kwargs["host"] == "db.example.com"
        assert src._connect_kwargs["port"] == 3306
        assert src._connect_kwargs["database"] == "warehouse"
        assert src._connect_kwargs["user"] == "u"
        assert src._connect_kwargs["password"] == "p"

    def test_explicit_port(self):
        from feather_etl.sources.mysql import MySQLSource

        entry = {
            "name": "wh",
            "type": "mysql",
            "host": "h",
            "port": 3307,
            "user": "u",
            "password": "p",
            "database": "X",
        }
        src = MySQLSource.from_yaml(entry, Path("."))
        assert src.port == 3307
        assert src._connect_kwargs["port"] == 3307

    def test_explicit_connection_string(self):
        from feather_etl.sources.mysql import MySQLSource

        entry = {
            "name": "wh",
            "type": "mysql",
            "connection_string": "host=raw;database=verbatim",
        }
        src = MySQLSource.from_yaml(entry, Path("."))
        assert src.connection_string == "host=raw;database=verbatim"

    def test_databases_list_and_xor_rules(self):
        from feather_etl.sources.mysql import MySQLSource

        ok = {
            "name": "wh",
            "type": "mysql",
            "host": "h",
            "user": "u",
            "password": "p",
            "databases": ["A", "B"],
        }
        src = MySQLSource.from_yaml(ok, Path("."))
        assert src.databases == ["A", "B"]

        with pytest.raises(ValueError, match="mutually exclusive"):
            MySQLSource.from_yaml({**ok, "database": "C"}, Path("."))

        with pytest.raises(ValueError, match="non-empty"):
            MySQLSource.from_yaml({**ok, "databases": []}, Path("."))

    def test_missing_host_and_connection_string_raises(self):
        from feather_etl.sources.mysql import MySQLSource

        with pytest.raises(ValueError, match="requires either"):
            MySQLSource.from_yaml({"name": "x", "type": "mysql"}, Path("."))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_mysql.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'feather_etl.sources.mysql'`

- [ ] **Step 3: Write the failing tests for `check` and `validate_source_table`**

Append to `tests/test_mysql.py`:

```python
# ---------------------------------------------------------------------------
# MySQLSource — unit tests (no DB needed)
# ---------------------------------------------------------------------------


class TestMySQLSourceUnit:
    def test_source_type_is_mysql(self):
        from feather_etl.sources.mysql import MySQLSource

        assert MySQLSource.type == "mysql"

    def test_watermark_passthrough(self):
        """MySQLSource uses the default _format_watermark (ISO unchanged)."""
        from feather_etl.sources.mysql import MySQLSource

        src = MySQLSource(connection_string="dummy")
        assert src._format_watermark("2026-01-01T10:00:00") == "2026-01-01T10:00:00"

    def test_build_where_filter_only(self):
        from feather_etl.sources.mysql import MySQLSource

        src = MySQLSource(connection_string="dummy")
        result = src._build_where_clause(filter="active = 1")
        assert result == " WHERE (active = 1)"

    def test_build_where_watermark_only(self):
        from feather_etl.sources.mysql import MySQLSource

        src = MySQLSource(connection_string="dummy")
        result = src._build_where_clause(
            watermark_column="modified_at", watermark_value="2026-01-01"
        )
        assert result == " WHERE modified_at > '2026-01-01'"

    def test_build_where_both(self):
        from feather_etl.sources.mysql import MySQLSource

        src = MySQLSource(connection_string="dummy")
        result = src._build_where_clause(
            filter="active = 1",
            watermark_column="modified_at",
            watermark_value="2026-01-01",
        )
        assert result == " WHERE (active = 1) AND modified_at > '2026-01-01'"


class TestMySQLValidateSourceTable:
    def test_plain_table_ok(self):
        from feather_etl.sources.mysql import MySQLSource

        src = MySQLSource(connection_string="dummy", name="x")
        assert src.validate_source_table("orders") == []

    def test_qualified_table_ok(self):
        from feather_etl.sources.mysql import MySQLSource

        src = MySQLSource(connection_string="dummy", name="x")
        assert src.validate_source_table("mydb.orders") == []


# ---------------------------------------------------------------------------
# MySQLSource.check() — unit tests (mocked connector)
# ---------------------------------------------------------------------------


class TestMySQLCheckLastError:
    def test_check_failure_populates_last_error(self, monkeypatch):
        from feather_etl.sources import mysql as mysql_mod
        from feather_etl.sources.mysql import MySQLSource

        def boom(**kwargs):
            raise mysql_mod.mysql.connector.Error("Access denied for user 'root'")

        monkeypatch.setattr(mysql_mod.mysql.connector, "connect", boom)

        src = MySQLSource(connection_string="dummy")
        src._connect_kwargs = {"host": "nope"}
        assert src.check() is False
        assert src._last_error is not None
        assert "Access denied" in src._last_error

    def test_check_success_clears_last_error(self, monkeypatch):
        from feather_etl.sources import mysql as mysql_mod
        from feather_etl.sources.mysql import MySQLSource

        src = MySQLSource(connection_string="dummy")
        src._connect_kwargs = {"host": "localhost"}
        src._last_error = "stale error from a prior call"

        class FakeConn:
            def close(self):
                pass

        monkeypatch.setattr(
            mysql_mod.mysql.connector, "connect", lambda **k: FakeConn()
        )
        assert src.check() is True
        assert src._last_error is None
```

- [ ] **Step 4: Write minimal `MySQLSource` implementation**

Create `src/feather_etl/sources/mysql.py`:

```python
"""MySQL source — reads from MySQL via mysql-connector-python."""

from __future__ import annotations

import decimal
from pathlib import Path
from typing import ClassVar

import mysql.connector
import pyarrow as pa

from feather_etl.sources import ChangeResult, StreamSchema
from feather_etl.sources.database_source import DatabaseSource

# mysql.connector FieldType constants → PyArrow type
_MYSQL_FIELD_TYPE_MAP: dict[int, pa.DataType] = {
    0: pa.float64(),  # DECIMAL
    1: pa.int8(),  # TINY
    2: pa.int16(),  # SHORT
    3: pa.int64(),  # LONG
    4: pa.float32(),  # FLOAT
    5: pa.float64(),  # DOUBLE
    7: pa.timestamp("us"),  # TIMESTAMP
    8: pa.int64(),  # LONGLONG
    9: pa.int64(),  # INT24
    10: pa.date32(),  # DATE
    11: pa.time64("us"),  # TIME
    12: pa.timestamp("us"),  # DATETIME
    13: pa.int16(),  # YEAR
    15: pa.string(),  # VARCHAR
    16: pa.bool_(),  # BIT
    246: pa.float64(),  # NEWDECIMAL
    249: pa.binary(),  # TINY_BLOB
    250: pa.binary(),  # MEDIUM_BLOB
    251: pa.binary(),  # LONG_BLOB
    252: pa.binary(),  # BLOB
    253: pa.string(),  # VAR_STRING
    254: pa.string(),  # STRING
}

# INFORMATION_SCHEMA DATA_TYPE string → PyArrow type
_MYSQL_INFO_SCHEMA_TYPE_MAP: dict[str, pa.DataType] = {
    "int": pa.int64(),
    "bigint": pa.int64(),
    "smallint": pa.int16(),
    "tinyint": pa.int8(),
    "mediumint": pa.int64(),
    "float": pa.float32(),
    "double": pa.float64(),
    "decimal": pa.float64(),
    "numeric": pa.float64(),
    "bit": pa.bool_(),
    "boolean": pa.bool_(),
    "char": pa.string(),
    "varchar": pa.string(),
    "text": pa.string(),
    "tinytext": pa.string(),
    "mediumtext": pa.string(),
    "longtext": pa.string(),
    "enum": pa.string(),
    "set": pa.string(),
    "date": pa.date32(),
    "time": pa.time64("us"),
    "datetime": pa.timestamp("us"),
    "timestamp": pa.timestamp("us"),
    "year": pa.int16(),
    "binary": pa.binary(),
    "varbinary": pa.binary(),
    "blob": pa.binary(),
    "tinyblob": pa.binary(),
    "mediumblob": pa.binary(),
    "longblob": pa.binary(),
    "json": pa.string(),
}


def _mysql_field_type_to_arrow(type_code: int) -> pa.DataType:
    """Map a mysql.connector FieldType code to a PyArrow type."""
    return _MYSQL_FIELD_TYPE_MAP.get(type_code, pa.string())


class MySQLSource(DatabaseSource):
    """Source that reads tables from MySQL via mysql-connector-python."""

    type: ClassVar[str] = "mysql"

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
        self._connect_kwargs: dict = {}

    def _connect(self):
        """Return a MySQL connection using stored kwargs."""
        return mysql.connector.connect(**self._connect_kwargs)

    @classmethod
    def from_yaml(cls, entry: dict, config_dir: Path) -> "MySQLSource":
        name = entry.get("name", "")
        explicit_conn = entry.get("connection_string")
        host = entry.get("host")
        port = entry.get("port", 3306)
        user = entry.get("user")
        password = entry.get("password")
        database = entry.get("database")
        databases = entry.get("databases")

        if database is not None and databases is not None:
            raise ValueError("database and databases are mutually exclusive; use one.")
        if databases is not None and not databases:
            raise ValueError("databases list must be non-empty.")

        if explicit_conn:
            conn_str = explicit_conn
            connect_kwargs: dict = {}
        elif host:
            connect_kwargs = {"host": host, "port": port}
            if database:
                connect_kwargs["database"] = database
            if user:
                connect_kwargs["user"] = user
            if password:
                connect_kwargs["password"] = password
            conn_str = (
                f"host={host};port={port};database={database or ''}"
                f";user={user or ''}"
            )
        else:
            raise ValueError(
                "mysql source requires either 'connection_string' or 'host'."
            )

        source = cls(
            connection_string=conn_str,
            name=name,
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            databases=databases,
        )
        source._connect_kwargs = connect_kwargs
        source._explicit_name = bool(entry.get("name"))
        return source

    def validate_source_table(self, source_table: str) -> list[str]:
        return []

    def check(self) -> bool:
        self._last_error = None
        try:
            conn = self._connect()
            conn.close()
            return True
        except mysql.connector.Error as e:
            self._last_error = str(e)
            return False

    def discover(self) -> list[StreamSchema]:
        raise NotImplementedError("discover not yet implemented")

    def get_schema(self, table: str) -> list[tuple[str, str]]:
        raise NotImplementedError("get_schema not yet implemented")

    def extract(
        self,
        table: str,
        columns: list[str] | None = None,
        filter: str | None = None,
        watermark_column: str | None = None,
        watermark_value: str | None = None,
    ) -> pa.Table:
        raise NotImplementedError("extract not yet implemented")

    def detect_changes(
        self, table: str, last_state: dict[str, object] | None = None
    ) -> ChangeResult:
        raise NotImplementedError("detect_changes not yet implemented")

    def list_databases(self) -> list[str]:
        raise NotImplementedError("list_databases not yet implemented")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_mysql.py -v`
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/feather_etl/sources/mysql.py tests/test_mysql.py
git commit -m "feat: add MySQLSource core — from_yaml, check, validate (#25)"
```

---

### Task 3: Implement `discover`

**Files:**
- Modify: `src/feather_etl/sources/mysql.py` (replace `discover` stub)
- Test: `tests/test_mysql.py`

- [ ] **Step 1: Write the failing integration test**

Append to `tests/test_mysql.py`:

```python
MYSQL_CONN_KWARGS = {"host": "localhost", "user": "root", "database": "feather_test"}


def _mysql_available() -> bool:
    try:
        import mysql.connector

        conn = mysql.connector.connect(**MYSQL_CONN_KWARGS)
        conn.close()
        return True
    except Exception:
        return False


mysql_db = pytest.mark.skipif(not _mysql_available(), reason="MySQL not available")


# ---------------------------------------------------------------------------
# MySQLSource — integration tests (real MySQL required)
# ---------------------------------------------------------------------------


@mysql_db
class TestMySQLDiscoverIntegration:
    @pytest.fixture
    def source(self):
        from feather_etl.sources.mysql import MySQLSource

        src = MySQLSource(connection_string="")
        src._connect_kwargs = MYSQL_CONN_KWARGS
        src.database = "feather_test"
        return src

    def test_discover_returns_erp_tables(self, source):
        schemas = source.discover()
        names = {s.name for s in schemas}
        assert "erp_customers" in names
        assert "erp_products" in names
        assert "erp_sales" in names

    def test_discover_schema_fields(self, source):
        schemas = source.discover()
        sales = next(s for s in schemas if s.name == "erp_sales")
        assert sales.supports_incremental is True
        assert sales.primary_key is None
        col_names = [c[0] for c in sales.columns]
        assert "id" in col_names
        assert "amount" in col_names

    def test_discover_column_types(self, source):
        schemas = source.discover()
        sales = next(s for s in schemas if s.name == "erp_sales")
        col_types = {c[0]: c[1] for c in sales.columns}
        assert col_types["id"] == "int"
        assert col_types["product"] == "varchar"
        assert col_types["amount"] == "decimal"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_mysql.py::TestMySQLDiscoverIntegration -v`
Expected: FAIL — `NotImplementedError: discover not yet implemented`

- [ ] **Step 3: Implement `discover`**

Replace the `discover` stub in `src/feather_etl/sources/mysql.py`:

```python
    def discover(self) -> list[StreamSchema]:
        conn = self._connect()
        try:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT TABLE_NAME "
                "FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_SCHEMA = %s "
                "AND TABLE_TYPE = 'BASE TABLE' "
                "ORDER BY TABLE_NAME",
                (self.database,),
            )
            tables = cursor.fetchall()

            schemas: list[StreamSchema] = []
            for (table_name,) in tables:
                cursor.execute(
                    "SELECT COLUMN_NAME, DATA_TYPE "
                    "FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
                    "ORDER BY ORDINAL_POSITION",
                    (self.database, table_name),
                )
                cols = cursor.fetchall()
                schemas.append(
                    StreamSchema(
                        name=table_name,
                        columns=[(c[0], c[1]) for c in cols],
                        primary_key=None,
                        supports_incremental=True,
                    )
                )

            cursor.close()
            return schemas
        finally:
            conn.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_mysql.py::TestMySQLDiscoverIntegration -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/feather_etl/sources/mysql.py tests/test_mysql.py
git commit -m "feat: implement MySQLSource.discover() (#25)"
```

---

### Task 4: Implement `get_schema`

**Files:**
- Modify: `src/feather_etl/sources/mysql.py` (replace `get_schema` stub)
- Test: `tests/test_mysql.py`

- [ ] **Step 1: Write the failing integration test**

Append to `tests/test_mysql.py`:

```python
@mysql_db
class TestMySQLGetSchemaIntegration:
    @pytest.fixture
    def source(self):
        from feather_etl.sources.mysql import MySQLSource

        src = MySQLSource(connection_string="")
        src._connect_kwargs = MYSQL_CONN_KWARGS
        src.database = "feather_test"
        return src

    def test_get_schema_returns_columns(self, source):
        cols = source.get_schema("erp_sales")
        col_names = [c[0] for c in cols]
        assert "id" in col_names
        assert "customer_id" in col_names
        assert "product" in col_names
        assert "amount" in col_names
        assert "modified_at" in col_names

    def test_get_schema_returns_types(self, source):
        cols = source.get_schema("erp_sales")
        col_types = {c[0]: c[1] for c in cols}
        assert col_types["id"] == "int"
        assert col_types["amount"] == "decimal"
        assert col_types["modified_at"] == "timestamp"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_mysql.py::TestMySQLGetSchemaIntegration -v`
Expected: FAIL — `NotImplementedError: get_schema not yet implemented`

- [ ] **Step 3: Implement `get_schema`**

Replace the `get_schema` stub in `src/feather_etl/sources/mysql.py`:

```python
    def get_schema(self, table: str) -> list[tuple[str, str]]:
        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COLUMN_NAME, DATA_TYPE "
                "FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
                "ORDER BY ORDINAL_POSITION",
                (self.database, table),
            )
            cols = cursor.fetchall()
            cursor.close()
            return [(c[0], c[1]) for c in cols]
        finally:
            conn.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_mysql.py::TestMySQLGetSchemaIntegration -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/feather_etl/sources/mysql.py tests/test_mysql.py
git commit -m "feat: implement MySQLSource.get_schema() (#25)"
```

---

### Task 5: Implement `extract` with type mapping

**Files:**
- Modify: `src/feather_etl/sources/mysql.py` (replace `extract` stub)
- Test: `tests/test_mysql.py`

- [ ] **Step 1: Write the failing integration tests**

Append to `tests/test_mysql.py`:

```python
@mysql_db
class TestMySQLExtractIntegration:
    @pytest.fixture
    def source(self):
        from feather_etl.sources.mysql import MySQLSource

        src = MySQLSource(connection_string="")
        src._connect_kwargs = MYSQL_CONN_KWARGS
        src.database = "feather_test"
        return src

    def test_extract_full(self, source):
        import pyarrow as pa

        table = source.extract("erp_sales")
        assert isinstance(table, pa.Table)
        assert table.num_rows == 10
        assert "id" in table.column_names
        assert "amount" in table.column_names

    def test_extract_with_columns(self, source):
        table = source.extract("erp_customers", columns=["id", "name"])
        assert table.column_names == ["id", "name"]
        assert table.num_rows == 4

    def test_extract_with_filter(self, source):
        table = source.extract("erp_sales", filter="amount > 150")
        assert table.num_rows > 0
        amounts = table.column("amount").to_pylist()
        assert all(a > 150 for a in amounts)

    def test_extract_incremental_with_watermark(self, source):
        import pyarrow as pa

        table = source.extract(
            "erp_sales",
            watermark_column="modified_at",
            watermark_value="2026-01-03",
        )
        assert isinstance(table, pa.Table)
        assert table.num_rows > 0

    def test_extract_empty_result(self, source):
        import pyarrow as pa

        table = source.extract("erp_sales", filter="id = -999")
        assert isinstance(table, pa.Table)
        assert table.num_rows == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_mysql.py::TestMySQLExtractIntegration -v`
Expected: FAIL — `NotImplementedError: extract not yet implemented`

- [ ] **Step 3: Implement `extract`**

Replace the `extract` stub in `src/feather_etl/sources/mysql.py`:

```python
    def extract(
        self,
        table: str,
        columns: list[str] | None = None,
        filter: str | None = None,
        watermark_column: str | None = None,
        watermark_value: str | None = None,
    ) -> pa.Table:
        conn = self._connect()
        cursor = conn.cursor()

        col_clause = ", ".join(columns) if columns else "*"
        where = self._build_where_clause(filter, watermark_column, watermark_value)
        query = f"SELECT {col_clause} FROM {table}{where}"

        cursor.execute(query)

        if cursor.description is None:
            cursor.close()
            conn.close()
            return pa.table({})

        col_names = [desc[0] for desc in cursor.description]
        col_types = [_mysql_field_type_to_arrow(desc[1]) for desc in cursor.description]
        arrow_schema = pa.schema(
            [pa.field(name, typ) for name, typ in zip(col_names, col_types)]
        )

        batches: list[pa.RecordBatch] = []
        while True:
            rows = cursor.fetchmany(self.batch_size)
            if not rows:
                break
            col_data: dict[str, list] = {name: [] for name in col_names}
            for row in rows:
                for i, name in enumerate(col_names):
                    val = row[i]
                    if isinstance(val, decimal.Decimal):
                        val = float(val)
                    col_data[name].append(val)
            batch = pa.RecordBatch.from_pydict(col_data, schema=arrow_schema)
            batches.append(batch)

        cursor.close()
        conn.close()

        if not batches:
            return pa.table(
                {
                    name: pa.array([], type=typ)
                    for name, typ in zip(col_names, col_types)
                }
            )

        return pa.Table.from_batches(batches, schema=arrow_schema)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_mysql.py::TestMySQLExtractIntegration -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/feather_etl/sources/mysql.py tests/test_mysql.py
git commit -m "feat: implement MySQLSource.extract() with type mapping (#25)"
```

---

### Task 6: Implement `detect_changes`

**Files:**
- Modify: `src/feather_etl/sources/mysql.py` (replace `detect_changes` stub)
- Test: `tests/test_mysql.py`

- [ ] **Step 1: Write the failing integration tests**

Append to `tests/test_mysql.py`:

```python
@mysql_db
class TestMySQLDetectChangesIntegration:
    @pytest.fixture
    def source(self):
        from feather_etl.sources.mysql import MySQLSource

        src = MySQLSource(connection_string="")
        src._connect_kwargs = MYSQL_CONN_KWARGS
        src.database = "feather_test"
        return src

    def test_detect_changes_first_run(self, source):
        result = source.detect_changes("erp_sales", last_state=None)
        assert result.changed is True
        assert result.reason == "first_run"
        assert "checksum" in result.metadata

    def test_detect_changes_unchanged(self, source):
        first = source.detect_changes("erp_sales", last_state=None)
        last_state = {
            "last_checksum": first.metadata.get("checksum"),
        }
        second = source.detect_changes("erp_sales", last_state=last_state)
        assert second.changed is False
        assert second.reason == "unchanged"

    def test_detect_changes_incremental_always_changed(self, source):
        last_state = {"strategy": "incremental"}
        result = source.detect_changes("erp_sales", last_state=last_state)
        assert result.changed is True
        assert result.reason == "incremental"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_mysql.py::TestMySQLDetectChangesIntegration -v`
Expected: FAIL — `NotImplementedError: detect_changes not yet implemented`

- [ ] **Step 3: Implement `detect_changes`**

Replace the `detect_changes` stub in `src/feather_etl/sources/mysql.py`:

```python
    def detect_changes(
        self, table: str, last_state: dict[str, object] | None = None
    ) -> ChangeResult:
        if last_state is not None and last_state.get("strategy") == "incremental":
            return ChangeResult(changed=True, reason="incremental")

        try:
            conn = self._connect()
            cursor = conn.cursor()
            # CHECKSUM TABLE returns (table_name, checksum_value)
            qualified = f"{self.database}.{table}" if self.database else table
            cursor.execute(f"CHECKSUM TABLE {qualified}")
            row = cursor.fetchone()
            cursor.close()
            conn.close()
        except mysql.connector.Error:
            return ChangeResult(changed=True, reason="checksum_error")

        if row is None:
            return ChangeResult(changed=True, reason="first_run")

        current_checksum = row[1]

        if last_state is None or last_state.get("last_checksum") is None:
            return ChangeResult(
                changed=True,
                reason="first_run",
                metadata={"checksum": current_checksum},
            )

        if current_checksum == last_state.get("last_checksum"):
            return ChangeResult(changed=False, reason="unchanged")

        return ChangeResult(
            changed=True,
            reason="checksum_changed",
            metadata={"checksum": current_checksum},
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_mysql.py::TestMySQLDetectChangesIntegration -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/feather_etl/sources/mysql.py tests/test_mysql.py
git commit -m "feat: implement MySQLSource.detect_changes() (#25)"
```

---

### Task 7: Implement `list_databases`

**Files:**
- Modify: `src/feather_etl/sources/mysql.py` (replace `list_databases` stub)
- Test: `tests/test_mysql.py`

- [ ] **Step 1: Write the failing unit test**

Append to `tests/test_mysql.py`:

```python
# ---------------------------------------------------------------------------
# MySQLSource.list_databases — unit tests (mocked connector)
# ---------------------------------------------------------------------------


class TestMySQLListDatabases:
    def test_query_filters_system_dbs(self, monkeypatch):
        from feather_etl.sources import mysql as mysql_mod
        from feather_etl.sources.mysql import MySQLSource

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

        monkeypatch.setattr(
            mysql_mod.mysql.connector, "connect", lambda **k: FakeConn()
        )

        src = MySQLSource(connection_string="dummy")
        src._connect_kwargs = {"host": "localhost"}
        result = src.list_databases()

        assert result == ["warehouse", "analytics"]
        sql = captured_sql[0]
        assert "SCHEMA_NAME" in sql
        assert "information_schema" in sql
        assert "mysql" in sql
        assert "performance_schema" in sql
        assert "sys" in sql

    def test_propagates_connector_error(self, monkeypatch):
        from feather_etl.sources import mysql as mysql_mod
        from feather_etl.sources.mysql import MySQLSource

        def raise_(**k):
            raise mysql_mod.mysql.connector.Error("connection refused")

        monkeypatch.setattr(mysql_mod.mysql.connector, "connect", raise_)
        src = MySQLSource(connection_string="dummy")
        src._connect_kwargs = {"host": "nope"}
        with pytest.raises(mysql_mod.mysql.connector.Error):
            src.list_databases()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_mysql.py::TestMySQLListDatabases -v`
Expected: FAIL — `NotImplementedError: list_databases not yet implemented`

- [ ] **Step 3: Implement `list_databases`**

Replace the `list_databases` stub in `src/feather_etl/sources/mysql.py`:

```python
    def list_databases(self) -> list[str]:
        """Return user databases on the server (excludes system databases).

        Raises mysql.connector.Error on connection/query failure (caller handles).
        """
        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA "
                "WHERE SCHEMA_NAME NOT IN "
                "('information_schema', 'mysql', 'performance_schema', 'sys') "
                "ORDER BY SCHEMA_NAME"
            )
            rows = cursor.fetchall()
            cursor.close()
            return [r[0] for r in rows]
        finally:
            conn.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_mysql.py::TestMySQLListDatabases -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/feather_etl/sources/mysql.py tests/test_mysql.py
git commit -m "feat: implement MySQLSource.list_databases() (#25)"
```

---

### Task 8: Register in registry

**Files:**
- Modify: `src/feather_etl/sources/registry.py:17-25` (add to `SOURCE_CLASSES`)
- Test: `tests/test_mysql.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_mysql.py`:

```python
# ---------------------------------------------------------------------------
# Registry — unit test
# ---------------------------------------------------------------------------


class TestMySQLRegistry:
    def test_source_in_registry(self):
        from feather_etl.sources.mysql import MySQLSource
        from feather_etl.sources.registry import get_source_class

        assert get_source_class("mysql") is MySQLSource
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_mysql.py::TestMySQLRegistry -v`
Expected: FAIL — `ValueError: Source type 'mysql' is not implemented`

- [ ] **Step 3: Add registry entry**

Add to `SOURCE_CLASSES` dict in `src/feather_etl/sources/registry.py`:

```python
SOURCE_CLASSES: dict[str, str] = {
    "duckdb": "feather_etl.sources.duckdb_file.DuckDBFileSource",
    "csv": "feather_etl.sources.csv.CsvSource",
    "sqlite": "feather_etl.sources.sqlite.SqliteSource",
    "sqlserver": "feather_etl.sources.sqlserver.SqlServerSource",
    "postgres": "feather_etl.sources.postgres.PostgresSource",
    "excel": "feather_etl.sources.excel.ExcelSource",
    "json": "feather_etl.sources.json_source.JsonSource",
    "mysql": "feather_etl.sources.mysql.MySQLSource",
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_mysql.py::TestMySQLRegistry -v`
Expected: PASS

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest -q`
Expected: 582+ passed, skipped count may increase (MySQL integration tests counted)

- [ ] **Step 6: Commit**

```bash
git add src/feather_etl/sources/registry.py tests/test_mysql.py
git commit -m "feat: register mysql source type in registry (#25)"
```
