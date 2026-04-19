"""Tests for the `feather cache` command."""

from __future__ import annotations

import shutil
from pathlib import Path

import duckdb
import pytest
import yaml
from typer.testing import CliRunner

from tests.conftest import FIXTURES_DIR
from tests.helpers import make_curation_entry, write_curation


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _project(tmp_path: Path) -> Path:
    """Minimal project: 1 DuckDB source, 1 curated table. Returns config path."""
    client_db = tmp_path / "client.duckdb"
    shutil.copy2(FIXTURES_DIR / "client.duckdb", client_db)
    config = {
        "sources": [{"type": "duckdb", "name": "icube", "path": str(client_db)}],
        "destination": {"path": str(tmp_path / "feather_data.duckdb")},
    }
    cp = tmp_path / "feather.yaml"
    cp.write_text(yaml.dump(config))
    write_curation(
        tmp_path,
        [make_curation_entry("icube", "icube.InventoryGroup", "inventory_group")],
    )
    return cp


class TestCacheBasic:
    def test_cold_run_extracts_tables(self, runner, tmp_path: Path):
        from feather_etl.cli import app

        config_path = _project(tmp_path)
        result = runner.invoke(app, ["cache", "--config", str(config_path)])
        assert result.exit_code == 0
        assert "extracted" in result.output


class TestCacheProdModeGuard:
    def test_rejects_yaml_mode_prod(self, runner, tmp_path: Path):
        from feather_etl.cli import app

        client_db = tmp_path / "client.duckdb"
        shutil.copy2(FIXTURES_DIR / "client.duckdb", client_db)
        config = {
            "mode": "prod",
            "sources": [{"type": "duckdb", "name": "icube", "path": str(client_db)}],
            "destination": {"path": str(tmp_path / "feather_data.duckdb")},
        }
        cp = tmp_path / "feather.yaml"
        cp.write_text(yaml.dump(config))
        write_curation(
            tmp_path,
            [make_curation_entry("icube", "icube.InventoryGroup", "inv")],
        )

        result = runner.invoke(app, ["cache", "--config", str(cp)])
        assert result.exit_code == 2
        assert "dev-only" in result.output

    def test_rejects_feather_mode_env_prod(self, runner, tmp_path: Path, monkeypatch):
        from feather_etl.cli import app

        monkeypatch.setenv("FEATHER_MODE", "prod")
        config_path = _project(tmp_path)
        result = runner.invoke(app, ["cache", "--config", str(config_path)])
        assert result.exit_code == 2
        assert "dev-only" in result.output


class TestCacheMissingCuration:
    def test_errors_with_curation_path_when_missing(
        self, runner, tmp_path: Path
    ):
        from feather_etl.cli import app

        client_db = tmp_path / "client.duckdb"
        shutil.copy2(FIXTURES_DIR / "client.duckdb", client_db)
        config = {
            "sources": [
                {"type": "duckdb", "name": "icube", "path": str(client_db)}
            ],
            "destination": {"path": str(tmp_path / "feather_data.duckdb")},
        }
        cp = tmp_path / "feather.yaml"
        cp.write_text(yaml.dump(config))
        # Intentionally no write_curation() call — curation.json does not exist.

        result = runner.invoke(app, ["cache", "--config", str(cp)])
        assert result.exit_code == 2
        assert "curation.json" in result.output
        assert "feather discover" in result.output
