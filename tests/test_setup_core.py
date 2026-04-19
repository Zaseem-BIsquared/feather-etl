"""Direct unit tests for feather_etl.setup.run_setup()."""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from tests.conftest import FIXTURES_DIR
from tests.helpers import make_curation_entry, write_curation


def _make_project(tmp_path: Path, *, mode: str | None = None) -> Path:
    """Build a minimal feather project. Returns config path.

    Note: ``load_config`` reads tables from ``discovery/curation.json``, not from
    the YAML, so the project layout uses ``write_curation`` (the same pattern as
    ``tests/commands/conftest.py::cli_env``).
    """
    shutil.copy2(FIXTURES_DIR / "sample_erp.sqlite", tmp_path / "source.sqlite")
    config: dict = {
        "sources": [{"type": "sqlite", "name": "erp", "path": "./source.sqlite"}],
        "destination": {"path": "./feather_data.duckdb"},
    }
    if mode is not None:
        config["mode"] = mode
    config_path = tmp_path / "feather.yaml"
    config_path.write_text(yaml.dump(config))
    write_curation(
        tmp_path,
        [make_curation_entry("erp", "orders", "orders")],
    )
    return config_path


def _write_silver_transform(tmp_path: Path) -> None:
    """Write a tiny silver view definition that depends on bronze.orders."""
    tdir = tmp_path / "transforms" / "silver"
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / "orders_clean.sql").write_text(
        "CREATE OR REPLACE VIEW silver.orders_clean AS SELECT * FROM bronze.orders;\n"
    )


class TestRunSetup:
    def test_initializes_state_db_and_destination(self, tmp_path: Path):
        from feather_etl.config import load_config
        from feather_etl.setup import run_setup

        cfg = load_config(_make_project(tmp_path))

        result = run_setup(cfg)

        assert result.state_db_path.exists()
        assert result.destination_path == cfg.destination.path
        assert result.transform_results is None  # no transforms in this project

    def test_returns_none_transforms_when_no_transforms_found(self, tmp_path: Path):
        from feather_etl.config import load_config
        from feather_etl.setup import run_setup

        cfg = load_config(_make_project(tmp_path))
        result = run_setup(cfg)

        assert result.transform_results is None

    def test_executes_transforms_when_present(self, tmp_path: Path):
        from feather_etl.config import load_config
        from feather_etl.setup import run_setup

        config_path = _make_project(tmp_path)
        _write_silver_transform(tmp_path)
        cfg = load_config(config_path)

        result = run_setup(cfg)

        assert result.transform_results is not None
        assert len(result.transform_results) >= 1
        assert any(
            t.name == "orders_clean" and t.schema == "silver"
            for t in result.transform_results
        )
