"""Tests for the `feather run` command."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml

from tests.commands.conftest import cli_config
from tests.conftest import FIXTURES_DIR


class TestRun:
    def test_extracts_tables(self, runner, cli_env: tuple[Path, Path]):
        from feather_etl.cli import app

        config_path, tmp_path = cli_env
        result = runner.invoke(app, ["run", "--config", str(config_path)])
        assert result.exit_code == 0
        assert "success" in result.output.lower()

    def test_run_with_bad_table_shows_failure(self, runner, tmp_path: Path):
        from feather_etl.cli import app

        client_db = tmp_path / "client.duckdb"
        shutil.copy2(FIXTURES_DIR / "client.duckdb", client_db)
        config = {
            "sources": [{"type": "duckdb", "path": str(client_db)}],
            "destination": {"path": str(tmp_path / "feather_data.duckdb")},
            "tables": [
                {
                    "name": "bad_table",
                    "source_table": "icube.NONEXISTENT",
                    "target_table": "bronze.bad_table",
                    "strategy": "full",
                },
            ],
        }
        (tmp_path / "feather.yaml").write_text(yaml.dump(config))
        result = runner.invoke(app, ["run", "--config", str(tmp_path / "feather.yaml")])
        assert result.exit_code == 1
        assert "failure" in result.output.lower()

    def test_backoff_skipped_table_exits_nonzero(self, runner, tmp_path: Path):
        """Second run after partial failure should exit non-zero (backoff-skipped)."""
        from feather_etl.cli import app

        client_db = tmp_path / "client.duckdb"
        shutil.copy2(FIXTURES_DIR / "client.duckdb", client_db)
        config = {
            "sources": [{"type": "duckdb", "path": str(client_db)}],
            "destination": {"path": str(tmp_path / "feather_data.duckdb")},
            "tables": [
                {
                    "name": "good_table",
                    "source_table": "icube.SALESINVOICE",
                    "target_table": "bronze.good_table",
                    "strategy": "full",
                },
                {
                    "name": "bad_table",
                    "source_table": "nonexistent.NOPE",
                    "target_table": "bronze.bad_table",
                    "strategy": "full",
                },
            ],
        }
        (tmp_path / "feather.yaml").write_text(yaml.dump(config))

        result1 = runner.invoke(
            app, ["run", "--config", str(tmp_path / "feather.yaml")]
        )
        assert result1.exit_code == 1

        result2 = runner.invoke(
            app, ["run", "--config", str(tmp_path / "feather.yaml")]
        )
        assert result2.exit_code == 1, (
            f"Expected non-zero exit when table is backoff-skipped, got 0. Output: {result2.output}"
        )

    def test_run_json_outputs_ndjson(self, runner, tmp_path: Path):
        from feather_etl.cli import app

        config_file = cli_config(tmp_path)
        result = runner.invoke(app, ["--json", "run", "--config", str(config_file)])
        assert result.exit_code == 0
        lines = [line for line in result.output.strip().split("\n") if line.strip()]
        assert len(lines) >= 1
        parsed = json.loads(lines[0])
        assert "table_name" in parsed
        assert "status" in parsed


class TestTableFilter:
    def test_table_filter_extracts_only_matching_table(
        self, runner, two_table_env: tuple[Path, Path]
    ):
        """--table inventory_group should extract only that table."""
        from feather_etl.cli import app

        config_path, tmp_path = two_table_env
        result = runner.invoke(
            app, ["run", "--config", str(config_path), "--table", "inventory_group"]
        )
        assert result.exit_code == 0
        assert "inventory_group" in result.output
        assert "customer_master" not in result.output

    def test_table_filter_nonexistent_table_exits_with_error(
        self, runner, two_table_env: tuple[Path, Path]
    ):
        """--table nonexistent should exit with code 1 and show error."""
        from feather_etl.cli import app

        config_path, _ = two_table_env
        result = runner.invoke(
            app, ["run", "--config", str(config_path), "--table", "nonexistent"]
        )
        assert result.exit_code == 1
        assert (
            "nonexistent" in result.output.lower()
            or "nonexistent" in (result.stderr or "").lower()
        )

    def test_no_table_flag_extracts_all_tables(
        self, runner, two_table_env: tuple[Path, Path]
    ):
        """Without --table, all configured tables are extracted."""
        from feather_etl.cli import app

        config_path, _ = two_table_env
        result = runner.invoke(app, ["run", "--config", str(config_path)])
        assert result.exit_code == 0
        assert "inventory_group" in result.output
        assert "customer_master" in result.output


class TestRunAutoCreates:
    def test_run_without_setup_auto_creates_state_and_data(
        self, runner, cli_env: tuple[Path, Path]
    ):
        """UX-7: feather run creates state/data DBs automatically. setup is optional."""
        from feather_etl.cli import app

        config_path, tmp_path = cli_env
        result = runner.invoke(app, ["run", "--config", str(config_path)])
        assert result.exit_code == 0
        assert (tmp_path / "feather_state.duckdb").exists()
        assert (tmp_path / "feather_data.duckdb").exists()
