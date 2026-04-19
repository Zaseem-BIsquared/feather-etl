"""Workflow stage 13: multi-source — multiple `sources:` entries.

Scenarios here exercise configs with 2+ sources: validation guards,
per-source curation routing, and full end-to-end extraction across
heterogeneous source types.
"""

from __future__ import annotations

import duckdb

from tests.helpers import make_curation_entry, write_curation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_two_fixture_sources(project) -> None:
    """Two DuckDB sources both seeded from the shared client.duckdb fixture.

    Used by the guard tests: they only care that commands *accept* a
    multi-source config, not that the sources have distinct content.
    """
    project.copy_fixture("client.duckdb")
    # Duplicate the fixture under a second name so each `source` entry points
    # at a distinct file on disk.
    import shutil

    shutil.copy2(project.root / "client.duckdb", project.root / "client_b.duckdb")
    project.write_config(
        sources=[
            {"name": "a", "type": "duckdb", "path": str(project.root / "client.duckdb")},
            {"name": "b", "type": "duckdb", "path": str(project.root / "client_b.duckdb")},
        ],
        destination={"path": str(project.root / "out.duckdb")},
    )
    write_curation(
        project.root,
        [make_curation_entry("a", "icube.InventoryGroup", "ig")],
    )


def _setup_multi_source_project(project) -> None:
    """Create a project with 2 DuckDB sources + curation.json (3 include + 1 exclude).

    - Source A (`erp`): `erp.orders` (3 rows), `erp.customers` (2 rows).
    - Source B (`inventory`): `inv.products` (2 rows).
    - curation.json routes the 3 tables via `include` entries (aliased
      `orders`/`customers`/`products`) and marks a non-existent
      `erp.audit_log` as `exclude` (preserved from the original test for
      curation-parser coverage).
    """
    # Source A: ERP with orders and customers.
    # Use distinct file names to avoid DuckDB catalog/schema name collision
    # (e.g. erp.duckdb + CREATE SCHEMA erp is ambiguous in newer DuckDB).
    src_a = project.root / "erp_source.duckdb"
    con = duckdb.connect(str(src_a))
    con.execute("CREATE SCHEMA erp")
    con.execute("CREATE TABLE erp.orders (id INT, amount DOUBLE)")
    con.execute("INSERT INTO erp.orders VALUES (1, 100.0), (2, 200.0), (3, 300.0)")
    con.execute("CREATE TABLE erp.customers (id INT, name VARCHAR)")
    con.execute("INSERT INTO erp.customers VALUES (1, 'Alice'), (2, 'Bob')")
    con.close()

    # Source B: inventory with products.
    src_b = project.root / "inventory_source.duckdb"
    con = duckdb.connect(str(src_b))
    con.execute("CREATE SCHEMA inv")
    con.execute("CREATE TABLE inv.products (id INT, sku VARCHAR, price DOUBLE)")
    con.execute(
        "INSERT INTO inv.products VALUES (1, 'SKU001', 9.99), (2, 'SKU002', 19.99)"
    )
    con.close()

    project.write_config(
        sources=[
            {"type": "duckdb", "name": "erp", "path": str(src_a)},
            {"type": "duckdb", "name": "inventory", "path": str(src_b)},
        ],
        destination={"path": str(project.data_db_path)},
    )

    entries = [
        make_curation_entry("erp", "erp.orders", "orders"),
        make_curation_entry("erp", "erp.customers", "customers"),
        make_curation_entry("inventory", "inv.products", "products"),
        # Exclude entry: make_curation_entry hardcodes decision="include",
        # so this one is built manually to preserve the original test's
        # curation-parser coverage.
        {
            "source_db": "erp",
            "source_table": "erp.audit_log",
            "decision": "exclude",
            "table_type": "audit",
            "group": "erp",
            "alias": None,
            "classification_notes": None,
            "strategy": None,
            "primary_key": None,
            "timestamp": None,
            "grain": None,
            "scd": None,
            "mapping": None,
            "dq_policy": None,
            "load_contract": None,
            "reason": "not needed",
        },
    ]
    write_curation(project.root, entries)


# ---------------------------------------------------------------------------
# Validation guards — multi-source configs are accepted by all commands
# (the old single-source guard was removed in issue #8).
# ---------------------------------------------------------------------------


def test_validate_accepts_multi_source(project, cli):
    _write_two_fixture_sources(project)
    r = cli("validate")
    assert "single-source" not in r.output
    assert r.exit_code in (0, 2)  # 0=all connected, 2=connection failure


def test_run_accepts_multi_source(project, cli):
    _write_two_fixture_sources(project)
    r = cli("run")
    assert "single-source" not in r.output


def test_setup_accepts_multi_source(project, cli):
    _write_two_fixture_sources(project)
    r = cli("setup")
    assert "single-source" not in r.output
    assert r.exit_code == 0


def test_status_accepts_multi_source(project, cli):
    _write_two_fixture_sources(project)
    r = cli("status")
    assert "single-source" not in r.output


def test_history_accepts_multi_source(project, cli):
    _write_two_fixture_sources(project)
    r = cli("history")
    assert "single-source" not in r.output


# ---------------------------------------------------------------------------
# Full end-to-end extraction across two heterogeneous DuckDB sources.
# ---------------------------------------------------------------------------


def test_feather_run_extracts_from_multiple_sources(project, cli, monkeypatch):
    """feather run extracts tables from 2 DuckDB sources via curation.json."""
    monkeypatch.chdir(project.root)
    _setup_multi_source_project(project)

    result = cli("run")
    assert result.exit_code == 0, f"stdout: {result.stdout}"

    # Verify data landed in bronze.
    rows = project.query(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'bronze'"
    )
    tables = [r[0] for r in rows]

    assert "erp_orders" in tables
    assert "erp_customers" in tables
    assert "inventory_products" in tables
    assert len(tables) == 3  # excluded / non-curated tables not present


def test_row_counts_correct(project, cli, monkeypatch):
    """Verify row counts match source data."""
    monkeypatch.chdir(project.root)
    _setup_multi_source_project(project)
    cli("run")

    orders = project.query("SELECT COUNT(*) FROM bronze.erp_orders")[0][0]
    customers = project.query("SELECT COUNT(*) FROM bronze.erp_customers")[0][0]
    products = project.query("SELECT COUNT(*) FROM bronze.inventory_products")[0][0]

    assert orders == 3
    assert customers == 2
    assert products == 2


def test_table_filter_works_with_bronze_name(project, cli, monkeypatch):
    """--table flag filters by curation-derived bronze name."""
    monkeypatch.chdir(project.root)
    _setup_multi_source_project(project)

    result = cli("run", "--table", "erp_orders")
    assert result.exit_code == 0

    rows = project.query(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'bronze'"
    )
    tables = [r[0] for r in rows]

    assert "erp_orders" in tables
    assert "erp_customers" not in tables  # not extracted — filtered out
