"""Tests for CsvSource, including multi-file CSV glob support (V6 extension)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tests.conftest import FIXTURES_DIR


GLOB_FIXTURES = FIXTURES_DIR / "csv_glob"


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


class TestCsvGlobDiscover:
    def test_discover_shows_glob_as_single_table(self, tmp_path: Path):
        """feather discover shows a glob pattern as one logical table."""
        from feather_etl.sources.csv import CsvSource

        data_dir = tmp_path / "data"
        shutil.copytree(GLOB_FIXTURES, data_dir)
        source = CsvSource(data_dir)
        schemas = source.discover()
        names = [s.name for s in schemas]
        assert "sales_jan.csv" in names
        assert "sales_feb.csv" in names
