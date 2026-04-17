import shutil
from pathlib import Path

from typer.testing import CliRunner

from tests.conftest import FIXTURES_DIR
from feather_etl.config import load_config
from feather_etl.sources.duckdb_file import DuckDBFileSource
from feather_etl.sources.postgres import PostgresSource
from tests.helpers import write_config


def test_file_source_sets_explicit_name_true_when_name_present(tmp_path: Path) -> None:
    source = DuckDBFileSource.from_yaml(
        {"type": "duckdb", "path": "source.duckdb", "name": "warehouse"},
        tmp_path,
    )
    assert source._explicit_name is True


def test_file_source_sets_explicit_name_false_when_name_omitted(tmp_path: Path) -> None:
    source = DuckDBFileSource.from_yaml(
        {"type": "duckdb", "path": "source.duckdb"},
        tmp_path,
    )
    assert source._explicit_name is False


def test_db_source_sets_explicit_name_true_when_name_present(tmp_path: Path) -> None:
    source = PostgresSource.from_yaml(
        {
            "type": "postgres",
            "connection_string": "host=localhost port=5432 dbname=postgres",
            "name": "pg_primary",
        },
        tmp_path,
    )
    assert source._explicit_name is True


def test_db_source_sets_explicit_name_false_when_name_omitted(tmp_path: Path) -> None:
    source = PostgresSource.from_yaml(
        {"type": "postgres", "connection_string": "host=localhost dbname=postgres"},
        tmp_path,
    )
    assert source._explicit_name is False


def test_single_source_name_backfill_keeps_explicit_name_false(tmp_path: Path) -> None:
    source_path = tmp_path / "source.duckdb"
    source_path.touch()
    config = {
        "sources": [{"type": "duckdb", "path": str(source_path)}],
        "destination": {"path": str(tmp_path / "feather_data.duckdb")},
        "tables": [
            {
                "name": "test_table",
                "source_table": "main.test",
                "target_table": "bronze.test_table",
                "strategy": "full",
            }
        ],
    }

    config_file = write_config(tmp_path, config)
    loaded = load_config(config_file, validate=False)

    source = loaded.sources[0]
    assert source.name != ""
    assert source._explicit_name is False


def test_discover_explicit_named_source_writes_typed_filename(
    tmp_path: Path, monkeypatch
) -> None:
    from feather_etl.cli import app
    from feather_etl.commands import discover as discover_cmd

    source_db = tmp_path / "source.duckdb"
    shutil.copy2(FIXTURES_DIR / "sample_erp.duckdb", source_db)

    config = {
        "sources": [
            {"type": "duckdb", "path": str(source_db), "name": "warehouse_primary"}
        ],
        "destination": {"path": str(tmp_path / "feather_data.duckdb")},
        "tables": [],
    }
    config_file = write_config(tmp_path, config)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(discover_cmd, "serve_and_open", lambda *args, **kwargs: None)

    runner = CliRunner()
    result = runner.invoke(app, ["discover", "--config", str(config_file)])

    assert result.exit_code == 0, result.output
    files = sorted(p.name for p in tmp_path.glob("schema_*.json"))
    assert files == ["schema_duckdb_warehouse_primary.json"]


def test_discover_auto_named_source_keeps_auto_derived_filename(
    tmp_path: Path, monkeypatch
) -> None:
    from feather_etl.cli import app
    from feather_etl.commands import discover as discover_cmd

    source_db = tmp_path / "source.duckdb"
    shutil.copy2(FIXTURES_DIR / "sample_erp.duckdb", source_db)

    config = {
        "sources": [{"type": "duckdb", "path": str(source_db)}],
        "destination": {"path": str(tmp_path / "feather_data.duckdb")},
        "tables": [],
    }
    config_file = write_config(tmp_path, config)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(discover_cmd, "serve_and_open", lambda *args, **kwargs: None)

    runner = CliRunner()
    result = runner.invoke(app, ["discover", "--config", str(config_file)])

    assert result.exit_code == 0, result.output
    files = sorted(p.name for p in tmp_path.glob("schema_*.json"))
    assert files == ["schema_duckdb-source.json"]
