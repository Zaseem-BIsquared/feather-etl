"""Tests for JSONL structured logging (V18 — Task 6) and --json output (Tasks 7-8)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml
from typer.testing import CliRunner

from tests.conftest import FIXTURES_DIR


class TestJsonlLogging:
    def test_feather_log_jsonl_created(self, tmp_path: Path):
        """feather_log.jsonl is created alongside state DB after feather run."""
        from feather.config import load_config
        from feather.pipeline import run_all

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
                }
            ],
        }
        config_file = tmp_path / "feather.yaml"
        config_file.write_text(yaml.dump(config, default_flow_style=False))
        cfg = load_config(config_file)

        run_all(cfg, config_file)

        log_path = tmp_path / "feather_log.jsonl"
        assert log_path.exists()

    def test_each_line_is_valid_json(self, tmp_path: Path):
        from feather.config import load_config
        from feather.pipeline import run_all

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
                }
            ],
        }
        config_file = tmp_path / "feather.yaml"
        config_file.write_text(yaml.dump(config, default_flow_style=False))
        cfg = load_config(config_file)

        run_all(cfg, config_file)

        log_path = tmp_path / "feather_log.jsonl"
        lines = log_path.read_text().strip().split("\n")
        assert len(lines) >= 1
        for line in lines:
            entry = json.loads(line)
            assert "timestamp" in entry
            assert "level" in entry
            assert "event" in entry

    def test_log_is_append_only(self, tmp_path: Path):
        from feather.config import load_config
        from feather.pipeline import run_all

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
                }
            ],
        }
        config_file = tmp_path / "feather.yaml"
        config_file.write_text(yaml.dump(config, default_flow_style=False))
        cfg = load_config(config_file)

        run_all(cfg, config_file)
        log_path = tmp_path / "feather_log.jsonl"
        lines_after_first = len(log_path.read_text().strip().split("\n"))

        run_all(cfg, config_file)
        lines_after_second = len(log_path.read_text().strip().split("\n"))

        assert lines_after_second > lines_after_first


class TestOutputHelper:
    def test_emit_single_dict_json_mode(self, capsys):
        from feather.output import emit_line

        emit_line({"table": "orders", "status": "success"}, json_mode=True)
        out = capsys.readouterr().out
        parsed = json.loads(out.strip())
        assert parsed["table"] == "orders"

    def test_emit_single_dict_noop_in_normal_mode(self, capsys):
        from feather.output import emit_line

        emit_line({"table": "orders"}, json_mode=False)
        assert capsys.readouterr().out == ""

    def test_emit_list_outputs_ndjson(self, capsys):
        from feather.output import emit

        data = [
            {"table": "orders", "status": "success"},
            {"table": "items", "status": "failure"},
        ]
        emit(data, json_mode=True)
        lines = capsys.readouterr().out.strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["table"] == "orders"
        assert json.loads(lines[1])["table"] == "items"

    def test_emit_datetime_serialized(self, capsys):
        from datetime import datetime, timezone

        from feather.output import emit_line

        dt = datetime(2026, 3, 28, 12, 0, 0, tzinfo=timezone.utc)
        emit_line({"ts": dt}, json_mode=True)
        parsed = json.loads(capsys.readouterr().out.strip())
        assert "2026-03-28" in parsed["ts"]


# --- CLI --json integration tests ---

runner = CliRunner()


def _cli_config(tmp_path: Path) -> Path:
    """Create a config for CLI --json tests."""
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
            }
        ],
    }
    config_file = tmp_path / "feather.yaml"
    config_file.write_text(yaml.dump(config, default_flow_style=False))
    return config_file


class TestCliJsonFlag:
    def test_run_json_outputs_ndjson(self, tmp_path: Path):
        from feather.cli import app

        config_file = _cli_config(tmp_path)
        result = runner.invoke(app, ["--json", "run", "--config", str(config_file)])
        assert result.exit_code == 0
        lines = [line for line in result.output.strip().split("\n") if line.strip()]
        # Should have at least one JSON line per table
        assert len(lines) >= 1
        parsed = json.loads(lines[0])
        assert "table_name" in parsed
        assert "status" in parsed

    def test_status_json_outputs_ndjson(self, tmp_path: Path):
        """AC-FR11.d: feather status --json outputs NDJSON with required fields."""
        from feather.cli import app

        config_file = _cli_config(tmp_path)
        # Run first to create state
        runner.invoke(app, ["run", "--config", str(config_file)])

        result = runner.invoke(app, ["--json", "status", "--config", str(config_file)])
        assert result.exit_code == 0
        lines = [line for line in result.output.strip().split("\n") if line.strip()]
        assert len(lines) >= 1
        parsed = json.loads(lines[0])
        assert "table_name" in parsed
        assert "status" in parsed

    def test_validate_json_outputs_json(self, tmp_path: Path):
        from feather.cli import app

        config_file = _cli_config(tmp_path)
        result = runner.invoke(app, ["--json", "validate", "--config", str(config_file)])
        assert result.exit_code == 0
        parsed = json.loads(result.output.strip())
        assert parsed["valid"] is True
        assert "tables_count" in parsed

    def test_history_json_outputs_ndjson(self, tmp_path: Path):
        from feather.cli import app

        config_file = _cli_config(tmp_path)
        runner.invoke(app, ["run", "--config", str(config_file)])

        result = runner.invoke(app, ["--json", "history", "--config", str(config_file)])
        assert result.exit_code == 0
        lines = [line for line in result.output.strip().split("\n") if line.strip()]
        assert len(lines) >= 1
        parsed = json.loads(lines[0])
        assert "run_id" in parsed
        assert "table_name" in parsed

    def test_default_output_unchanged(self, tmp_path: Path):
        """Default (no --json) output should still be human-readable."""
        from feather.cli import app

        config_file = _cli_config(tmp_path)
        result = runner.invoke(app, ["validate", "--config", str(config_file)])
        assert result.exit_code == 0
        # Should have human text, not JSON
        assert "Config valid" in result.output
