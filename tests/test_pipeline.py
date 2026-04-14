"""Tests for feather.pipeline module."""

from pathlib import Path

import duckdb
import pytest
import yaml

from tests.conftest import FIXTURES_DIR


@pytest.fixture
def setup_env(tmp_path: Path) -> tuple[Path, Path]:
    """Set up a complete pipeline environment: config + source DB."""
    import shutil

    client_db = tmp_path / "client.duckdb"
    shutil.copy2(FIXTURES_DIR / "client.duckdb", client_db)

    config = {
        "sources": [{"type": "duckdb", "path": str(client_db)}],
        "destination": {"path": str(tmp_path / "feather_data.duckdb")},
        "tables": [
            {
                "name": "inventory_group",
                "source_table": "icube.InventoryGroup",
                "target_table": "bronze.inventory_group",
                "strategy": "full",
            },
            {
                "name": "customer_master",
                "source_table": "icube.CUSTOMERMASTER",
                "target_table": "bronze.customer_master",
                "strategy": "full",
            },
        ],
    }
    config_path = tmp_path / "feather.yaml"
    config_path.write_text(yaml.dump(config, default_flow_style=False))
    return config_path, tmp_path


class TestRunTable:
    def test_extracts_and_loads(self, setup_env: tuple[Path, Path]):
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_table

        config_path, tmp_path = setup_env
        cfg = load_config(config_path)

        result = run_table(cfg, cfg.tables[0], tmp_path)
        assert result.status == "success"
        assert result.rows_loaded == 66  # InventoryGroup has 66 rows

    def test_records_state(self, setup_env: tuple[Path, Path]):
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_table
        from feather_etl.state import StateManager

        config_path, tmp_path = setup_env
        cfg = load_config(config_path)
        run_table(cfg, cfg.tables[0], tmp_path)

        sm = StateManager(tmp_path / "feather_state.duckdb")
        status = sm.get_status()
        assert len(status) == 1
        assert status[0]["status"] == "success"

    def test_data_has_etl_metadata(self, setup_env: tuple[Path, Path]):
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_table

        config_path, tmp_path = setup_env
        cfg = load_config(config_path)
        run_table(cfg, cfg.tables[0], tmp_path)

        con = duckdb.connect(str(tmp_path / "feather_data.duckdb"), read_only=True)
        row = con.execute(
            "SELECT _etl_loaded_at, _etl_run_id FROM bronze.inventory_group LIMIT 1"
        ).fetchone()
        con.close()
        assert row[0] is not None
        assert "inventory_group" in row[1]


class TestRunAll:
    def test_runs_all_tables(self, setup_env: tuple[Path, Path]):
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_all

        config_path, tmp_path = setup_env
        cfg = load_config(config_path)

        results = run_all(cfg, config_path)
        assert len(results) == 2
        assert all(r.status == "success" for r in results)

    def test_failed_table_doesnt_stop_others(self, setup_env: tuple[Path, Path]):
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_all

        config_path, tmp_path = setup_env
        cfg = load_config(config_path)
        # Point one table to nonexistent source table
        cfg.tables[0].source_table = "icube.NONEXISTENT"

        results = run_all(cfg, config_path)
        statuses = {r.table_name: r.status for r in results}
        assert statuses["inventory_group"] == "failure"
        assert statuses["customer_master"] == "success"

    def test_run_all_does_not_write_validation_json(self, setup_env: tuple[Path, Path]):
        """L-1: run_all() should NOT write validation JSON — CLI owns that."""
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_all

        config_path, tmp_path = setup_env
        cfg = load_config(config_path)

        # Remove any pre-existing validation file
        vj_path = config_path.parent / "feather_validation.json"
        vj_path.unlink(missing_ok=True)

        run_all(cfg, config_path)

        # run_all should NOT create validation JSON
        assert not vj_path.exists()

    def test_first_run_always_extracts(self, setup_env: tuple[Path, Path]):
        """First run with no prior watermark always extracts."""
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_table

        config_path, tmp_path = setup_env
        cfg = load_config(config_path)
        result = run_table(cfg, cfg.tables[0], tmp_path)
        assert result.status == "success"
        assert result.rows_loaded > 0

    def test_watermark_populated_after_success(self, setup_env: tuple[Path, Path]):
        """After successful run, watermark has mtime and hash."""
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_table
        from feather_etl.state import StateManager

        config_path, tmp_path = setup_env
        cfg = load_config(config_path)
        run_table(cfg, cfg.tables[0], tmp_path)

        sm = StateManager(tmp_path / "feather_state.duckdb")
        wm = sm.read_watermark("inventory_group")
        assert wm is not None
        assert wm["last_file_mtime"] is not None
        assert wm["last_file_hash"] is not None

    def test_second_run_skips_unchanged(self, setup_env: tuple[Path, Path]):
        """Second run on unchanged source → all tables skipped."""
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_all

        config_path, tmp_path = setup_env
        cfg = load_config(config_path)

        run_all(cfg, config_path)
        results2 = run_all(cfg, config_path)
        assert all(r.status == "skipped" for r in results2)

    def test_modified_source_reextracts(self, setup_env: tuple[Path, Path]):
        """Modify source file → next run extracts again."""
        import time

        from feather_etl.config import load_config
        from feather_etl.pipeline import run_all

        config_path, tmp_path = setup_env
        cfg = load_config(config_path)

        run_all(cfg, config_path)

        # Modify source: add a row to change content and hash
        time.sleep(0.05)  # ensure mtime differs on coarse-resolution filesystems
        source_db = tmp_path / "client.duckdb"
        con = duckdb.connect(str(source_db))
        con.execute(
            "INSERT INTO icube.InventoryGroup "
            "SELECT * FROM icube.InventoryGroup LIMIT 1"
        )
        con.close()

        results2 = run_all(cfg, config_path)
        assert all(r.status == "success" for r in results2)

    def test_touch_source_skips(self, setup_env: tuple[Path, Path]):
        """Touch source file (mtime changes, content identical) → skipped."""
        import os
        import time

        from feather_etl.config import load_config
        from feather_etl.pipeline import run_all

        config_path, tmp_path = setup_env
        cfg = load_config(config_path)

        run_all(cfg, config_path)

        # Touch: update mtime without changing content
        time.sleep(0.05)
        os.utime(tmp_path / "client.duckdb", None)

        results2 = run_all(cfg, config_path)
        assert all(r.status == "skipped" for r in results2)

    def test_skipped_run_recorded_in_state(self, setup_env: tuple[Path, Path]):
        """Skipped runs are recorded in _runs table."""
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_all
        from feather_etl.state import StateManager

        config_path, tmp_path = setup_env
        cfg = load_config(config_path)

        run_all(cfg, config_path)
        run_all(cfg, config_path)

        sm = StateManager(tmp_path / "feather_state.duckdb")
        status = sm.get_status()
        # get_status returns last run per table — should be "skipped"
        assert all(s["status"] == "skipped" for s in status)

    def test_failed_extraction_doesnt_update_watermark(
        self, setup_env: tuple[Path, Path]
    ):
        """Failed extraction should not populate mtime/hash in watermark."""
        from feather_etl.config import load_config
        from feather_etl.pipeline import run_table
        from feather_etl.state import StateManager

        config_path, tmp_path = setup_env
        cfg = load_config(config_path)
        # Point to nonexistent table to trigger failure
        cfg.tables[0].source_table = "icube.NONEXISTENT"

        run_table(cfg, cfg.tables[0], tmp_path)

        sm = StateManager(tmp_path / "feather_state.duckdb")
        wm = sm.read_watermark("inventory_group")
        # Watermark value not advanced on failure (retry metadata may exist)
        if wm is not None:
            assert wm["last_value"] is None
            assert wm["last_run_at"] is None
            assert wm["retry_count"] == 1  # retry state set by V14
