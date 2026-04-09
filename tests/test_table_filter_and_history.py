"""Tests for --table filter on `feather run` and the `feather history` command."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from tests.conftest import FIXTURES_DIR

runner = CliRunner()


@pytest.fixture
def two_table_env(tmp_path: Path) -> tuple[Path, Path]:
    """Config with two tables: inventory_group and customer_master."""
    client_db = tmp_path / "client.duckdb"
    shutil.copy2(FIXTURES_DIR / "client.duckdb", client_db)

    config = {
        "source": {"type": "duckdb", "path": str(client_db)},
        "destination": {"path": str(tmp_path / "feather_data.duckdb")},
        "tables": [
            {
                "name": "inventory_group",
                "source_table": "icube.InventoryGroup",
                "target_table": "bronze.inventory_group",
                "strategy": "full",
            },
            {
                "name": "customer_master",
                "source_table": "icube.CUSTOMERMASTER",
                "target_table": "bronze.customer_master",
                "strategy": "full",
            },
        ],
    }
    config_path = tmp_path / "feather.yaml"
    config_path.write_text(yaml.dump(config, default_flow_style=False))
    return config_path, tmp_path


class TestTableFilter:
    def test_table_filter_extracts_only_matching_table(
        self, two_table_env: tuple[Path, Path]
    ):
        """--table inventory_group should extract only that table."""
        from feather_etl.cli import app

        config_path, tmp_path = two_table_env
        result = runner.invoke(
            app, ["run", "--config", str(config_path), "--table", "inventory_group"]
        )
        assert result.exit_code == 0
        assert "inventory_group" in result.output
        # customer_master should NOT appear in output
        assert "customer_master" not in result.output

    def test_table_filter_nonexistent_table_exits_with_error(
        self, two_table_env: tuple[Path, Path]
    ):
        """--table nonexistent should exit with code 1 and show error."""
        from feather_etl.cli import app

        config_path, _ = two_table_env
        result = runner.invoke(
            app, ["run", "--config", str(config_path), "--table", "nonexistent"]
        )
        assert result.exit_code == 1
        assert "nonexistent" in result.output.lower() or "nonexistent" in (
            result.stderr or ""
        ).lower()

    def test_no_table_flag_extracts_all_tables(
        self, two_table_env: tuple[Path, Path]
    ):
        """Without --table, all configured tables are extracted."""
        from feather_etl.cli import app

        config_path, _ = two_table_env
        result = runner.invoke(app, ["run", "--config", str(config_path)])
        assert result.exit_code == 0
        assert "inventory_group" in result.output
        assert "customer_master" in result.output


class TestHistory:
    def test_history_shows_runs_after_run(self, two_table_env: tuple[Path, Path]):
        """feather history shows a table of recent runs."""
        from feather_etl.cli import app

        config_path, _ = two_table_env
        runner.invoke(app, ["run", "--config", str(config_path)])
        result = runner.invoke(app, ["history", "--config", str(config_path)])
        assert result.exit_code == 0
        assert "inventory_group" in result.output
        assert "customer_master" in result.output

    def test_history_table_filter(self, two_table_env: tuple[Path, Path]):
        """feather history --table inventory_group shows only that table's runs."""
        from feather_etl.cli import app

        config_path, _ = two_table_env
        runner.invoke(app, ["run", "--config", str(config_path)])
        result = runner.invoke(
            app,
            ["history", "--config", str(config_path), "--table", "inventory_group"],
        )
        assert result.exit_code == 0
        assert "inventory_group" in result.output
        assert "customer_master" not in result.output

    def test_history_limit(self, two_table_env: tuple[Path, Path]):
        """feather history --limit 1 shows at most 1 run."""
        from feather_etl.cli import app

        config_path, _ = two_table_env
        # Run twice to build up history
        runner.invoke(app, ["run", "--config", str(config_path)])
        runner.invoke(app, ["run", "--config", str(config_path)])
        result = runner.invoke(
            app, ["history", "--config", str(config_path), "--limit", "1"]
        )
        assert result.exit_code == 0
        # At most 1 data row (plus header + separator)
        lines = [line for line in result.output.splitlines() if line.strip()]
        # Header + separator + at most 1 data row = at most 3 lines
        data_lines = [
            line
            for line in lines
            if not line.startswith("-") and "Table" not in line and line.strip()
        ]
        assert len(data_lines) <= 1

    def test_history_empty_state_shows_message(
        self, two_table_env: tuple[Path, Path]
    ):
        """feather history with no runs shows a friendly message."""
        from feather_etl.cli import app

        config_path, _ = two_table_env
        runner.invoke(app, ["setup", "--config", str(config_path)])
        result = runner.invoke(app, ["history", "--config", str(config_path)])
        assert result.exit_code == 0
        assert "No runs recorded" in result.output
