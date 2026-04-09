"""Tests for dedup config + extraction filtering (V9 companion)."""

from __future__ import annotations

from pathlib import Path

import yaml



class TestDedupConfig:
    def test_dedup_and_dedup_columns_mutually_exclusive(self, tmp_path: Path):
        """Validation rejects both dedup and dedup_columns set."""
        from feather_etl.config import load_config
        import pytest

        config = {
            "source": {"type": "csv", "path": str(tmp_path)},
            "destination": {"path": str(tmp_path / "out.duckdb")},
            "tables": [{
                "name": "orders",
                "source_table": "orders.csv",
                "strategy": "full",
                "dedup": True,
                "dedup_columns": ["order_id"],
            }],
        }
        # Create empty csv dir and file to avoid path validation error
        (tmp_path / "orders.csv").write_text("order_id,name\n1,A\n")

        (tmp_path / "feather.yaml").write_text(yaml.dump(config))
        with pytest.raises(ValueError, match="dedup.*dedup_columns"):
            load_config(tmp_path / "feather.yaml")


class TestDedupExtraction:
    def test_dedup_true_removes_exact_duplicates(self, tmp_path: Path):
        """dedup: true causes SELECT DISTINCT at extraction."""
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_table

        # Create CSV with duplicate rows
        csv_dir = tmp_path / "data"
        csv_dir.mkdir()
        (csv_dir / "orders.csv").write_text(
            "order_id,name,amount\n1,A,100\n2,B,200\n1,A,100\n3,C,300\n"
        )
        config = {
            "source": {"type": "csv", "path": str(csv_dir)},
            "destination": {"path": str(tmp_path / "feather_data.duckdb")},
            "tables": [{
                "name": "orders",
                "source_table": "orders.csv",
                "target_table": "bronze.orders",
                "strategy": "full",
                "dedup": True,
            }],
        }
        (tmp_path / "feather.yaml").write_text(yaml.dump(config))
        cfg = load_config(tmp_path / "feather.yaml")

        result = run_table(cfg, cfg.tables[0], tmp_path)
        assert result.status == "success"
        assert result.rows_loaded == 3  # 4 rows → 3 after DISTINCT

    def test_dedup_columns_deduplicates_by_key(self, tmp_path: Path):
        """dedup_columns removes duplicates by specified columns."""
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_table

        csv_dir = tmp_path / "data"
        csv_dir.mkdir()
        (csv_dir / "orders.csv").write_text(
            "order_id,name,amount\n1,A,100\n2,B,200\n1,X,150\n3,C,300\n"
        )
        config = {
            "source": {"type": "csv", "path": str(csv_dir)},
            "destination": {"path": str(tmp_path / "feather_data.duckdb")},
            "tables": [{
                "name": "orders",
                "source_table": "orders.csv",
                "target_table": "bronze.orders",
                "strategy": "full",
                "dedup_columns": ["order_id"],
            }],
        }
        (tmp_path / "feather.yaml").write_text(yaml.dump(config))
        cfg = load_config(tmp_path / "feather.yaml")

        result = run_table(cfg, cfg.tables[0], tmp_path)
        assert result.status == "success"
        assert result.rows_loaded == 3  # 4 rows → 3 (dedup on order_id)

    def test_no_dedup_keeps_all_rows(self, tmp_path: Path):
        """Without dedup config, all rows are kept including duplicates."""
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_table

        csv_dir = tmp_path / "data"
        csv_dir.mkdir()
        (csv_dir / "orders.csv").write_text(
            "order_id,name,amount\n1,A,100\n2,B,200\n1,A,100\n3,C,300\n"
        )
        config = {
            "source": {"type": "csv", "path": str(csv_dir)},
            "destination": {"path": str(tmp_path / "feather_data.duckdb")},
            "tables": [{
                "name": "orders",
                "source_table": "orders.csv",
                "target_table": "bronze.orders",
                "strategy": "full",
            }],
        }
        (tmp_path / "feather.yaml").write_text(yaml.dump(config))
        cfg = load_config(tmp_path / "feather.yaml")

        result = run_table(cfg, cfg.tables[0], tmp_path)
        assert result.status == "success"
        assert result.rows_loaded == 4  # All rows kept

    def test_dedup_works_for_json_source(self, tmp_path: Path):
        """Dedup works for JSON sources via pipeline-level _apply_dedup."""
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_table

        json_dir = tmp_path / "data"
        json_dir.mkdir()
        (json_dir / "orders.json").write_text(
            '[{"id":1,"name":"A"},{"id":2,"name":"B"},{"id":1,"name":"A"}]'
        )
        config = {
            "source": {"type": "json", "path": str(json_dir)},
            "destination": {"path": str(tmp_path / "feather_data.duckdb")},
            "tables": [{
                "name": "orders",
                "source_table": "orders.json",
                "target_table": "bronze.orders",
                "strategy": "full",
                "dedup": True,
            }],
        }
        (tmp_path / "feather.yaml").write_text(yaml.dump(config))
        cfg = load_config(tmp_path / "feather.yaml")

        result = run_table(cfg, cfg.tables[0], tmp_path)
        assert result.status == "success"
        assert result.rows_loaded == 2  # 3 rows → 2 after DISTINCT
