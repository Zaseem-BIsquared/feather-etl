"""Workflow stage 07: transforms — silver views, gold materialization via CLI.

Scenarios here exercise `feather setup` with transforms configured: the
setup command reads `transforms/*.sql`, discovers the DAG, and persists
silver views + gold materialized tables.

This file currently contains only the CLI-invoking transform tests;
integration-level transform tests (DAG execution without CLI) live in
tests/integration/test_transforms.py after Wave C.
"""

from __future__ import annotations

from pathlib import Path

import duckdb


def _write_sql(base: Path, schema: str, name: str, content: str) -> Path:
    """Write a .sql file under base/transforms/{schema}/{name}.sql."""
    d = base / "transforms" / schema
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.sql"
    p.write_text(content)
    return p


def test_setup_creates_transforms(project, cli):
    source_db = project.root / "source.duckdb"
    con = duckdb.connect(str(source_db))
    con.execute("CREATE SCHEMA IF NOT EXISTS erp")
    con.execute("CREATE TABLE erp.employees (id INT, name VARCHAR)")
    con.execute("INSERT INTO erp.employees VALUES (1, 'Alice'), (2, 'Bob')")
    con.close()

    con = duckdb.connect(str(project.data_db_path))
    con.execute("CREATE SCHEMA IF NOT EXISTS bronze")
    con.execute("CREATE TABLE bronze.src_employees (id INT, name VARCHAR)")
    con.execute("INSERT INTO bronze.src_employees VALUES (1, 'Alice'), (2, 'Bob')")
    con.close()

    project.write_config(
        sources=[{"type": "duckdb", "name": "src", "path": str(source_db)}],
        destination={"path": str(project.data_db_path)},
    )
    project.write_curation([("src", "erp.employees", "employees")])

    _write_sql(
        project.root,
        "silver",
        "emp_clean",
        "SELECT id, name AS employee_name FROM bronze.src_employees",
    )

    result = cli("setup")

    assert result.exit_code == 0
    assert "Transforms applied" in result.output
    assert "1 silver view(s)" in result.output


def test_setup_no_transforms_dir_ok(project, cli):
    source_db = project.root / "source.duckdb"
    con = duckdb.connect(str(source_db))
    con.execute("CREATE SCHEMA IF NOT EXISTS erp")
    con.execute("CREATE TABLE erp.employees (id INT, name VARCHAR)")
    con.close()

    project.write_config(
        sources=[{"type": "duckdb", "name": "src", "path": str(source_db)}],
        destination={"path": str(project.data_db_path)},
    )
    project.write_curation([("src", "erp.employees", "employees")])

    result = cli("setup")

    assert result.exit_code == 0
    assert "Transforms applied" not in result.output
