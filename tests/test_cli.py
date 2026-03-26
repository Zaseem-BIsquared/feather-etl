"""Tests for feather CLI commands."""

import json
import shutil
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from tests.conftest import FIXTURES_DIR

runner = CliRunner()


@pytest.fixture
def cli_env(tmp_path: Path) -> tuple[Path, Path]:
    """Config + source DB for CLI tests."""
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
        ],
    }
    config_path = tmp_path / "feather.yaml"
    config_path.write_text(yaml.dump(config, default_flow_style=False))
    return config_path, tmp_path


class TestInit:
    def test_scaffolds_project(self, tmp_path: Path):
        from feather.cli import app

        result = runner.invoke(app, ["init", str(tmp_path / "test-project")])
        assert result.exit_code == 0
        project = tmp_path / "test-project"
        assert (project / "feather.yaml").exists()
        assert (project / "pyproject.toml").exists()
        assert (project / ".gitignore").exists()
        assert (project / ".env.example").exists()
        assert (project / "transforms" / "silver").is_dir()
        assert (project / "transforms" / "gold").is_dir()
        assert (project / "tables").is_dir()
        assert (project / "extracts").is_dir()

    def test_init_nonempty_dir_fails(self, tmp_path: Path):
        from feather.cli import app

        project = tmp_path / "existing"
        project.mkdir()
        (project / "somefile.txt").write_text("exists")
        result = runner.invoke(app, ["init", str(project)])
        assert result.exit_code != 0
        assert "already exists" in result.output

    def test_init_allows_git_only_dir(self, tmp_path: Path):
        """UX-3: .git directory should not block feather init."""
        from feather.cli import app

        project = tmp_path / "git-project"
        project.mkdir()
        (project / ".git").mkdir()
        (project / ".gitignore").write_text("*.duckdb\n")
        result = runner.invoke(app, ["init", str(project)])
        assert result.exit_code == 0
        assert (project / "feather.yaml").exists()

    def test_init_dot_uses_cwd_name(self, tmp_path: Path):
        """UX-2: feather init . should use directory name, not empty string."""
        import os

        from feather.cli import app

        project = tmp_path / "my-client"
        project.mkdir()
        original_cwd = os.getcwd()
        try:
            os.chdir(project)
            result = runner.invoke(app, ["init", "."])
            assert result.exit_code == 0
            toml = (project / "pyproject.toml").read_text()
            assert 'name = ""' not in toml
            assert "my-client" in toml
        finally:
            os.chdir(original_cwd)


class TestValidate:
    def test_valid_config(self, cli_env: tuple[Path, Path]):
        from feather.cli import app

        config_path, tmp_path = cli_env
        result = runner.invoke(app, ["validate", "--config", str(config_path)])
        assert result.exit_code == 0
        assert (config_path.parent / "feather_validation.json").exists()

    def test_invalid_config(self, tmp_path: Path):
        from feather.cli import app

        bad_config = tmp_path / "feather.yaml"
        bad_config.write_text(yaml.dump({
            "source": {"type": "mongodb", "path": "/nope"},
            "destination": {"path": "./data.duckdb"},
            "tables": [],
        }))
        result = runner.invoke(app, ["validate", "--config", str(bad_config)])
        assert result.exit_code != 0

    def test_missing_config_file_shows_friendly_error(self, tmp_path: Path):
        """BUG-3: Missing feather.yaml should not show a Python traceback."""
        from feather.cli import app

        result = runner.invoke(app, ["validate", "--config", str(tmp_path / "nope.yaml")])
        assert result.exit_code != 0
        assert "Config file not found" in result.output

    def test_validate_shows_state_path(self, cli_env: tuple[Path, Path]):
        """UX-9: validate output should show where the state DB will be created."""
        from feather.cli import app

        config_path, _ = cli_env
        result = runner.invoke(app, ["validate", "--config", str(config_path)])
        assert result.exit_code == 0
        assert "State:" in result.output
        assert "feather_state.duckdb" in result.output


class TestDiscover:
    def test_lists_tables(self, cli_env: tuple[Path, Path]):
        from feather.cli import app

        config_path, _ = cli_env
        result = runner.invoke(app, ["discover", "--config", str(config_path)])
        assert result.exit_code == 0
        assert "SALESINVOICE" in result.output
        assert "CUSTOMERMASTER" in result.output

    def test_discover_bad_source_fails(self, tmp_path: Path):
        from feather.cli import app

        db = tmp_path / "empty.duckdb"
        db.write_bytes(b"not a duckdb file")
        config = {
            "source": {"type": "duckdb", "path": str(db)},
            "destination": {"path": str(tmp_path / "data.duckdb")},
            "tables": [{"name": "t", "source_table": "main.t", "target_table": "bronze.t", "strategy": "full"}],
        }
        (tmp_path / "feather.yaml").write_text(yaml.dump(config))
        result = runner.invoke(app, ["discover", "--config", str(tmp_path / "feather.yaml")])
        assert result.exit_code != 0
        assert "Source connection failed" in result.output


class TestSetup:
    def test_creates_state_and_schemas(self, cli_env: tuple[Path, Path]):
        from feather.cli import app

        config_path, tmp_path = cli_env
        result = runner.invoke(app, ["setup", "--config", str(config_path)])
        assert result.exit_code == 0
        assert (tmp_path / "feather_state.duckdb").exists()


class TestRun:
    def test_extracts_tables(self, cli_env: tuple[Path, Path]):
        from feather.cli import app

        config_path, tmp_path = cli_env
        result = runner.invoke(app, ["run", "--config", str(config_path)])
        assert result.exit_code == 0
        assert "success" in result.output.lower()

    def test_run_with_bad_table_shows_failure(self, tmp_path: Path):
        from feather.cli import app

        client_db = tmp_path / "client.duckdb"
        shutil.copy2(FIXTURES_DIR / "client.duckdb", client_db)
        config = {
            "source": {"type": "duckdb", "path": str(client_db)},
            "destination": {"path": str(tmp_path / "feather_data.duckdb")},
            "tables": [
                {"name": "bad_table", "source_table": "icube.NONEXISTENT", "target_table": "bronze.bad_table", "strategy": "full"},
            ],
        }
        (tmp_path / "feather.yaml").write_text(yaml.dump(config))
        result = runner.invoke(app, ["run", "--config", str(tmp_path / "feather.yaml")])
        assert result.exit_code == 1
        assert "failure" in result.output.lower()


class TestStatus:
    def test_shows_status_after_run(self, cli_env: tuple[Path, Path]):
        from feather.cli import app

        config_path, tmp_path = cli_env
        runner.invoke(app, ["run", "--config", str(config_path)])
        result = runner.invoke(app, ["status", "--config", str(config_path)])
        assert result.exit_code == 0
        assert "inventory_group" in result.output

    def test_status_no_state_db(self, cli_env: tuple[Path, Path]):
        from feather.cli import app

        config_path, _ = cli_env
        result = runner.invoke(app, ["status", "--config", str(config_path)])
        assert result.exit_code != 0
        assert "No state DB found" in result.output

    def test_status_no_runs_yet(self, cli_env: tuple[Path, Path]):
        from feather.cli import app

        config_path, _ = cli_env
        # setup creates state DB but no runs yet
        runner.invoke(app, ["setup", "--config", str(config_path)])
        result = runner.invoke(app, ["status", "--config", str(config_path)])
        assert result.exit_code == 0
        assert "No runs recorded" in result.output

    def test_status_shows_error_message_for_failures(self, tmp_path: Path):
        """UX-5: feather status should display error text for failed tables."""
        from feather.cli import app

        client_db = tmp_path / "client.duckdb"
        shutil.copy2(FIXTURES_DIR / "client.duckdb", client_db)
        config = {
            "source": {"type": "duckdb", "path": str(client_db)},
            "destination": {"path": str(tmp_path / "feather_data.duckdb")},
            "tables": [
                {"name": "bad_table", "source_table": "icube.NONEXISTENT",
                 "target_table": "bronze.bad_table", "strategy": "full"},
            ],
        }
        config_path = tmp_path / "feather.yaml"
        config_path.write_text(yaml.dump(config, default_flow_style=False))

        runner.invoke(app, ["run", "--config", str(config_path)])
        result = runner.invoke(app, ["status", "--config", str(config_path)])
        assert result.exit_code == 0
        assert "Error:" in result.output

    def test_status_shows_all_time_history(self, tmp_path: Path):
        """BUG-8 (intentional): status shows tables from ALL runs, not just current config.
        This is correct behavior — history should not be lost when config changes."""
        from feather.cli import app

        client_db = tmp_path / "client.duckdb"
        shutil.copy2(FIXTURES_DIR / "client.duckdb", client_db)

        # Run config with table A
        config_a = {
            "source": {"type": "duckdb", "path": str(client_db)},
            "destination": {"path": str(tmp_path / "feather_data.duckdb")},
            "tables": [
                {"name": "inventory_group", "source_table": "icube.InventoryGroup",
                 "target_table": "bronze.inventory_group", "strategy": "full"},
            ],
        }
        config_path = tmp_path / "feather.yaml"
        config_path.write_text(yaml.dump(config_a, default_flow_style=False))
        runner.invoke(app, ["run", "--config", str(config_path)])

        # Switch to config with table B only
        config_b = {
            "source": {"type": "duckdb", "path": str(client_db)},
            "destination": {"path": str(tmp_path / "feather_data.duckdb")},
            "tables": [
                {"name": "customer_master", "source_table": "icube.CUSTOMERMASTER",
                 "target_table": "bronze.customer_master", "strategy": "full"},
            ],
        }
        config_path.write_text(yaml.dump(config_b, default_flow_style=False))
        runner.invoke(app, ["run", "--config", str(config_path)])

        # Status should show BOTH tables
        result = runner.invoke(app, ["status", "--config", str(config_path)])
        assert result.exit_code == 0
        assert "inventory_group" in result.output
        assert "customer_master" in result.output


class TestRunAutoCreates:
    def test_run_without_setup_auto_creates_state_and_data(self, cli_env: tuple[Path, Path]):
        """UX-7: feather run creates state/data DBs automatically. setup is optional."""
        from feather.cli import app

        config_path, tmp_path = cli_env
        # Do NOT call setup first
        result = runner.invoke(app, ["run", "--config", str(config_path)])
        assert result.exit_code == 0
        assert (tmp_path / "feather_state.duckdb").exists()
        assert (tmp_path / "feather_data.duckdb").exists()
