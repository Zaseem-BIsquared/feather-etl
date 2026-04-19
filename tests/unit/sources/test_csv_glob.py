"""Tests for multi-file CSV glob support (V6 extension)."""

from __future__ import annotations

import shutil
from pathlib import Path

from tests.conftest import FIXTURES_DIR


GLOB_FIXTURES = FIXTURES_DIR / "csv_glob"


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
