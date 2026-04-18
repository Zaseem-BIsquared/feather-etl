"""Tests for curation.json integration with load_config."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest
import yaml


def _write_feather_yaml(tmp_path: Path, sources: list[dict]) -> Path:
    """Write a feather.yaml with sources and destination, no tables."""
    config = {
        "sources": sources,
        "destination": {"path": str(tmp_path / "feather_data.duckdb")},
    }
    config_file = tmp_path / "feather.yaml"
    config_file.write_text(yaml.dump(config, default_flow_style=False))
    return config_file


def _write_curation(tmp_path: Path, tables: list[dict]) -> None:
    """Write discovery/curation.json."""
    discovery_dir = tmp_path / "discovery"
    discovery_dir.mkdir(exist_ok=True)
    manifest = {
        "version": 2,
        "updated_at": "2026-04-18T00:00:00Z",
        "notes": "test",
        "source_systems": {},
        "policies": {"data_quality": {"default": "flag", "escalations": []}},
        "tables": tables,
    }
    (discovery_dir / "curation.json").write_text(json.dumps(manifest))


def _make_include(
    source_db: str,
    source_table: str,
    alias: str,
    strategy: str = "full",
) -> dict:
    return {
        "source_db": source_db,
        "source_table": source_table,
        "decision": "include",
        "table_type": "fact",
        "group": "test",
        "alias": alias,
        "classification_notes": None,
        "strategy": strategy,
        "primary_key": ["id"],
        "timestamp": None,
        "grain": None,
        "scd": None,
        "mapping": None,
        "dq_policy": None,
        "load_contract": None,
        "reason": "test",
    }


class TestLoadConfigWithCuration:
    def test_loads_tables_from_curation_json(self, tmp_path: Path):
        from feather_etl.config import load_config

        src_db = tmp_path / "source.duckdb"
        con = duckdb.connect(str(src_db))
        con.execute("CREATE SCHEMA erp")
        con.execute("CREATE TABLE erp.orders (id INT, amount DOUBLE)")
        con.execute("INSERT INTO erp.orders VALUES (1, 100.0)")
        con.close()

        config_file = _write_feather_yaml(
            tmp_path,
            [
                {"type": "duckdb", "name": "erp", "path": str(src_db)},
            ],
        )
        _write_curation(
            tmp_path,
            [
                _make_include("erp", "erp.orders", "orders"),
            ],
        )

        cfg = load_config(config_file, validate=False)
        assert len(cfg.tables) == 1
        assert cfg.tables[0].name == "erp_orders"
        assert cfg.tables[0].target_table == ""  # mode-derived at runtime
        assert cfg.tables[0].source_table == "erp.orders"
        assert cfg.tables[0].database == "erp"

    def test_multi_source_loads_from_curation(self, tmp_path: Path):
        from feather_etl.config import load_config

        src_a = tmp_path / "source_a.duckdb"
        con = duckdb.connect(str(src_a))
        con.execute("CREATE TABLE main.items (id INT)")
        con.close()

        src_b = tmp_path / "source_b.duckdb"
        con = duckdb.connect(str(src_b))
        con.execute("CREATE TABLE main.users (id INT)")
        con.close()

        config_file = _write_feather_yaml(
            tmp_path,
            [
                {"type": "duckdb", "name": "inventory", "path": str(src_a)},
                {"type": "duckdb", "name": "crm", "path": str(src_b)},
            ],
        )
        _write_curation(
            tmp_path,
            [
                _make_include("inventory", "main.items", "items"),
                _make_include("crm", "main.users", "users"),
            ],
        )

        cfg = load_config(config_file, validate=False)
        assert len(cfg.tables) == 2
        names = {t.name for t in cfg.tables}
        assert names == {"inventory_items", "crm_users"}

    def test_no_curation_no_tables_raises(self, tmp_path: Path):
        from feather_etl.config import load_config

        src_db = tmp_path / "source.duckdb"
        src_db.touch()
        config_file = _write_feather_yaml(
            tmp_path,
            [
                {"type": "duckdb", "name": "erp", "path": str(src_db)},
            ],
        )

        with pytest.raises(FileNotFoundError, match="curation.json"):
            load_config(config_file)
