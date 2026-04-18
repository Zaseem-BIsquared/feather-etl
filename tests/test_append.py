"""Tests for append load strategy."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import duckdb
import pyarrow as pa
import yaml

from tests.conftest import FIXTURES_DIR
from tests.helpers import make_curation_entry, write_curation


def _make_table(num_rows: int = 5, id_offset: int = 0) -> pa.Table:
    return pa.table(
        {
            "id": list(range(id_offset, id_offset + num_rows)),
            "name": [f"item_{i}" for i in range(id_offset, id_offset + num_rows)],
        }
    )


class TestLoadAppend:
    def test_load_append_inserts_with_metadata(self, tmp_path: Path):
        from feather_etl.destinations.duckdb import DuckDBDestination

        db_path = tmp_path / "data.duckdb"
        dest = DuckDBDestination(path=db_path)
        dest.setup_schemas()

        data = _make_table(5)
        rows = dest.load_append("bronze.audit_log", data, "run_001")

        assert rows == 5

        con = duckdb.connect(str(db_path), read_only=True)
        count = con.execute("SELECT COUNT(*) FROM bronze.audit_log").fetchone()[0]
        row = con.execute(
            "SELECT _etl_loaded_at, _etl_run_id FROM bronze.audit_log LIMIT 1"
        ).fetchone()
        con.close()

        assert count == 5
        assert row[0] is not None
        assert row[1] == "run_001"

    def test_load_append_accumulates_rows(self, tmp_path: Path):
        from feather_etl.destinations.duckdb import DuckDBDestination

        db_path = tmp_path / "data.duckdb"
        dest = DuckDBDestination(path=db_path)
        dest.setup_schemas()

        data1 = _make_table(5, id_offset=0)
        dest.load_append("bronze.audit_log", data1, "run_001")

        data2 = _make_table(3, id_offset=100)
        dest.load_append("bronze.audit_log", data2, "run_002")

        con = duckdb.connect(str(db_path), read_only=True)
        count = con.execute("SELECT COUNT(*) FROM bronze.audit_log").fetchone()[0]
        run_ids = {
            r[0]
            for r in con.execute(
                "SELECT DISTINCT _etl_run_id FROM bronze.audit_log"
            ).fetchall()
        }
        con.close()

        assert count == 8
        assert run_ids == {"run_001", "run_002"}

    def test_load_append_creates_table_if_not_exists(self, tmp_path: Path):
        from feather_etl.destinations.duckdb import DuckDBDestination

        db_path = tmp_path / "data.duckdb"
        dest = DuckDBDestination(path=db_path)
        dest.setup_schemas()

        data = _make_table(2)
        dest.load_append("bronze.new_table", data, "run_001")

        dest.load_append("bronze.new_table", _make_table(3, id_offset=10), "run_002")

        con = duckdb.connect(str(db_path), read_only=True)
        count = con.execute("SELECT COUNT(*) FROM bronze.new_table").fetchone()[0]
        con.close()
        assert count == 5


class TestPipelineAppendDispatch:
    def _make_config(
        self,
        tmp_path: Path,
        source_db: Path,
        strategy: str = "append",
        source_table: str = "erp.customers",
    ) -> Path:
        config = {
            "sources": [{"type": "duckdb", "name": "src", "path": str(source_db)}],
            "destination": {"path": str(tmp_path / "feather_data.duckdb")},
        }
        config_path = tmp_path / "feather.yaml"
        config_path.write_text(yaml.dump(config, default_flow_style=False))
        write_curation(
            tmp_path,
            [
                make_curation_entry(
                    "src",
                    source_table,
                    "customers",
                    strategy=strategy,
                    primary_key=["customer_id"],
                ),
            ],
        )
        return config_path

    def test_pipeline_dispatches_to_load_append(self, tmp_path: Path):
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_table

        source_db = tmp_path / "sample_erp.duckdb"
        shutil.copy2(FIXTURES_DIR / "sample_erp.duckdb", source_db)
        config_path = self._make_config(tmp_path, source_db)

        cfg = load_config(config_path)
        result = run_table(cfg, cfg.tables[0], tmp_path)

        assert result.status == "success"
        assert result.rows_loaded == 4

        con = duckdb.connect(str(tmp_path / "feather_data.duckdb"), read_only=True)
        count = con.execute("SELECT COUNT(*) FROM bronze.src_customers").fetchone()[0]
        con.close()
        assert count == 4

    def test_append_second_run_appends_on_change(self, tmp_path: Path):
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_all

        source_db = tmp_path / "sample_erp.duckdb"
        shutil.copy2(FIXTURES_DIR / "sample_erp.duckdb", source_db)
        config_path = self._make_config(tmp_path, source_db)

        cfg = load_config(config_path)

        results1 = run_all(cfg, config_path)
        assert all(r.status == "success" for r in results1)

        time.sleep(0.05)
        con = duckdb.connect(str(source_db))
        con.execute(
            "INSERT INTO erp.customers VALUES (105, 'New Corp', 'new@corp.com', 'Pune', 15000.00, CURRENT_TIMESTAMP)"
        )
        con.close()

        cfg2 = load_config(config_path)
        results2 = run_all(cfg2, config_path)
        assert all(r.status == "success" for r in results2)

        dest_con = duckdb.connect(str(tmp_path / "feather_data.duckdb"), read_only=True)
        count = dest_con.execute(
            "SELECT COUNT(*) FROM bronze.src_customers"
        ).fetchone()[0]
        dest_con.close()
        assert count == 9

    def test_append_unchanged_source_skips(self, tmp_path: Path):
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_all

        source_db = tmp_path / "sample_erp.duckdb"
        shutil.copy2(FIXTURES_DIR / "sample_erp.duckdb", source_db)
        config_path = self._make_config(tmp_path, source_db)

        cfg = load_config(config_path)
        run_all(cfg, config_path)

        cfg2 = load_config(config_path)
        results2 = run_all(cfg2, config_path)
        assert all(r.status == "skipped" for r in results2)

        dest_con = duckdb.connect(str(tmp_path / "feather_data.duckdb"), read_only=True)
        count = dest_con.execute(
            "SELECT COUNT(*) FROM bronze.src_customers"
        ).fetchone()[0]
        dest_con.close()
        assert count == 4
