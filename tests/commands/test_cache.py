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


class TestCacheSelectors:
    def _two_table_project(self, tmp_path: Path) -> Path:
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
        write_curation(
            tmp_path,
            [
                make_curation_entry("icube", "icube.InventoryGroup", "inv"),
                make_curation_entry("icube", "icube.CUSTOMERMASTER", "cust"),
            ],
        )
        return cp

    def test_table_filter_restricts_extraction(self, runner, tmp_path: Path):
        from feather_etl.cli import app

        cp = self._two_table_project(tmp_path)
        result = runner.invoke(
            app, ["cache", "--config", str(cp), "--table", "icube_inv"]
        )
        assert result.exit_code == 0

        data_db = tmp_path / "feather_data.duckdb"
        con = duckdb.connect(str(data_db), read_only=True)
        tables = {
            r[0]
            for r in con.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'bronze'"
            ).fetchall()
        }
        con.close()
        assert "icube_inv" in tables
        assert "icube_cust" not in tables


    def test_source_filter_restricts_extraction(self, runner, tmp_path: Path):
        from feather_etl.cli import app

        cp = self._two_table_project(tmp_path)
        # Only one source_db here (icube); this also confirms the filter accepts it.
        result = runner.invoke(
            app, ["cache", "--config", str(cp), "--source", "icube"]
        )
        assert result.exit_code == 0

        data_db = tmp_path / "feather_data.duckdb"
        con = duckdb.connect(str(data_db), read_only=True)
        tables = {
            r[0]
            for r in con.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'bronze'"
            ).fetchall()
        }
        con.close()
        assert "icube_inv" in tables
        assert "icube_cust" in tables

    def test_table_and_source_intersect(self, runner, tmp_path: Path):
        from feather_etl.cli import app

        cp = self._two_table_project(tmp_path)
        result = runner.invoke(
            app,
            [
                "cache",
                "--config",
                str(cp),
                "--table",
                "icube_inv",
                "--source",
                "icube",
            ],
        )
        assert result.exit_code == 0

        data_db = tmp_path / "feather_data.duckdb"
        con = duckdb.connect(str(data_db), read_only=True)
        tables = {
            r[0]
            for r in con.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'bronze'"
            ).fetchall()
        }
        con.close()
        assert tables == {"icube_inv"}

    def test_unknown_table_errors_with_valid_list(self, runner, tmp_path: Path):
        from feather_etl.cli import app

        cp = self._two_table_project(tmp_path)
        result = runner.invoke(
            app, ["cache", "--config", str(cp), "--table", "no_such_table"]
        )
        assert result.exit_code == 2
        assert "no_such_table" in result.output
        assert "icube_inv" in result.output
        assert "icube_cust" in result.output

    def test_unknown_source_errors_with_valid_list(self, runner, tmp_path: Path):
        from feather_etl.cli import app

        cp = self._two_table_project(tmp_path)
        result = runner.invoke(
            app, ["cache", "--config", str(cp), "--source", "nope"]
        )
        assert result.exit_code == 2
        assert "nope" in result.output
        assert "icube" in result.output


class TestCacheRefresh:
    def test_refresh_forces_re_extraction(self, runner, tmp_path: Path):
        from feather_etl.cli import app

        config_path = _project(tmp_path)
        # Cold run
        r1 = runner.invoke(app, ["cache", "--config", str(config_path)])
        assert r1.exit_code == 0
        assert "1 extracted" in r1.output

        # Warm run — should be cached
        r2 = runner.invoke(app, ["cache", "--config", str(config_path)])
        assert r2.exit_code == 0
        assert "1 cached" in r2.output

        # Refresh — should re-extract
        r3 = runner.invoke(
            app, ["cache", "--config", str(config_path), "--refresh"]
        )
        assert r3.exit_code == 0
        assert "1 extracted" in r3.output


class TestCacheOutputFormat:
    def test_grouped_output_with_failure_expansion(
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
        write_curation(
            tmp_path,
            [
                make_curation_entry("icube", "icube.InventoryGroup", "good"),
                make_curation_entry("icube", "icube.NOPE", "bad"),
            ],
        )

        result = runner.invoke(app, ["cache", "--config", str(cp)])
        # Non-zero exit because of the failed table
        assert result.exit_code == 1
        out = result.output

        assert "Mode: dev (cache)" in out
        # Grouped: a line starts with "icube" (source_db), has counts
        assert "icube" in out
        # Summary: totals across groups
        assert "2 tables:" in out
        # Failure details expanded
        assert "✗ icube_bad" in out
