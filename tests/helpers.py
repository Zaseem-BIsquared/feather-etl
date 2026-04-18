"""Shared test utility functions."""

from __future__ import annotations

import json
from pathlib import Path

import yaml


def write_config(tmp_path: Path, config: dict, directory: Path | None = None) -> Path:
    config_file = (directory or tmp_path) / "feather.yaml"
    config_file.write_text(yaml.dump(config, default_flow_style=False))
    return config_file


def write_curation(tmp_path: Path, tables: list[dict]) -> Path:
    """Write a discovery/curation.json for testing."""
    discovery_dir = tmp_path / "discovery"
    discovery_dir.mkdir(exist_ok=True)
    manifest = {
        "version": 2,
        "updated_at": "2026-04-18T00:00:00Z",
        "notes": "test fixture",
        "source_systems": {},
        "policies": {"data_quality": {"default": "flag", "escalations": []}},
        "tables": tables,
    }
    path = discovery_dir / "curation.json"
    path.write_text(json.dumps(manifest))
    return path


def make_curation_entry(
    source_db: str,
    source_table: str,
    alias: str,
    strategy: str = "full",
    primary_key: list[str] | None = None,
    timestamp_column: str | None = None,
    filter: str | None = None,
    quality_checks: dict | None = None,
    column_map: dict[str, str] | None = None,
    dedup: bool = False,
    dedup_columns: list[str] | None = None,
    schedule: str | None = None,
) -> dict:
    """Create a curation.json include entry for testing."""
    timestamp = None
    if timestamp_column:
        timestamp = {"column": timestamp_column, "reason": None, "rejected": []}
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
        "reason": "test fixture",
    }
