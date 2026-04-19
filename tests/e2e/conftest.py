"""End-to-end test harness for feather-etl.

This module provides:

- `ProjectFixture`: a small object representing "a feather project on disk,
  ready to use." Bundles the project directory, config/data/state paths, and
  helpers for writing YAML, writing curation.json, copying fixture data, and
  querying the data DB.
- `project`: a pytest fixture yielding a fresh `ProjectFixture` rooted at
  pytest's `tmp_path`.
- `cli`: a pytest fixture yielding a callable that invokes the feather Typer
  app via `CliRunner`, automatically forwarding `--config` pointing at the
  project's config file.

The API is deliberately minimal. Do not add assertion helpers
(`assert_table_rows`, etc.) here — write them inline in tests until the same
assertion shows up a third time, then lift it into the fixture.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable

import duckdb
import pytest
import yaml
from typer.testing import CliRunner, Result

from feather_etl.cli import app

from tests.conftest import FIXTURES_DIR
from tests.helpers import make_curation_entry, write_curation


class ProjectFixture:
    """A feather project on disk, usable by e2e tests."""

    def __init__(self, root: Path) -> None:
        self.root = root

    @property
    def config_path(self) -> Path:
        return self.root / "feather.yaml"

    @property
    def data_db_path(self) -> Path:
        return self.root / "feather_data.duckdb"

    @property
    def state_db_path(self) -> Path:
        return self.root / "feather_state.duckdb"

    def write_config(self, **fields) -> Path:
        """Write `fields` as YAML to `feather.yaml` in the project root.

        Example:
            project.write_config(
                sources=[{"type": "duckdb", "name": "s", "path": "./src.duckdb"}],
                destination={"path": "./feather_data.duckdb"},
            )
        """
        self.config_path.write_text(yaml.dump(fields, default_flow_style=False))
        return self.config_path

    def write_curation(self, entries: list[tuple[str, str, str]]) -> Path:
        """Write `discovery/curation.json` using a list of (source_db, source_table, alias) tuples.

        For richer entries (timestamp, filter, dq_policy, etc.) call
        `tests.helpers.make_curation_entry` directly and then
        `tests.helpers.write_curation` yourself.
        """
        tables = [make_curation_entry(src, table, alias) for (src, table, alias) in entries]
        return write_curation(self.root, tables)

    def copy_fixture(self, name: str) -> Path:
        """Copy a file or directory from `tests/fixtures/<name>` into the project root.

        Returns the destination path.
        """
        src = FIXTURES_DIR / name
        dst = self.root / name
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        return dst

    def query(self, sql: str) -> list[tuple]:
        """Execute `sql` against the project's data DB (read-only) and return all rows."""
        with duckdb.connect(str(self.data_db_path), read_only=True) as con:
            return con.execute(sql).fetchall()


@pytest.fixture
def project(tmp_path: Path) -> ProjectFixture:
    """A fresh `ProjectFixture` rooted at pytest's `tmp_path`."""
    return ProjectFixture(tmp_path)


@pytest.fixture
def cli(project: ProjectFixture) -> Callable[..., Result]:
    """Return a callable that runs feather CLI commands against `project`.

    The `--config` flag is forwarded automatically after the positional args.
    Because `--config` is a per-subcommand option, invocations should start
    with a subcommand:

        cli("validate")
        cli("run")
        cli("setup")
        cli("validate", "--help")    # subcommand help is fine

    `cli("--help")` (app-level help) is ambiguous with the auto-appended
    --config and should be avoided; use `cli("<cmd>", "--help")` instead.

    Returns a `click.testing.Result` (re-exported as `typer.testing.Result`)
    exposing `.exit_code`, `.output`, `.stdout`, `.stderr`, etc.
    """
    runner = CliRunner()

    def _run(*args: str) -> Result:
        return runner.invoke(app, list(args) + ["--config", str(project.config_path)])

    return _run
