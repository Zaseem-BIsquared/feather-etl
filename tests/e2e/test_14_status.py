"""Workflow stage 14: feather status.

Scenarios exercise `feather status` before setup, after setup with no
runs, and after successful + failed runs.
"""

from __future__ import annotations

import json

from tests.helpers import make_curation_entry, write_curation


def test_shows_status_after_run(cli, project):
    project.copy_fixture("client.duckdb")
    project.write_config(
        sources=[
            {
                "type": "duckdb",
                "name": "icube",
                "path": str(project.root / "client.duckdb"),
            }
        ],
        destination={"path": str(project.root / "feather_data.duckdb")},
    )
    project.write_curation([("icube", "icube.InventoryGroup", "inventory_group")])

    cli("run")
    result = cli("status")
    assert result.exit_code == 0
    assert "icube_inventory_group" in result.output


def test_status_no_state_db(cli, project):
    project.copy_fixture("client.duckdb")
    project.write_config(
        sources=[
            {
                "type": "duckdb",
                "name": "icube",
                "path": str(project.root / "client.duckdb"),
            }
        ],
        destination={"path": str(project.root / "feather_data.duckdb")},
    )
    project.write_curation([("icube", "icube.InventoryGroup", "inventory_group")])

    result = cli("status")
    assert result.exit_code != 0
    assert "No state DB found" in result.output


def test_status_no_runs_yet(cli, project):
    project.copy_fixture("client.duckdb")
    project.write_config(
        sources=[
            {
                "type": "duckdb",
                "name": "icube",
                "path": str(project.root / "client.duckdb"),
            }
        ],
        destination={"path": str(project.root / "feather_data.duckdb")},
    )
    project.write_curation([("icube", "icube.InventoryGroup", "inventory_group")])

    cli("setup")
    result = cli("status")
    assert result.exit_code == 0
    assert "No runs recorded" in result.output


def test_status_json_empty_rows_is_silent(cli, project):
    """In --json mode, when there are no runs, feather status prints nothing
    (early-returns) rather than emitting a 'No runs recorded' sentinel."""
    project.copy_fixture("client.duckdb")
    project.write_config(
        sources=[
            {
                "type": "duckdb",
                "name": "icube",
                "path": str(project.root / "client.duckdb"),
            }
        ],
        destination={"path": str(project.root / "feather_data.duckdb")},
    )
    project.write_curation([("icube", "icube.InventoryGroup", "inventory_group")])
    cli("setup")

    result = cli("--json", "status")
    assert result.exit_code == 0
    # No runs yet → no NDJSON lines; no friendly prose either.
    assert result.output.strip() == ""


def test_status_shows_error_message_for_failures(cli, project):
    """UX-5: feather status should display error text for failed tables."""
    project.copy_fixture("client.duckdb")
    project.write_config(
        sources=[
            {
                "type": "duckdb",
                "name": "icube",
                "path": str(project.root / "client.duckdb"),
            }
        ],
        destination={"path": str(project.root / "feather_data.duckdb")},
    )
    write_curation(
        project.root,
        [make_curation_entry("icube", "icube.NONEXISTENT", "bad_table")],
    )

    cli("run")
    result = cli("status")
    assert result.exit_code == 0
    assert "Error:" in result.output


def test_status_shows_all_time_history(cli, project):
    """BUG-8 (intentional): status shows tables from ALL runs, not just current config.
    This is correct behavior — history should not be lost when config changes."""
    project.copy_fixture("client.duckdb")

    # First config: inventory_group
    project.write_config(
        sources=[
            {
                "type": "duckdb",
                "name": "icube",
                "path": str(project.root / "client.duckdb"),
            }
        ],
        destination={"path": str(project.root / "feather_data.duckdb")},
    )
    write_curation(
        project.root,
        [
            make_curation_entry("icube", "icube.InventoryGroup", "inventory_group"),
        ],
    )
    cli("run")

    # Second config: customer_master
    write_curation(
        project.root,
        [
            make_curation_entry("icube", "icube.CUSTOMERMASTER", "customer_master"),
        ],
    )
    cli("run")

    result = cli("status")
    assert result.exit_code == 0
    assert "icube_inventory_group" in result.output
    assert "icube_customer_master" in result.output


def test_status_json_outputs_ndjson(cli, project):
    """AC-FR11.d: feather status --json outputs NDJSON with required fields."""
    project.copy_fixture("client.duckdb")
    project.write_config(
        sources=[
            {
                "type": "duckdb",
                "name": "icube",
                "path": str(project.root / "client.duckdb"),
            }
        ],
        destination={"path": str(project.root / "feather_data.duckdb")},
    )
    project.write_curation([("icube", "icube.InventoryGroup", "inventory_group")])

    cli("run")

    result = cli("--json", "status")
    assert result.exit_code == 0
    lines = [line for line in result.output.strip().split("\n") if line.strip()]
    assert len(lines) >= 1
    parsed = json.loads(lines[0])
    assert "table_name" in parsed
    assert "status" in parsed
