"""Workflow stage 11: path resolution — CWD-independence of --config.

Scenarios in this file verify that feather commands resolve paths correctly
regardless of the process CWD when the config is passed via an absolute
--config argument.
"""

from __future__ import annotations

from pathlib import Path

from tests.helpers import make_curation_entry, write_curation


def test_config_absolute_path_from_different_cwd(
    project, cli, tmp_path_factory, monkeypatch
):
    """S10: running feather with --config /abs/path from a different CWD works.

    Setup:
        - A project with a SQLite source (fast, no DuckDB fixture needed).
        - curation.json defines three tables.
        - The project lives under pytest's tmp_path; we chdir into a
          *different* tmp directory before invoking the CLI.

    Expectation:
        - `feather setup` exits 0.
        - `feather run` exits 0.
        - Both invocations happen while CWD is not the project root.
    """
    # 1. Arrange: a real SQLite-backed project.
    project.copy_fixture("sample_erp.sqlite")
    project.write_config(
        sources=[{"type": "sqlite", "name": "erp", "path": "./sample_erp.sqlite"}],
        destination={"path": "./feather_data.duckdb"},
    )
    write_curation(
        project.root,
        [
            make_curation_entry("erp", "orders", "orders"),
            make_curation_entry("erp", "customers", "customers"),
            make_curation_entry("erp", "products", "products"),
        ],
    )

    # 2. Change CWD to a directory that is NOT the project root.
    foreign_cwd = tmp_path_factory.mktemp("foreign_cwd")
    monkeypatch.chdir(foreign_cwd)
    # .resolve() normalizes /private symlinks on macOS so the != comparison
    # is meaningful regardless of platform.
    assert Path.cwd().resolve() != project.root.resolve()

    # 3. Act + assert: setup + run both succeed despite CWD mismatch.
    setup_result = cli("setup")
    assert setup_result.exit_code == 0, setup_result.output

    run_result = cli("run")
    assert run_result.exit_code == 0, run_result.output
