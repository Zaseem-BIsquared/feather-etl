"""Multi-source guard for non-discover commands (B2 deferral)."""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from tests.conftest import FIXTURES_DIR


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
        "tables": [
            {"name": "ig", "source_table": "icube.InventoryGroup",
             "target_table": "bronze.ig", "strategy": "full"},
        ],
    }
    p = tmp_path / "feather.yaml"
    p.write_text(yaml.dump(cfg))
    return p


class TestMultiSourceGuard:
    def test_validate_exits_2_with_guidance(self, runner, tmp_path):
        from feather_etl.cli import app
        cfg = _multi_source_yaml(tmp_path)
        r = runner.invoke(app, ["validate", "--config", str(cfg)])
        assert r.exit_code == 2
        assert "single-source" in r.output
        assert "discover" in r.output

    def test_run_exits_2(self, runner, tmp_path):
        from feather_etl.cli import app
        cfg = _multi_source_yaml(tmp_path)
        r = runner.invoke(app, ["run", "--config", str(cfg)])
        assert r.exit_code == 2

    def test_status_exits_2(self, runner, tmp_path):
        from feather_etl.cli import app
        cfg = _multi_source_yaml(tmp_path)
        r = runner.invoke(app, ["status", "--config", str(cfg)])
        assert r.exit_code == 2

    def test_history_exits_2(self, runner, tmp_path):
        from feather_etl.cli import app
        cfg = _multi_source_yaml(tmp_path)
        r = runner.invoke(app, ["history", "--config", str(cfg)])
        assert r.exit_code == 2

    def test_setup_exits_2(self, runner, tmp_path):
        from feather_etl.cli import app
        cfg = _multi_source_yaml(tmp_path)
        r = runner.invoke(app, ["setup", "--config", str(cfg)])
        assert r.exit_code == 2
