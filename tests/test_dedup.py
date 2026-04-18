"""Tests for dedup config + extraction filtering (V9 companion)."""

from __future__ import annotations

from pathlib import Path

import yaml

from tests.helpers import make_curation_entry, write_curation


class TestDedupConfig:
    def test_dedup_and_dedup_columns_mutually_exclusive(self, tmp_path: Path):
        """Validation rejects both dedup and dedup_columns set."""
        from feather_etl.config import load_config, _validate

        (tmp_path / "orders.csv").write_text("order_id,name\n1,A\n")

        config = {
            "sources": [{"type": "csv", "name": "csvs", "path": str(tmp_path)}],
            "destination": {"path": str(tmp_path / "out.duckdb")},
        }
        (tmp_path / "feather.yaml").write_text(yaml.dump(config))
        write_curation(
            tmp_path,
            [make_curation_entry("csvs", "orders.csv", "orders")],
        )
        cfg = load_config(tmp_path / "feather.yaml", validate=False)
        cfg.tables[0].dedup = True
        cfg.tables[0].dedup_columns = ["order_id"]
        errors = _validate(cfg)
        assert any("dedup" in e and "dedup_columns" in e for e in errors)


class TestDedupExtraction:
    def test_dedup_true_removes_exact_duplicates(self, tmp_path: Path):
        """dedup: true causes SELECT DISTINCT at extraction."""
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_table

        csv_dir = tmp_path / "data"
        csv_dir.mkdir()
        (csv_dir / "orders.csv").write_text(
            "order_id,name,amount\n1,A,100\n2,B,200\n1,A,100\n3,C,300\n"
        )
        config = {
            "sources": [{"type": "csv", "name": "csvs", "path": str(csv_dir)}],
            "destination": {"path": str(tmp_path / "feather_data.duckdb")},
        }
        (tmp_path / "feather.yaml").write_text(yaml.dump(config))
        write_curation(
            tmp_path,
            [make_curation_entry("csvs", "orders.csv", "orders")],
        )
        cfg = load_config(tmp_path / "feather.yaml")
        cfg.tables[0].dedup = True

        result = run_table(cfg, cfg.tables[0], tmp_path)
        assert result.status == "success"
        assert result.rows_loaded == 3

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
            "sources": [{"type": "csv", "name": "csvs", "path": str(csv_dir)}],
            "destination": {"path": str(tmp_path / "feather_data.duckdb")},
        }
        (tmp_path / "feather.yaml").write_text(yaml.dump(config))
        write_curation(
            tmp_path,
            [make_curation_entry("csvs", "orders.csv", "orders")],
        )
        cfg = load_config(tmp_path / "feather.yaml")
        cfg.tables[0].dedup_columns = ["order_id"]

        result = run_table(cfg, cfg.tables[0], tmp_path)
        assert result.status == "success"
        assert result.rows_loaded == 3

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
            "sources": [{"type": "csv", "name": "csvs", "path": str(csv_dir)}],
            "destination": {"path": str(tmp_path / "feather_data.duckdb")},
        }
        (tmp_path / "feather.yaml").write_text(yaml.dump(config))
        write_curation(
            tmp_path,
            [make_curation_entry("csvs", "orders.csv", "orders")],
        )
        cfg = load_config(tmp_path / "feather.yaml")

        result = run_table(cfg, cfg.tables[0], tmp_path)
        assert result.status == "success"
        assert result.rows_loaded == 4

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
            "sources": [{"type": "json", "name": "jsons", "path": str(json_dir)}],
            "destination": {"path": str(tmp_path / "feather_data.duckdb")},
        }
        (tmp_path / "feather.yaml").write_text(yaml.dump(config))
        write_curation(
            tmp_path,
            [make_curation_entry("jsons", "orders.json", "orders")],
        )
        cfg = load_config(tmp_path / "feather.yaml")
        cfg.tables[0].dedup = True

        result = run_table(cfg, cfg.tables[0], tmp_path)
        assert result.status == "success"
        assert result.rows_loaded == 2
