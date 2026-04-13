"""Tests for the `feather setup` command."""

from __future__ import annotations

from pathlib import Path


class TestSetup:
    def test_creates_state_and_schemas(self, runner, cli_env: tuple[Path, Path]):
        from feather_etl.cli import app

        config_path, tmp_path = cli_env
        result = runner.invoke(app, ["setup", "--config", str(config_path)])
        assert result.exit_code == 0
        assert (tmp_path / "feather_state.duckdb").exists()
