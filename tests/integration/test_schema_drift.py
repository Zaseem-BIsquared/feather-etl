"""Integration: schema drift detection — pipeline re-runs after ALTER TABLE
on source DB.
"""

from __future__ import annotations

import json
import os
import time

import duckdb

from feather_etl.config import load_config
from feather_etl.pipeline import run_table
from feather_etl.state import StateManager
from tests.helpers import make_curation_entry, write_curation


def test_first_run_saves_baseline(project, sample_erp_db):
    project.write_config(
        sources=[{"type": "duckdb", "name": "src", "path": str(sample_erp_db)}],
        destination={"path": str(project.data_db_path)},
    )
    write_curation(
        project.root,
        [
            make_curation_entry(
                "src",
                "erp.customers",
                "customers",
                primary_key=["customer_id"],
            ),
        ],
    )
    cfg = load_config(project.config_path)

    result = run_table(cfg, cfg.tables[0], project.root)
    assert result.status == "success"

    sm = StateManager(project.state_db_path)
    snapshot = sm.get_schema_snapshot("src_customers")
    assert snapshot is not None
    assert len(snapshot) > 0


def test_schema_changes_logged_in_runs(project, sample_erp_db):
    project.write_config(
        sources=[{"type": "duckdb", "name": "src", "path": str(sample_erp_db)}],
        destination={"path": str(project.data_db_path)},
    )
    write_curation(
        project.root,
        [
            make_curation_entry(
                "src",
                "erp.customers",
                "customers",
                primary_key=["customer_id"],
            ),
        ],
    )
    cfg = load_config(project.config_path)

    run_table(cfg, cfg.tables[0], project.root)

    con = duckdb.connect(str(sample_erp_db))
    con.execute("ALTER TABLE erp.customers ADD COLUMN phone VARCHAR")
    con.close()

    time.sleep(0.1)
    os.utime(str(sample_erp_db), None)

    result = run_table(cfg, cfg.tables[0], project.root)
    assert result.status == "success"

    sm = StateManager(project.state_db_path)
    con = sm._connect()
    rows = con.execute(
        "SELECT schema_changes FROM _runs WHERE table_name = 'src_customers' "
        "AND schema_changes IS NOT NULL"
    ).fetchall()
    con.close()
    assert len(rows) >= 1
    changes = json.loads(rows[0][0])
    assert "added" in changes
    assert any("phone" in str(col) for col in changes["added"])
