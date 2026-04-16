"""Tests for the `feather discover` command."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml
import typer

from tests.conftest import FIXTURES_DIR


def _write_sqlite_config(tmp_path: Path, source_name: str | None = None) -> Path:
    """Set up a tmp SQLite feather project. Returns config path."""
    shutil.copy2(FIXTURES_DIR / "sample_erp.sqlite", tmp_path / "source.sqlite")
    source: dict = {"type": "sqlite", "path": "./source.sqlite"}
    if source_name is not None:
        source["name"] = source_name
    cfg = {
        "sources": [source],
        "destination": {"path": "./feather_data.duckdb"},
        "tables": [
            {
                "name": "orders",
                "source_table": "orders",
                "target_table": "bronze.orders",
                "strategy": "full",
            }
        ],
    }
    config_path = tmp_path / "feather.yaml"
    config_path.write_text(yaml.dump(cfg))
    return config_path


@pytest.mark.usefixtures("stub_viewer_serve")
class TestDiscover:
    def test_writes_json_with_tables(
        self, runner, cli_env: tuple[Path, Path], monkeypatch
    ):
        from feather_etl.cli import app

        config_path, tmp_path = cli_env
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["discover", "--config", str(config_path)])
        assert result.exit_code == 0
        assert "discovered" in result.output

        schema_files = list(tmp_path.glob("schema_*.json"))
        assert len(schema_files) == 1
        payload = json.loads(schema_files[0].read_text())
        table_names = [entry["table_name"] for entry in payload]
        assert any("SALESINVOICE" in t for t in table_names)
        assert any("CUSTOMERMASTER" in t for t in table_names)

    def test_invokes_shared_viewer_runtime_after_writing_json(
        self, runner, tmp_path: Path, monkeypatch
    ):
        from feather_etl.cli import app
        from feather_etl.commands import discover as discover_cmd

        config_dir = tmp_path / "config"
        work_dir = tmp_path / "work"
        config_dir.mkdir()
        work_dir.mkdir()
        shutil.copy2(FIXTURES_DIR / "client.duckdb", config_dir / "client.duckdb")

        config_path = config_dir / "feather.yaml"
        config = {
            "sources": [{"type": "duckdb", "path": "./client.duckdb"}],
            "destination": {"path": str(work_dir / "feather_data.duckdb")},
            "tables": [
                {
                    "name": "inventory_group",
                    "source_table": "icube.InventoryGroup",
                    "target_table": "bronze.inventory_group",
                    "strategy": "full",
                },
            ],
        }
        config_path.write_text(yaml.dump(config, default_flow_style=False))
        monkeypatch.chdir(work_dir)

        seen: dict[str, object] = {}

        def fake_serve_and_open(target_dir: Path, preferred_port: int = 8000):
            seen["serve_target_dir"] = target_dir
            seen["preferred_port"] = preferred_port

        monkeypatch.setattr(discover_cmd, "serve_and_open", fake_serve_and_open)

        result = runner.invoke(app, ["discover", "--config", str(config_path)])

        assert result.exit_code == 0, result.output
        schema_files = list(work_dir.glob("schema_*.json"))
        assert len(schema_files) == 1
        expected_target_dir = schema_files[0].parent.resolve()
        assert expected_target_dir != config_dir.resolve()
        assert seen["serve_target_dir"] == expected_target_dir
        assert seen["preferred_port"] == 8000
        assert "discovered" in result.output
        assert "Schema viewer" not in result.output

    def test_runtime_emitted_output_line_is_surfaced(
        self, runner, cli_env: tuple[Path, Path], monkeypatch
    ):
        from feather_etl.cli import app
        from feather_etl.commands import discover as discover_cmd

        config_path, tmp_path = cli_env
        monkeypatch.chdir(tmp_path)

        monkeypatch.setattr(
            discover_cmd,
            "serve_and_open",
            lambda *args, **kwargs: typer.echo("Schema viewer updated."),
        )

        result = runner.invoke(app, ["discover", "--config", str(config_path)])

        assert result.exit_code == 0, result.output
        assert "Schema viewer updated." in result.output
        assert "discovered" in result.output

    def test_discover_bad_source_fails(self, runner, tmp_path: Path, monkeypatch):
        from feather_etl.cli import app

        monkeypatch.chdir(tmp_path)
        db = tmp_path / "empty.duckdb"
        db.write_bytes(b"not a duckdb file")
        config = {
            "sources": [{"type": "duckdb", "path": str(db)}],
            "destination": {"path": str(tmp_path / "data.duckdb")},
            "tables": [
                {
                    "name": "t",
                    "source_table": "main.t",
                    "target_table": "bronze.t",
                    "strategy": "full",
                }
            ],
        }
        (tmp_path / "feather.yaml").write_text(yaml.dump(config))
        result = runner.invoke(
            app, ["discover", "--config", str(tmp_path / "feather.yaml")]
        )
        assert result.exit_code != 0
        assert "→ FAILED:" in result.output

    def test_writes_auto_named_file_for_sqlite(
        self, runner, tmp_path: Path, monkeypatch
    ):
        from feather_etl.cli import app

        config_path = _write_sqlite_config(tmp_path)
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["discover", "--config", str(config_path)])
        assert result.exit_code == 0, result.output

        expected = tmp_path / "schema_sqlite-source.json"
        assert expected.exists()

    def test_prints_header_source_and_summary_lines(self, runner, tmp_path: Path, monkeypatch):
        from feather_etl.cli import app

        config_path = _write_sqlite_config(tmp_path)
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["discover", "--config", str(config_path)])
        assert result.exit_code == 0

        lines = [line for line in result.output.splitlines() if line.strip()]
        # header ("Discovering from ...") + [1/1] per-source line + summary line
        assert len(lines) == 3
        assert "Discovering from" in lines[0]
        assert "schema_sqlite-source.json" in lines[1]
        assert "discovered" in lines[2]

    def test_json_payload_has_expected_shape(self, runner, tmp_path: Path, monkeypatch):
        from feather_etl.cli import app

        config_path = _write_sqlite_config(tmp_path)
        monkeypatch.chdir(tmp_path)

        runner.invoke(app, ["discover", "--config", str(config_path)])

        payload = json.loads((tmp_path / "schema_sqlite-source.json").read_text())
        assert isinstance(payload, list)
        assert len(payload) > 0
        assert set(payload[0].keys()) == {"table_name", "columns"}
        assert isinstance(payload[0]["columns"], list)
        if payload[0]["columns"]:
            assert set(payload[0]["columns"][0].keys()) == {"name", "type"}

    def test_user_name_overrides_auto_derivation(
        self, runner, tmp_path: Path, monkeypatch
    ):
        from feather_etl.cli import app

        config_path = _write_sqlite_config(tmp_path, source_name="prod-erp")
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["discover", "--config", str(config_path)])
        assert result.exit_code == 0
        assert (tmp_path / "schema_prod-erp.json").exists()
        assert not (tmp_path / "schema_sqlite-source.json").exists()

    def test_user_name_with_unsafe_chars_is_sanitized(
        self, runner, tmp_path: Path, monkeypatch
    ):
        from feather_etl.cli import app

        config_path = _write_sqlite_config(tmp_path, source_name="prod/erp")
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["discover", "--config", str(config_path)])
        assert result.exit_code == 0
        assert (tmp_path / "schema_prod_erp.json").exists()

    def test_second_run_uses_cache_by_default(self, runner, tmp_path: Path, monkeypatch):
        from feather_etl.cli import app
        import time

        config_path = _write_sqlite_config(tmp_path)
        monkeypatch.chdir(tmp_path)

        r1 = runner.invoke(app, ["discover", "--config", str(config_path)])
        assert r1.exit_code == 0
        first_mtime = (tmp_path / "schema_sqlite-source.json").stat().st_mtime_ns

        # Sleep briefly so a rewrite would produce a different mtime.
        time.sleep(0.05)

        r2 = runner.invoke(app, ["discover", "--config", str(config_path)])
        assert r2.exit_code == 0
        assert "cached" in r2.output
        # Cached run must NOT rewrite the schema file.
        second_mtime = (tmp_path / "schema_sqlite-source.json").stat().st_mtime_ns
        assert second_mtime == first_mtime

    def test_zero_tables_writes_empty_array(self, runner, tmp_path: Path, monkeypatch):
        """An empty source still produces a valid file with '[]' content."""
        import sqlite3

        from feather_etl.cli import app

        empty_db = tmp_path / "source.sqlite"
        conn = sqlite3.connect(empty_db)
        conn.close()

        cfg = {
            "sources": [{"type": "sqlite", "path": "./source.sqlite"}],
            "destination": {"path": "./feather_data.duckdb"},
            "tables": [
                {
                    "name": "placeholder",
                    "source_table": "sqlite_master",
                    "target_table": "bronze.placeholder",
                    "strategy": "full",
                }
            ],
        }
        config_path = tmp_path / "feather.yaml"
        config_path.write_text(yaml.dump(cfg))
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["discover", "--config", str(config_path)])
        assert result.exit_code == 0, result.output

        out = tmp_path / "schema_sqlite-source.json"
        assert out.exists()
        assert json.loads(out.read_text()) == []
        assert "0 tables" in result.output


@pytest.mark.usefixtures("stub_viewer_serve")
class TestDiscoverAutoEnumPermissionError:
    def test_empty_enumeration_records_failed_with_hint(
        self, runner, tmp_path, monkeypatch
    ):
        """If list_databases() returns [], record FAILED with remediation hint (E1)."""
        from unittest.mock import MagicMock
        from feather_etl.cli import app
        from feather_etl.sources.sqlserver import SqlServerSource

        # Patch list_databases to return [].
        monkeypatch.setattr(SqlServerSource, "list_databases", lambda self: [])
        # Patch pyodbc.connect to return a mock connection that closes cleanly.
        import pyodbc
        mock_conn = MagicMock()
        monkeypatch.setattr(pyodbc, "connect", lambda *args, **kwargs: mock_conn)

        cfg_text = """
sources:
  - name: erp
    type: sqlserver
    host: db.example.com
    user: u
    password: p
destination:
  path: ./out.duckdb
tables: []
"""
        (tmp_path / "feather.yaml").write_text(cfg_text)
        monkeypatch.chdir(tmp_path)

        r = runner.invoke(
            app, ["discover", "--config", str(tmp_path / "feather.yaml")]
        )
        assert r.exit_code == 2
        combined_output = r.output + (getattr(r, 'stderr', '') or '')
        assert "Found 0 databases" in combined_output
        assert "VIEW ANY DATABASE" in combined_output


@pytest.mark.usefixtures("stub_viewer_serve")
class TestRenameAmbiguousMatch:
    def test_ambiguous_fingerprint_match_errors(
        self, runner, tmp_path: Path, monkeypatch
    ):
        from feather_etl.cli import app
        from feather_etl.discover_state import DiscoverState

        config_path = _write_sqlite_config(tmp_path, source_name="c")
        monkeypatch.chdir(tmp_path)

        state = DiscoverState.load(tmp_path)
        fingerprint = f"sqlite:{(tmp_path / 'source.sqlite').resolve()}"
        for name in ("a", "b"):
            state.record_ok(
                name=name,
                type_="sqlite",
                fingerprint=fingerprint,
                table_count=1,
                output_path=tmp_path / f"schema_{name}.json",
            )
        state.save()

        result = runner.invoke(app, ["discover", "--config", str(config_path)])
        assert result.exit_code == 2
        output = result.output.lower()
        assert "ambiguous" in output
        assert "a" in result.output
        assert "b" in result.output
