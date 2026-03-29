"""Tests for feather init wizard (V17)."""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml
from typer.testing import CliRunner

from tests.conftest import FIXTURES_DIR

runner = CliRunner()


class TestNonInteractiveInit:
    def test_non_interactive_with_duckdb_source(self, tmp_path: Path):
        """--non-interactive creates project with valid config from CLI flags."""
        from feather.cli import app

        client_db = tmp_path / "source.duckdb"
        shutil.copy2(FIXTURES_DIR / "sample_erp.duckdb", client_db)

        project = tmp_path / "test-project"
        result = runner.invoke(app, [
            "init", str(project),
            "--non-interactive",
            "--source-type", "duckdb",
            "--source-path", str(client_db),
        ])
        assert result.exit_code == 0, f"Failed: {result.output}"
        assert (project / "feather.yaml").exists()

        # Verify generated config is valid
        cfg = yaml.safe_load((project / "feather.yaml").read_text())
        assert cfg["source"]["type"] == "duckdb"
        assert len(cfg["tables"]) > 0
        # Tables come from discovery, not template
        table_sources = [t["source_table"] for t in cfg["tables"]]
        assert any("erp." in s for s in table_sources)  # Should have discovered tables

    def test_non_interactive_with_tables_filter(self, tmp_path: Path):
        """--tables flag selects specific tables."""
        from feather.cli import app

        client_db = tmp_path / "source.duckdb"
        shutil.copy2(FIXTURES_DIR / "sample_erp.duckdb", client_db)

        project = tmp_path / "test-project"
        result = runner.invoke(app, [
            "init", str(project),
            "--non-interactive",
            "--source-type", "duckdb",
            "--source-path", str(client_db),
            "--tables", "erp.customers",
        ])
        assert result.exit_code == 0, f"Failed: {result.output}"

        cfg = yaml.safe_load((project / "feather.yaml").read_text())
        assert len(cfg["tables"]) == 1
        assert cfg["tables"][0]["source_table"] == "erp.customers"

    def test_non_interactive_generates_silver_stubs(self, tmp_path: Path):
        """Silver transform stubs are created for each table."""
        from feather.cli import app

        client_db = tmp_path / "source.duckdb"
        shutil.copy2(FIXTURES_DIR / "sample_erp.duckdb", client_db)

        project = tmp_path / "test-project"
        result = runner.invoke(app, [
            "init", str(project),
            "--non-interactive",
            "--source-type", "duckdb",
            "--source-path", str(client_db),
            "--tables", "erp.customers",
        ])
        assert result.exit_code == 0

        # Check silver stub exists
        silver_dir = project / "transforms" / "silver"
        sql_files = list(silver_dir.glob("*.sql"))
        assert len(sql_files) >= 1

        content = sql_files[0].read_text()
        assert "depends_on" in content
        assert "SELECT" in content

    def test_non_interactive_json_output(self, tmp_path: Path):
        """--json produces JSON summary."""
        import json
        from feather.cli import app

        client_db = tmp_path / "source.duckdb"
        shutil.copy2(FIXTURES_DIR / "sample_erp.duckdb", client_db)

        project = tmp_path / "test-project"
        result = runner.invoke(app, [
            "--json", "init", str(project),
            "--non-interactive",
            "--source-type", "duckdb",
            "--source-path", str(client_db),
        ])
        assert result.exit_code == 0
        data = json.loads(result.output.strip())
        assert "project" in data
        assert "tables_configured" in data


class TestInteractiveInit:
    def test_interactive_prompts_and_generates(self, tmp_path: Path):
        """Interactive mode prompts for source type and generates config."""
        from feather.cli import app

        client_db = tmp_path / "source.duckdb"
        shutil.copy2(FIXTURES_DIR / "sample_erp.duckdb", client_db)

        project = tmp_path / "test-project"
        # Simulate interactive input: source_type=duckdb, path, select all tables
        user_input = f"duckdb\n{client_db}\nall\n"
        result = runner.invoke(
            app, ["init", str(project)],
            input=user_input,
        )
        assert result.exit_code == 0, f"Failed: {result.output}"
        assert (project / "feather.yaml").exists()

        cfg = yaml.safe_load((project / "feather.yaml").read_text())
        assert cfg["source"]["type"] == "duckdb"
        assert len(cfg["tables"]) > 0
        # Tables come from discovery, not template
        table_sources = [t["source_table"] for t in cfg["tables"]]
        assert any("erp." in s for s in table_sources)
