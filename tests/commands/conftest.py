"""Shared fixtures and helpers for command test modules."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from tests.conftest import FIXTURES_DIR
from tests.helpers import make_curation_entry, write_curation


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def cli_env(tmp_path: Path) -> tuple[Path, Path]:
    """Config + source DB for CLI tests."""
    client_db = tmp_path / "client.duckdb"
    shutil.copy2(FIXTURES_DIR / "client.duckdb", client_db)

    config = {
        "sources": [{"type": "duckdb", "name": "icube", "path": str(client_db)}],
        "destination": {"path": str(tmp_path / "feather_data.duckdb")},
    }
    config_path = tmp_path / "feather.yaml"
    config_path.write_text(yaml.dump(config, default_flow_style=False))
    write_curation(
        tmp_path,
        [
            make_curation_entry("icube", "icube.InventoryGroup", "inventory_group"),
        ],
    )
    return config_path, tmp_path


@pytest.fixture
def two_table_env(tmp_path: Path) -> tuple[Path, Path]:
    """Config with two tables: inventory_group and customer_master."""
    client_db = tmp_path / "client.duckdb"
    shutil.copy2(FIXTURES_DIR / "client.duckdb", client_db)

    config = {
        "sources": [{"type": "duckdb", "name": "icube", "path": str(client_db)}],
        "destination": {"path": str(tmp_path / "feather_data.duckdb")},
    }
    config_path = tmp_path / "feather.yaml"
    config_path.write_text(yaml.dump(config, default_flow_style=False))
    write_curation(
        tmp_path,
        [
            make_curation_entry("icube", "icube.InventoryGroup", "inventory_group"),
            make_curation_entry("icube", "icube.CUSTOMERMASTER", "customer_master"),
        ],
    )
    return config_path, tmp_path


def cli_config(tmp_path: Path) -> Path:
    """Create a config for CLI --json tests."""
    client_db = tmp_path / "client.duckdb"
    shutil.copy2(FIXTURES_DIR / "client.duckdb", client_db)
    config = {
        "sources": [{"type": "duckdb", "name": "icube", "path": str(client_db)}],
        "destination": {"path": str(tmp_path / "feather_data.duckdb")},
    }
    config_file = tmp_path / "feather.yaml"
    config_file.write_text(yaml.dump(config, default_flow_style=False))
    write_curation(
        tmp_path,
        [
            make_curation_entry("icube", "icube.InventoryGroup", "inventory_group"),
        ],
    )
    return config_file


@pytest.fixture
def stub_viewer_serve(monkeypatch):
    from feather_etl.commands import discover as discover_cmd

    monkeypatch.setattr(discover_cmd, "serve_and_open", lambda *args, **kwargs: None)


def multi_source_yaml(
    tmp_path: Path,
    sources: list[dict],
    destination_path: str | None = None,
) -> Path:
    """Build a feather.yaml with arbitrary sources/destinations."""
    cfg = {
        "sources": sources,
        "destination": {
            "path": destination_path or str(tmp_path / "feather_data.duckdb")
        },
    }
    p = tmp_path / "feather.yaml"
    p.write_text(yaml.dump(cfg, default_flow_style=False))
    return p
