"""Tests for schema drift detection (V10)."""

from __future__ import annotations

from pathlib import Path

import duckdb

from feather_etl.schema_drift import detect_drift


class TestDetectDrift:
    def test_no_drift_same_schema(self):
        current = [("id", "INTEGER"), ("name", "VARCHAR")]
        stored = [("id", "INTEGER"), ("name", "VARCHAR")]
        drift = detect_drift(current, stored)
        assert not drift.has_drift
        assert drift.added == []
        assert drift.removed == []
        assert drift.type_changed == []

    def test_added_column(self):
        current = [("id", "INTEGER"), ("name", "VARCHAR"), ("phone", "VARCHAR")]
        stored = [("id", "INTEGER"), ("name", "VARCHAR")]
        drift = detect_drift(current, stored)
        assert drift.has_drift
        assert drift.added == [("phone", "VARCHAR")]
        assert drift.removed == []

    def test_removed_column(self):
        current = [("id", "INTEGER")]
        stored = [("id", "INTEGER"), ("name", "VARCHAR")]
        drift = detect_drift(current, stored)
        assert drift.has_drift
        assert drift.removed == [("name", "VARCHAR")]
        assert drift.added == []

    def test_type_changed(self):
        current = [("id", "INTEGER"), ("name", "BIGINT")]
        stored = [("id", "INTEGER"), ("name", "VARCHAR")]
        drift = detect_drift(current, stored)
        assert drift.has_drift
        assert drift.type_changed == [("name", "VARCHAR", "BIGINT")]

    def test_multiple_changes(self):
        current = [("id", "INTEGER"), ("email", "VARCHAR")]
        stored = [("id", "INTEGER"), ("name", "VARCHAR")]
        drift = detect_drift(current, stored)
        assert drift.has_drift
        assert drift.added == [("email", "VARCHAR")]
        assert drift.removed == [("name", "VARCHAR")]

    def test_severity_info_for_added_removed(self):
        current = [("id", "INTEGER"), ("phone", "VARCHAR")]
        stored = [("id", "INTEGER")]
        drift = detect_drift(current, stored)
        assert drift.severity == "INFO"

    def test_severity_critical_for_type_changed(self):
        current = [("id", "BIGINT")]
        stored = [("id", "INTEGER")]
        drift = detect_drift(current, stored)
        assert drift.severity == "CRITICAL"


class TestStateSnapshot:
    def test_save_and_read_snapshot(self, tmp_path: Path):
        from feather_etl.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()
        schema = [("id", "INTEGER"), ("name", "VARCHAR")]
        sm.save_schema_snapshot("orders", schema)

        stored = sm.get_schema_snapshot("orders")
        assert stored == [("id", "INTEGER"), ("name", "VARCHAR")]

    def test_no_snapshot_returns_none(self, tmp_path: Path):
        from feather_etl.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()
        assert sm.get_schema_snapshot("nonexistent") is None

    def test_upsert_overwrites(self, tmp_path: Path):
        from feather_etl.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()
        sm.save_schema_snapshot("orders", [("id", "INTEGER"), ("name", "VARCHAR")])
        sm.save_schema_snapshot("orders", [("id", "INTEGER"), ("email", "VARCHAR")])

        stored = sm.get_schema_snapshot("orders")
        # Should have new schema, not old
        cols = [c[0] for c in stored]
        assert "email" in cols
        assert "name" not in cols


class TestPipelineIntegration:
    def test_first_run_saves_baseline(self, tmp_path: Path):
        """First extraction saves schema baseline, no drift reported."""
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
            "tables": [{
                "name": "customers",
                "source_table": "erp.customers",
                "target_table": "bronze.customers",
                "strategy": "full",
            }],
        }
        (tmp_path / "feather.yaml").write_text(yaml.dump(config))
        cfg = load_config(tmp_path / "feather.yaml")

        result = run_table(cfg, cfg.tables[0], tmp_path)
        assert result.status == "success"

        # Check baseline saved
        sm = StateManager(tmp_path / "feather_state.duckdb")
        snapshot = sm.get_schema_snapshot("customers")
        assert snapshot is not None
        assert len(snapshot) > 0

    def test_schema_changes_logged_in_runs(self, tmp_path: Path):
        """Schema drift is detected and logged in _runs.schema_changes."""
        import json
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
            "tables": [{
                "name": "customers",
                "source_table": "erp.customers",
                "target_table": "bronze.customers",
                "strategy": "full",
            }],
        }
        (tmp_path / "feather.yaml").write_text(yaml.dump(config))
        cfg = load_config(tmp_path / "feather.yaml")

        # First run: saves baseline
        run_table(cfg, cfg.tables[0], tmp_path)

        # Modify source schema: add a column
        con = duckdb.connect(str(client_db))
        con.execute("ALTER TABLE erp.customers ADD COLUMN phone VARCHAR")
        con.close()

        # Ensure mtime changes so change detection triggers re-extraction
        import time
        import os
        time.sleep(0.1)
        os.utime(str(client_db), None)

        # Second run: should detect drift
        result = run_table(cfg, cfg.tables[0], tmp_path)
        assert result.status == "success"

        # Check _runs.schema_changes is populated
        sm = StateManager(tmp_path / "feather_state.duckdb")
        con = sm._connect()
        rows = con.execute(
            "SELECT schema_changes FROM _runs WHERE table_name = 'customers' "
            "AND schema_changes IS NOT NULL"
        ).fetchall()
        con.close()
        assert len(rows) >= 1
        changes = json.loads(rows[0][0])
        assert "added" in changes
        assert any("phone" in str(col) for col in changes["added"])
