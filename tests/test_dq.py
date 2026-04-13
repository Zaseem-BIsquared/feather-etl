"""Tests for data quality checks (V9)."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from feather_etl.dq import run_dq_checks


@pytest.fixture
def dq_db(tmp_path: Path):
    """Create a temp DuckDB with test data for DQ checks."""
    db_path = tmp_path / "test.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute("CREATE SCHEMA IF NOT EXISTS bronze")
    con.execute("""
        CREATE TABLE bronze.orders (
            order_id INTEGER,
            customer_code VARCHAR,
            amount DOUBLE
        )
    """)
    con.execute("""
        INSERT INTO bronze.orders VALUES
        (1, 'C001', 100.0),
        (2, 'C002', 200.0),
        (3, NULL, 300.0),
        (4, 'C001', 100.0),
        (4, 'C001', 100.0)
    """)
    con.close()
    return db_path


class TestNotNull:
    def test_not_null_fails_on_nulls(self, dq_db: Path):
        con = duckdb.connect(str(dq_db))
        results = run_dq_checks(
            con,
            "orders",
            "bronze.orders",
            {"not_null": ["customer_code"]},
            "run_1",
        )
        con.close()
        not_null = [r for r in results if r.check_type == "not_null"]
        assert len(not_null) == 1
        assert not_null[0].result == "fail"
        assert "1" in not_null[0].details  # 1 NULL row

    def test_not_null_passes_on_clean_column(self, dq_db: Path):
        con = duckdb.connect(str(dq_db))
        results = run_dq_checks(
            con,
            "orders",
            "bronze.orders",
            {"not_null": ["order_id"]},
            "run_1",
        )
        con.close()
        not_null = [r for r in results if r.check_type == "not_null"]
        assert len(not_null) == 1
        assert not_null[0].result == "pass"


class TestUnique:
    def test_unique_fails_on_duplicates(self, dq_db: Path):
        con = duckdb.connect(str(dq_db))
        results = run_dq_checks(
            con,
            "orders",
            "bronze.orders",
            {"unique": ["order_id"]},
            "run_1",
        )
        con.close()
        unique = [r for r in results if r.check_type == "unique"]
        assert len(unique) == 1
        assert unique[0].result == "fail"

    def test_unique_passes_on_unique_column(self, tmp_path: Path):
        db_path = tmp_path / "unique.duckdb"
        con = duckdb.connect(str(db_path))
        con.execute("CREATE SCHEMA IF NOT EXISTS bronze")
        con.execute("CREATE TABLE bronze.items (id INTEGER, name VARCHAR)")
        con.execute("INSERT INTO bronze.items VALUES (1, 'A'), (2, 'B'), (3, 'C')")
        results = run_dq_checks(
            con,
            "items",
            "bronze.items",
            {"unique": ["id"]},
            "run_1",
        )
        con.close()
        unique = [r for r in results if r.check_type == "unique"]
        assert len(unique) == 1
        assert unique[0].result == "pass"


class TestRowCount:
    def test_row_count_always_runs(self, dq_db: Path):
        """row_count runs even with no quality_checks configured."""
        con = duckdb.connect(str(dq_db))
        results = run_dq_checks(con, "orders", "bronze.orders", None, "run_1")
        con.close()
        rc = [r for r in results if r.check_type == "row_count"]
        assert len(rc) == 1
        assert rc[0].result == "pass"
        assert "5" in rc[0].details

    def test_row_count_warns_on_zero(self, tmp_path: Path):
        db_path = tmp_path / "empty.duckdb"
        con = duckdb.connect(str(db_path))
        con.execute("CREATE SCHEMA IF NOT EXISTS bronze")
        con.execute("CREATE TABLE bronze.empty_table (id INTEGER)")
        results = run_dq_checks(con, "empty_table", "bronze.empty_table", None, "run_1")
        con.close()
        rc = [r for r in results if r.check_type == "row_count"]
        assert len(rc) == 1
        assert rc[0].result == "warn"


class TestDuplicate:
    def test_config_driven_duplicate_detects_exact_rows(self, dq_db: Path):
        """quality_checks: {duplicate: true} detects exact duplicate rows."""
        con = duckdb.connect(str(dq_db))
        results = run_dq_checks(
            con,
            "orders",
            "bronze.orders",
            {"duplicate": True},
            "run_1",
        )
        con.close()
        dup = [r for r in results if r.check_type == "duplicate"]
        assert len(dup) == 1
        assert dup[0].result == "fail"
        assert "exact duplicate" in dup[0].details

    def test_pk_based_duplicate_detects_pk_duplicates(self, dq_db: Path):
        con = duckdb.connect(str(dq_db))
        results = run_dq_checks(
            con,
            "orders",
            "bronze.orders",
            {},
            "run_1",
            primary_key=["order_id"],
        )
        con.close()
        dup = [r for r in results if r.check_type == "duplicate"]
        assert len(dup) == 1
        assert dup[0].result == "fail"

    def test_no_duplicate_on_unique_data(self, tmp_path: Path):
        db_path = tmp_path / "unique.duckdb"
        con = duckdb.connect(str(db_path))
        con.execute("CREATE SCHEMA IF NOT EXISTS bronze")
        con.execute("CREATE TABLE bronze.clean (id INTEGER, name VARCHAR)")
        con.execute("INSERT INTO bronze.clean VALUES (1, 'A'), (2, 'B'), (3, 'C')")
        results = run_dq_checks(
            con,
            "clean",
            "bronze.clean",
            {},
            "run_1",
            primary_key=["id"],
        )
        con.close()
        dup = [r for r in results if r.check_type == "duplicate"]
        assert len(dup) == 1
        assert dup[0].result == "pass"


class TestPipelineIntegration:
    def test_dq_results_stored_in_state(self, tmp_path: Path):
        """DQ results are recorded in _dq_results after a run."""
        import shutil
        import yaml

        from tests.conftest import FIXTURES_DIR
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_table
        from feather_etl.state import StateManager

        client_db = tmp_path / "client.duckdb"
        shutil.copy2(FIXTURES_DIR / "sample_erp.duckdb", client_db)
        config = {
            "source": {"type": "duckdb", "path": str(client_db)},
            "destination": {"path": str(tmp_path / "feather_data.duckdb")},
            "tables": [
                {
                    "name": "customers",
                    "source_table": "erp.customers",
                    "target_table": "bronze.customers",
                    "strategy": "full",
                    "quality_checks": {"not_null": ["name"]},
                }
            ],
        }
        (tmp_path / "feather.yaml").write_text(yaml.dump(config))
        cfg = load_config(tmp_path / "feather.yaml")

        result = run_table(cfg, cfg.tables[0], tmp_path)
        assert result.status == "success"

        # Check _dq_results has entries
        sm = StateManager(tmp_path / "feather_state.duckdb")
        con = sm._connect()
        rows = con.execute(
            "SELECT * FROM _dq_results WHERE table_name = 'customers'"
        ).fetchall()
        con.close()
        # Should have at least row_count + not_null checks
        assert len(rows) >= 2

    def test_dq_failure_does_not_block_pipeline(self, tmp_path: Path):
        """Pipeline continues even when DQ check fails."""
        import shutil
        import yaml

        from tests.conftest import FIXTURES_DIR
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_table

        client_db = tmp_path / "client.duckdb"
        shutil.copy2(FIXTURES_DIR / "sample_erp.duckdb", client_db)
        config = {
            "source": {"type": "duckdb", "path": str(client_db)},
            "destination": {"path": str(tmp_path / "feather_data.duckdb")},
            "tables": [
                {
                    "name": "customers",
                    "source_table": "erp.customers",
                    "target_table": "bronze.customers",
                    "strategy": "full",
                    # name column has some NULLs in sample_erp — force a check on id
                    # that will pass, confirming pipeline completes
                    "quality_checks": {"unique": ["name"]},
                }
            ],
        }
        (tmp_path / "feather.yaml").write_text(yaml.dump(config))
        cfg = load_config(tmp_path / "feather.yaml")

        result = run_table(cfg, cfg.tables[0], tmp_path)
        # Pipeline still succeeds even though unique check may fail
        assert result.status == "success"
