"""Tests for the `feather status` command."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml

from tests.commands.conftest import cli_config
from tests.conftest import FIXTURES_DIR


class TestStatus:
    def test_shows_status_after_run(self, runner, cli_env: tuple[Path, Path]):
        from feather_etl.cli import app

        config_path, tmp_path = cli_env
        runner.invoke(app, ["run", "--config", str(config_path)])
        result = runner.invoke(app, ["status", "--config", str(config_path)])
        assert result.exit_code == 0
        assert "inventory_group" in result.output

    def test_status_no_state_db(self, runner, cli_env: tuple[Path, Path]):
        from feather_etl.cli import app

        config_path, _ = cli_env
        result = runner.invoke(app, ["status", "--config", str(config_path)])
        assert result.exit_code != 0
        assert "No state DB found" in result.output

    def test_status_no_runs_yet(self, runner, cli_env: tuple[Path, Path]):
        from feather_etl.cli import app

        config_path, _ = cli_env
        runner.invoke(app, ["setup", "--config", str(config_path)])
        result = runner.invoke(app, ["status", "--config", str(config_path)])
        assert result.exit_code == 0
        assert "No runs recorded" in result.output

    def test_status_shows_error_message_for_failures(self, runner, tmp_path: Path):
        """UX-5: feather status should display error text for failed tables."""
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
        config_path = tmp_path / "feather.yaml"
        config_path.write_text(yaml.dump(config, default_flow_style=False))

        runner.invoke(app, ["run", "--config", str(config_path)])
        result = runner.invoke(app, ["status", "--config", str(config_path)])
        assert result.exit_code == 0
        assert "Error:" in result.output

    def test_status_shows_all_time_history(self, runner, tmp_path: Path):
        """BUG-8 (intentional): status shows tables from ALL runs, not just current config.
        This is correct behavior — history should not be lost when config changes."""
        from feather_etl.cli import app

        client_db = tmp_path / "client.duckdb"
        shutil.copy2(FIXTURES_DIR / "client.duckdb", client_db)

        config_a = {
            "sources": [{"type": "duckdb", "path": str(client_db)}],
            "destination": {"path": str(tmp_path / "feather_data.duckdb")},
            "tables": [
                {
                    "name": "inventory_group",
                    "source_table": "icube.InventoryGroup",
                    "target_table": "bronze.inventory_group",
                    "strategy": "full",
                },
            ],
        }
        config_path = tmp_path / "feather.yaml"
        config_path.write_text(yaml.dump(config_a, default_flow_style=False))
        runner.invoke(app, ["run", "--config", str(config_path)])

        config_b = {
            "sources": [{"type": "duckdb", "path": str(client_db)}],
            "destination": {"path": str(tmp_path / "feather_data.duckdb")},
            "tables": [
                {
                    "name": "customer_master",
                    "source_table": "icube.CUSTOMERMASTER",
                    "target_table": "bronze.customer_master",
                    "strategy": "full",
                },
            ],
        }
        config_path.write_text(yaml.dump(config_b, default_flow_style=False))
        runner.invoke(app, ["run", "--config", str(config_path)])

        result = runner.invoke(app, ["status", "--config", str(config_path)])
        assert result.exit_code == 0
        assert "inventory_group" in result.output
        assert "customer_master" in result.output

    def test_status_json_outputs_ndjson(self, runner, tmp_path: Path):
        """AC-FR11.d: feather status --json outputs NDJSON with required fields."""
        from feather_etl.cli import app

        config_file = cli_config(tmp_path)
        runner.invoke(app, ["run", "--config", str(config_file)])

        result = runner.invoke(app, ["--json", "status", "--config", str(config_file)])
        assert result.exit_code == 0
        lines = [line for line in result.output.strip().split("\n") if line.strip()]
        assert len(lines) >= 1
        parsed = json.loads(lines[0])
        assert "table_name" in parsed
        assert "status" in parsed
