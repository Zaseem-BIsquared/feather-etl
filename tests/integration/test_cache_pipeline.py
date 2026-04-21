"""Integration: feather_etl.cache.run_cache — parquet cache builder.

Exercises cache + config + state + destinations cross-module behavior.
All tests invoke cache.run_cache directly; the CLI counterpart lives
in tests/e2e/test_12_cache.py.
"""

from __future__ import annotations

import duckdb

from feather_etl.cache import run_cache
from feather_etl.config import load_config
from tests.helpers import make_curation_entry, write_curation


def _setup_project(project):
    """Build a minimal feather project: 1 DuckDB source, 1 curated table."""
    project.copy_fixture("client.duckdb")
    project.write_config(
        sources=[
            {
                "type": "duckdb",
                "name": "icube",
                "path": str(project.root / "client.duckdb"),
            }
        ],
        destination={"path": str(project.root / "feather_data.duckdb")},
    )
    project.write_curation([("icube", "icube.InventoryGroup", "inventory_group")])


def test_extracts_all_columns_into_bronze(project):
    _setup_project(project)
    cfg = load_config(project.config_path)
    results = run_cache(cfg, cfg.tables, project.root)

    assert len(results) == 1
    assert results[0].status == "success"
    assert results[0].table_name == "icube_inventory_group"
    assert results[0].rows_loaded > 0

    # Verify bronze table exists with all source columns
    con = duckdb.connect(str(cfg.destination.path), read_only=True)
    cols = {
        r[0]
        for r in con.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'bronze' "
            "AND table_name = 'icube_inventory_group'"
        ).fetchall()
    }
    con.close()
    # Must include _etl_* metadata columns AND specific source columns
    # (known subset of InventoryGroup). Asserting specific source columns
    # (not just len > 2) catches silent column dropping.
    required = {
        "_etl_loaded_at",
        "_etl_run_id",
        "GRPCODE",
        "GRPNAME",
        "Alias",
    }
    assert required.issubset(cols), f"Missing expected columns. Got: {sorted(cols)}"


def test_writes_only_to_cache_watermarks(project):
    """After run_cache, _watermarks must be empty and _cache_watermarks populated."""
    _setup_project(project)
    cfg = load_config(project.config_path)
    run_cache(cfg, cfg.tables, project.root)

    con = duckdb.connect(str(project.state_db_path), read_only=True)
    prod = con.execute("SELECT COUNT(*) FROM _watermarks").fetchone()[0]
    cache = con.execute("SELECT COUNT(*) FROM _cache_watermarks").fetchone()[0]
    runs = con.execute("SELECT COUNT(*) FROM _runs").fetchone()[0]
    con.close()

    assert prod == 0, "run_cache must not write to _watermarks"
    assert runs == 0, "run_cache must not write to _runs"
    assert cache == 1, "run_cache must write to _cache_watermarks"


def test_skips_unchanged_on_second_run(project):
    _setup_project(project)
    cfg = load_config(project.config_path)

    first = run_cache(cfg, cfg.tables, project.root)
    assert first[0].status == "success"

    second = run_cache(cfg, cfg.tables, project.root)
    assert second[0].status == "cached"
    assert second[0].rows_loaded == 0


def test_refresh_forces_repull(project):
    _setup_project(project)
    cfg = load_config(project.config_path)

    run_cache(cfg, cfg.tables, project.root)
    second = run_cache(cfg, cfg.tables, project.root, refresh=True)

    assert second[0].status == "success"
    assert second[0].rows_loaded > 0


def test_one_failure_does_not_block_others(project):
    """One bad table should not prevent other tables from being cached."""
    project.copy_fixture("client.duckdb")
    project.write_config(
        sources=[
            {
                "type": "duckdb",
                "name": "icube",
                "path": str(project.root / "client.duckdb"),
            }
        ],
        destination={"path": str(project.root / "feather_data.duckdb")},
    )
    write_curation(
        project.root,
        [
            make_curation_entry("icube", "icube.InventoryGroup", "good_table"),
            make_curation_entry("icube", "icube.DOES_NOT_EXIST", "bad_table"),
        ],
    )

    cfg = load_config(project.config_path)
    results = run_cache(cfg, cfg.tables, project.root)

    statuses = {r.table_name: r.status for r in results}
    assert statuses["icube_good_table"] == "success"
    assert statuses["icube_bad_table"] == "failure"


def test_unresolvable_source_db_records_failure_without_raising(project):
    """A curation entry whose ``database`` doesn't match any configured
    source produces a ``CacheResult(status='failure')`` with the
    resolve_source error message — no exception propagates.
    (cache.py:51-60)"""
    project.copy_fixture("client.duckdb")
    project.write_config(
        sources=[
            {
                "type": "duckdb",
                "name": "icube",
                "path": str(project.root / "client.duckdb"),
            }
        ],
        destination={"path": str(project.root / "feather_data.duckdb")},
    )
    entry = make_curation_entry("icube", "icube.InventoryGroup", "orphan_table")
    # Override database to a name that doesn't exist anywhere in cfg.sources
    entry["source_db"] = "nonexistent_system"
    write_curation(project.root, [entry])

    cfg = load_config(project.config_path)
    # load_config's validator tolerates this (config-level check is
    # informational); run_cache must not raise either.
    results = run_cache(cfg, cfg.tables, project.root)

    assert len(results) == 1
    assert results[0].status == "failure"
    assert results[0].source_db == "nonexistent_system"
    assert results[0].error_message is not None
    assert "nonexistent_system" in results[0].error_message
    # Cache shouldn't mutate bronze for a source-resolution failure.
    assert results[0].rows_loaded == 0
