"""Workflow stage 10: error handling — isolation, exit codes, stream routing.

Scenarios here use real subprocess execution when they need OS-level stream
separation (stdout vs stderr). Tests that only care about combined output
should use the in-process `cli` fixture instead.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from tests.helpers import make_curation_entry, write_curation


def _find_feather_binary() -> Path:
    """Locate the installed `feather` script in the current venv.

    shutil.which respects the active PATH (which pytest inherits from `uv run`).
    If it's missing the dev environment is broken — fail loudly.
    """
    path = shutil.which("feather")
    if path is None:
        raise RuntimeError(
            "Cannot locate the 'feather' script on PATH. Run "
            "`uv sync` and re-run tests from `uv run pytest`."
        )
    return Path(path)


def test_errors_not_duplicated_on_stderr(project):
    """S14/BUG-1: error text appears on stdout only, not duplicated on stderr.

    CliRunner merges streams, so this test uses subprocess.run to get the
    real OS-level stdout/stderr split.

    Setup:
        - A DuckDB source copied into the project.
        - curation.json references a table name that does NOT exist in the
          source (erp.NOSUCH).
    Expectation:
        - `feather run` exits non-zero.
        - The error keyword 'NOSUCH' appears on stdout at least once.
        - 'NOSUCH' does NOT appear on stderr (or appears 0 times).
    """
    # Arrange: real DuckDB source, curation pointing at a non-existent table.
    project.copy_fixture("sample_erp.duckdb")
    project.write_config(
        sources=[{"type": "duckdb", "name": "erp", "path": "./sample_erp.duckdb"}],
        destination={"path": "./feather_data.duckdb"},
    )
    write_curation(
        project.root,
        [make_curation_entry("erp", "erp.NOSUCH", "bad")],
    )

    # Act: run via real subprocess so stdout and stderr are physically separate.
    feather = _find_feather_binary()
    result = subprocess.run(
        [str(feather), "run", "--config", str(project.config_path)],
        capture_output=True,
        text=True,
        cwd=project.root,
    )

    # Assert: non-zero exit, error visible on stdout, NOT on stderr.
    assert result.returncode != 0, (
        f"feather run unexpectedly succeeded.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    stdout_hits = result.stdout.count("NOSUCH")
    stderr_hits = result.stderr.count("NOSUCH")
    assert stdout_hits >= 1, (
        f"Expected 'NOSUCH' on stdout, got 0 hits.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert stderr_hits == 0, (
        f"'NOSUCH' leaked onto stderr {stderr_hits} times; BUG-1 regression.\n"
        f"stderr:\n{result.stderr}"
    )
