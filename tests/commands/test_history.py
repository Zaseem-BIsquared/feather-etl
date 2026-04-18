"""Tests for the `feather history` command."""

from __future__ import annotations

import json
from pathlib import Path

from tests.commands.conftest import cli_config


class TestHistory:
    def test_history_shows_runs_after_run(
        self, runner, two_table_env: tuple[Path, Path]
    ):
        """feather history shows a table of recent runs."""
        from feather_etl.cli import app

        config_path, _ = two_table_env
        runner.invoke(app, ["run", "--config", str(config_path)])
        result = runner.invoke(app, ["history", "--config", str(config_path)])
        assert result.exit_code == 0
        assert "inventory_group" in result.output
        assert "customer_master" in result.output

    def test_history_table_filter(self, runner, two_table_env: tuple[Path, Path]):
        """feather history --table icube_inventory_group shows only that table's runs."""
        from feather_etl.cli import app

        config_path, _ = two_table_env
        runner.invoke(app, ["run", "--config", str(config_path)])
        result = runner.invoke(
            app,
            [
                "history",
                "--config",
                str(config_path),
                "--table",
                "icube_inventory_group",
            ],
        )
        assert result.exit_code == 0
        assert "icube_inventory_group" in result.output
        assert "icube_customer_master" not in result.output

    def test_history_limit(self, runner, two_table_env: tuple[Path, Path]):
        """feather history --limit 1 shows at most 1 run."""
        from feather_etl.cli import app

        config_path, _ = two_table_env
        runner.invoke(app, ["run", "--config", str(config_path)])
        runner.invoke(app, ["run", "--config", str(config_path)])
        result = runner.invoke(
            app, ["history", "--config", str(config_path), "--limit", "1"]
        )
        assert result.exit_code == 0
        lines = [line for line in result.output.splitlines() if line.strip()]
        data_lines = [
            line
            for line in lines
            if not line.startswith("-") and "Table" not in line and line.strip()
        ]
        assert len(data_lines) <= 1

    def test_history_empty_state_shows_message(
        self, runner, two_table_env: tuple[Path, Path]
    ):
        """feather history with no runs shows a friendly message."""
        from feather_etl.cli import app

        config_path, _ = two_table_env
        runner.invoke(app, ["setup", "--config", str(config_path)])
        result = runner.invoke(app, ["history", "--config", str(config_path)])
        assert result.exit_code == 0
        assert "No runs recorded" in result.output

    def test_history_json_outputs_ndjson(self, runner, tmp_path: Path):
        from feather_etl.cli import app

        config_file = cli_config(tmp_path)
        runner.invoke(app, ["run", "--config", str(config_file)])

        result = runner.invoke(app, ["--json", "history", "--config", str(config_file)])
        assert result.exit_code == 0
        lines = [line for line in result.output.strip().split("\n") if line.strip()]
        assert len(lines) >= 1
        parsed = json.loads(lines[0])
        assert "run_id" in parsed
        assert "table_name" in parsed
