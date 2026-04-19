"""Workflow stage 18: non-default source types — end-to-end via CLI.

Scenarios here prove a source type works across the full validate-setup-run
cycle. They deliberately exercise the CLI (not a direct Python API call) to
catch wiring issues between the thin commands/ wrappers and the pure-core
modules.
"""

from __future__ import annotations

from tests.helpers import make_curation_entry, write_curation


def test_sqlite_source_validate_setup_run(project, cli):
    """S17: a SQLite source passes validate, setup, and run with 3/3 tables.

    The fixture `sample_erp.sqlite` contains three tables: orders, customers,
    products. After `feather run`, the destination DuckDB should have three
    populated bronze.* tables.
    """
    # Arrange.
    project.copy_fixture("sample_erp.sqlite")
    project.write_config(
        sources=[{"type": "sqlite", "name": "erp", "path": "./sample_erp.sqlite"}],
        destination={"path": "./feather_data.duckdb"},
    )
    write_curation(
        project.root,
        [
            make_curation_entry("erp", "orders", "orders"),
            make_curation_entry("erp", "customers", "customers"),
            make_curation_entry("erp", "products", "products"),
        ],
    )

    # Act: validate.
    validate_result = cli("validate")
    assert validate_result.exit_code == 0, validate_result.output
    # Hands_on S17 asserts "3 table" appears — CLI prints a count summary.
    assert "3 table" in validate_result.output, validate_result.output

    # Act: setup (creates state DB + destination schemas).
    setup_result = cli("setup")
    assert setup_result.exit_code == 0, setup_result.output

    # Act: run.
    run_result = cli("run")
    assert run_result.exit_code == 0, run_result.output
    assert "3/3" in run_result.output, run_result.output

    # Assert: destination has three bronze tables with data.
    for alias in ("orders", "customers", "products"):
        rows = project.query(f"SELECT count(*) FROM bronze.erp_{alias}")
        assert rows[0][0] > 0, f"bronze.erp_{alias} is empty"
