"""Integration: feather_etl.setup.run_setup — orchestrates state init +
destination creation + transform execution.
"""

from __future__ import annotations

from feather_etl.config import load_config
from feather_etl.setup import run_setup


def _setup_project(project):
    """Build a minimal feather project. Returns config path."""
    project.copy_fixture("sample_erp.sqlite")
    (project.root / "sample_erp.sqlite").rename(project.root / "source.sqlite")
    project.write_config(
        sources=[{"type": "sqlite", "name": "erp", "path": "./source.sqlite"}],
        destination={"path": "./feather_data.duckdb"},
    )
    project.write_curation([("erp", "orders", "orders")])
    return project.config_path


def _write_silver_transform(project) -> None:
    """Write a tiny silver view definition that depends on bronze.orders."""
    tdir = project.root / "transforms" / "silver"
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / "orders_clean.sql").write_text(
        "CREATE OR REPLACE VIEW silver.orders_clean AS SELECT * FROM bronze.orders;\n"
    )


def test_initializes_state_db_and_destination(project):
    cfg = load_config(_setup_project(project))

    result = run_setup(cfg)

    assert result.state_db_path.exists()
    assert result.destination_path == cfg.destination.path
    assert result.transform_results is None  # no transforms in this project


def test_returns_none_transforms_when_no_transforms_found(project):
    cfg = load_config(_setup_project(project))
    result = run_setup(cfg)

    assert result.transform_results is None


def test_executes_transforms_when_present(project):
    config_path = _setup_project(project)
    _write_silver_transform(project)
    cfg = load_config(config_path)

    result = run_setup(cfg)

    assert result.transform_results is not None
    assert len(result.transform_results) >= 1
    assert any(
        t.name == "orders_clean" and t.schema == "silver"
        for t in result.transform_results
    )
