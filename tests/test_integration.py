"""
Integration tests derived from the hands-on review of Slice 1.

These tests use real DuckDB fixtures (no mocking) and cover:
  - sample_erp fixture (custom synthetic data: erp.orders / customers / products)
  - Icube client fixture edge cases (BLOB cols, spaces in column names, full table set)
  - Known bugs (documented with BUG-N labels matching the review report)
  - UX scenarios (error isolation, idempotency, path resolution, tables/ merge)

When a bug is fixed the corresponding assertion should be INVERTED and the
BUG label removed from the test name.

Fixture layout
--------------
tests/fixtures/sample_erp.duckdb  — synthetic ERP (erp schema, 3 tables, 12 rows)
    erp.orders    5 rows  — order_id, customer_id, order_date, total_amount, status, created_at
    erp.customers 4 rows  — customer_id, name, email, city, credit_limit, created_at
    erp.products  3 rows  — product_id, product_name, category, unit_price, stock_qty
                            row 3: stock_qty IS NULL  (tests NULL pass-through)

tests/fixtures/client.duckdb       — real Icube ERP data (icube schema, 6 tables)
"""

from __future__ import annotations

import shutil
from pathlib import Path

import duckdb
import pytest
import yaml

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_erp_db(tmp_path) -> Path:
    """Copy sample_erp.duckdb to tmp_path."""
    src = FIXTURES_DIR / "sample_erp.duckdb"
    dst = tmp_path / "source.duckdb"
    shutil.copy2(src, dst)
    return dst


@pytest.fixture
def client_db_copy(tmp_path) -> Path:
    """Copy client.duckdb to tmp_path."""
    src = FIXTURES_DIR / "client.duckdb"
    dst = tmp_path / "source.duckdb"
    shutil.copy2(src, dst)
    return dst


def _write_config(tmp_path: Path, source_db: Path, tables: list[dict]) -> Path:
    cfg = {
        "source": {"type": "duckdb", "path": str(source_db)},
        "destination": {"path": str(tmp_path / "feather_data.duckdb")},
        "tables": tables,
    }
    p = tmp_path / "feather.yaml"
    p.write_text(yaml.dump(cfg, default_flow_style=False))
    return p


# ---------------------------------------------------------------------------
# sample_erp fixture — basic correctness
# ---------------------------------------------------------------------------


class TestSampleErpFixture:
    """Tests using the synthetic sample_erp fixture."""

    def test_fixture_has_expected_tables(self, sample_erp_db):
        con = duckdb.connect(str(sample_erp_db), read_only=True)
        tables = {
            (r[0], r[1])
            for r in con.execute(
                "SELECT table_schema, table_name FROM information_schema.tables "
                "WHERE table_schema NOT IN ('information_schema','pg_catalog')"
            ).fetchall()
        }
        con.close()
        assert ("erp", "orders") in tables
        assert ("erp", "customers") in tables
        assert ("erp", "products") in tables

    def test_fixture_row_counts(self, sample_erp_db):
        con = duckdb.connect(str(sample_erp_db), read_only=True)
        assert con.execute("SELECT COUNT(*) FROM erp.orders").fetchone()[0] == 5
        assert con.execute("SELECT COUNT(*) FROM erp.customers").fetchone()[0] == 4
        assert con.execute("SELECT COUNT(*) FROM erp.products").fetchone()[0] == 3
        con.close()

    def test_fixture_null_in_products(self, sample_erp_db):
        """stock_qty is NULL for the 'Service Pack' row — tests NULL pass-through."""
        con = duckdb.connect(str(sample_erp_db), read_only=True)
        row = con.execute(
            "SELECT stock_qty FROM erp.products WHERE product_name = 'Service Pack'"
        ).fetchone()
        con.close()
        assert row is not None
        assert row[0] is None


class TestSampleErpFullPipeline:
    """Full pipeline run against the synthetic sample_erp fixture."""

    @pytest.fixture
    def config(self, sample_erp_db, tmp_path) -> Path:
        return _write_config(
            tmp_path,
            sample_erp_db,
            [
                {
                    "name": "orders",
                    "source_table": "erp.orders",
                    "target_table": "bronze.orders",
                    "strategy": "full",
                },
                {
                    "name": "customers",
                    "source_table": "erp.customers",
                    "target_table": "bronze.customers",
                    "strategy": "full",
                },
                {
                    "name": "products",
                    "source_table": "erp.products",
                    "target_table": "bronze.products",
                    "strategy": "full",
                },
            ],
        )

    def test_run_all_succeeds(self, config):
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_all

        cfg = load_config(config)
        results = run_all(cfg, config)
        assert all(r.status == "success" for r in results)
        assert {r.table_name for r in results} == {"orders", "customers", "products"}

    def test_row_counts_in_bronze(self, config):
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_all

        cfg = load_config(config)
        run_all(cfg, config)

        con = duckdb.connect(str(cfg.destination.path), read_only=True)
        assert con.execute("SELECT COUNT(*) FROM bronze.orders").fetchone()[0] == 5
        assert con.execute("SELECT COUNT(*) FROM bronze.customers").fetchone()[0] == 4
        assert con.execute("SELECT COUNT(*) FROM bronze.products").fetchone()[0] == 3
        con.close()

    def test_null_passthrough(self, config):
        """NULL in source (products.stock_qty) must survive the Arrow round-trip."""
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_all

        cfg = load_config(config)
        run_all(cfg, config)

        con = duckdb.connect(str(cfg.destination.path), read_only=True)
        row = con.execute(
            "SELECT stock_qty FROM bronze.products WHERE product_name = 'Service Pack'"
        ).fetchone()
        con.close()
        assert row is not None, "Service Pack row missing from bronze.products"
        assert row[0] is None, f"Expected NULL stock_qty, got {row[0]!r}"

    def test_etl_metadata_columns_added(self, config):
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_all

        cfg = load_config(config)
        run_all(cfg, config)

        con = duckdb.connect(str(cfg.destination.path), read_only=True)
        cols = {
            r[0]
            for r in con.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'bronze' AND table_name = 'orders'"
            ).fetchall()
        }
        con.close()
        assert "_etl_loaded_at" in cols
        assert "_etl_run_id" in cols

    def test_source_columns_preserved(self, config):
        """All source columns (minus added ETL ones) must appear in bronze."""
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_all

        cfg = load_config(config)
        run_all(cfg, config)

        con = duckdb.connect(str(cfg.destination.path), read_only=True)
        bronze_cols = {
            r[0]
            for r in con.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'bronze' AND table_name = 'orders'"
            ).fetchall()
        }
        con.close()
        expected = {
            "order_id",
            "customer_id",
            "order_date",
            "total_amount",
            "status",
            "created_at",
        }
        assert expected.issubset(bronze_cols)

    def test_idempotency(self, config):
        """Running twice must give same row counts (full swap replaces, not appends)."""
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_all

        cfg = load_config(config)
        run_all(cfg, config)
        run_all(cfg, config)

        con = duckdb.connect(str(cfg.destination.path), read_only=True)
        assert con.execute("SELECT COUNT(*) FROM bronze.orders").fetchone()[0] == 5
        con.close()

    def test_state_records_runs(self, config):
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_all

        cfg = load_config(config)
        run_all(cfg, config)

        state_path = config.parent / "feather_state.duckdb"
        assert state_path.exists()
        con = duckdb.connect(str(state_path), read_only=True)
        runs = con.execute(
            "SELECT table_name, status, rows_loaded FROM _runs ORDER BY table_name"
        ).fetchall()
        con.close()
        run_map = {r[0]: (r[1], r[2]) for r in runs}
        assert run_map["orders"] == ("success", 5)
        assert run_map["customers"] == ("success", 4)
        assert run_map["products"] == ("success", 3)


# ---------------------------------------------------------------------------
# Icube client fixture — edge cases
# ---------------------------------------------------------------------------


class TestClientFixtureEdgeCases:
    def test_salesinvoicemaster_column_with_space(self, client_db_copy, tmp_path):
        """SALESINVOICEMASTER has a column called 'Round Off' (space in name).
        Arrow must preserve it without error or renaming."""
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_all

        config = _write_config(
            tmp_path,
            client_db_copy,
            [
                {
                    "name": "sim",
                    "source_table": "icube.SALESINVOICEMASTER",
                    "target_table": "bronze.sim",
                    "strategy": "full",
                }
            ],
        )
        cfg = load_config(config)
        results = run_all(cfg, config)
        assert results[0].status == "success"

        con = duckdb.connect(str(cfg.destination.path), read_only=True)
        cols = {
            r[0]
            for r in con.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='bronze' AND table_name='sim'"
            ).fetchall()
        }
        con.close()
        assert "Round Off" in cols, "'Round Off' column (space) should be preserved"

    def test_invitem_blob_columns(self, client_db_copy, tmp_path):
        """INVITEM has BLOB columns (IMAGE, DivImage).  Should load without error."""
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_all

        config = _write_config(
            tmp_path,
            client_db_copy,
            [
                {
                    "name": "invitem",
                    "source_table": "icube.INVITEM",
                    "target_table": "bronze.invitem",
                    "strategy": "full",
                }
            ],
        )
        cfg = load_config(config)
        results = run_all(cfg, config)
        assert results[0].status == "success"
        assert results[0].rows_loaded == 1058

    def test_all_six_icube_tables(self, client_db_copy, tmp_path):
        """All six Icube tables load in a single run."""
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_all

        tables = [
            {
                "name": "sales_invoice",
                "source_table": "icube.SALESINVOICE",
                "target_table": "bronze.sales_invoice",
                "strategy": "full",
            },
            {
                "name": "customer_master",
                "source_table": "icube.CUSTOMERMASTER",
                "target_table": "bronze.customer_master",
                "strategy": "full",
            },
            {
                "name": "inventory_group",
                "source_table": "icube.InventoryGroup",
                "target_table": "bronze.inventory_group",
                "strategy": "full",
            },
            {
                "name": "inv_item",
                "source_table": "icube.INVITEM",
                "target_table": "bronze.inv_item",
                "strategy": "full",
            },
            {
                "name": "sales_invoice_master",
                "source_table": "icube.SALESINVOICEMASTER",
                "target_table": "bronze.sales_invoice_master",
                "strategy": "full",
            },
            {
                "name": "employee",
                "source_table": "icube.EmployeeForm",
                "target_table": "bronze.employee",
                "strategy": "full",
            },
        ]
        config = _write_config(tmp_path, client_db_copy, tables)
        cfg = load_config(config)
        results = run_all(cfg, config)

        assert all(r.status == "success" for r in results), [
            (r.table_name, r.error_message) for r in results if r.status != "success"
        ]
        row_map = {r.table_name: r.rows_loaded for r in results}
        assert row_map["sales_invoice"] == 11676
        assert row_map["customer_master"] == 1339
        assert row_map["inventory_group"] == 66
        assert row_map["inv_item"] == 1058
        assert row_map["sales_invoice_master"] == 335
        assert row_map["employee"] == 55

    def test_discover_icube_source(self, client_db_copy):
        """discover() returns all 6 Icube tables with column metadata."""
        from feather_etl.sources.duckdb_file import DuckDBFileSource

        src = DuckDBFileSource(client_db_copy)
        schemas = src.discover()
        names = {s.name for s in schemas}
        assert "icube.SALESINVOICE" in names
        assert "icube.CUSTOMERMASTER" in names
        assert len(schemas) == 6
        # each schema has at least one column
        for s in schemas:
            assert len(s.columns) > 0, f"{s.name} has no columns"


# ---------------------------------------------------------------------------
# Error isolation — a bad table must not stop good tables
# ---------------------------------------------------------------------------


class TestErrorIsolation:
    def test_good_table_succeeds_despite_bad_table(self, sample_erp_db, tmp_path):
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_all

        config = _write_config(
            tmp_path,
            sample_erp_db,
            [
                {
                    "name": "good",
                    "source_table": "erp.orders",
                    "target_table": "bronze.good",
                    "strategy": "full",
                },
                {
                    "name": "bad",
                    "source_table": "erp.NOSUCH",
                    "target_table": "bronze.bad",
                    "strategy": "full",
                },
            ],
        )
        cfg = load_config(config)
        results = run_all(cfg, config)

        good = next(r for r in results if r.table_name == "good")
        bad = next(r for r in results if r.table_name == "bad")
        assert good.status == "success", "good table should succeed"
        assert bad.status == "failure", "bad table should fail"
        assert good.rows_loaded == 5

    def test_failure_error_message_stored_in_state(self, sample_erp_db, tmp_path):
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_all

        config = _write_config(
            tmp_path,
            sample_erp_db,
            [
                {
                    "name": "bad",
                    "source_table": "erp.NOSUCH",
                    "target_table": "bronze.bad",
                    "strategy": "full",
                }
            ],
        )
        cfg = load_config(config)
        run_all(cfg, config)

        state_path = tmp_path / "feather_state.duckdb"
        con = duckdb.connect(str(state_path), read_only=True)
        row = con.execute(
            "SELECT status, error_message FROM _runs WHERE table_name = 'bad'"
        ).fetchone()
        con.close()
        assert row is not None
        assert row[0] == "failure"
        assert row[1] is not None and len(row[1]) > 0, (
            "error_message should be non-empty"
        )

    def test_partial_failure_still_writes_good_table_to_bronze(
        self, sample_erp_db, tmp_path
    ):
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_all

        config = _write_config(
            tmp_path,
            sample_erp_db,
            [
                {
                    "name": "good",
                    "source_table": "erp.orders",
                    "target_table": "bronze.orders",
                    "strategy": "full",
                },
                {
                    "name": "bad",
                    "source_table": "erp.NOSUCH",
                    "target_table": "bronze.bad",
                    "strategy": "full",
                },
            ],
        )
        cfg = load_config(config)
        run_all(cfg, config)

        con = duckdb.connect(str(cfg.destination.path), read_only=True)
        assert con.execute("SELECT COUNT(*) FROM bronze.orders").fetchone()[0] == 5
        tables = {
            r[0]
            for r in con.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='bronze'"
            ).fetchall()
        }
        con.close()
        assert "orders" in tables
        assert "bad" not in tables  # failed table must not appear in bronze


# ---------------------------------------------------------------------------
# Tables/ directory merge
# ---------------------------------------------------------------------------


class TestTablesDirectoryMerge:
    def test_tables_in_subdir_are_discovered(self, sample_erp_db, tmp_path):
        """Tables defined in tables/*.yaml are merged with inline tables."""
        from feather_etl.config import load_config

        tables_dir = tmp_path / "tables"
        tables_dir.mkdir()
        (tables_dir / "sales.yaml").write_text(
            yaml.dump(
                {
                    "tables": [
                        {
                            "name": "orders",
                            "source_table": "erp.orders",
                            "target_table": "bronze.orders",
                            "strategy": "full",
                        }
                    ]
                }
            )
        )
        (tables_dir / "master.yaml").write_text(
            yaml.dump(
                {
                    "tables": [
                        {
                            "name": "customers",
                            "source_table": "erp.customers",
                            "target_table": "bronze.customers",
                            "strategy": "full",
                        }
                    ]
                }
            )
        )
        cfg_dict = {
            "source": {"type": "duckdb", "path": str(sample_erp_db)},
            "destination": {"path": str(tmp_path / "feather_data.duckdb")},
            "tables": [],
        }
        config_path = tmp_path / "feather.yaml"
        config_path.write_text(yaml.dump(cfg_dict))

        cfg = load_config(config_path)
        assert len(cfg.tables) == 2
        names = {t.name for t in cfg.tables}
        assert names == {"orders", "customers"}

    def test_tables_dir_and_inline_combined(self, sample_erp_db, tmp_path):
        """Inline tables + tables/*.yaml tables are all loaded."""
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_all

        tables_dir = tmp_path / "tables"
        tables_dir.mkdir()
        (tables_dir / "extra.yaml").write_text(
            yaml.dump(
                {
                    "tables": [
                        {
                            "name": "products",
                            "source_table": "erp.products",
                            "target_table": "bronze.products",
                            "strategy": "full",
                        }
                    ]
                }
            )
        )
        config = _write_config(
            tmp_path,
            sample_erp_db,
            [
                {
                    "name": "orders",
                    "source_table": "erp.orders",
                    "target_table": "bronze.orders",
                    "strategy": "full",
                }
            ],
        )
        cfg = load_config(config)
        assert len(cfg.tables) == 2

        results = run_all(cfg, config)
        assert all(r.status == "success" for r in results)


# ---------------------------------------------------------------------------
# Validation guards — graduated from TestKnownBugs after fixes
# ---------------------------------------------------------------------------


class TestValidationGuards:
    """Tests that validate catches invalid config before runtime.
    Graduated from TestKnownBugs after BUG-2, BUG-3, BUG-7 fixes."""

    def test_csv_source_validates_with_valid_directory(self, tmp_path):
        """CSV source type with a valid directory passes validation.
        (Graduated from BUG-2: csv is now a registered source type.)"""
        from feather_etl.config import load_config

        csv_dir = tmp_path / "csv_data"
        csv_dir.mkdir()
        (csv_dir / "orders.csv").write_text("id,name\n1,foo\n")
        config_path = tmp_path / "feather.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "source": {"type": "csv", "path": str(csv_dir)},
                    "destination": {"path": str(tmp_path / "data.duckdb")},
                    "tables": [
                        {
                            "name": "t",
                            "source_table": "orders.csv",
                            "target_table": "bronze.t",
                            "strategy": "full",
                        }
                    ],
                }
            )
        )
        cfg = load_config(config_path)
        assert cfg.source.type == "csv"

    def test_csv_source_rejects_file_path(self, tmp_path):
        """CSV source path must be a directory, not a file."""
        from feather_etl.config import load_config

        csv_file = tmp_path / "source.csv"
        csv_file.write_text("id,name\n1,foo\n")
        config_path = tmp_path / "feather.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "source": {"type": "csv", "path": str(csv_file)},
                    "destination": {"path": str(tmp_path / "data.duckdb")},
                    "tables": [
                        {
                            "name": "t",
                            "source_table": "orders.csv",
                            "target_table": "bronze.t",
                            "strategy": "full",
                        }
                    ],
                }
            )
        )
        with pytest.raises(ValueError, match="CSV source path must be a directory"):
            load_config(config_path)

    def test_csv_source_rejects_nonexistent_path(self, tmp_path):
        """CSV source path that doesn't exist at all fails validation."""
        from feather_etl.config import load_config

        config_path = tmp_path / "feather.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "source": {"type": "csv", "path": str(tmp_path / "no_such_dir")},
                    "destination": {"path": str(tmp_path / "data.duckdb")},
                    "tables": [
                        {
                            "name": "t",
                            "source_table": "orders.csv",
                            "target_table": "bronze.t",
                            "strategy": "full",
                        }
                    ],
                }
            )
        )
        with pytest.raises(ValueError, match="CSV source path must be a directory"):
            load_config(config_path)

    def test_missing_source_section_raises_valueerror(self, tmp_path):
        """Missing 'source' section raises ValueError with a clear message.
        (Graduated from BUG-3: previously raised raw KeyError.)"""
        from feather_etl.config import load_config

        config_path = tmp_path / "feather.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "destination": {"path": str(tmp_path / "data.duckdb")},
                    "tables": [],
                }
            )
        )
        with pytest.raises(ValueError, match="Missing required config section"):
            load_config(config_path)

    def test_missing_strategy_field_raises_valueerror(self, sample_erp_db, tmp_path):
        """Missing required table fields raise ValueError with field name.
        (Graduated from BUG-3/BUG-4: previously raised raw KeyError.)"""
        from feather_etl.config import load_config

        cfg_dict = {
            "source": {"type": "duckdb", "path": str(sample_erp_db)},
            "destination": {"path": str(tmp_path / "data.duckdb")},
            "tables": [
                {"name": "t", "source_table": "erp.orders", "target_table": "bronze.t"}
            ],  # strategy missing
        }
        config_path = tmp_path / "feather.yaml"
        config_path.write_text(yaml.dump(cfg_dict))
        with pytest.raises(ValueError, match="missing required field"):
            load_config(config_path)

    def test_target_table_requires_schema_prefix(self, sample_erp_db, tmp_path):
        """target_table without schema prefix (e.g. 'my_table') is rejected.
        (Graduated from BUG-7: previously passed validate, crashed at runtime.)"""
        from feather_etl.config import load_config

        config = _write_config(
            tmp_path,
            sample_erp_db,
            [
                {
                    "name": "t",
                    "source_table": "erp.orders",
                    "target_table": "no_schema_table",
                    "strategy": "full",
                }
            ],
        )
        with pytest.raises(ValueError, match="must include a schema prefix"):
            load_config(config)

    def test_hyphenated_target_table_rejected(self, sample_erp_db, tmp_path):
        """Hyphens in target_table are caught at validate time.
        (Graduated from BUG-7: previously passed validate, crashed at runtime.)"""
        from feather_etl.config import load_config

        config = _write_config(
            tmp_path,
            sample_erp_db,
            [
                {
                    "name": "my-table",
                    "source_table": "erp.orders",
                    "target_table": "bronze.my-table",
                    "strategy": "full",
                }
            ],
        )
        with pytest.raises(ValueError, match="invalid characters"):
            load_config(config)


# ---------------------------------------------------------------------------
# Error isolation (additional graduated tests)
# ---------------------------------------------------------------------------


class TestPipelineReturnsOnFailure:
    """run_all() returns RunResult list (no exception) even when tables fail.
    The CLI layer is responsible for exit codes.
    (Graduated from BUG-5: CLI now exits 1 on failure.)"""

    def test_run_all_returns_results_on_total_failure(self, sample_erp_db, tmp_path):
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_all

        config = _write_config(
            tmp_path,
            sample_erp_db,
            [
                {
                    "name": "bad",
                    "source_table": "erp.NOSUCH",
                    "target_table": "bronze.bad",
                    "strategy": "full",
                }
            ],
        )
        cfg = load_config(config)
        results = run_all(cfg, config)
        assert len(results) == 1
        assert results[0].status == "failure"


# ---------------------------------------------------------------------------
# Known bugs — remaining issues not yet fixed
# ---------------------------------------------------------------------------


class TestKnownBugs:
    # M-6 (strategy dispatch) — deferred to Slice 2
    def test_M6_incremental_strategy_silently_does_full_load(
        self, sample_erp_db, tmp_path
    ):
        """M-6: strategy='incremental' (with timestamp_column) silently does a
        full load instead of incremental extraction.  The validation gap (BUG-8:
        incremental without timestamp_column) is now fixed.  This test documents
        the remaining issue: strategy dispatch is not implemented yet.
        After fix (Slice 2): run should perform actual incremental extraction."""
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_all

        config = _write_config(
            tmp_path,
            sample_erp_db,
            [
                {
                    "name": "orders",
                    "source_table": "erp.orders",
                    "target_table": "bronze.orders",
                    "strategy": "incremental",
                    "timestamp_column": "created_at",
                }
            ],
        )
        cfg = load_config(config)
        results = run_all(cfg, config)
        # Currently succeeds (full load performed silently) — strategy dispatch deferred
        assert results[0].status == "success"
        con = duckdb.connect(str(cfg.destination.path), read_only=True)
        count = con.execute("SELECT COUNT(*) FROM bronze.orders").fetchone()[0]
        con.close()
        assert count == 5  # all 5 rows loaded — full load, not incremental


# ---------------------------------------------------------------------------
# CSV source — full pipeline integration
# ---------------------------------------------------------------------------


def _write_csv_config(tmp_path: Path, csv_dir: Path, tables: list[dict]) -> Path:
    cfg = {
        "source": {"type": "csv", "path": str(csv_dir)},
        "destination": {"path": str(tmp_path / "feather_data.duckdb")},
        "tables": tables,
    }
    p = tmp_path / "feather.yaml"
    p.write_text(yaml.dump(cfg, default_flow_style=False))
    return p


def _write_sqlite_config(tmp_path: Path, sqlite_path: Path, tables: list[dict]) -> Path:
    cfg = {
        "source": {"type": "sqlite", "path": str(sqlite_path)},
        "destination": {"path": str(tmp_path / "feather_data.duckdb")},
        "tables": tables,
    }
    p = tmp_path / "feather.yaml"
    p.write_text(yaml.dump(cfg, default_flow_style=False))
    return p


class TestCsvFullPipeline:
    """Full pipeline run using CSV source."""

    CSV_TABLES = [
        {
            "name": "orders",
            "source_table": "orders.csv",
            "target_table": "bronze.orders",
            "strategy": "full",
        },
        {
            "name": "customers",
            "source_table": "customers.csv",
            "target_table": "bronze.customers",
            "strategy": "full",
        },
        {
            "name": "products",
            "source_table": "products.csv",
            "target_table": "bronze.products",
            "strategy": "full",
        },
    ]

    @pytest.fixture
    def csv_data_dir(self, tmp_path) -> Path:
        src = Path(__file__).parent / "fixtures" / "csv_data"
        dst = tmp_path / "csv_data"
        shutil.copytree(src, dst)
        return dst

    @pytest.fixture
    def config(self, csv_data_dir, tmp_path) -> Path:
        return _write_csv_config(tmp_path, csv_data_dir, self.CSV_TABLES)

    def test_run_all_succeeds(self, config):
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_all

        cfg = load_config(config)
        results = run_all(cfg, config)
        assert all(r.status == "success" for r in results)
        assert {r.table_name for r in results} == {"orders", "customers", "products"}

    def test_row_counts_in_bronze(self, config):
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_all

        cfg = load_config(config)
        run_all(cfg, config)

        con = duckdb.connect(str(cfg.destination.path), read_only=True)
        assert con.execute("SELECT COUNT(*) FROM bronze.orders").fetchone()[0] == 5
        assert con.execute("SELECT COUNT(*) FROM bronze.customers").fetchone()[0] == 4
        assert con.execute("SELECT COUNT(*) FROM bronze.products").fetchone()[0] == 3
        con.close()

    def test_null_passthrough(self, config):
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_all

        cfg = load_config(config)
        run_all(cfg, config)

        con = duckdb.connect(str(cfg.destination.path), read_only=True)
        row = con.execute(
            "SELECT stock_qty FROM bronze.products WHERE product_name = 'Service Pack'"
        ).fetchone()
        con.close()
        assert row is not None
        assert row[0] is None

    def test_etl_metadata_columns(self, config):
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_all

        cfg = load_config(config)
        run_all(cfg, config)

        con = duckdb.connect(str(cfg.destination.path), read_only=True)
        cols = {
            r[0]
            for r in con.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'bronze' AND table_name = 'orders'"
            ).fetchall()
        }
        con.close()
        assert "_etl_loaded_at" in cols
        assert "_etl_run_id" in cols


# ---------------------------------------------------------------------------
# SQLite source — full pipeline integration
# ---------------------------------------------------------------------------


class TestSqliteFullPipeline:
    """Full pipeline run using SQLite source."""

    SQLITE_TABLES = [
        {
            "name": "orders",
            "source_table": "orders",
            "target_table": "bronze.orders",
            "strategy": "full",
        },
        {
            "name": "customers",
            "source_table": "customers",
            "target_table": "bronze.customers",
            "strategy": "full",
        },
        {
            "name": "products",
            "source_table": "products",
            "target_table": "bronze.products",
            "strategy": "full",
        },
    ]

    @pytest.fixture
    def sqlite_db(self, tmp_path) -> Path:
        src = Path(__file__).parent / "fixtures" / "sample_erp.sqlite"
        dst = tmp_path / "sample_erp.sqlite"
        shutil.copy2(src, dst)
        return dst

    @pytest.fixture
    def config(self, sqlite_db, tmp_path) -> Path:
        return _write_sqlite_config(tmp_path, sqlite_db, self.SQLITE_TABLES)

    def test_run_all_succeeds(self, config):
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_all

        cfg = load_config(config)
        results = run_all(cfg, config)
        assert all(r.status == "success" for r in results)
        assert {r.table_name for r in results} == {"orders", "customers", "products"}

    def test_row_counts_in_bronze(self, config):
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_all

        cfg = load_config(config)
        run_all(cfg, config)

        con = duckdb.connect(str(cfg.destination.path), read_only=True)
        assert con.execute("SELECT COUNT(*) FROM bronze.orders").fetchone()[0] == 5
        assert con.execute("SELECT COUNT(*) FROM bronze.customers").fetchone()[0] == 4
        assert con.execute("SELECT COUNT(*) FROM bronze.products").fetchone()[0] == 3
        con.close()

    def test_null_passthrough(self, config):
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_all

        cfg = load_config(config)
        run_all(cfg, config)

        con = duckdb.connect(str(cfg.destination.path), read_only=True)
        row = con.execute(
            "SELECT stock_qty FROM bronze.products WHERE product_name = 'Service Pack'"
        ).fetchone()
        con.close()
        assert row is not None
        assert row[0] is None

    def test_etl_metadata_columns(self, config):
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_all

        cfg = load_config(config)
        run_all(cfg, config)

        con = duckdb.connect(str(cfg.destination.path), read_only=True)
        cols = {
            r[0]
            for r in con.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'bronze' AND table_name = 'orders'"
            ).fetchall()
        }
        con.close()
        assert "_etl_loaded_at" in cols
        assert "_etl_run_id" in cols
