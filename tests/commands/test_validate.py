"""Tests for the `feather validate` command."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from tests.commands.conftest import cli_config


class TestValidate:
    def test_valid_config(self, runner, cli_env: tuple[Path, Path]):
        from feather_etl.cli import app

        config_path, tmp_path = cli_env
        result = runner.invoke(app, ["validate", "--config", str(config_path)])
        assert result.exit_code == 0
        assert (config_path.parent / "feather_validation.json").exists()

    def test_invalid_config(self, runner, tmp_path: Path):
        from feather_etl.cli import app

        bad_config = tmp_path / "feather.yaml"
        bad_config.write_text(
            yaml.dump(
                {
                    "source": {"type": "mongodb", "path": "/nope"},
                    "destination": {"path": "./data.duckdb"},
                    "tables": [],
                }
            )
        )
        result = runner.invoke(app, ["validate", "--config", str(bad_config)])
        assert result.exit_code != 0

    def test_missing_config_file_shows_friendly_error(self, runner, tmp_path: Path):
        """BUG-3: Missing feather.yaml should not show a Python traceback."""
        from feather_etl.cli import app

        result = runner.invoke(
            app, ["validate", "--config", str(tmp_path / "nope.yaml")]
        )
        assert result.exit_code != 0
        assert "Config file not found" in result.output

    def test_validate_prints_details_on_source_failure(
        self, runner, cli_env: tuple[Path, Path], monkeypatch
    ):
        """When source.check() fails, the real exception must be surfaced as 'Details: ...'.

        Regression for siraj-samsudeen/feather-etl#2: the CLI used to print only
        'Source connection failed.' and swallow the real error, making remote DB
        misconfig (TLS, creds, driver) impossible to diagnose without code changes.
        """
        from feather_etl.cli import app

        import feather_etl.config as _config_mod

        real_load = _config_mod.load_config

        class FakeFailingSource:
            def __init__(self):
                self._last_error = "TLS Provider: certificate verify failed"
                self.type = "duckdb"

            def check(self) -> bool:
                return False

        def fake_load_config(path, **kwargs):
            cfg = real_load(path, **kwargs)
            cfg.source = FakeFailingSource()
            return cfg

        monkeypatch.setattr(_config_mod, "load_config", fake_load_config)

        config_path, _ = cli_env
        result = runner.invoke(
            app, ["validate", "--config", str(config_path)], catch_exceptions=False
        )
        assert result.exit_code == 2
        assert "Source connection failed." in result.output
        assert "Details: TLS Provider: certificate verify failed" in result.output

    def test_validate_shows_state_path(self, runner, cli_env: tuple[Path, Path]):
        """UX-9: validate output should show where the state DB will be created."""
        from feather_etl.cli import app

        config_path, _ = cli_env
        result = runner.invoke(app, ["validate", "--config", str(config_path)])
        assert result.exit_code == 0
        assert "State:" in result.output
        assert "feather_state.duckdb" in result.output

    def test_validate_json_outputs_json(self, runner, tmp_path: Path):
        from feather_etl.cli import app

        config_file = cli_config(tmp_path)
        result = runner.invoke(
            app, ["--json", "validate", "--config", str(config_file)]
        )
        assert result.exit_code == 0
        parsed = json.loads(result.output.strip())
        assert parsed["valid"] is True
        assert "tables_count" in parsed
