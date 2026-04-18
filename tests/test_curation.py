"""Tests for curation.json loader and source resolution."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def _write_curation(
    tmp_path: Path, tables: list[dict], source_systems: dict | None = None
) -> Path:
    """Write a minimal curation.json for testing."""
    discovery_dir = tmp_path / "discovery"
    discovery_dir.mkdir(exist_ok=True)
    manifest = {
        "version": 2,
        "updated_at": "2026-04-18T00:00:00Z",
        "notes": "test",
        "source_systems": source_systems or {},
        "policies": {"data_quality": {"default": "flag", "escalations": []}},
        "tables": tables,
    }
    path = discovery_dir / "curation.json"
    path.write_text(json.dumps(manifest, indent=2))
    return path


def _make_include_entry(
    source_db: str = "test_db",
    source_table: str = "dbo.Sales",
    alias: str = "sales",
    strategy: str = "full",
    primary_key: list[str] | None = None,
    timestamp: dict | None = None,
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
        "primary_key": primary_key or ["id"],
        "timestamp": timestamp,
        "grain": None,
        "scd": None,
        "mapping": None,
        "dq_policy": None,
        "load_contract": None,
        "reason": "test entry",
    }


class TestLoadCuration:
    def test_filters_to_include_only(self, tmp_path: Path):
        from feather_etl.curation import load_curation_tables

        tables = [
            _make_include_entry(alias="sales"),
            {**_make_include_entry(alias="excluded"), "decision": "exclude"},
            {**_make_include_entry(alias="review"), "decision": "review"},
        ]
        _write_curation(tmp_path, tables)
        result = load_curation_tables(tmp_path)
        assert len(result) == 1
        assert result[0].name == "test_db_sales"

    def test_derives_bronze_name_from_source_db_and_alias(self, tmp_path: Path):
        from feather_etl.curation import load_curation_tables

        entry = _make_include_entry(source_db="Gofrugal", alias="sales")
        _write_curation(tmp_path, [entry])
        result = load_curation_tables(tmp_path)
        assert result[0].name == "gofrugal_sales"
        assert result[0].target_table == ""  # mode-derived at runtime

    def test_maps_strategy(self, tmp_path: Path):
        from feather_etl.curation import load_curation_tables

        entry = _make_include_entry(
            strategy="incremental",
            timestamp={"column": "SyncDate", "reason": None, "rejected": []},
        )
        _write_curation(tmp_path, [entry])
        result = load_curation_tables(tmp_path)
        assert result[0].strategy == "incremental"
        assert result[0].timestamp_column == "SyncDate"

    def test_maps_primary_key(self, tmp_path: Path):
        from feather_etl.curation import load_curation_tables

        entry = _make_include_entry(primary_key=["record_no", "line_no"])
        _write_curation(tmp_path, [entry])
        result = load_curation_tables(tmp_path)
        assert result[0].primary_key == ["record_no", "line_no"]

    def test_sets_source_name_and_database(self, tmp_path: Path):
        from feather_etl.curation import load_curation_tables

        entry = _make_include_entry(source_db="SAP")
        _write_curation(tmp_path, [entry])
        result = load_curation_tables(tmp_path)
        assert result[0].database == "SAP"
        assert result[0].source_name == "SAP"

    def test_missing_curation_raises(self, tmp_path: Path):
        from feather_etl.curation import load_curation_tables

        with pytest.raises(FileNotFoundError, match="discovery/curation.json"):
            load_curation_tables(tmp_path)

    def test_no_include_entries_raises(self, tmp_path: Path):
        from feather_etl.curation import load_curation_tables

        entry = {**_make_include_entry(), "decision": "exclude"}
        _write_curation(tmp_path, [entry])
        with pytest.raises(ValueError, match="No tables with decision.*include"):
            load_curation_tables(tmp_path)

    def test_sanitizes_bronze_name(self, tmp_path: Path):
        from feather_etl.curation import load_curation_tables

        entry = _make_include_entry(source_db="My-Source", alias="Sales Data!")
        _write_curation(tmp_path, [entry])
        result = load_curation_tables(tmp_path)
        # Should be lowercased and sanitized
        assert result[0].name == "my_source_sales_data_"

    def test_bronze_name_collision_case_difference_raises(self, tmp_path: Path):
        """Two aliases that differ only in case must collide after normalization."""
        from feather_etl.curation import load_curation_tables

        tables = [
            _make_include_entry(source_db="SAP", alias="Sales"),
            _make_include_entry(source_db="SAP", alias="sales"),
        ]
        _write_curation(tmp_path, tables)
        with pytest.raises(ValueError, match="duplicate bronze.*sap_sales"):
            load_curation_tables(tmp_path)

    def test_bronze_name_collision_punctuation_difference_raises(self, tmp_path: Path):
        """Two aliases that differ only in punctuation must collide after normalization."""
        from feather_etl.curation import load_curation_tables

        tables = [
            _make_include_entry(source_db="SAP", alias="sales_b"),
            _make_include_entry(source_db="SAP", alias="sales-b"),
        ]
        _write_curation(tmp_path, tables)
        with pytest.raises(ValueError, match="duplicate bronze.*sap_sales_b"):
            load_curation_tables(tmp_path)


class TestResolveSource:
    def test_resolves_source_by_databases_list(self):
        from feather_etl.curation import resolve_source

        mock_src = MagicMock()
        mock_src.name = "Rama"
        mock_src.database = None
        mock_src.databases = ["Gofrugal", "SAP", "ZAKYA"]
        mock_src.type = "sqlserver"

        result = resolve_source("Gofrugal", [mock_src])
        assert result == mock_src

    def test_resolves_source_by_single_database(self):
        from feather_etl.curation import resolve_source

        mock_src = MagicMock()
        mock_src.name = "erp"
        mock_src.database = "mydb"
        mock_src.databases = None

        result = resolve_source("mydb", [mock_src])
        assert result == mock_src

    def test_resolves_file_source_by_name(self):
        from feather_etl.curation import resolve_source

        mock_src = MagicMock()
        mock_src.name = "csv_data"
        mock_src.database = None
        mock_src.databases = None
        # File source — no database attribute logic, matched by name
        del mock_src.database
        del mock_src.databases
        mock_src.name = "csv_data"

        result = resolve_source("csv_data", [mock_src])
        assert result == mock_src

    def test_no_match_raises(self):
        from feather_etl.curation import resolve_source

        mock_src = MagicMock()
        mock_src.name = "Rama"
        mock_src.database = None
        mock_src.databases = ["Gofrugal"]

        with pytest.raises(ValueError, match="does not match any declared source"):
            resolve_source("NonExistent", [mock_src])

    def test_ambiguous_match_raises(self):
        from feather_etl.curation import resolve_source

        src_a = MagicMock()
        src_a.name = "ServerA"
        src_a.database = None
        src_a.databases = ["sales"]

        src_b = MagicMock()
        src_b.name = "ServerB"
        src_b.database = None
        src_b.databases = ["sales"]

        with pytest.raises(ValueError, match="ambiguous.*matches multiple sources"):
            resolve_source("sales", [src_a, src_b])
