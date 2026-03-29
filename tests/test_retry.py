"""Tests for retry + backoff state management (V14)."""

from __future__ import annotations

import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from tests.conftest import FIXTURES_DIR


class TestIncrementRetry:
    def test_first_failure_sets_retry_count_1(self, tmp_path: Path):
        from feather.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()
        sm.write_watermark("orders", strategy="full")

        sm.increment_retry("orders")
        wm = sm.read_watermark("orders")
        assert wm["retry_count"] == 1

    def test_first_failure_sets_retry_after_15_min(self, tmp_path: Path):
        from feather.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()
        sm.write_watermark("orders", strategy="full")

        before = datetime.now(timezone.utc).replace(tzinfo=None)
        sm.increment_retry("orders")
        wm = sm.read_watermark("orders")

        # retry_after should be ~15 min from now
        retry_after = wm["retry_after"]
        assert retry_after is not None
        expected_min = before + timedelta(minutes=14)
        expected_max = before + timedelta(minutes=16)
        assert expected_min <= retry_after <= expected_max

    def test_two_failures_30_min_backoff(self, tmp_path: Path):
        """AC-FR13.a: 2 failures → retry_after = now + 30 min."""
        from feather.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()
        sm.write_watermark("orders", strategy="full")

        sm.increment_retry("orders")
        before = datetime.now(timezone.utc).replace(tzinfo=None)
        sm.increment_retry("orders")
        wm = sm.read_watermark("orders")

        assert wm["retry_count"] == 2
        retry_after = wm["retry_after"]
        expected_min = before + timedelta(minutes=29)
        expected_max = before + timedelta(minutes=31)
        assert expected_min <= retry_after <= expected_max

    def test_ten_failures_capped_at_120_min(self, tmp_path: Path):
        """AC-FR13.c: 10 failures → capped at 120 min, not 150."""
        from feather.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()
        sm.write_watermark("orders", strategy="full")

        for _ in range(9):
            sm.increment_retry("orders")

        before = datetime.now(timezone.utc).replace(tzinfo=None)
        sm.increment_retry("orders")  # 10th failure
        wm = sm.read_watermark("orders")

        assert wm["retry_count"] == 10
        retry_after = wm["retry_after"]
        expected_min = before + timedelta(minutes=119)
        expected_max = before + timedelta(minutes=121)
        assert expected_min <= retry_after <= expected_max

    def test_increment_creates_watermark_if_missing(self, tmp_path: Path):
        from feather.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()
        # No write_watermark call — table doesn't exist yet

        sm.increment_retry("new_table")
        wm = sm.read_watermark("new_table")
        assert wm is not None
        assert wm["retry_count"] == 1


class TestResetRetry:
    def test_reset_clears_retry_state(self, tmp_path: Path):
        from feather.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()
        sm.write_watermark("orders", strategy="full")

        sm.increment_retry("orders")
        sm.increment_retry("orders")
        sm.reset_retry("orders")

        wm = sm.read_watermark("orders")
        assert wm["retry_count"] == 0
        assert wm["retry_after"] is None

    def test_reset_noop_on_clean_table(self, tmp_path: Path):
        from feather.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()
        sm.write_watermark("orders", strategy="full")

        # Should not error
        sm.reset_retry("orders")
        wm = sm.read_watermark("orders")
        assert wm["retry_count"] == 0


class TestShouldSkipRetry:
    def test_no_backoff_returns_false(self, tmp_path: Path):
        from feather.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()
        sm.write_watermark("orders", strategy="full")

        skip, error = sm.should_skip_retry("orders")
        assert skip is False
        assert error is None

    def test_in_backoff_returns_true_with_error(self, tmp_path: Path):
        from feather.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()
        sm.write_watermark("orders", strategy="full")

        # Record a failure run so error message is available
        now = datetime.now(timezone.utc)
        sm.record_run(
            run_id="orders_fail",
            table_name="orders",
            started_at=now,
            ended_at=now,
            status="failure",
            error_message="Connection refused",
        )
        sm.increment_retry("orders")

        skip, error = sm.should_skip_retry("orders")
        assert skip is True
        assert error == "Connection refused"

    def test_past_backoff_returns_false(self, tmp_path: Path):
        import duckdb

        from feather.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()
        sm.write_watermark("orders", strategy="full")
        sm.increment_retry("orders")

        # Manually set retry_after to past (naive UTC, matching DuckDB storage)
        con = duckdb.connect(str(sm.path))
        past = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5)
        con.execute(
            "UPDATE _watermarks SET retry_after = ? WHERE table_name = 'orders'",
            [past],
        )
        con.close()

        skip, _ = sm.should_skip_retry("orders")
        assert skip is False

    def test_nonexistent_table_returns_false(self, tmp_path: Path):
        from feather.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()

        skip, error = sm.should_skip_retry("nonexistent")
        assert skip is False
        assert error is None


class TestGetLastFailureMessage:
    def test_returns_error_from_last_failure(self, tmp_path: Path):
        from feather.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()

        now = datetime.now(timezone.utc)
        sm.record_run(
            run_id="orders_1",
            table_name="orders",
            started_at=now,
            ended_at=now,
            status="failure",
            error_message="First error",
        )
        sm.record_run(
            run_id="orders_2",
            table_name="orders",
            started_at=now + timedelta(seconds=1),
            ended_at=now + timedelta(seconds=1),
            status="failure",
            error_message="Second error",
        )

        msg = sm.get_last_failure_message("orders")
        assert msg == "Second error"

    def test_returns_none_when_no_failures(self, tmp_path: Path):
        from feather.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()

        msg = sm.get_last_failure_message("orders")
        assert msg is None


class TestConnectionCleanupRetry:
    def test_increment_retry_closes_on_error(self, tmp_path: Path):
        from unittest.mock import MagicMock

        from feather.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()

        mock_con = MagicMock()
        mock_con.execute.side_effect = RuntimeError("db error")
        sm._connect = lambda: mock_con

        with pytest.raises(RuntimeError, match="db error"):
            sm.increment_retry("test")

        mock_con.close.assert_called_once()

    def test_should_skip_retry_closes_on_error(self, tmp_path: Path):
        from unittest.mock import MagicMock

        from feather.state import StateManager

        sm = StateManager(tmp_path / "state.duckdb")
        sm.init_state()

        mock_con = MagicMock()
        mock_con.execute.side_effect = RuntimeError("db error")
        sm._connect = lambda: mock_con

        with pytest.raises(RuntimeError, match="db error"):
            sm.should_skip_retry("test")

        mock_con.close.assert_called_once()


# --- Pipeline integration tests ---


def _make_broken_config(tmp_path: Path) -> Path:
    """Config with valid source file but non-existent table to force extraction failure."""
    client_db = tmp_path / "client.duckdb"
    shutil.copy2(FIXTURES_DIR / "client.duckdb", client_db)
    config = {
        "source": {"type": "duckdb", "path": str(client_db)},
        "destination": {"path": str(tmp_path / "feather_data.duckdb")},
        "tables": [
            {
                "name": "orders",
                "source_table": "icube.nonexistent_table_xyz",
                "target_table": "bronze.orders",
                "strategy": "full",
            }
        ],
    }
    config_file = tmp_path / "feather.yaml"
    config_file.write_text(yaml.dump(config, default_flow_style=False))
    return config_file


def _make_good_config(tmp_path: Path) -> Path:
    """Config pointing at a real DuckDB fixture."""
    client_db = tmp_path / "client.duckdb"
    shutil.copy2(FIXTURES_DIR / "client.duckdb", client_db)
    config = {
        "source": {"type": "duckdb", "path": str(client_db)},
        "destination": {"path": str(tmp_path / "feather_data.duckdb")},
        "tables": [
            {
                "name": "inventory_group",
                "source_table": "icube.InventoryGroup",
                "target_table": "bronze.inventory_group",
                "strategy": "full",
            }
        ],
    }
    config_file = tmp_path / "feather.yaml"
    config_file.write_text(yaml.dump(config, default_flow_style=False))
    return config_file


class TestRetryPipelineIntegration:
    def test_failure_increments_retry_count(self, tmp_path: Path):
        from feather.config import load_config
        from feather.pipeline import run_table
        from feather.state import StateManager

        config_path = _make_broken_config(tmp_path)
        cfg = load_config(config_path)

        result = run_table(cfg, cfg.tables[0], tmp_path)
        assert result.status == "failure"

        sm = StateManager(tmp_path / "feather_state.duckdb")
        wm = sm.read_watermark("orders")
        assert wm is not None
        assert wm["retry_count"] == 1
        assert wm["retry_after"] is not None

    def test_table_in_backoff_is_skipped(self, tmp_path: Path):
        from feather.config import load_config
        from feather.pipeline import run_table

        config_path = _make_broken_config(tmp_path)
        cfg = load_config(config_path)

        # First failure sets backoff
        run_table(cfg, cfg.tables[0], tmp_path)

        # Second call should skip (in backoff window)
        result = run_table(cfg, cfg.tables[0], tmp_path)
        assert result.status == "skipped"
        assert result.error_message is not None

    def test_success_resets_retry_count(self, tmp_path: Path):
        from feather.config import load_config
        from feather.pipeline import run_table
        from feather.state import StateManager

        # Start with good config, manually set retry state
        config_path = _make_good_config(tmp_path)
        cfg = load_config(config_path)

        sm = StateManager(tmp_path / "feather_state.duckdb")
        sm.init_state()
        sm.write_watermark("inventory_group", strategy="full")
        sm.increment_retry("inventory_group")
        sm.increment_retry("inventory_group")

        wm = sm.read_watermark("inventory_group")
        assert wm["retry_count"] == 2

        # Manually clear backoff so the run actually executes
        sm.reset_retry("inventory_group")
        sm.increment_retry("inventory_group")  # set count=1 but far future backoff
        import duckdb

        con = duckdb.connect(str(sm.path))
        con.execute(
            "UPDATE _watermarks SET retry_count = 2, retry_after = ? "
            "WHERE table_name = 'inventory_group'",
            [datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5)],
        )
        con.close()

        # Run should succeed and reset retry
        result = run_table(cfg, cfg.tables[0], tmp_path)
        assert result.status == "success"

        wm = sm.read_watermark("inventory_group")
        assert wm["retry_count"] == 0
        assert wm["retry_after"] is None

    def test_other_tables_continue_when_one_fails(self, tmp_path: Path):
        """FR13.5: per-table isolation."""
        from feather.config import load_config
        from feather.pipeline import run_all

        client_db = tmp_path / "client.duckdb"
        shutil.copy2(FIXTURES_DIR / "client.duckdb", client_db)
        config = {
            "source": {"type": "duckdb", "path": str(client_db)},
            "destination": {"path": str(tmp_path / "feather_data.duckdb")},
            "tables": [
                {
                    "name": "inventory_group",
                    "source_table": "icube.InventoryGroup",
                    "target_table": "bronze.inventory_group",
                    "strategy": "full",
                },
                {
                    "name": "bad_table",
                    "source_table": "icube.nonexistent_table",
                    "target_table": "bronze.bad_table",
                    "strategy": "full",
                },
            ],
        }
        config_file = tmp_path / "feather.yaml"
        config_file.write_text(yaml.dump(config, default_flow_style=False))

        cfg = load_config(config_file)
        results = run_all(cfg, config_file)

        statuses = {r.table_name: r.status for r in results}
        assert statuses["inventory_group"] == "success"
        assert statuses["bad_table"] == "failure"
