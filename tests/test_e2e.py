"""End-to-end integration test: full Slice 1 onboarding flow."""

import shutil
from pathlib import Path

import duckdb
import yaml
from typer.testing import CliRunner

from tests.conftest import FIXTURES_DIR
from tests.helpers import make_curation_entry, write_curation

runner = CliRunner()


def test_full_onboarding_flow(tmp_path: Path, monkeypatch):
    """init -> validate -> discover -> setup -> run -> status -> run again."""
    from feather_etl.cli import app

    # --- 1. feather init ---
    project_dir = tmp_path / "client-test"
    result = runner.invoke(app, ["init", str(project_dir)])
    assert result.exit_code == 0, result.output
    assert (project_dir / "feather.yaml").exists()
    assert (project_dir / "pyproject.toml").exists()
    assert (project_dir / ".gitignore").exists()
    assert (project_dir / ".env.example").exists()

    # --- 2. Edit feather.yaml (simulating operator) ---
    client_db = project_dir / "client.duckdb"
    shutil.copy2(FIXTURES_DIR / "client.duckdb", client_db)

    config = {
        "sources": [{"type": "duckdb", "name": "icube", "path": str(client_db)}],
        "destination": {"path": str(project_dir / "feather_data.duckdb")},
    }
    config_path = project_dir / "feather.yaml"
    config_path.write_text(yaml.dump(config, default_flow_style=False))

    write_curation(
        project_dir,
        [
            make_curation_entry("icube", "icube.SALESINVOICE", "sales_invoice"),
            make_curation_entry("icube", "icube.CUSTOMERMASTER", "customer_master"),
            make_curation_entry("icube", "icube.InventoryGroup", "inventory_group"),
        ],
    )

    # --- 3. feather validate ---
    result = runner.invoke(app, ["validate", "--config", str(config_path)])
    assert result.exit_code == 0, result.output
    vj_path = project_dir / "feather_validation.json"
    assert vj_path.exists()

    # --- 4. feather discover ---
    monkeypatch.chdir(project_dir)
    import feather_etl.commands.discover as discover_cmd

    monkeypatch.setattr(discover_cmd, "serve_and_open", lambda *args, **kwargs: None)
    result = runner.invoke(app, ["discover", "--config", str(config_path)])
    assert result.exit_code == 0, result.output
    assert "discovered" in result.output

    import json

    schema_files = list(project_dir.glob("schema_*.json"))
    assert len(schema_files) == 1, f"Expected one schema file, found: {schema_files}"
    payload = json.loads(schema_files[0].read_text())
    table_names = [entry["table_name"] for entry in payload]
    assert any("SALESINVOICE" in t for t in table_names)
    assert any("CUSTOMERMASTER" in t for t in table_names)
    assert any("InventoryGroup" in t for t in table_names)

    # --- 5. feather setup ---
    result = runner.invoke(app, ["setup", "--config", str(config_path)])
    assert result.exit_code == 0, result.output
    assert (project_dir / "feather_state.duckdb").exists()

    # --- 6. feather run ---
    result = runner.invoke(app, ["run", "--config", str(config_path)])
    assert result.exit_code == 0, result.output
    assert "3/3 tables extracted" in result.output

    # Verify bronze tables exist with correct data
    data_db = str(project_dir / "feather_data.duckdb")
    con = duckdb.connect(data_db, read_only=True)

    si_count = con.execute(
        "SELECT COUNT(*) FROM bronze.icube_sales_invoice"
    ).fetchone()[0]
    assert si_count == 11676

    cm_count = con.execute(
        "SELECT COUNT(*) FROM bronze.icube_customer_master"
    ).fetchone()[0]
    assert cm_count == 1339

    ig_count = con.execute(
        "SELECT COUNT(*) FROM bronze.icube_inventory_group"
    ).fetchone()[0]
    assert ig_count == 66

    # Verify ETL metadata columns
    row = con.execute(
        "SELECT _etl_loaded_at, _etl_run_id FROM bronze.icube_sales_invoice LIMIT 1"
    ).fetchone()
    assert row[0] is not None
    assert "icube_sales_invoice" in row[1]
    con.close()

    # --- 7. feather status ---
    result = runner.invoke(app, ["status", "--config", str(config_path)])
    assert result.exit_code == 0, result.output
    assert "icube_sales_invoice" in result.output
    assert "icube_customer_master" in result.output
    assert "icube_inventory_group" in result.output
    assert "success" in result.output

    # --- 8. Second feather run (change detection -> skip unchanged) ---
    result = runner.invoke(app, ["run", "--config", str(config_path)])
    assert result.exit_code == 0, result.output
    assert "skipped (unchanged)" in result.output
    assert "3 skipped" in result.output

    # Verify feather_validation.json was written
    assert vj_path.exists()
