"""Workflow stage 17: --json flag across commands.

Scenarios exercise the `--json` root flag — CLI commands emit NDJSON
instead of human-readable output when --json is set. Currently only
one e2e test exercises this; integration / unit coverage of the JSON
output helpers lives in tests/test_json_output.py (pending Wave C/D).
"""

from __future__ import annotations


def test_default_output_unchanged(cli, project):
    """Default (no --json) output should still be human-readable."""
    project.write_config(
        sources=[
            {
                "type": "duckdb",
                "name": "icube",
                "path": str(project.copy_fixture("client.duckdb")),
            }
        ],
        destination={"path": str(project.data_db_path)},
    )
    project.write_curation(
        [("icube", "icube.InventoryGroup", "inventory_group")],
    )

    result = cli("validate")

    assert result.exit_code == 0
    assert "Config valid" in result.output
