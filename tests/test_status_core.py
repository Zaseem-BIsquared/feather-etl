"""Direct unit tests for feather_etl.status.load_status()."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest


def _make_state_with_runs(state_path: Path) -> None:
    """Create a state DB and insert run rows for two tables."""
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


class TestLoadStatus:
    def test_returns_rows_for_each_table(self, tmp_path: Path):
        from feather_etl.status import load_status

        state_path = tmp_path / "feather_state.duckdb"
        _make_state_with_runs(state_path)

        rows = load_status(state_path)

        assert {r["table_name"] for r in rows} == {"orders", "customers"}

    def test_returns_empty_list_when_no_runs(self, tmp_path: Path):
        from feather_etl.state import StateManager
        from feather_etl.status import load_status

        state_path = tmp_path / "feather_state.duckdb"
        sm = StateManager(state_path)
        sm.init_state()

        rows = load_status(state_path)

        assert rows == []


class TestLoadStatusPreconditions:
    def test_raises_state_db_missing_when_no_db(self, tmp_path: Path):
        from feather_etl.exceptions import StateDBMissingError
        from feather_etl.status import load_status

        with pytest.raises(StateDBMissingError):
            load_status(tmp_path / "missing.duckdb")
