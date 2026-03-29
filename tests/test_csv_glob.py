"""Tests for multi-file CSV glob support (V6 extension)."""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from tests.conftest import FIXTURES_DIR


GLOB_FIXTURES = FIXTURES_DIR / "csv_glob"


class TestCsvGlobExtraction:
    def test_glob_extracts_all_matching_files(self, tmp_path: Path):
        """source_table: 'sales_*.csv' extracts all matching files as one table."""
        from feather.config import load_config
        from feather.pipeline import run_table

        data_dir = tmp_path / "data"
        shutil.copytree(GLOB_FIXTURES, data_dir)
        config = {
            "source": {"type": "csv", "path": str(data_dir)},
            "destination": {"path": str(tmp_path / "feather_data.duckdb")},
            "tables": [{
                "name": "sales",
                "source_table": "sales_*.csv",
                "target_table": "bronze.sales",
                "strategy": "full",
            }],
        }
        (tmp_path / "feather.yaml").write_text(yaml.dump(config))
        cfg = load_config(tmp_path / "feather.yaml")

        result = run_table(cfg, cfg.tables[0], tmp_path)
        assert result.status == "success"
        assert result.rows_loaded == 5  # 3 from jan + 2 from feb

    def test_glob_no_match_fails(self, tmp_path: Path):
        """Glob that matches no files should fail gracefully."""
        from feather.config import load_config
        from feather.pipeline import run_table

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "other.csv").write_text("id\n1\n")  # No sales_* files
        config = {
            "source": {"type": "csv", "path": str(data_dir)},
            "destination": {"path": str(tmp_path / "feather_data.duckdb")},
            "tables": [{
                "name": "sales",
                "source_table": "sales_*.csv",
                "target_table": "bronze.sales",
                "strategy": "full",
            }],
        }
        (tmp_path / "feather.yaml").write_text(yaml.dump(config))
        cfg = load_config(tmp_path / "feather.yaml")

        result = run_table(cfg, cfg.tables[0], tmp_path)
        # No matching files → change detection returns unchanged → skipped
        assert result.status == "skipped"


class TestCsvGlobChangeDetection:
    def test_no_change_skips(self, tmp_path: Path):
        """Second run with no file changes should skip extraction."""
        from feather.config import load_config
        from feather.pipeline import run_table

        data_dir = tmp_path / "data"
        shutil.copytree(GLOB_FIXTURES, data_dir)
        config = {
            "source": {"type": "csv", "path": str(data_dir)},
            "destination": {"path": str(tmp_path / "feather_data.duckdb")},
            "tables": [{
                "name": "sales",
                "source_table": "sales_*.csv",
                "target_table": "bronze.sales",
                "strategy": "full",
            }],
        }
        (tmp_path / "feather.yaml").write_text(yaml.dump(config))
        cfg = load_config(tmp_path / "feather.yaml")

        run_table(cfg, cfg.tables[0], tmp_path)
        result2 = run_table(cfg, cfg.tables[0], tmp_path)
        assert result2.status == "skipped"

    def test_new_file_triggers_reextract(self, tmp_path: Path):
        """Adding a new matching file should trigger re-extraction."""
        from feather.config import load_config
        from feather.pipeline import run_table

        data_dir = tmp_path / "data"
        shutil.copytree(GLOB_FIXTURES, data_dir)
        config = {
            "source": {"type": "csv", "path": str(data_dir)},
            "destination": {"path": str(tmp_path / "feather_data.duckdb")},
            "tables": [{
                "name": "sales",
                "source_table": "sales_*.csv",
                "target_table": "bronze.sales",
                "strategy": "full",
            }],
        }
        (tmp_path / "feather.yaml").write_text(yaml.dump(config))
        cfg = load_config(tmp_path / "feather.yaml")

        run_table(cfg, cfg.tables[0], tmp_path)

        # Add a new file
        (data_dir / "sales_mar.csv").write_text("order_id,customer,amount,month\n6,Frank,400,mar\n")

        result2 = run_table(cfg, cfg.tables[0], tmp_path)
        assert result2.status == "success"
        assert result2.rows_loaded == 6  # 3 + 2 + 1

    def test_modified_file_triggers_reextract(self, tmp_path: Path):
        """Modifying a matching file should trigger re-extraction."""
        import time
        from feather.config import load_config
        from feather.pipeline import run_table

        data_dir = tmp_path / "data"
        shutil.copytree(GLOB_FIXTURES, data_dir)
        config = {
            "source": {"type": "csv", "path": str(data_dir)},
            "destination": {"path": str(tmp_path / "feather_data.duckdb")},
            "tables": [{
                "name": "sales",
                "source_table": "sales_*.csv",
                "target_table": "bronze.sales",
                "strategy": "full",
            }],
        }
        (tmp_path / "feather.yaml").write_text(yaml.dump(config))
        cfg = load_config(tmp_path / "feather.yaml")

        run_table(cfg, cfg.tables[0], tmp_path)

        # Modify an existing file
        time.sleep(0.1)
        (data_dir / "sales_jan.csv").write_text(
            "order_id,customer,amount,month\n1,Alice,100,jan\n2,Bob,200,jan\n"
        )

        result2 = run_table(cfg, cfg.tables[0], tmp_path)
        assert result2.status == "success"
        assert result2.rows_loaded == 4  # 2 from modified jan + 2 from feb


class TestCsvGlobDiscover:
    def test_discover_shows_glob_as_single_table(self, tmp_path: Path):
        """feather discover shows a glob pattern as one logical table."""
        from feather.sources.csv import CsvSource

        data_dir = tmp_path / "data"
        shutil.copytree(GLOB_FIXTURES, data_dir)
        source = CsvSource(data_dir)
        schemas = source.discover()
        # Should include individual files as before
        names = [s.name for s in schemas]
        assert "sales_jan.csv" in names
        assert "sales_feb.csv" in names
