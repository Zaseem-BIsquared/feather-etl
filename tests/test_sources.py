"""Tests for feather.sources module."""

from pathlib import Path

import pytest

from tests.conftest import FIXTURES_DIR


@pytest.fixture
def client_db(tmp_path: Path) -> Path:
    """Local copy of client.duckdb for source tests."""
    import shutil

    src = FIXTURES_DIR / "client.duckdb"
    dst = tmp_path / "client.duckdb"
    shutil.copy2(src, dst)
    return dst


class TestSourceDataclasses:
    def test_stream_schema_fields(self):
        from feather_etl.sources import StreamSchema

        s = StreamSchema(
            name="test",
            columns=[("id", "BIGINT"), ("name", "VARCHAR")],
            primary_key=["id"],
            supports_incremental=True,
        )
        assert s.name == "test"
        assert len(s.columns) == 2

    def test_change_result_fields(self):
        from feather_etl.sources import ChangeResult

        r = ChangeResult(changed=True, reason="first_run", metadata={})
        assert r.changed is True
        assert r.reason == "first_run"


class TestFileSource:
    def test_check_existing_path(self, tmp_path: Path):
        from feather_etl.sources.file_source import FileSource

        existing = tmp_path / "somefile"
        existing.write_text("data")
        source = FileSource(path=existing)
        assert source.check() is True

    def test_check_nonexistent_path(self, tmp_path: Path):
        from feather_etl.sources.file_source import FileSource

        source = FileSource(path=tmp_path / "nope")
        assert source.check() is False

    def test_detect_changes_first_run(self, tmp_path: Path):
        from feather_etl.sources.file_source import FileSource

        existing = tmp_path / "somefile"
        existing.write_text("data")
        source = FileSource(path=existing)
        result = source.detect_changes("any_table")
        assert result.changed is True
        assert result.reason == "first_run"
        assert "file_mtime" in result.metadata
        assert "file_hash" in result.metadata

    def test_detect_changes_unchanged(self, tmp_path: Path):
        """File untouched between runs → changed=False, empty metadata."""
        import os

        from feather_etl.sources.file_source import FileSource

        f = tmp_path / "somefile"
        f.write_text("data")
        source = FileSource(path=f)

        # Simulate a prior successful run by building last_state
        mtime = os.path.getmtime(f)
        first = source.detect_changes("any_table")
        last_state = {
            "last_file_mtime": mtime,
            "last_file_hash": first.metadata["file_hash"],
        }

        result = source.detect_changes("any_table", last_state=last_state)
        assert result.changed is False
        assert result.reason == "unchanged"
        assert result.metadata == {}

    def test_detect_changes_touch_scenario(self, tmp_path: Path):
        """Mtime changes but content identical → changed=False, metadata populated."""
        import os
        import time

        from feather_etl.sources.file_source import FileSource

        f = tmp_path / "somefile"
        f.write_text("data")
        source = FileSource(path=f)

        first = source.detect_changes("any_table")
        last_state = {
            "last_file_mtime": first.metadata["file_mtime"],
            "last_file_hash": first.metadata["file_hash"],
        }

        # Touch: update mtime without changing content
        time.sleep(0.05)
        os.utime(f, None)

        result = source.detect_changes("any_table", last_state=last_state)
        assert result.changed is False
        assert result.reason == "unchanged"
        # Metadata populated so pipeline can update watermark mtime
        assert "file_mtime" in result.metadata
        assert result.metadata["file_mtime"] != last_state["last_file_mtime"]
        assert result.metadata["file_hash"] == last_state["last_file_hash"]

    def test_detect_changes_content_changed(self, tmp_path: Path):
        """File content changes → changed=True, reason=hash_changed."""
        from feather_etl.sources.file_source import FileSource

        f = tmp_path / "somefile"
        f.write_text("original")
        source = FileSource(path=f)

        first = source.detect_changes("any_table")
        last_state = {
            "last_file_mtime": first.metadata["file_mtime"],
            "last_file_hash": first.metadata["file_hash"],
        }

        f.write_text("modified")

        result = source.detect_changes("any_table", last_state=last_state)
        assert result.changed is True
        assert result.reason == "hash_changed"
        assert "file_mtime" in result.metadata
        assert result.metadata["file_hash"] != last_state["last_file_hash"]

    def test_detect_changes_partial_state_null_mtime(self, tmp_path: Path):
        """Watermark exists but mtime is NULL (Slice 1 legacy) → treat as first run."""
        from feather_etl.sources.file_source import FileSource

        f = tmp_path / "somefile"
        f.write_text("data")
        source = FileSource(path=f)

        last_state = {"last_file_mtime": None, "last_file_hash": None}
        result = source.detect_changes("any_table", last_state=last_state)
        assert result.changed is True
        assert result.reason == "first_run"
        assert "file_mtime" in result.metadata
        assert "file_hash" in result.metadata

    def test_source_path_for_table_returns_self_path(self, tmp_path: Path):
        """Base FileSource returns self.path (whole file)."""
        from feather_etl.sources.file_source import FileSource

        f = tmp_path / "db.duckdb"
        f.write_text("data")
        source = FileSource(path=f)
        assert source._source_path_for_table("any_table") == f

    def test_path_stored(self, tmp_path: Path):
        from feather_etl.sources.file_source import FileSource

        p = tmp_path / "test"
        source = FileSource(path=p)
        assert source.path == p

    def test_duckdb_file_source_extends_file_source(self, client_db: Path):
        from feather_etl.sources.duckdb_file import DuckDBFileSource
        from feather_etl.sources.file_source import FileSource

        source = DuckDBFileSource(path=client_db)
        assert isinstance(source, FileSource)


class TestDuckDBFileSource:
    def test_check_valid_file(self, client_db: Path):
        from feather_etl.sources.duckdb_file import DuckDBFileSource

        source = DuckDBFileSource(path=client_db)
        assert source.check() is True

    def test_check_nonexistent_file(self, tmp_path: Path):
        from feather_etl.sources.duckdb_file import DuckDBFileSource

        source = DuckDBFileSource(path=tmp_path / "nope.duckdb")
        assert source.check() is False

    def test_discover_lists_tables(self, client_db: Path):
        from feather_etl.sources.duckdb_file import DuckDBFileSource

        source = DuckDBFileSource(path=client_db)
        schemas = source.discover()
        names = {s.name for s in schemas}
        assert "icube.SALESINVOICE" in names
        assert "icube.CUSTOMERMASTER" in names
        assert "icube.InventoryGroup" in names
        assert len(schemas) == 6

    def test_discover_has_columns(self, client_db: Path):
        from feather_etl.sources.duckdb_file import DuckDBFileSource

        source = DuckDBFileSource(path=client_db)
        schemas = source.discover()
        si = next(s for s in schemas if s.name == "icube.SALESINVOICE")
        col_names = [c[0] for c in si.columns]
        assert "ID" in col_names
        assert "SI_NO" in col_names

    def test_extract_returns_arrow(self, client_db: Path):
        import pyarrow as pa

        from feather_etl.sources.duckdb_file import DuckDBFileSource

        source = DuckDBFileSource(path=client_db)
        table = source.extract("icube.InventoryGroup")
        assert isinstance(table, pa.Table)
        assert table.num_rows == 66

    def test_extract_salesinvoice_row_count(self, client_db: Path):
        from feather_etl.sources.duckdb_file import DuckDBFileSource

        source = DuckDBFileSource(path=client_db)
        table = source.extract("icube.SALESINVOICE")
        assert table.num_rows == 11676

    def test_get_schema(self, client_db: Path):
        from feather_etl.sources.duckdb_file import DuckDBFileSource

        source = DuckDBFileSource(path=client_db)
        schema = source.get_schema("icube.InventoryGroup")
        col_names = [c[0] for c in schema]
        assert len(col_names) > 0

    def test_detect_changes_first_run(self, client_db: Path):
        from feather_etl.sources.duckdb_file import DuckDBFileSource

        source = DuckDBFileSource(path=client_db)
        result = source.detect_changes("icube.SALESINVOICE")
        assert result.changed is True
        assert result.reason == "first_run"
        assert "file_mtime" in result.metadata
        assert "file_hash" in result.metadata

    def test_source_path_for_table_returns_file_path(self, client_db: Path):
        """DuckDB source uses the single .duckdb file for all tables."""
        from feather_etl.sources.duckdb_file import DuckDBFileSource

        source = DuckDBFileSource(path=client_db)
        assert source._source_path_for_table("icube.SALESINVOICE") == client_db

    def test_check_corrupt_file_returns_false(self, tmp_path: Path):
        from feather_etl.sources.duckdb_file import DuckDBFileSource

        bad_file = tmp_path / "corrupt.duckdb"
        bad_file.write_bytes(b"this is not a valid duckdb file")
        source = DuckDBFileSource(path=bad_file)
        assert source.check() is False


class TestCsvSource:
    @pytest.fixture
    def csv_dir(self, tmp_path: Path) -> Path:
        """Copy CSV fixture directory to tmp_path."""
        import shutil

        src = FIXTURES_DIR / "csv_data"
        dst = tmp_path / "csv_data"
        shutil.copytree(src, dst)
        return dst

    def test_check_valid_directory(self, csv_dir: Path):
        from feather_etl.sources.csv import CsvSource

        source = CsvSource(path=csv_dir)
        assert source.check() is True

    def test_check_nonexistent_directory(self, tmp_path: Path):
        from feather_etl.sources.csv import CsvSource

        source = CsvSource(path=tmp_path / "nope")
        assert source.check() is False

    def test_check_file_not_directory(self, tmp_path: Path):
        from feather_etl.sources.csv import CsvSource

        f = tmp_path / "file.csv"
        f.write_text("a,b\n1,2\n")
        source = CsvSource(path=f)
        assert source.check() is False

    def test_discover_lists_csv_files(self, csv_dir: Path):
        from feather_etl.sources.csv import CsvSource

        source = CsvSource(path=csv_dir)
        schemas = source.discover()
        names = {s.name for s in schemas}
        assert names == {"orders.csv", "customers.csv", "products.csv"}

    def test_discover_has_columns(self, csv_dir: Path):
        from feather_etl.sources.csv import CsvSource

        source = CsvSource(path=csv_dir)
        schemas = source.discover()
        orders = next(s for s in schemas if s.name == "orders.csv")
        col_names = [c[0] for c in orders.columns]
        assert "order_id" in col_names
        assert "status" in col_names

    def test_discover_not_incremental(self, csv_dir: Path):
        from feather_etl.sources.csv import CsvSource

        source = CsvSource(path=csv_dir)
        schemas = source.discover()
        assert all(not s.supports_incremental for s in schemas)

    def test_extract_returns_arrow(self, csv_dir: Path):
        import pyarrow as pa

        from feather_etl.sources.csv import CsvSource

        source = CsvSource(path=csv_dir)
        table = source.extract("orders.csv")
        assert isinstance(table, pa.Table)
        assert table.num_rows == 5

    def test_extract_customers_row_count(self, csv_dir: Path):
        from feather_etl.sources.csv import CsvSource

        source = CsvSource(path=csv_dir)
        table = source.extract("customers.csv")
        assert table.num_rows == 4

    def test_extract_null_preserved(self, csv_dir: Path):
        from feather_etl.sources.csv import CsvSource

        source = CsvSource(path=csv_dir)
        table = source.extract("products.csv")
        assert table.num_rows == 3
        stock_qty = table.column("stock_qty")
        assert stock_qty[2].as_py() is None

    def test_get_schema(self, csv_dir: Path):
        from feather_etl.sources.csv import CsvSource

        source = CsvSource(path=csv_dir)
        schema = source.get_schema("orders.csv")
        col_names = [c[0] for c in schema]
        assert "order_id" in col_names
        assert len(col_names) > 0

    def test_detect_changes_first_run(self, csv_dir: Path):
        from feather_etl.sources.csv import CsvSource

        source = CsvSource(path=csv_dir)
        result = source.detect_changes("orders.csv")
        assert result.changed is True
        assert result.reason == "first_run"
        assert "file_mtime" in result.metadata
        assert "file_hash" in result.metadata

    def test_source_path_for_table_per_file(self, csv_dir: Path):
        """CSV source resolves per-file: path/orders.csv, not the directory."""
        from feather_etl.sources.csv import CsvSource

        source = CsvSource(path=csv_dir)
        assert source._source_path_for_table("orders.csv") == csv_dir / "orders.csv"


class TestSqliteSource:
    @pytest.fixture
    def sqlite_db(self, tmp_path: Path) -> Path:
        """Copy SQLite fixture to tmp_path."""
        import shutil

        src = FIXTURES_DIR / "sample_erp.sqlite"
        dst = tmp_path / "sample_erp.sqlite"
        shutil.copy2(src, dst)
        return dst

    def test_check_valid_file(self, sqlite_db: Path):
        from feather_etl.sources.sqlite import SqliteSource

        source = SqliteSource(path=sqlite_db)
        assert source.check() is True

    def test_check_nonexistent_file(self, tmp_path: Path):
        from feather_etl.sources.sqlite import SqliteSource

        source = SqliteSource(path=tmp_path / "nope.sqlite")
        assert source.check() is False

    def test_check_corrupt_file(self, tmp_path: Path):
        from feather_etl.sources.sqlite import SqliteSource

        bad = tmp_path / "bad.sqlite"
        bad.write_bytes(b"not a sqlite file")
        source = SqliteSource(path=bad)
        assert source.check() is False

    def test_discover_lists_tables(self, sqlite_db: Path):
        from feather_etl.sources.sqlite import SqliteSource

        source = SqliteSource(path=sqlite_db)
        schemas = source.discover()
        names = {s.name for s in schemas}
        assert names == {"orders", "customers", "products"}

    def test_discover_has_columns(self, sqlite_db: Path):
        from feather_etl.sources.sqlite import SqliteSource

        source = SqliteSource(path=sqlite_db)
        schemas = source.discover()
        orders = next(s for s in schemas if s.name == "orders")
        col_names = [c[0] for c in orders.columns]
        assert "order_id" in col_names
        assert "status" in col_names

    def test_discover_supports_incremental(self, sqlite_db: Path):
        from feather_etl.sources.sqlite import SqliteSource

        source = SqliteSource(path=sqlite_db)
        schemas = source.discover()
        assert all(s.supports_incremental for s in schemas)

    def test_extract_returns_arrow(self, sqlite_db: Path):
        import pyarrow as pa

        from feather_etl.sources.sqlite import SqliteSource

        source = SqliteSource(path=sqlite_db)
        table = source.extract("orders")
        assert isinstance(table, pa.Table)
        assert table.num_rows == 5

    def test_extract_customers_row_count(self, sqlite_db: Path):
        from feather_etl.sources.sqlite import SqliteSource

        source = SqliteSource(path=sqlite_db)
        table = source.extract("customers")
        assert table.num_rows == 4

    def test_extract_null_preserved(self, sqlite_db: Path):
        from feather_etl.sources.sqlite import SqliteSource

        source = SqliteSource(path=sqlite_db)
        table = source.extract("products")
        assert table.num_rows == 3
        stock_qty = table.column("stock_qty")
        assert stock_qty[2].as_py() is None

    def test_get_schema(self, sqlite_db: Path):
        from feather_etl.sources.sqlite import SqliteSource

        source = SqliteSource(path=sqlite_db)
        schema = source.get_schema("orders")
        col_names = [c[0] for c in schema]
        assert "order_id" in col_names
        assert len(col_names) > 0

    def test_detect_changes_first_run(self, sqlite_db: Path):
        from feather_etl.sources.sqlite import SqliteSource

        source = SqliteSource(path=sqlite_db)
        result = source.detect_changes("orders")
        assert result.changed is True
        assert result.reason == "first_run"
        assert "file_mtime" in result.metadata
        assert "file_hash" in result.metadata

    def test_source_path_for_table_returns_file_path(self, sqlite_db: Path):
        """SQLite source uses the single .sqlite file for all tables."""
        from feather_etl.sources.sqlite import SqliteSource

        source = SqliteSource(path=sqlite_db)
        assert source._source_path_for_table("orders") == sqlite_db


class TestSourceRegistry:
    def test_registry_resolves_duckdb(self):
        from feather_etl.sources.duckdb_file import DuckDBFileSource
        from feather_etl.sources.registry import get_source_class

        assert get_source_class("duckdb") is DuckDBFileSource

    def test_registry_resolves_csv(self):
        from feather_etl.sources.csv import CsvSource
        from feather_etl.sources.registry import get_source_class

        assert get_source_class("csv") is CsvSource

    def test_registry_resolves_sqlite(self):
        from feather_etl.sources.registry import get_source_class
        from feather_etl.sources.sqlite import SqliteSource

        assert get_source_class("sqlite") is SqliteSource

    def test_get_source_class_and_instantiate(self, client_db: Path):
        from feather_etl.sources.registry import get_source_class

        cls = get_source_class("duckdb")
        source = cls(path=client_db)
        assert source.check() is True

    def test_get_source_class_unknown_type(self):
        from feather_etl.sources.registry import get_source_class

        with pytest.raises(ValueError, match="not implemented"):
            get_source_class("cassandra")


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
        f.write_bytes(b"")
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
        assert errs and "unqualified" in errs[0]
        assert "'table'" in errs[0]  # suggests correct form

    def test_sqlite_rejects_invalid_identifier(self, tmp_path):
        from feather_etl.sources.sqlite import SqliteSource

        src = SqliteSource(path=tmp_path / "x.sqlite", name="x")
        errs = src.validate_source_table("bad-name")  # hyphen not allowed
        assert errs and "identifier" in errs[0].lower()

    def test_duckdb_requires_dotted(self, tmp_path):
        from feather_etl.sources.duckdb_file import DuckDBFileSource

        src = DuckDBFileSource(path=tmp_path / "x.duckdb", name="x")
        errs = src.validate_source_table("plain")
        assert errs and "schema.table" in errs[0]


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

        # Snapshot and restore sys.modules so clearing for this test does not
        # break module-level imports in other test files (e.g. test_sqlserver.py
        # imports SqlServerSource at the top level, and mock.patch targets that
        # same module object).
        snapshot = dict(sys.modules)

        try:
            for mod_name in list(sys.modules):
                if mod_name.startswith("feather_etl.sources"):
                    del sys.modules[mod_name]

            importlib.import_module("feather_etl.sources.registry")
            loaded = {m for m in sys.modules if m.startswith("feather_etl.sources")}

            assert "feather_etl.sources.sqlserver" not in loaded
            assert "feather_etl.sources.postgres" not in loaded
            assert "feather_etl.sources.csv" not in loaded
        finally:
            sys.modules.update(snapshot)


class TestFileSourcesRejectDbFields:
    """Every file source must reject DB fields in its YAML entry with the
    correct type name in the error message."""

    @pytest.mark.parametrize(
        "cls_path,type_name,path_factory",
        [
            ("feather_etl.sources.csv.CsvSource", "csv", "dir"),
            ("feather_etl.sources.sqlite.SqliteSource", "sqlite", "file"),
            ("feather_etl.sources.duckdb_file.DuckDBFileSource", "duckdb", "file"),
            ("feather_etl.sources.excel.ExcelSource", "excel", "dir"),
            ("feather_etl.sources.json_source.JsonSource", "json", "dir"),
        ],
    )
    def test_rejects_database_field(self, cls_path, type_name, path_factory, tmp_path):
        import importlib

        module_path, cls_name = cls_path.rsplit(".", 1)
        cls = getattr(importlib.import_module(module_path), cls_name)

        if path_factory == "dir":
            target = tmp_path / "d"
            target.mkdir()
        else:
            target = tmp_path / "f"
            target.write_bytes(b"")

        entry = {"name": "x", "type": type_name, "path": str(target),
                 "database": "BAD"}
        with pytest.raises(ValueError, match=f"not supported for source type {type_name}"):
            cls.from_yaml(entry, tmp_path)
