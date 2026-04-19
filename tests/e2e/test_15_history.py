"""Workflow stage 15: feather history.

Scenarios exercise `feather history` — listing prior runs, filtering by
table, and output formatting.
"""

from __future__ import annotations

import json


def _two_table_env(project):
    project.copy_fixture("client.duckdb")
    project.write_config(
        sources=[{"type": "duckdb", "name": "icube", "path": str(project.root / "client.duckdb")}],
        destination={"path": str(project.root / "feather_data.duckdb")},
    )
    project.write_curation(
        [
            ("icube", "icube.InventoryGroup", "inventory_group"),
            ("icube", "icube.CUSTOMERMASTER", "customer_master"),
        ]
    )


def test_history_shows_runs_after_run(cli, project):
    """feather history shows a table of recent runs."""
    _two_table_env(project)
    cli("run")
    result = cli("history")
    assert result.exit_code == 0
    assert "inventory_group" in result.output
    assert "customer_master" in result.output


def test_history_table_filter(cli, project):
    """feather history --table icube_inventory_group shows only that table's runs."""
    _two_table_env(project)
    cli("run")
    result = cli("history", "--table", "icube_inventory_group")
    assert result.exit_code == 0
    assert "icube_inventory_group" in result.output
    assert "icube_customer_master" not in result.output


def test_history_limit(cli, project):
    """feather history --limit 1 shows at most 1 run."""
    _two_table_env(project)
    cli("run")
    cli("run")
    result = cli("history", "--limit", "1")
    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    data_lines = [
        line
        for line in lines
        if not line.startswith("-") and "Table" not in line and line.strip()
    ]
    assert len(data_lines) <= 1


def test_history_empty_state_shows_message(cli, project):
    """feather history with no runs shows a friendly message."""
    _two_table_env(project)
    cli("setup")
    result = cli("history")
    assert result.exit_code == 0
    assert "No runs recorded" in result.output


def test_history_json_outputs_ndjson(cli, project):
    project.copy_fixture("client.duckdb")
    project.write_config(
        sources=[{"type": "duckdb", "name": "icube", "path": str(project.root / "client.duckdb")}],
        destination={"path": str(project.root / "feather_data.duckdb")},
    )
    project.write_curation([("icube", "icube.InventoryGroup", "inventory_group")])

    cli("run")
    result = cli("--json", "history")
    assert result.exit_code == 0
    lines = [line for line in result.output.strip().split("\n") if line.strip()]
    assert len(lines) >= 1
    parsed = json.loads(lines[0])
    assert "run_id" in parsed
    assert "table_name" in parsed
