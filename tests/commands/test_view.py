"""Tests for the `feather view` command."""

from __future__ import annotations

from pathlib import Path

import pytest


def _forbid_sync(*args, **kwargs):
    raise AssertionError("view should not call sync_viewer_html directly")


class TestView:
    def test_uses_current_directory_by_default(
        self, runner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        from feather_etl.cli import app
        from feather_etl import viewer_server

        seen: dict[str, object] = {}

        def fake_serve_and_open(target_dir: Path, preferred_port: int = viewer_server.DEFAULT_PORT):
            seen["serve_target_dir"] = target_dir
            seen["preferred_port"] = preferred_port

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(viewer_server, "sync_viewer_html", _forbid_sync)
        monkeypatch.setattr(viewer_server, "serve_and_open", fake_serve_and_open)

        result = runner.invoke(app, ["view"])

        assert result.exit_code == 0, result.output
        assert seen["serve_target_dir"] == tmp_path
        assert seen["preferred_port"] == viewer_server.DEFAULT_PORT

    def test_uses_path_and_port_options(
        self, runner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        from feather_etl.cli import app
        from feather_etl import viewer_server

        target_dir = tmp_path / "viewer"
        target_dir.mkdir()
        seen: dict[str, object] = {}

        def fake_serve_and_open(path: Path, preferred_port: int = viewer_server.DEFAULT_PORT):
            seen["serve_target_dir"] = path
            seen["preferred_port"] = preferred_port

        monkeypatch.setattr(viewer_server, "sync_viewer_html", _forbid_sync)
        monkeypatch.setattr(viewer_server, "serve_and_open", fake_serve_and_open)

        result = runner.invoke(app, ["view", str(target_dir), "--port", "8123"])

        assert result.exit_code == 0, result.output
        assert seen["serve_target_dir"] == target_dir.resolve()
        assert seen["preferred_port"] == 8123

    def test_invalid_path_fails(self, runner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        from feather_etl.cli import app

        result = runner.invoke(app, ["view", str(tmp_path / "missing")])

        assert result.exit_code != 0
        assert "does not exist" in result.output

    def test_help_mentions_existing_directory(self, runner):
        from feather_etl.cli import app

        result = runner.invoke(app, ["view", "--help"])

        assert result.exit_code == 0, result.output
        assert "Existing directory to serve the schema viewer from." in result.output
