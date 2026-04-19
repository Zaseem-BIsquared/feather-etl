"""Direct unit tests for feather_etl.discover top-level functions."""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from tests.conftest import FIXTURES_DIR


def _make_sqlite_project(tmp_path: Path, source_name: str | None = None) -> Path:
    """Set up a tmp SQLite feather project. Returns config path."""
    shutil.copy2(FIXTURES_DIR / "sample_erp.sqlite", tmp_path / "source.sqlite")
    source: dict = {"type": "sqlite", "path": "./source.sqlite"}
    if source_name is not None:
        source["name"] = source_name
    cfg = {
        "sources": [source],
        "destination": {"path": "./feather_data.duckdb"},
        "tables": [
            {
                "name": "orders",
                "source_table": "orders",
                "target_table": "bronze.orders",
                "strategy": "full",
            }
        ],
    }
    config_path = tmp_path / "feather.yaml"
    config_path.write_text(yaml.dump(cfg))
    return config_path


class TestDetectRenamesForSources:
    def test_returns_empty_proposals_when_state_is_empty(self, tmp_path: Path):
        from feather_etl.config import load_config
        from feather_etl.discover import detect_renames_for_sources
        from feather_etl.discover_state import DiscoverState
        from feather_etl.sources.expand import expand_db_sources

        cfg = load_config(_make_sqlite_project(tmp_path), validate=False)
        state = DiscoverState.load(tmp_path)
        sources = expand_db_sources(cfg.sources)

        detection = detect_renames_for_sources(state, sources)

        assert detection.proposals == []
        assert detection.ambiguous == []

    def test_finds_rename_when_fingerprint_matches_under_new_name(self, tmp_path: Path):
        """Rename a source in YAML; same fingerprint → proposal."""
        from feather_etl.config import load_config
        from feather_etl.discover import detect_renames_for_sources
        from feather_etl.discover_state import DiscoverState
        from feather_etl.sources.expand import expand_db_sources

        # First load with name "old_db" — record state.
        config_path = _make_sqlite_project(tmp_path, source_name="old_db")
        cfg = load_config(config_path, validate=False)
        state = DiscoverState.load(tmp_path)
        sources = expand_db_sources(cfg.sources)
        # Simulate a prior successful discover under "old_db".
        from feather_etl.discover import _fingerprint_for

        state.record_ok(
            name="old_db",
            type_=sources[0].type,
            fingerprint=_fingerprint_for(sources[0]),
            table_count=1,
            output_path=tmp_path / "schemas-sqlite-old_db.json",
        )

        # Now rename source to "new_db".
        config_path = _make_sqlite_project(tmp_path, source_name="new_db")
        cfg = load_config(config_path, validate=False)
        sources = expand_db_sources(cfg.sources)

        detection = detect_renames_for_sources(state, sources)

        assert detection.proposals == [("old_db", "new_db")]
        assert detection.ambiguous == []

    def test_returns_ambiguous_when_multiple_state_entries_match(self, tmp_path: Path):
        """Two stale state entries with the same fingerprint as one current
        source → ambiguous (cannot decide which old name was renamed)."""
        from feather_etl.config import load_config
        from feather_etl.discover import _fingerprint_for, detect_renames_for_sources
        from feather_etl.discover_state import DiscoverState
        from feather_etl.sources.expand import expand_db_sources

        config_path = _make_sqlite_project(tmp_path, source_name="new_db")
        cfg = load_config(config_path, validate=False)
        state = DiscoverState.load(tmp_path)
        sources = expand_db_sources(cfg.sources)
        fp = _fingerprint_for(sources[0])
        state.record_ok(
            name="old_a",
            type_=sources[0].type,
            fingerprint=fp,
            table_count=1,
            output_path=tmp_path / "schemas-sqlite-old_a.json",
        )
        state.record_ok(
            name="old_b",
            type_=sources[0].type,
            fingerprint=fp,
            table_count=1,
            output_path=tmp_path / "schemas-sqlite-old_b.json",
        )

        detection = detect_renames_for_sources(state, sources)

        assert detection.proposals == []
        assert len(detection.ambiguous) == 1
        new_name, candidates = detection.ambiguous[0]
        assert new_name == "new_db"
        assert set(candidates) == {"old_a", "old_b"}


class TestApplyRenameDecision:
    def test_renames_state_and_files_for_accepted_proposals(self, tmp_path: Path):
        from feather_etl.config import load_config
        from feather_etl.discover import (
            _fingerprint_for,
            apply_rename_decision,
        )
        from feather_etl.discover_state import DiscoverState
        from feather_etl.sources.expand import expand_db_sources

        config_path = _make_sqlite_project(tmp_path, source_name="new_db")
        cfg = load_config(config_path, validate=False)
        state = DiscoverState.load(tmp_path)
        sources = expand_db_sources(cfg.sources)
        fp = _fingerprint_for(sources[0])
        old_path = tmp_path / "schemas-sqlite-old_db.json"
        old_path.write_text("[]")
        state.record_ok(
            name="old_db",
            type_=sources[0].type,
            fingerprint=fp,
            table_count=1,
            output_path=old_path,
        )

        apply_rename_decision(
            state,
            accepted=[("old_db", "new_db")],
            rejected=[],
            sources=sources,
            config_dir=tmp_path,
        )

        assert "new_db" in state.sources
        assert "old_db" not in state.sources

    def test_marks_orphaned_for_rejected_proposals(self, tmp_path: Path):
        from feather_etl.config import load_config
        from feather_etl.discover import _fingerprint_for, apply_rename_decision
        from feather_etl.discover_state import DiscoverState
        from feather_etl.sources.expand import expand_db_sources

        config_path = _make_sqlite_project(tmp_path, source_name="new_db")
        cfg = load_config(config_path, validate=False)
        state = DiscoverState.load(tmp_path)
        sources = expand_db_sources(cfg.sources)
        fp = _fingerprint_for(sources[0])
        state.record_ok(
            name="old_db",
            type_=sources[0].type,
            fingerprint=fp,
            table_count=1,
            output_path=tmp_path / "schemas-sqlite-old_db.json",
        )

        apply_rename_decision(
            state,
            accepted=[],
            rejected=[("old_db", "new_db")],
            sources=sources,
            config_dir=tmp_path,
        )

        assert state.sources["old_db"].get("status") == "orphaned"


class TestRunDiscover:
    def test_records_succeeded_sources_with_table_counts(self, tmp_path: Path):
        from feather_etl.config import load_config
        from feather_etl.discover import run_discover

        cfg = load_config(_make_sqlite_project(tmp_path), validate=False)

        report = run_discover(
            cfg,
            tmp_path,
            refresh=False,
            retry_failed=False,
            prune=False,
        )

        assert report.succeeded_count == 1
        assert report.failed_count == 0
        assert len(report.results) == 1
        r = report.results[0]
        assert r.status == "succeeded"
        assert r.table_count > 0
        assert r.output_path is not None
        assert r.output_path.exists()

    def test_records_failed_sources_with_error_message(self, tmp_path: Path):
        """Source pointing at a missing file → failed, error captured in result."""
        from feather_etl.config import load_config
        from feather_etl.discover import run_discover

        # Build config with a deliberately missing SQLite file.
        cfg_dict = {
            "sources": [{"type": "sqlite", "path": "./missing.sqlite"}],
            "destination": {"path": "./feather_data.duckdb"},
            "tables": [
                {
                    "name": "orders",
                    "source_table": "orders",
                    "target_table": "bronze.orders",
                    "strategy": "full",
                }
            ],
        }
        config_path = tmp_path / "feather.yaml"
        config_path.write_text(yaml.dump(cfg_dict))
        # discover_mode skips table validation
        cfg = load_config(config_path, validate=False)

        report = run_discover(
            cfg,
            tmp_path,
            refresh=False,
            retry_failed=False,
            prune=False,
        )

        assert report.failed_count == 1
        assert report.succeeded_count == 0
        assert report.results[0].status == "failed"
        assert report.results[0].error is not None

    def test_with_refresh_ignores_cached_state(self, tmp_path: Path):
        """A second run with refresh=True re-discovers a previously-discovered source."""
        from feather_etl.config import load_config
        from feather_etl.discover import run_discover

        cfg = load_config(_make_sqlite_project(tmp_path), validate=False)

        # First run — establishes state.
        run_discover(cfg, tmp_path, refresh=False, retry_failed=False, prune=False)

        # Second run with refresh — should re-discover, not return cached.
        report = run_discover(
            cfg, tmp_path, refresh=True, retry_failed=False, prune=False
        )

        assert report.succeeded_count == 1
        assert report.cached_count == 0

    def test_second_run_without_refresh_reports_cached(self, tmp_path: Path):
        from feather_etl.config import load_config
        from feather_etl.discover import run_discover

        cfg = load_config(_make_sqlite_project(tmp_path), validate=False)

        run_discover(cfg, tmp_path, refresh=False, retry_failed=False, prune=False)
        report = run_discover(
            cfg, tmp_path, refresh=False, retry_failed=False, prune=False
        )

        assert report.cached_count == 1
        assert report.succeeded_count == 0

    def test_with_prune_removes_state_and_files_for_removed_sources(
        self, tmp_path: Path
    ):
        from feather_etl.config import load_config
        from feather_etl.discover import run_discover
        from feather_etl.discover_state import DiscoverState

        cfg = load_config(_make_sqlite_project(tmp_path), validate=False)

        # Seed a state entry for a now-removed source with a file on disk.
        state = DiscoverState.load(tmp_path)
        old_path = tmp_path / "schemas-sqlite-stale.json"
        old_path.write_text("[]")
        state.record_ok(
            name="stale",
            type_="sqlite",
            fingerprint="sqlite:/non/existent",
            table_count=1,
            output_path=old_path,
        )
        state.save()

        report = run_discover(
            cfg, tmp_path, refresh=False, retry_failed=False, prune=True
        )

        assert report.pruned_count >= 1
        assert not old_path.exists()

        state = DiscoverState.load(tmp_path)
        assert "stale" not in state.sources
