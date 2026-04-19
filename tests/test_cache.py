"""Unit tests for feather_etl.cache.run_cache()."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pytest
import yaml

from tests.conftest import FIXTURES_DIR
from tests.helpers import make_curation_entry, write_curation


def _make_project(tmp_path: Path) -> Path:
    """Build a minimal feather project: 1 DuckDB source, 1 curated table."""
    client_db = tmp_path / "client.duckdb"
    shutil.copy2(FIXTURES_DIR / "client.duckdb", client_db)
    config = {
        "sources": [{"type": "duckdb", "name": "icube", "path": str(client_db)}],
        "destination": {"path": str(tmp_path / "feather_data.duckdb")},
    }
    (tmp_path / "feather.yaml").write_text(yaml.dump(config))
    write_curation(
        tmp_path,
        [make_curation_entry("icube", "icube.InventoryGroup", "inventory_group")],
    )
    return tmp_path / "feather.yaml"


class TestRunCacheBasic:
    def test_extracts_all_columns_into_bronze(self, tmp_path: Path):
        from feather_etl.cache import run_cache
        from feather_etl.config import load_config

        config_path = _make_project(tmp_path)
        cfg = load_config(config_path)
        results = run_cache(cfg, cfg.tables, tmp_path)

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
        # Must include _etl_* metadata columns + source columns
        assert "_etl_loaded_at" in cols
        assert "_etl_run_id" in cols
        assert len(cols) > 2  # more than just the metadata columns


class TestRunCacheStateIsolation:
    def test_writes_only_to_cache_watermarks(self, tmp_path: Path):
        """After run_cache, _watermarks must be empty and _cache_watermarks populated."""
        from feather_etl.cache import run_cache
        from feather_etl.config import load_config

        config_path = _make_project(tmp_path)
        cfg = load_config(config_path)
        run_cache(cfg, cfg.tables, tmp_path)

        state_db = tmp_path / "feather_state.duckdb"
        con = duckdb.connect(str(state_db), read_only=True)
        prod = con.execute("SELECT COUNT(*) FROM _watermarks").fetchone()[0]
        cache = con.execute(
            "SELECT COUNT(*) FROM _cache_watermarks"
        ).fetchone()[0]
        runs = con.execute("SELECT COUNT(*) FROM _runs").fetchone()[0]
        con.close()

        assert prod == 0, "run_cache must not write to _watermarks"
        assert runs == 0, "run_cache must not write to _runs"
        assert cache == 1, "run_cache must write to _cache_watermarks"


class TestRunCacheSkip:
    def test_skips_unchanged_on_second_run(self, tmp_path: Path):
        from feather_etl.cache import run_cache
        from feather_etl.config import load_config

        config_path = _make_project(tmp_path)
        cfg = load_config(config_path)

        first = run_cache(cfg, cfg.tables, tmp_path)
        assert first[0].status == "success"

        second = run_cache(cfg, cfg.tables, tmp_path)
        assert second[0].status == "cached"
        assert second[0].rows_loaded == 0

    def test_refresh_forces_repull(self, tmp_path: Path):
        from feather_etl.cache import run_cache
        from feather_etl.config import load_config

        config_path = _make_project(tmp_path)
        cfg = load_config(config_path)

        run_cache(cfg, cfg.tables, tmp_path)
        second = run_cache(cfg, cfg.tables, tmp_path, refresh=True)

        assert second[0].status == "success"
        assert second[0].rows_loaded > 0


class TestRunCachePartialFailure:
    def test_one_failure_does_not_block_others(self, tmp_path: Path):
        """One bad table should not prevent other tables from being cached."""
        from feather_etl.cache import run_cache
        from feather_etl.config import load_config

        client_db = tmp_path / "client.duckdb"
        shutil.copy2(FIXTURES_DIR / "client.duckdb", client_db)
        config = {
            "sources": [
                {"type": "duckdb", "name": "icube", "path": str(client_db)}
            ],
            "destination": {"path": str(tmp_path / "feather_data.duckdb")},
        }
        (tmp_path / "feather.yaml").write_text(yaml.dump(config))
        write_curation(
            tmp_path,
            [
                make_curation_entry(
                    "icube", "icube.InventoryGroup", "good_table"
                ),
                make_curation_entry("icube", "icube.DOES_NOT_EXIST", "bad_table"),
            ],
        )

        cfg = load_config(tmp_path / "feather.yaml")
        results = run_cache(cfg, cfg.tables, tmp_path)

        statuses = {r.table_name: r.status for r in results}
        assert statuses["icube_good_table"] == "success"
        assert statuses["icube_bad_table"] == "failure"
