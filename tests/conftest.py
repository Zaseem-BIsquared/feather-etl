"""Shared test fixtures for feather-etl."""

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from tests.helpers import make_curation_entry, write_curation


def pytest_configure(config):
    """Start PostgreSQL before test collection (so skipif checks see it)."""
    if shutil.which("pg_ctl"):
        subprocess.run(["pg_ctl", "start", "-l", "/dev/null"], capture_output=True)


def pytest_unconfigure(config):
    """Stop PostgreSQL after the test session."""
    if shutil.which("pg_ctl"):
        subprocess.run(["pg_ctl", "stop"], capture_output=True)


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def client_db(tmp_path) -> Path:
    """Copy test client DuckDB to tmp_path so tests don't modify the fixture."""
    src = FIXTURES_DIR / "client.duckdb"
    dst = tmp_path / "client.duckdb"
    shutil.copy2(src, dst)
    return dst


@pytest.fixture
def config_path(client_db, tmp_path) -> Path:
    """Write a feather.yaml + curation.json pointing at client_db, return path."""
    config = {
        "sources": [
            {
                "type": "duckdb",
                "name": "icube",
                "path": str(client_db),
            }
        ],
        "destination": {
            "path": str(tmp_path / "feather_data.duckdb"),
        },
    }
    config_file = tmp_path / "feather.yaml"
    config_file.write_text(yaml.dump(config, default_flow_style=False))
    write_curation(
        tmp_path,
        [
            make_curation_entry("icube", "icube.SALESINVOICE", "sales_invoice"),
            make_curation_entry("icube", "icube.CUSTOMERMASTER", "customer_master"),
            make_curation_entry("icube", "icube.InventoryGroup", "inventory_group"),
        ],
    )
    return config_file


@pytest.fixture
def csv_data_dir(tmp_path) -> Path:
    """Copy CSV fixture directory to tmp_path."""
    src = FIXTURES_DIR / "csv_data"
    dst = tmp_path / "csv_data"
    shutil.copytree(src, dst)
    return dst


@pytest.fixture
def sqlite_db(tmp_path) -> Path:
    """Copy SQLite fixture to tmp_path."""
    src = FIXTURES_DIR / "sample_erp.sqlite"
    dst = tmp_path / "sample_erp.sqlite"
    shutil.copy2(src, dst)
    return dst


@pytest.fixture
def sample_erp_db(tmp_path) -> Path:
    """Copy sample_erp DuckDB to tmp_path (includes erp.sales for incremental tests)."""
    src = FIXTURES_DIR / "sample_erp.duckdb"
    dst = tmp_path / "sample_erp.duckdb"
    shutil.copy2(src, dst)
    return dst
