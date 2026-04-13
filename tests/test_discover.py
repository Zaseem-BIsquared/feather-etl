"""End-to-end tests for `feather discover`."""

import json
import shutil
from pathlib import Path

import yaml
from typer.testing import CliRunner

from tests.conftest import FIXTURES_DIR

runner = CliRunner()


def _write_sqlite_config(tmp_path: Path, source_name: str | None = None) -> Path:
    """Set up a tmp SQLite feather project. Returns config path."""
    shutil.copy2(FIXTURES_DIR / "sample_erp.sqlite", tmp_path / "source.sqlite")
    source: dict = {"type": "sqlite", "path": "./source.sqlite"}
    if source_name is not None:
        source["name"] = source_name
    cfg = {
        "source": source,
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


class TestDiscoverSavesJson:
    def test_writes_auto_named_file_for_sqlite(self, tmp_path: Path, monkeypatch):
        from feather_etl.cli import app

        config_path = _write_sqlite_config(tmp_path)
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["discover", "--config", str(config_path)])
        assert result.exit_code == 0, result.output

        expected = tmp_path / "schema_sqlite-source.json"
        assert expected.exists()

    def test_prints_single_summary_line(self, tmp_path: Path, monkeypatch):
        from feather_etl.cli import app

        config_path = _write_sqlite_config(tmp_path)
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["discover", "--config", str(config_path)])
        assert result.exit_code == 0

        lines = [line for line in result.output.splitlines() if line.strip()]
        assert len(lines) == 1
        assert "schema_sqlite-source.json" in lines[0]
        assert "Wrote" in lines[0]

    def test_json_payload_has_expected_shape(self, tmp_path: Path, monkeypatch):
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

    def test_user_name_overrides_auto_derivation(self, tmp_path: Path, monkeypatch):
        from feather_etl.cli import app

        config_path = _write_sqlite_config(tmp_path, source_name="prod-erp")
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["discover", "--config", str(config_path)])
        assert result.exit_code == 0
        assert (tmp_path / "schema_prod-erp.json").exists()
        assert not (tmp_path / "schema_sqlite-source.json").exists()

    def test_user_name_with_unsafe_chars_is_sanitized(
        self, tmp_path: Path, monkeypatch
    ):
        from feather_etl.cli import app

        config_path = _write_sqlite_config(tmp_path, source_name="prod/erp")
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["discover", "--config", str(config_path)])
        assert result.exit_code == 0
        assert (tmp_path / "schema_prod_erp.json").exists()

    def test_silent_overwrite_on_second_run(self, tmp_path: Path, monkeypatch):
        from feather_etl.cli import app

        config_path = _write_sqlite_config(tmp_path)
        monkeypatch.chdir(tmp_path)

        r1 = runner.invoke(app, ["discover", "--config", str(config_path)])
        assert r1.exit_code == 0
        first_mtime = (tmp_path / "schema_sqlite-source.json").stat().st_mtime_ns

        r2 = runner.invoke(app, ["discover", "--config", str(config_path)])
        assert r2.exit_code == 0
        second_mtime = (tmp_path / "schema_sqlite-source.json").stat().st_mtime_ns
        assert second_mtime >= first_mtime

    def test_zero_tables_writes_empty_array(self, tmp_path: Path, monkeypatch):
        """An empty source still produces a valid file with '[]' content."""
        import sqlite3

        from feather_etl.cli import app

        empty_db = tmp_path / "source.sqlite"
        conn = sqlite3.connect(empty_db)
        conn.close()

        cfg = {
            "source": {"type": "sqlite", "path": "./source.sqlite"},
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
        assert "Wrote 0 table(s)" in result.output
