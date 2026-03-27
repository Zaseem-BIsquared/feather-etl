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


class TestSourceProtocol:
    def test_stream_schema_fields(self):
        from feather.sources import StreamSchema

        s = StreamSchema(
            name="test",
            columns=[("id", "BIGINT"), ("name", "VARCHAR")],
            primary_key=["id"],
            supports_incremental=True,
        )
        assert s.name == "test"
        assert len(s.columns) == 2

    def test_change_result_fields(self):
        from feather.sources import ChangeResult

        r = ChangeResult(changed=True, reason="first_run", metadata={})
        assert r.changed is True
        assert r.reason == "first_run"


class TestFileSource:
    def test_check_existing_path(self, tmp_path: Path):
        from feather.sources.file_source import FileSource

        existing = tmp_path / "somefile"
        existing.write_text("data")
        source = FileSource(path=existing)
        assert source.check() is True

    def test_check_nonexistent_path(self, tmp_path: Path):
        from feather.sources.file_source import FileSource

        source = FileSource(path=tmp_path / "nope")
        assert source.check() is False

    def test_detect_changes_always_changed(self, tmp_path: Path):
        from feather.sources.file_source import FileSource

        existing = tmp_path / "somefile"
        existing.write_text("data")
        source = FileSource(path=existing)
        result = source.detect_changes("any_table")
        assert result.changed is True
        assert result.reason == "first_run"

    def test_path_stored(self, tmp_path: Path):
        from feather.sources.file_source import FileSource

        p = tmp_path / "test"
        source = FileSource(path=p)
        assert source.path == p

    def test_duckdb_file_source_extends_file_source(self, client_db: Path):
        from feather.sources.duckdb_file import DuckDBFileSource
        from feather.sources.file_source import FileSource

        source = DuckDBFileSource(path=client_db)
        assert isinstance(source, FileSource)


class TestDuckDBFileSource:
    def test_check_valid_file(self, client_db: Path):
        from feather.sources.duckdb_file import DuckDBFileSource

        source = DuckDBFileSource(path=client_db)
        assert source.check() is True

    def test_check_nonexistent_file(self, tmp_path: Path):
        from feather.sources.duckdb_file import DuckDBFileSource

        source = DuckDBFileSource(path=tmp_path / "nope.duckdb")
        assert source.check() is False

    def test_discover_lists_tables(self, client_db: Path):
        from feather.sources.duckdb_file import DuckDBFileSource

        source = DuckDBFileSource(path=client_db)
        schemas = source.discover()
        names = {s.name for s in schemas}
        assert "icube.SALESINVOICE" in names
        assert "icube.CUSTOMERMASTER" in names
        assert "icube.InventoryGroup" in names
        assert len(schemas) == 6

    def test_discover_has_columns(self, client_db: Path):
        from feather.sources.duckdb_file import DuckDBFileSource

        source = DuckDBFileSource(path=client_db)
        schemas = source.discover()
        si = next(s for s in schemas if s.name == "icube.SALESINVOICE")
        col_names = [c[0] for c in si.columns]
        assert "ID" in col_names
        assert "SI_NO" in col_names

    def test_extract_returns_arrow(self, client_db: Path):
        import pyarrow as pa

        from feather.sources.duckdb_file import DuckDBFileSource

        source = DuckDBFileSource(path=client_db)
        table = source.extract("icube.InventoryGroup")
        assert isinstance(table, pa.Table)
        assert table.num_rows == 66

    def test_extract_salesinvoice_row_count(self, client_db: Path):
        from feather.sources.duckdb_file import DuckDBFileSource

        source = DuckDBFileSource(path=client_db)
        table = source.extract("icube.SALESINVOICE")
        assert table.num_rows == 11676

    def test_get_schema(self, client_db: Path):
        from feather.sources.duckdb_file import DuckDBFileSource

        source = DuckDBFileSource(path=client_db)
        schema = source.get_schema("icube.InventoryGroup")
        col_names = [c[0] for c in schema]
        assert len(col_names) > 0

    def test_detect_changes_always_true(self, client_db: Path):
        from feather.sources.duckdb_file import DuckDBFileSource

        source = DuckDBFileSource(path=client_db)
        result = source.detect_changes("icube.SALESINVOICE")
        assert result.changed is True
        assert result.reason == "first_run"

    def test_check_corrupt_file_returns_false(self, tmp_path: Path):
        from feather.sources.duckdb_file import DuckDBFileSource

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
        from feather.sources.csv import CsvSource

        source = CsvSource(path=csv_dir)
        assert source.check() is True

    def test_check_nonexistent_directory(self, tmp_path: Path):
        from feather.sources.csv import CsvSource

        source = CsvSource(path=tmp_path / "nope")
        assert source.check() is False

    def test_check_file_not_directory(self, tmp_path: Path):
        from feather.sources.csv import CsvSource

        f = tmp_path / "file.csv"
        f.write_text("a,b\n1,2\n")
        source = CsvSource(path=f)
        assert source.check() is False

    def test_discover_lists_csv_files(self, csv_dir: Path):
        from feather.sources.csv import CsvSource

        source = CsvSource(path=csv_dir)
        schemas = source.discover()
        names = {s.name for s in schemas}
        assert names == {"orders.csv", "customers.csv", "products.csv"}

    def test_discover_has_columns(self, csv_dir: Path):
        from feather.sources.csv import CsvSource

        source = CsvSource(path=csv_dir)
        schemas = source.discover()
        orders = next(s for s in schemas if s.name == "orders.csv")
        col_names = [c[0] for c in orders.columns]
        assert "order_id" in col_names
        assert "status" in col_names

    def test_discover_not_incremental(self, csv_dir: Path):
        from feather.sources.csv import CsvSource

        source = CsvSource(path=csv_dir)
        schemas = source.discover()
        assert all(not s.supports_incremental for s in schemas)

    def test_extract_returns_arrow(self, csv_dir: Path):
        import pyarrow as pa

        from feather.sources.csv import CsvSource

        source = CsvSource(path=csv_dir)
        table = source.extract("orders.csv")
        assert isinstance(table, pa.Table)
        assert table.num_rows == 5

    def test_extract_customers_row_count(self, csv_dir: Path):
        from feather.sources.csv import CsvSource

        source = CsvSource(path=csv_dir)
        table = source.extract("customers.csv")
        assert table.num_rows == 4

    def test_extract_null_preserved(self, csv_dir: Path):
        from feather.sources.csv import CsvSource

        source = CsvSource(path=csv_dir)
        table = source.extract("products.csv")
        assert table.num_rows == 3
        stock_qty = table.column("stock_qty")
        assert stock_qty[2].as_py() is None

    def test_get_schema(self, csv_dir: Path):
        from feather.sources.csv import CsvSource

        source = CsvSource(path=csv_dir)
        schema = source.get_schema("orders.csv")
        col_names = [c[0] for c in schema]
        assert "order_id" in col_names
        assert len(col_names) > 0

    def test_detect_changes_always_true(self, csv_dir: Path):
        from feather.sources.csv import CsvSource

        source = CsvSource(path=csv_dir)
        result = source.detect_changes("orders.csv")
        assert result.changed is True
        assert result.reason == "first_run"


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
        from feather.sources.sqlite import SqliteSource

        source = SqliteSource(path=sqlite_db)
        assert source.check() is True

    def test_check_nonexistent_file(self, tmp_path: Path):
        from feather.sources.sqlite import SqliteSource

        source = SqliteSource(path=tmp_path / "nope.sqlite")
        assert source.check() is False

    def test_check_corrupt_file(self, tmp_path: Path):
        from feather.sources.sqlite import SqliteSource

        bad = tmp_path / "bad.sqlite"
        bad.write_bytes(b"not a sqlite file")
        source = SqliteSource(path=bad)
        assert source.check() is False

    def test_discover_lists_tables(self, sqlite_db: Path):
        from feather.sources.sqlite import SqliteSource

        source = SqliteSource(path=sqlite_db)
        schemas = source.discover()
        names = {s.name for s in schemas}
        assert names == {"orders", "customers", "products"}

    def test_discover_has_columns(self, sqlite_db: Path):
        from feather.sources.sqlite import SqliteSource

        source = SqliteSource(path=sqlite_db)
        schemas = source.discover()
        orders = next(s for s in schemas if s.name == "orders")
        col_names = [c[0] for c in orders.columns]
        assert "order_id" in col_names
        assert "status" in col_names

    def test_discover_supports_incremental(self, sqlite_db: Path):
        from feather.sources.sqlite import SqliteSource

        source = SqliteSource(path=sqlite_db)
        schemas = source.discover()
        assert all(s.supports_incremental for s in schemas)

    def test_extract_returns_arrow(self, sqlite_db: Path):
        import pyarrow as pa

        from feather.sources.sqlite import SqliteSource

        source = SqliteSource(path=sqlite_db)
        table = source.extract("orders")
        assert isinstance(table, pa.Table)
        assert table.num_rows == 5

    def test_extract_customers_row_count(self, sqlite_db: Path):
        from feather.sources.sqlite import SqliteSource

        source = SqliteSource(path=sqlite_db)
        table = source.extract("customers")
        assert table.num_rows == 4

    def test_extract_null_preserved(self, sqlite_db: Path):
        from feather.sources.sqlite import SqliteSource

        source = SqliteSource(path=sqlite_db)
        table = source.extract("products")
        assert table.num_rows == 3
        stock_qty = table.column("stock_qty")
        assert stock_qty[2].as_py() is None

    def test_get_schema(self, sqlite_db: Path):
        from feather.sources.sqlite import SqliteSource

        source = SqliteSource(path=sqlite_db)
        schema = source.get_schema("orders")
        col_names = [c[0] for c in schema]
        assert "order_id" in col_names
        assert len(col_names) > 0

    def test_detect_changes_always_true(self, sqlite_db: Path):
        from feather.sources.sqlite import SqliteSource

        source = SqliteSource(path=sqlite_db)
        result = source.detect_changes("orders")
        assert result.changed is True
        assert result.reason == "first_run"


class TestSourceRegistry:
    def test_registry_resolves_duckdb(self):
        from feather.sources.duckdb_file import DuckDBFileSource
        from feather.sources.registry import SOURCE_REGISTRY

        assert SOURCE_REGISTRY["duckdb"] is DuckDBFileSource

    def test_registry_resolves_csv(self):
        from feather.sources.csv import CsvSource
        from feather.sources.registry import SOURCE_REGISTRY

        assert SOURCE_REGISTRY["csv"] is CsvSource

    def test_registry_resolves_sqlite(self):
        from feather.sources.registry import SOURCE_REGISTRY
        from feather.sources.sqlite import SqliteSource

        assert SOURCE_REGISTRY["sqlite"] is SqliteSource

    def test_create_source(self, client_db: Path):
        from feather.config import SourceConfig
        from feather.sources.registry import create_source

        cfg = SourceConfig(type="duckdb", path=client_db)
        source = create_source(cfg)
        assert source.check() is True

    def test_create_source_unknown_type(self):
        from feather.config import SourceConfig
        from feather.sources.registry import create_source

        cfg = SourceConfig(type="cassandra", path=None)
        with pytest.raises(ValueError, match="not implemented"):
            create_source(cfg)
