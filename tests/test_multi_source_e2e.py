"""End-to-end test: multi-source extraction via curation.json."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import yaml

from feather_etl.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def _setup_multi_source_project(tmp_path: Path) -> Path:
    """Create a project with 2 DuckDB sources + curation.json."""
    # Source A: ERP with orders and customers
    # Use distinct file names to avoid DuckDB catalog/schema name collision
    # (e.g. erp.duckdb + CREATE SCHEMA erp is ambiguous in newer DuckDB).
    src_a = tmp_path / "erp_source.duckdb"
    con = duckdb.connect(str(src_a))
    con.execute("CREATE SCHEMA erp")
    con.execute("CREATE TABLE erp.orders (id INT, amount DOUBLE)")
    con.execute("INSERT INTO erp.orders VALUES (1, 100.0), (2, 200.0), (3, 300.0)")
    con.execute("CREATE TABLE erp.customers (id INT, name VARCHAR)")
    con.execute("INSERT INTO erp.customers VALUES (1, 'Alice'), (2, 'Bob')")
    con.close()

    # Source B: inventory with products
    src_b = tmp_path / "inventory_source.duckdb"
    con = duckdb.connect(str(src_b))
    con.execute("CREATE SCHEMA inv")
    con.execute("CREATE TABLE inv.products (id INT, sku VARCHAR, price DOUBLE)")
    con.execute(
        "INSERT INTO inv.products VALUES (1, 'SKU001', 9.99), (2, 'SKU002', 19.99)"
    )
    con.close()

    # feather.yaml — two sources, no tables
    config = {
        "sources": [
            {"type": "duckdb", "name": "erp", "path": str(src_a)},
            {"type": "duckdb", "name": "inventory", "path": str(src_b)},
        ],
        "destination": {"path": str(tmp_path / "feather_data.duckdb")},
    }
    config_file = tmp_path / "feather.yaml"
    config_file.write_text(yaml.dump(config, default_flow_style=False))

    # discovery/curation.json — 3 include entries across 2 sources
    discovery_dir = tmp_path / "discovery"
    discovery_dir.mkdir()
    curation = {
        "version": 2,
        "updated_at": "2026-04-18T00:00:00Z",
        "notes": "test",
        "source_systems": {},
        "policies": {"data_quality": {"default": "flag", "escalations": []}},
        "tables": [
            {
                "source_db": "erp",
                "source_table": "erp.orders",
                "decision": "include",
                "table_type": "fact",
                "group": "erp",
                "alias": "orders",
                "classification_notes": None,
                "strategy": "full",
                "primary_key": ["id"],
                "timestamp": None,
                "grain": "one row per order",
                "scd": None,
                "mapping": None,
                "dq_policy": None,
                "load_contract": None,
                "reason": "test",
            },
            {
                "source_db": "erp",
                "source_table": "erp.customers",
                "decision": "include",
                "table_type": "dimension",
                "group": "erp",
                "alias": "customers",
                "classification_notes": None,
                "strategy": "full",
                "primary_key": ["id"],
                "timestamp": None,
                "grain": None,
                "scd": None,
                "mapping": None,
                "dq_policy": None,
                "load_contract": None,
                "reason": "test",
            },
            {
                "source_db": "inventory",
                "source_table": "inv.products",
                "decision": "include",
                "table_type": "dimension",
                "group": "inventory",
                "alias": "products",
                "classification_notes": None,
                "strategy": "full",
                "primary_key": ["id"],
                "timestamp": None,
                "grain": None,
                "scd": None,
                "mapping": None,
                "dq_policy": None,
                "load_contract": None,
                "reason": "test",
            },
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
        ],
    }
    (discovery_dir / "curation.json").write_text(json.dumps(curation))

    return config_file


class TestMultiSourceE2E:
    def test_feather_run_extracts_from_multiple_sources(
        self, tmp_path: Path, monkeypatch
    ):
        """feather run extracts tables from 2 DuckDB sources via curation.json."""
        monkeypatch.chdir(tmp_path)
        config_file = _setup_multi_source_project(tmp_path)

        result = runner.invoke(app, ["run", "--config", str(config_file)])
        assert result.exit_code == 0, f"stdout: {result.stdout}"

        # Verify data landed in bronze
        dest = duckdb.connect(str(tmp_path / "feather_data.duckdb"), read_only=True)
        tables = [
            row[0]
            for row in dest.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'bronze'"
            ).fetchall()
        ]
        dest.close()

        assert "erp_orders" in tables
        assert "erp_customers" in tables
        assert "inventory_products" in tables
        assert len(tables) == 3  # excluded table not present

    def test_row_counts_correct(self, tmp_path: Path, monkeypatch):
        """Verify row counts match source data."""
        monkeypatch.chdir(tmp_path)
        config_file = _setup_multi_source_project(tmp_path)
        runner.invoke(app, ["run", "--config", str(config_file)])

        dest = duckdb.connect(str(tmp_path / "feather_data.duckdb"), read_only=True)
        orders = dest.execute("SELECT COUNT(*) FROM bronze.erp_orders").fetchone()[0]
        customers = dest.execute(
            "SELECT COUNT(*) FROM bronze.erp_customers"
        ).fetchone()[0]
        products = dest.execute(
            "SELECT COUNT(*) FROM bronze.inventory_products"
        ).fetchone()[0]
        dest.close()

        assert orders == 3
        assert customers == 2
        assert products == 2

    def test_table_filter_works_with_bronze_name(self, tmp_path: Path, monkeypatch):
        """--table flag filters by curation-derived bronze name."""
        monkeypatch.chdir(tmp_path)
        config_file = _setup_multi_source_project(tmp_path)

        result = runner.invoke(
            app, ["run", "--config", str(config_file), "--table", "erp_orders"]
        )
        assert result.exit_code == 0

        dest = duckdb.connect(str(tmp_path / "feather_data.duckdb"), read_only=True)
        tables = [
            row[0]
            for row in dest.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'bronze'"
            ).fetchall()
        ]
        dest.close()

        assert "erp_orders" in tables
        assert "erp_customers" not in tables  # not extracted — filtered out
