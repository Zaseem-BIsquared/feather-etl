"""Workflow stage 02: feather validate — config parsing and validation errors.

Scenarios in this file cover the CLI-visible behavior of `feather validate`:
friendly error messages, structural rejections, and happy-path smoke.
"""

from __future__ import annotations

from typer.testing import CliRunner

from feather_etl.cli import app


def test_validate_missing_config_shows_friendly_error(tmp_path, monkeypatch):
    """S13/BUG-3: running validate in a directory with no feather.yaml
    must print 'Config file not found', not a Python traceback.

    This test does NOT use the `project`/`cli` fixtures because the whole
    point is that there is no config at all — `cli` would pass --config
    pointing at a path that doesn't exist, which changes what's being tested.
    """
    runner = CliRunner()

    # Arrange: a completely empty directory.
    monkeypatch.chdir(tmp_path)
    assert not (tmp_path / "feather.yaml").exists()

    # Act: validate with no flags, so it uses CWD discovery.
    result = runner.invoke(app, ["validate"])

    # Assert: exits non-zero with a friendly message, not a traceback.
    assert result.exit_code != 0, result.output
    assert "Config file not found" in result.output
    assert "Traceback" not in result.output
