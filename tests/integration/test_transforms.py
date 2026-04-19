"""Integration: transforms + pipeline — rebuild_materialized_gold invoked
from pipeline.run_all.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import yaml

from feather_etl.config import load_config
from feather_etl.pipeline import run_all
from tests.helpers import make_curation_entry, write_curation


def _write_sql(base: Path, schema: str, name: str, content: str) -> Path:
    """Write a .sql file under base/transforms/{schema}/{name}.sql."""
    d = base / "transforms" / schema
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.sql"
    p.write_text(content)
    return p


def test_run_rebuilds_materialized_gold(tmp_path: Path):
    source_db = tmp_path / "source.duckdb"
    con = duckdb.connect(str(source_db))
    con.execute("CREATE SCHEMA IF NOT EXISTS erp")
    con.execute("CREATE TABLE erp.employees (id INT, name VARCHAR)")
    con.execute("INSERT INTO erp.employees VALUES (1, 'Alice'), (2, 'Bob')")
    con.close()

    dest_db = tmp_path / "feather_data.duckdb"
    config = {
        "sources": [{"type": "duckdb", "name": "src", "path": str(source_db)}],
        "destination": {"path": str(dest_db)},
    }
    config_file = tmp_path / "feather.yaml"
    config_file.write_text(yaml.dump(config))
    write_curation(
        tmp_path,
        [make_curation_entry("src", "erp.employees", "employees")],
    )

    _write_sql(
        tmp_path,
        "silver",
        "emp_clean",
        "SELECT id, name AS employee_name FROM bronze.src_employees",
    )
    _write_sql(
        tmp_path,
        "gold",
        "emp_snapshot",
        (
            "-- depends_on: silver.emp_clean\n"
            "-- materialized: true\n"
            "SELECT * FROM silver.emp_clean"
        ),
    )

    cfg = load_config(config_file)
    results = run_all(cfg, config_file)

    assert any(r.status == "success" for r in results)

    con = duckdb.connect(str(dest_db))
    gold_rows = con.execute("SELECT * FROM gold.emp_snapshot").fetchall()
    assert len(gold_rows) == 2
    con.close()


def test_run_mode_switch_rematerializes_gold(tmp_path: Path):
    source_db = tmp_path / "source.duckdb"
    con = duckdb.connect(str(source_db))
    con.execute("CREATE SCHEMA IF NOT EXISTS erp")
    con.execute("CREATE TABLE erp.employees (id INT, name VARCHAR)")
    con.execute("INSERT INTO erp.employees VALUES (1, 'Alice'), (2, 'Bob')")
    con.close()

    dest_db = tmp_path / "feather_data.duckdb"
    config = {
        "sources": [{"type": "duckdb", "name": "src", "path": str(source_db)}],
        "destination": {"path": str(dest_db)},
        "mode": "dev",
    }
    config_file = tmp_path / "feather.yaml"
    config_file.write_text(yaml.dump(config))
    write_curation(
        tmp_path,
        [make_curation_entry("src", "erp.employees", "employees")],
    )

    _write_sql(
        tmp_path,
        "silver",
        "emp_clean",
        "SELECT id, name AS employee_name FROM bronze.src_employees",
    )
    _write_sql(
        tmp_path,
        "gold",
        "emp_snapshot",
        (
            "-- depends_on: silver.emp_clean\n"
            "-- materialized: true\n"
            "SELECT * FROM silver.emp_clean"
        ),
    )

    cfg_dev = load_config(config_file)
    results1 = run_all(cfg_dev, config_file)
    assert any(r.status == "success" for r in results1)

    con = duckdb.connect(str(dest_db))
    gold_type_dev = con.execute(
        "SELECT table_type FROM information_schema.tables "
        "WHERE table_schema='gold' AND table_name='emp_snapshot'"
    ).fetchone()[0]
    con.close()
    assert gold_type_dev == "VIEW"

    config["mode"] = "prod"
    config_file.write_text(yaml.dump(config))
    cfg_prod = load_config(config_file)
    results2 = run_all(cfg_prod, config_file)
    assert all(r.status == "skipped" for r in results2)

    con = duckdb.connect(str(dest_db))
    gold_type_prod = con.execute(
        "SELECT table_type FROM information_schema.tables "
        "WHERE table_schema='gold' AND table_name='emp_snapshot'"
    ).fetchone()[0]
    con.close()
    assert gold_type_prod == "BASE TABLE"


def test_run_no_rebuild_when_all_skipped(tmp_path: Path):
    source_db = tmp_path / "source.duckdb"
    con = duckdb.connect(str(source_db))
    con.execute("CREATE SCHEMA IF NOT EXISTS erp")
    con.execute("CREATE TABLE erp.employees (id INT, name VARCHAR)")
    con.execute("INSERT INTO erp.employees VALUES (1, 'Alice')")
    con.close()

    dest_db = tmp_path / "feather_data.duckdb"
    config = {
        "sources": [{"type": "duckdb", "name": "src", "path": str(source_db)}],
        "destination": {"path": str(dest_db)},
    }
    config_file = tmp_path / "feather.yaml"
    config_file.write_text(yaml.dump(config))
    write_curation(
        tmp_path,
        [make_curation_entry("src", "erp.employees", "employees")],
    )

    _write_sql(
        tmp_path, "gold", "emp_snap", ("-- materialized: true\nSELECT 1 AS val")
    )

    cfg = load_config(config_file)

    results1 = run_all(cfg, config_file)
    assert any(r.status == "success" for r in results1)

    results2 = run_all(cfg, config_file)
    assert all(r.status == "skipped" for r in results2)

    con = duckdb.connect(str(dest_db))
    row = con.execute("SELECT * FROM gold.emp_snap").fetchone()
    assert row is not None
    con.close()
