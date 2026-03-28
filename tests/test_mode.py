"""Tests for mode: dev/prod/test pipeline behavior."""

from pathlib import Path

import duckdb
import pytest
import yaml

from tests.conftest import FIXTURES_DIR


# --- Task 1: Config tests ---


def _write_config(tmp_path: Path, mode: str | None = None, **overrides) -> Path:
    """Write a minimal feather.yaml with optional mode and return config path."""
    import shutil

    src_db = tmp_path / "sample_erp.duckdb"
    shutil.copy2(FIXTURES_DIR / "sample_erp.duckdb", src_db)

    config = {
        "source": {"type": "duckdb", "path": str(src_db)},
        "destination": {"path": str(tmp_path / "output.duckdb")},
        "tables": [
            {
                "name": "customers",
                "source_table": "erp.customers",
                "strategy": "full",
                "target_table": "bronze.customers",
            },
        ],
    }
    if mode is not None:
        config["mode"] = mode
    config.update(overrides)

    config_path = tmp_path / "feather.yaml"
    config_path.write_text(yaml.dump(config, default_flow_style=False))
    return config_path


def test_config_mode_defaults_to_dev(tmp_path):
    """mode defaults to 'dev' when not specified."""
    from feather.config import load_config

    config_path = _write_config(tmp_path)
    cfg = load_config(config_path)
    assert cfg.mode == "dev"


def test_config_mode_parsed_from_yaml(tmp_path):
    """mode: prod in YAML is parsed correctly."""
    from feather.config import load_config

    config_path = _write_config(tmp_path, mode="prod")
    cfg = load_config(config_path)
    assert cfg.mode == "prod"


def test_config_invalid_mode_rejected(tmp_path):
    """Invalid mode value raises validation error."""
    from feather.config import load_config

    config_path = _write_config(tmp_path, mode="staging")
    with pytest.raises(ValueError, match="mode"):
        load_config(config_path)


def test_config_mode_env_var_overrides_yaml(tmp_path, monkeypatch):
    """FEATHER_MODE env var overrides YAML mode."""
    from feather.config import load_config

    config_path = _write_config(tmp_path, mode="dev")
    monkeypatch.setenv("FEATHER_MODE", "prod")
    cfg = load_config(config_path)
    assert cfg.mode == "prod"


def test_config_mode_cli_override(tmp_path):
    """mode_override parameter overrides both YAML and env var."""
    from feather.config import load_config

    config_path = _write_config(tmp_path, mode="dev")
    cfg = load_config(config_path, mode_override="prod")
    assert cfg.mode == "prod"


def test_config_row_limit_parsed(tmp_path):
    """defaults.row_limit is parsed from YAML."""
    from feather.config import load_config

    config_path = _write_config(tmp_path, defaults={"row_limit": 100})
    cfg = load_config(config_path)
    assert cfg.defaults.row_limit == 100


def test_config_row_limit_defaults_to_none(tmp_path):
    """defaults.row_limit defaults to None."""
    from feather.config import load_config

    config_path = _write_config(tmp_path)
    cfg = load_config(config_path)
    assert cfg.defaults.row_limit is None


def test_config_empty_target_table_valid_with_mode(tmp_path):
    """Tables without target_table are valid — mode derives the target."""
    import shutil

    from feather.config import load_config

    src_db = tmp_path / "sample_erp.duckdb"
    shutil.copy2(FIXTURES_DIR / "sample_erp.duckdb", src_db)

    config = {
        "source": {"type": "duckdb", "path": str(src_db)},
        "destination": {"path": str(tmp_path / "output.duckdb")},
        "mode": "dev",
        "tables": [
            {
                "name": "customers",
                "source_table": "erp.customers",
                "strategy": "full",
                # NO target_table — mode derives it
            },
        ],
    }
    config_path = tmp_path / "feather.yaml"
    config_path.write_text(yaml.dump(config, default_flow_style=False))

    cfg = load_config(config_path)
    assert cfg.tables[0].target_table == ""


# --- Task 2: Pipeline mode-driven target + column_map ---


def _run_pipeline(tmp_path: Path, mode: str, column_map: dict[str, str] | None = None,
                  target_table: str | None = None) -> tuple:
    """Helper: run pipeline and return (config, results, dest_path)."""
    import shutil

    from feather.config import load_config
    from feather.pipeline import run_all

    src_db = tmp_path / "sample_erp.duckdb"
    shutil.copy2(FIXTURES_DIR / "sample_erp.duckdb", src_db)

    table_def: dict = {
        "name": "customers",
        "source_table": "erp.customers",
        "strategy": "full",
    }
    if target_table is not None:
        table_def["target_table"] = target_table
    if column_map is not None:
        table_def["column_map"] = column_map

    dest_path = tmp_path / "output.duckdb"
    config = {
        "source": {"type": "duckdb", "path": str(src_db)},
        "destination": {"path": str(dest_path)},
        "mode": mode,
        "tables": [table_def],
    }
    config_path = tmp_path / "feather.yaml"
    config_path.write_text(yaml.dump(config, default_flow_style=False))

    cfg = load_config(config_path)
    results = run_all(cfg, config_path)
    return cfg, results, dest_path


def test_dev_extracts_to_bronze(tmp_path):
    """Dev mode: data lands in bronze.{name}."""
    _, results, dest_path = _run_pipeline(tmp_path, mode="dev")

    assert results[0].status == "success"
    con = duckdb.connect(str(dest_path))
    count = con.execute("SELECT COUNT(*) FROM bronze.customers").fetchone()[0]
    con.close()
    assert count > 0


def test_prod_extracts_to_silver(tmp_path):
    """Prod mode without column_map: all columns land in silver.{name}."""
    _, results, dest_path = _run_pipeline(tmp_path, mode="prod")

    assert results[0].status == "success"
    con = duckdb.connect(str(dest_path))
    count = con.execute("SELECT COUNT(*) FROM silver.customers").fetchone()[0]
    con.close()
    assert count > 0


def test_prod_with_column_map(tmp_path):
    """Prod mode with column_map: only mapped columns, renamed, in silver."""
    _, results, dest_path = _run_pipeline(
        tmp_path, mode="prod",
        column_map={"customer_id": "cust_id", "name": "cust_name"},
    )

    assert results[0].status == "success"
    con = duckdb.connect(str(dest_path))
    cols = [row[0] for row in con.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='silver' AND table_name='customers' "
        "ORDER BY ordinal_position"
    ).fetchall()]
    con.close()

    # Should have renamed columns + ETL metadata
    assert "cust_id" in cols
    assert "cust_name" in cols
    assert "customer_id" not in cols  # source name should be renamed
    assert "email" not in cols  # unmapped columns excluded


def test_dev_with_column_map_ignores_it(tmp_path):
    """Dev mode ignores column_map — extracts all columns to bronze."""
    _, results, dest_path = _run_pipeline(
        tmp_path, mode="dev",
        column_map={"customer_id": "cust_id", "name": "cust_name"},
    )

    assert results[0].status == "success"
    con = duckdb.connect(str(dest_path))
    cols = [row[0] for row in con.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='bronze' AND table_name='customers' "
        "ORDER BY ordinal_position"
    ).fetchall()]
    con.close()

    # All original source columns present (not renamed)
    assert "customer_id" in cols
    assert "name" in cols
    assert "email" in cols  # all columns present


def test_explicit_target_overrides_mode(tmp_path):
    """Explicit target_table in YAML overrides mode-derived target."""
    _, results, dest_path = _run_pipeline(
        tmp_path, mode="prod",
        target_table="bronze.customers",  # explicit override
    )

    assert results[0].status == "success"
    con = duckdb.connect(str(dest_path))
    count = con.execute("SELECT COUNT(*) FROM bronze.customers").fetchone()[0]
    con.close()
    assert count > 0


# --- Task 3: Gold materialization per mode ---


def _run_with_transforms(tmp_path: Path, mode: str) -> Path:
    """Helper: run pipeline with a gold transform SQL file and return dest_path."""
    import shutil

    from feather.config import load_config
    from feather.pipeline import run_all

    src_db = tmp_path / "sample_erp.duckdb"
    shutil.copy2(FIXTURES_DIR / "sample_erp.duckdb", src_db)

    # Create transform dirs + files
    silver_dir = tmp_path / "transforms" / "silver"
    gold_dir = tmp_path / "transforms" / "gold"
    silver_dir.mkdir(parents=True)
    gold_dir.mkdir(parents=True)

    # Silver view: rename columns from bronze
    (silver_dir / "customers_clean.sql").write_text(
        "-- depends_on: bronze.customers\n"
        "SELECT customer_id, name AS customer_name, city\n"
        "FROM bronze.customers\n"
    )

    # Gold materialized table
    (gold_dir / "customer_summary.sql").write_text(
        "-- depends_on: silver.customers_clean\n"
        "-- materialized: true\n"
        "SELECT city, COUNT(*) AS customer_count\n"
        "FROM silver.customers_clean\n"
        "GROUP BY city\n"
    )

    dest_path = tmp_path / "output.duckdb"
    config = {
        "source": {"type": "duckdb", "path": str(src_db)},
        "destination": {"path": str(dest_path)},
        "mode": mode,
        "tables": [
            {
                "name": "customers",
                "source_table": "erp.customers",
                "strategy": "full",
                "target_table": "bronze.customers",
            },
        ],
    }
    config_path = tmp_path / "feather.yaml"
    config_path.write_text(yaml.dump(config, default_flow_style=False))

    cfg = load_config(config_path)
    run_all(cfg, config_path)
    return dest_path


def test_prod_gold_materialized(tmp_path):
    """Prod mode: gold transform is a materialized TABLE."""
    dest_path = _run_with_transforms(tmp_path, mode="prod")

    con = duckdb.connect(str(dest_path))
    result = con.execute(
        "SELECT table_type FROM information_schema.tables "
        "WHERE table_schema='gold' AND table_name='customer_summary'"
    ).fetchone()
    con.close()

    assert result is not None
    assert result[0] == "BASE TABLE"


def test_dev_gold_is_view(tmp_path):
    """Dev mode: gold transform is a VIEW, not a materialized table."""
    dest_path = _run_with_transforms(tmp_path, mode="dev")

    con = duckdb.connect(str(dest_path))
    result = con.execute(
        "SELECT table_type FROM information_schema.tables "
        "WHERE table_schema='gold' AND table_name='customer_summary'"
    ).fetchone()
    con.close()

    assert result is not None
    assert result[0] == "VIEW"


# --- Task 4: row_limit for test mode ---


def test_test_mode_with_row_limit(tmp_path):
    """Test mode with row_limit: extracts at most N rows."""
    import shutil

    from feather.config import load_config
    from feather.pipeline import run_all

    src_db = tmp_path / "sample_erp.duckdb"
    shutil.copy2(FIXTURES_DIR / "sample_erp.duckdb", src_db)

    dest_path = tmp_path / "output.duckdb"
    config = {
        "source": {"type": "duckdb", "path": str(src_db)},
        "destination": {"path": str(dest_path)},
        "mode": "test",
        "defaults": {"row_limit": 2},
        "tables": [
            {
                "name": "customers",
                "source_table": "erp.customers",
                "strategy": "full",
                "target_table": "bronze.customers",
            },
        ],
    }
    config_path = tmp_path / "feather.yaml"
    config_path.write_text(yaml.dump(config, default_flow_style=False))

    cfg = load_config(config_path)
    results = run_all(cfg, config_path)

    assert results[0].status == "success"
    assert results[0].rows_loaded <= 2

    con = duckdb.connect(str(dest_path))
    count = con.execute("SELECT COUNT(*) FROM bronze.customers").fetchone()[0]
    con.close()
    assert count <= 2


def test_dev_mode_ignores_row_limit(tmp_path):
    """Dev mode ignores row_limit even if set."""
    import shutil

    from feather.config import load_config
    from feather.pipeline import run_all

    src_db = tmp_path / "sample_erp.duckdb"
    shutil.copy2(FIXTURES_DIR / "sample_erp.duckdb", src_db)

    dest_path = tmp_path / "output.duckdb"
    config = {
        "source": {"type": "duckdb", "path": str(src_db)},
        "destination": {"path": str(dest_path)},
        "mode": "dev",
        "defaults": {"row_limit": 2},
        "tables": [
            {
                "name": "customers",
                "source_table": "erp.customers",
                "strategy": "full",
                "target_table": "bronze.customers",
            },
        ],
    }
    config_path = tmp_path / "feather.yaml"
    config_path.write_text(yaml.dump(config, default_flow_style=False))

    cfg = load_config(config_path)
    results = run_all(cfg, config_path)

    assert results[0].status == "success"
    # sample_erp has 4 customers — dev should get all of them
    assert results[0].rows_loaded > 2


# --- Task 6: CLI + env var mode override E2E ---


def test_cli_mode_overrides_yaml(tmp_path):
    """--mode prod CLI flag overrides mode: dev in YAML."""
    _, results, dest_path = _run_pipeline(tmp_path, mode="dev")
    # Dev mode: data in bronze
    con = duckdb.connect(str(dest_path))
    bronze_count = con.execute("SELECT COUNT(*) FROM bronze.customers").fetchone()[0]
    con.close()
    assert bronze_count > 0

    # Now re-run with mode_override=prod — should go to silver
    import shutil

    from feather.config import load_config
    from feather.pipeline import run_all

    tmp2 = tmp_path / "prod_run"
    tmp2.mkdir()
    src_db = tmp2 / "sample_erp.duckdb"
    shutil.copy2(FIXTURES_DIR / "sample_erp.duckdb", src_db)

    dest_path2 = tmp2 / "output.duckdb"
    config = {
        "source": {"type": "duckdb", "path": str(src_db)},
        "destination": {"path": str(dest_path2)},
        "mode": "dev",  # YAML says dev
        "tables": [
            {
                "name": "customers",
                "source_table": "erp.customers",
                "strategy": "full",
            },
        ],
    }
    config_path = tmp2 / "feather.yaml"
    config_path.write_text(yaml.dump(config, default_flow_style=False))

    cfg = load_config(config_path, mode_override="prod")  # CLI says prod
    assert cfg.mode == "prod"
    run_all(cfg, config_path)

    con = duckdb.connect(str(dest_path2))
    silver_count = con.execute("SELECT COUNT(*) FROM silver.customers").fetchone()[0]
    con.close()
    assert silver_count > 0


def test_cli_mode_flag_via_runner(tmp_path):
    """--mode prod CLI flag exercises the actual Typer CLI path (Truth #7)."""
    import shutil

    from typer.testing import CliRunner

    from feather.cli import app

    src_db = tmp_path / "sample_erp.duckdb"
    shutil.copy2(FIXTURES_DIR / "sample_erp.duckdb", src_db)

    dest_path = tmp_path / "output.duckdb"
    config = {
        "source": {"type": "duckdb", "path": str(src_db)},
        "destination": {"path": str(dest_path)},
        "mode": "dev",  # YAML says dev
        "tables": [
            {
                "name": "customers",
                "source_table": "erp.customers",
                "strategy": "full",
            },
        ],
    }
    config_path = tmp_path / "feather.yaml"
    config_path.write_text(yaml.dump(config, default_flow_style=False))

    runner = CliRunner()
    result = runner.invoke(app, ["run", "--config", str(config_path), "--mode", "prod"])
    assert result.exit_code == 0

    # --mode prod should land data in silver, not bronze
    con = duckdb.connect(str(dest_path))
    silver_count = con.execute("SELECT COUNT(*) FROM silver.customers").fetchone()[0]
    con.close()
    assert silver_count > 0


def test_env_var_overrides_yaml(tmp_path, monkeypatch):
    """FEATHER_MODE=prod env var overrides mode: dev in YAML."""
    import shutil

    from feather.config import load_config
    from feather.pipeline import run_all

    src_db = tmp_path / "sample_erp.duckdb"
    shutil.copy2(FIXTURES_DIR / "sample_erp.duckdb", src_db)

    dest_path = tmp_path / "output.duckdb"
    config = {
        "source": {"type": "duckdb", "path": str(src_db)},
        "destination": {"path": str(dest_path)},
        "mode": "dev",  # YAML says dev
        "tables": [
            {
                "name": "customers",
                "source_table": "erp.customers",
                "strategy": "full",
            },
        ],
    }
    config_path = tmp_path / "feather.yaml"
    config_path.write_text(yaml.dump(config, default_flow_style=False))

    monkeypatch.setenv("FEATHER_MODE", "prod")
    cfg = load_config(config_path)
    assert cfg.mode == "prod"
    run_all(cfg, config_path)

    con = duckdb.connect(str(dest_path))
    silver_count = con.execute("SELECT COUNT(*) FROM silver.customers").fetchone()[0]
    con.close()
    assert silver_count > 0
