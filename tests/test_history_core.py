"""Direct unit tests for feather_etl.history.load_history()."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest


def _make_state_with_runs(state_path: Path) -> None:
    """Create a state DB and insert two run rows."""
    from feather_etl.state import StateManager

    sm = StateManager(state_path)
    sm.init_state()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    sm.record_run(
        run_id="run-1",
        table_name="orders",
        started_at=now,
        ended_at=now,
        status="success",
        rows_loaded=10,
    )
    sm.record_run(
        run_id="run-2",
        table_name="customers",
        started_at=now,
        ended_at=now,
        status="success",
        rows_loaded=5,
    )


class TestLoadHistory:
    def test_returns_rows_from_state_db(self, tmp_path: Path):
        from feather_etl.history import load_history

        state_path = tmp_path / "feather_state.duckdb"
        _make_state_with_runs(state_path)

        rows = load_history(state_path)

        assert len(rows) == 2
        assert {r["table_name"] for r in rows} == {"orders", "customers"}
        assert all(r["status"] == "success" for r in rows)

    def test_filters_by_table_name(self, tmp_path: Path):
        from feather_etl.history import load_history

        state_path = tmp_path / "feather_state.duckdb"
        _make_state_with_runs(state_path)

        rows = load_history(state_path, table="orders")

        assert len(rows) == 1
        assert rows[0]["table_name"] == "orders"

    def test_respects_limit(self, tmp_path: Path):
        from feather_etl.history import load_history

        state_path = tmp_path / "feather_state.duckdb"
        _make_state_with_runs(state_path)

        rows = load_history(state_path, limit=1)

        assert len(rows) == 1


class TestLoadHistoryPreconditions:
    def test_raises_state_db_missing_when_no_db(self, tmp_path: Path):
        from feather_etl.exceptions import StateDBMissingError
        from feather_etl.history import load_history

        with pytest.raises(StateDBMissingError):
            load_history(tmp_path / "missing.duckdb")
