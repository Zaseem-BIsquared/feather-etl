"""Multi-source commands are now supported (guard removed in #8)."""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from tests.conftest import FIXTURES_DIR
from tests.helpers import make_curation_entry, write_curation


def _multi_source_yaml(tmp_path: Path) -> Path:
    src1 = tmp_path / "a.duckdb"
    src2 = tmp_path / "b.duckdb"
    shutil.copy2(FIXTURES_DIR / "client.duckdb", src1)
    shutil.copy2(FIXTURES_DIR / "client.duckdb", src2)
    cfg = {
        "sources": [
            {"name": "a", "type": "duckdb", "path": str(src1)},
            {"name": "b", "type": "duckdb", "path": str(src2)},
        ],
        "destination": {"path": str(tmp_path / "out.duckdb")},
    }
    p = tmp_path / "feather.yaml"
    p.write_text(yaml.dump(cfg))
    write_curation(
        tmp_path,
        [make_curation_entry("a", "icube.InventoryGroup", "ig")],
    )
    return p


class TestMultiSource:
    """Multi-source configs are accepted by all commands — the old single-source
    guard was removed as part of issue #8 (multi-source pipeline support)."""

    def test_validate_accepts_multi_source(self, runner, tmp_path):
        from feather_etl.cli import app

        cfg = _multi_source_yaml(tmp_path)
        r = runner.invoke(app, ["validate", "--config", str(cfg)])
        # No longer rejected — both sources should be checked
        assert "single-source" not in r.output
        assert r.exit_code in (0, 2)  # 0=all connected, 2=connection failure

    def test_run_accepts_multi_source(self, runner, tmp_path):
        from feather_etl.cli import app

        cfg = _multi_source_yaml(tmp_path)
        r = runner.invoke(app, ["run", "--config", str(cfg)])
        # No longer rejected at the guard level
        assert "single-source" not in r.output

    def test_setup_accepts_multi_source(self, runner, tmp_path):
        from feather_etl.cli import app

        cfg = _multi_source_yaml(tmp_path)
        r = runner.invoke(app, ["setup", "--config", str(cfg)])
        assert "single-source" not in r.output
        assert r.exit_code == 0

    def test_status_accepts_multi_source(self, runner, tmp_path):
        from feather_etl.cli import app

        cfg = _multi_source_yaml(tmp_path)
        r = runner.invoke(app, ["status", "--config", str(cfg)])
        assert "single-source" not in r.output

    def test_history_accepts_multi_source(self, runner, tmp_path):
        from feather_etl.cli import app

        cfg = _multi_source_yaml(tmp_path)
        r = runner.invoke(app, ["history", "--config", str(cfg)])
        assert "single-source" not in r.output
