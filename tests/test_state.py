"""Tests for feather.state module."""

import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import duckdb
import pytest


CURRENT_SCHEMA_VERSION = 1


class TestStateInit:
    def test_creates_all_tables(self, tmp_path: Path):
        from feather_etl.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()

        con = duckdb.connect(str(sm.path), read_only=True)
        tables = {
            r[0]
            for r in con.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'main'"
            ).fetchall()
        }
        con.close()
        expected = {
            "_state_meta",
            "_watermarks",
            "_runs",
            "_run_steps",
            "_dq_results",
            "_schema_snapshots",
        }
        assert tables == expected

    def test_state_meta_version(self, tmp_path: Path):
        from feather_etl.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()

        con = duckdb.connect(str(sm.path), read_only=True)
        row = con.execute("SELECT schema_version FROM _state_meta").fetchone()
        con.close()
        assert row[0] == CURRENT_SCHEMA_VERSION

    def test_idempotent_init(self, tmp_path: Path):
        from feather_etl.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()
        sm.init_state()  # should not error or duplicate

        con = duckdb.connect(str(sm.path), read_only=True)
        count = con.execute("SELECT COUNT(*) FROM _state_meta").fetchone()[0]
        con.close()
        assert count == 1

    def test_downgrade_protection(self, tmp_path: Path):
        from feather_etl.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()

        # Simulate a future version writing version=99
        con = duckdb.connect(str(sm.path))
        con.execute("UPDATE _state_meta SET schema_version = 99")
        con.close()

        with pytest.raises(RuntimeError, match="newer than feather-etl"):
            sm.init_state()

    def test_new_state_db_gets_600_permissions(self, tmp_path: Path):
        from feather_etl.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()
        mode = stat.S_IMODE(os.stat(sm.path).st_mode)
        assert mode == 0o600

    def test_chmod_oserror_is_swallowed(self, tmp_path: Path):
        from feather_etl.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        with patch("feather_etl.state.os.chmod", side_effect=OSError("denied")):
            sm.init_state()  # should not raise
        assert sm.path.exists()


class TestWatermarks:
    def test_write_and_read(self, tmp_path: Path):
        from feather_etl.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()

        sm.write_watermark("sales_invoice", strategy="full")
        wm = sm.read_watermark("sales_invoice")
        assert wm is not None
        assert wm["table_name"] == "sales_invoice"
        assert wm["strategy"] == "full"

    def test_read_nonexistent(self, tmp_path: Path):
        from feather_etl.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()
        assert sm.read_watermark("nonexistent") is None

    def test_upsert_watermark(self, tmp_path: Path):
        from feather_etl.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()

        sm.write_watermark("test_table", strategy="full")
        sm.write_watermark("test_table", strategy="full")

        con = duckdb.connect(str(sm.path), read_only=True)
        count = con.execute(
            "SELECT COUNT(*) FROM _watermarks WHERE table_name = 'test_table'"
        ).fetchone()[0]
        con.close()
        assert count == 1

    def test_write_watermark_with_mtime_and_hash(self, tmp_path: Path):
        from feather_etl.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()

        sm.write_watermark(
            "test_table",
            strategy="full",
            last_file_mtime=1234567890.5,
            last_file_hash="abc123def456",
        )
        wm = sm.read_watermark("test_table")
        assert wm["last_file_mtime"] == 1234567890.5
        assert wm["last_file_hash"] == "abc123def456"

    def test_write_watermark_update_preserves_mtime_hash(self, tmp_path: Path):
        from feather_etl.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()

        sm.write_watermark(
            "test_table",
            strategy="full",
            last_file_mtime=100.0,
            last_file_hash="hash1",
        )
        sm.write_watermark(
            "test_table",
            strategy="full",
            last_file_mtime=200.0,
            last_file_hash="hash2",
        )
        wm = sm.read_watermark("test_table")
        assert wm["last_file_mtime"] == 200.0
        assert wm["last_file_hash"] == "hash2"

    def test_write_watermark_without_mtime_hash_stays_null(self, tmp_path: Path):
        from feather_etl.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()

        sm.write_watermark("test_table", strategy="full")
        wm = sm.read_watermark("test_table")
        assert wm["last_file_mtime"] is None
        assert wm["last_file_hash"] is None

    def test_write_watermark_preserves_last_value_on_update(self, tmp_path: Path):
        """H-1: write_watermark() without last_value must preserve existing last_value."""
        from feather_etl.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()

        # First write: set last_value
        sm.write_watermark(
            "test_table",
            strategy="incremental",
            last_value="2026-03-01T00:00:00",
            last_file_mtime=100.0,
            last_file_hash="hash1",
        )
        wm = sm.read_watermark("test_table")
        assert wm["last_value"] == "2026-03-01T00:00:00"

        # Second write: touch-skip path — no last_value provided
        sm.write_watermark(
            "test_table",
            strategy="incremental",
            last_file_mtime=200.0,
            last_file_hash="hash1",
        )
        wm = sm.read_watermark("test_table")
        # last_value must survive — not be nulled
        assert wm["last_value"] == "2026-03-01T00:00:00"

    def test_write_watermark_updates_last_value_when_provided(self, tmp_path: Path):
        """H-1: write_watermark() with explicit last_value should update it."""
        from feather_etl.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()

        sm.write_watermark(
            "test_table",
            strategy="incremental",
            last_value="2026-03-01T00:00:00",
        )
        sm.write_watermark(
            "test_table",
            strategy="incremental",
            last_value="2026-03-15T00:00:00",
        )
        wm = sm.read_watermark("test_table")
        assert wm["last_value"] == "2026-03-15T00:00:00"


class TestConnectionCleanup:
    """M-2: DB connections must be closed even on exception paths."""

    def test_read_watermark_closes_on_error(self, tmp_path: Path):
        from unittest.mock import MagicMock

        from feather_etl.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()

        mock_con = MagicMock()
        mock_con.execute.side_effect = RuntimeError("db error")
        sm._connect = lambda: mock_con

        with pytest.raises(RuntimeError, match="db error"):
            sm.read_watermark("test")

        mock_con.close.assert_called_once()

    def test_write_watermark_closes_on_error(self, tmp_path: Path):
        from unittest.mock import MagicMock

        from feather_etl.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()

        mock_con = MagicMock()
        mock_con.execute.side_effect = RuntimeError("db error")
        sm._connect = lambda: mock_con

        with pytest.raises(RuntimeError, match="db error"):
            sm.write_watermark("test", strategy="full")

        mock_con.close.assert_called_once()

    def test_record_run_closes_on_error(self, tmp_path: Path):
        from unittest.mock import MagicMock

        from feather_etl.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()

        mock_con = MagicMock()
        mock_con.execute.side_effect = RuntimeError("db error")
        sm._connect = lambda: mock_con

        now = datetime.now(timezone.utc)
        with pytest.raises(RuntimeError, match="db error"):
            sm.record_run(
                run_id="r1",
                table_name="t1",
                started_at=now,
                ended_at=now,
                status="success",
            )

        mock_con.close.assert_called_once()

    def test_get_status_closes_on_error(self, tmp_path: Path):
        from unittest.mock import MagicMock

        from feather_etl.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()

        mock_con = MagicMock()
        mock_con.execute.side_effect = RuntimeError("db error")
        sm._connect = lambda: mock_con

        with pytest.raises(RuntimeError, match="db error"):
            sm.get_status()

        mock_con.close.assert_called_once()


class TestRuns:
    def test_record_and_get_status(self, tmp_path: Path):
        from feather_etl.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()

        now = datetime.now(timezone.utc)
        sm.record_run(
            run_id="sales_invoice_2025-01-01T00:00:00",
            table_name="sales_invoice",
            started_at=now,
            ended_at=now,
            status="success",
            rows_extracted=100,
            rows_loaded=100,
        )

        status = sm.get_status()
        assert len(status) == 1
        assert status[0]["table_name"] == "sales_invoice"
        assert status[0]["status"] == "success"
        assert status[0]["rows_loaded"] == 100
