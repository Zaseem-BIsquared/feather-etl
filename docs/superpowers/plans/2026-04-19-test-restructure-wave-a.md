# Test Restructure — Wave A (Foundation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce the `tests/e2e/`, `tests/integration/`, `tests/unit/` directory structure, a `ProjectFixture`-based end-to-end harness, and the five pytest tests that close the last coverage gaps versus `scripts/hands_on_test.sh`. After this wave, the bash script still exists; nothing under `tests/` is moved or renamed; every existing test remains untouched.

**Architecture:** A small `ProjectFixture` class in `tests/e2e/conftest.py` represents "a feather project on disk" (root path, config path, data/state DB paths, helpers for writing YAML/curation, copying fixture data, running SQL). A companion `cli` fixture returns a callable that invokes the feather Typer app via `CliRunner` against the project's config. The five gap tests use these fixtures (plus raw `subprocess.run` for the one test that needs real OS-level stream separation).

**Tech Stack:** pytest, `typer.testing.CliRunner`, `duckdb`, PyYAML, stdlib `subprocess` + `shutil`, existing `tests/helpers.py` (`write_curation`, `make_curation_entry`). No new dependencies.

**Source spec:** [`docs/superpowers/specs/2026-04-19-test-restructure-design.md`](../specs/2026-04-19-test-restructure-design.md)

**Issue:** https://github.com/siraj-samsudeen/feather-etl/issues/40

**Branch:** `feat/test-restructure` (long-running; Waves B–E land on this branch in subsequent planning cycles; one PR at the end).

---

## Scope

**In scope for Wave A:**

- Create empty directory structure: `tests/e2e/`, `tests/integration/`, `tests/unit/`, `tests/unit/sources/`, `tests/unit/destinations/`, `tests/unit/commands/`.
- Implement `ProjectFixture` + `project` + `cli` pytest fixtures in `tests/e2e/conftest.py`.
- Port five tests from `scripts/hands_on_test.sh`:
  - S10 — `--config` absolute path from a different CWD
  - S13 — missing `feather.yaml` shows a friendly error
  - S14 — error output not duplicated on stderr (BUG-1 regression; requires subprocess)
  - S16a — CSV source rejects a file path (must be a directory)
  - S17 — SQLite source end-to-end via the CLI
- Write `tests/README.md` documenting the three-way decision rule and the fixture API.
- Create the coverage-map skeleton at `docs/superpowers/specs/2026-04-19-test-restructure-coverage-map.md` (table header only; rows are filled during Wave E).

**Out of scope for Wave A:**

- Migrating any existing test file (Waves B/C/D).
- Deleting `scripts/hands_on_test.sh` (Wave E).
- Updating `CLAUDE.md` or `docs/CONTRIBUTING.md` (Wave E).
- Any change under `src/feather_etl/`, `tests/fixtures/`, or any existing test file.

**Boundary rule:** `uv run pytest -q` before Wave A starts and after every Wave A task must show identical or strictly greater green counts. Existing tests do not change.

---

## File Structure

New files created in Wave A:

| Path | Responsibility |
|---|---|
| `tests/e2e/__init__.py` | Package marker (empty) |
| `tests/e2e/conftest.py` | `ProjectFixture` class + `project` + `cli` fixtures (the e2e harness) |
| `tests/e2e/test_fixture_smoke.py` | Exercises every public method/property of `ProjectFixture` + `cli` — tightens the harness contract |
| `tests/e2e/test_02_validate.py` | Workflow-stage file for `feather validate` e2e scenarios (gap tests S13 + S16a land here) |
| `tests/e2e/test_10_error_handling.py` | Workflow-stage file for error-path e2e scenarios (gap test S14 lands here) |
| `tests/e2e/test_11_path_resolution.py` | Workflow-stage file for CWD-independence scenarios (gap test S10 lands here) |
| `tests/e2e/test_18_sources_e2e.py` | Workflow-stage file for non-default source types end-to-end (gap test S17 lands here) |
| `tests/integration/__init__.py` | Package marker (empty; Wave C populates) |
| `tests/unit/__init__.py` | Package marker (empty; Wave D populates) |
| `tests/unit/sources/__init__.py` | Package marker (empty; Wave D populates) |
| `tests/unit/destinations/__init__.py` | Package marker (empty; Wave D populates) |
| `tests/unit/commands/__init__.py` | Package marker (empty; likely stays empty) |
| `tests/README.md` | Written contract: three-way decision rule + `ProjectFixture` API + file-naming conventions |
| `docs/superpowers/specs/2026-04-19-test-restructure-coverage-map.md` | Table header only; Wave E fills rows mapping each bash check to a pytest test |

No existing files are modified or deleted in Wave A.

---

## Key design points the engineer must internalize

1. **Modern config shape:** feather's current config format is a YAML with `sources:` + `destination:` only; table/curation details live in a separate `discovery/curation.json`. See `tests/helpers.py::write_curation` + `make_curation_entry` and `tests/test_integration.py::_write_config` for the canonical shape. Do **not** reproduce the bash script's inline `tables:` YAML — use the modern form.

2. **`ProjectFixture` API is closed:** only the methods listed below exist. If a gap test seems to need another helper, the right move is to write the needed logic inline in the test, not to silently extend the fixture. (Growing the fixture is allowed — but only as a deliberate decision, not a drive-by edit.)

3. **Gap tests are expected to PASS on first run.** Each scenario is behavior the production code already implements (the bash script has been asserting it for months). A test that fails on first run is a signal the test is wrong, not the code. Investigate before committing a failing test.

4. **TDD framing for Wave A:** classical red-green-refactor applies to Task 2 (`ProjectFixture`), where the smoke tests really do fail before the fixture exists. For Tasks 3–7 (gap tests), TDD is still the shape — write the test, run it, see it pass — but the "red" phase is degenerate because the behavior already works. The discipline that matters there is: **write the test first, run it, confirm the assertion reflects real behavior before committing.**

5. **Workflow-stage numbering:** the file names `test_02_validate.py`, `test_10_error_handling.py`, `test_11_path_resolution.py`, `test_18_sources_e2e.py` are placeholders that Wave B/C will expand. Don't invent new numbers. The full ordered list is in the spec's architecture section.

---

### Task 1: Create the directory skeleton

**Files:**
- Create: `tests/e2e/__init__.py`
- Create: `tests/integration/__init__.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/unit/sources/__init__.py`
- Create: `tests/unit/destinations/__init__.py`
- Create: `tests/unit/commands/__init__.py`

- [ ] **Step 1: Record the pre-task baseline**

Run:
```bash
uv run pytest --collect-only -q 2>&1 | tail -2
```
Expected: a line like `704 tests collected in X.XXs`. Write this number down — every subsequent task must match or exceed it.

- [ ] **Step 2: Create the six empty package markers**

Run:
```bash
mkdir -p tests/e2e tests/integration tests/unit/sources tests/unit/destinations tests/unit/commands
touch tests/e2e/__init__.py
touch tests/integration/__init__.py
touch tests/unit/__init__.py
touch tests/unit/sources/__init__.py
touch tests/unit/destinations/__init__.py
touch tests/unit/commands/__init__.py
```

- [ ] **Step 3: Verify pytest still collects the same tests**

Run:
```bash
uv run pytest --collect-only -q 2>&1 | tail -2
```
Expected: identical test count to Step 1. Empty `__init__.py` files under empty directories must not change collection.

- [ ] **Step 4: Verify the full suite still passes**

Run:
```bash
uv run pytest -q
```
Expected: green; same test count as Step 1.

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/__init__.py tests/integration/__init__.py \
        tests/unit/__init__.py tests/unit/sources/__init__.py \
        tests/unit/destinations/__init__.py tests/unit/commands/__init__.py
git commit -m "test(a): add empty tests/e2e, integration, unit directory skeletons (#40)"
```

---

### Task 2: Build `ProjectFixture` + `project` + `cli` fixtures

**Files:**
- Create: `tests/e2e/conftest.py`
- Create: `tests/e2e/test_fixture_smoke.py`

- [ ] **Step 1: Write the fixture smoke test (failing)**

Create `tests/e2e/test_fixture_smoke.py` with the following content exactly:

```python
"""Smoke tests that pin the public API of ProjectFixture + cli.

Every method/property exercised here is a load-bearing part of the Wave A
contract. If a test here fails because a method was renamed or removed,
that's a breaking change and every e2e test needs to be updated.
"""

from __future__ import annotations

from pathlib import Path


def test_project_root_is_a_directory(project):
    assert isinstance(project.root, Path)
    assert project.root.is_dir()


def test_project_paths_are_under_root(project):
    assert project.config_path == project.root / "feather.yaml"
    assert project.data_db_path == project.root / "feather_data.duckdb"
    assert project.state_db_path == project.root / "feather_state.duckdb"


def test_write_config_persists_yaml(project):
    project.write_config(
        sources=[{"type": "duckdb", "name": "s", "path": "./source.duckdb"}],
        destination={"path": "./feather_data.duckdb"},
    )
    assert project.config_path.exists()
    # The file parses back to a dict we recognise.
    import yaml
    parsed = yaml.safe_load(project.config_path.read_text())
    assert parsed["sources"][0]["name"] == "s"
    assert parsed["destination"]["path"] == "./feather_data.duckdb"


def test_write_curation_creates_discovery_json(project):
    project.write_curation([("s", "s.orders", "orders")])
    curation_path = project.root / "discovery" / "curation.json"
    assert curation_path.exists()
    import json
    manifest = json.loads(curation_path.read_text())
    assert manifest["tables"][0]["alias"] == "orders"
    assert manifest["tables"][0]["source_db"] == "s"
    assert manifest["tables"][0]["source_table"] == "s.orders"


def test_copy_fixture_file_copies_into_project(project):
    dst = project.copy_fixture("sample_erp.sqlite")
    assert dst == project.root / "sample_erp.sqlite"
    assert dst.exists()
    assert dst.stat().st_size > 0


def test_copy_fixture_directory_copies_recursively(project):
    dst = project.copy_fixture("csv_data")
    assert dst.is_dir()
    assert any(dst.iterdir())


def test_query_returns_rows_from_data_db(project):
    # Seed the data DB directly so we can exercise .query without running a pipeline.
    import duckdb
    with duckdb.connect(str(project.data_db_path)) as con:
        con.execute("CREATE TABLE t (x INT)")
        con.execute("INSERT INTO t VALUES (1), (2), (3)")
    rows = project.query("SELECT count(*) FROM t")
    assert rows == [(3,)]


def test_cli_subcommand_help_exits_zero(project, cli):
    """`feather validate --help` must exit 0 with usage text.

    We test a subcommand's --help (not the app's top-level --help) because
    --config is a per-subcommand option; the cli fixture appends it
    automatically, so invoking --help at the app level would produce the
    ambiguous `feather --help --config <path>`.
    """
    project.write_config(
        sources=[{"type": "duckdb", "name": "s", "path": "./source.duckdb"}],
        destination={"path": "./feather_data.duckdb"},
    )
    result = cli("validate", "--help")
    assert result.exit_code == 0
    assert "Usage" in result.output
```

- [ ] **Step 2: Run the smoke test and confirm it fails (red phase)**

Run:
```bash
uv run pytest tests/e2e/test_fixture_smoke.py -v
```
Expected: every test errors out with a fixture-not-found message such as:
```
fixture 'project' not found
```

This is the red phase of TDD — it confirms nothing accidentally passes before the fixture is written.

- [ ] **Step 3: Write the `ProjectFixture` class and both fixtures**

Create `tests/e2e/conftest.py` with the following content exactly:

```python
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
from typer.testing import CliRunner

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
def cli(project: ProjectFixture) -> Callable[..., object]:
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
    """
    runner = CliRunner()

    def _run(*args: str):
        return runner.invoke(app, list(args) + ["--config", str(project.config_path)])

    return _run
```

- [ ] **Step 4: Re-run the smoke test and confirm it passes (green phase)**

Run:
```bash
uv run pytest tests/e2e/test_fixture_smoke.py -v
```
Expected: all eight tests PASS.

- [ ] **Step 5: Verify the full suite is green and the count grew by exactly 8**

Run:
```bash
uv run pytest --collect-only -q 2>&1 | tail -2
uv run pytest -q
```
Expected: collected count = Task 1 baseline + 8; full suite green.

- [ ] **Step 6: Commit**

```bash
git add tests/e2e/conftest.py tests/e2e/test_fixture_smoke.py
git commit -m "test(a): add ProjectFixture + project + cli e2e fixtures (#40)

ProjectFixture represents 'a feather project on disk' with minimal helpers:
.root, .config_path, .data_db_path, .state_db_path,
.write_config(**fields), .write_curation(entries),
.copy_fixture(name), .query(sql). Paired with a 'cli' fixture that
invokes the feather Typer app via CliRunner against the project's config.

This becomes the standard harness for tests/e2e/. See tests/README.md
(following commit) for the contract."
```

---

### Task 3: Port gap S10 — `--config` absolute path from a different CWD

**Files:**
- Create: `tests/e2e/test_11_path_resolution.py`

**Bash scenario this replaces** (`scripts/hands_on_test.sh:449-457`):
After S8 (sample_erp) has run once, `cd /tmp && feather run --config $S8/feather.yaml` must exit 0 — proving CWD-independence of `--config`.

- [ ] **Step 1: Write the test**

Create `tests/e2e/test_11_path_resolution.py` with the following content exactly:

```python
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
```

- [ ] **Step 2: Run the test and confirm it passes**

Run:
```bash
uv run pytest tests/e2e/test_11_path_resolution.py -v
```
Expected: `test_config_absolute_path_from_different_cwd PASSED`. If it fails with something like "table not found" or "destination not found", the `--config` path resolution has regressed — stop and investigate (do not weaken the assertions).

- [ ] **Step 3: Verify the full suite is still green**

Run:
```bash
uv run pytest -q
```
Expected: green; count = previous baseline + 1.

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/test_11_path_resolution.py
git commit -m "test(a): port S10 (--config absolute path from different CWD) (#40)

Bash hands_on_test.sh check S10 verifies that 'cd /tmp && feather run
--config /abs/path' exits 0. Port to pytest using ProjectFixture + cli,
with monkeypatch.chdir to a foreign tmp dir to prove CWD-independence."
```

---

### Task 4: Port gap S13 — missing `feather.yaml` shows a friendly error

**Files:**
- Create: `tests/e2e/test_02_validate.py`

**Bash scenario this replaces** (`scripts/hands_on_test.sh:547-552`):
`cd $WORK_DIR && feather validate` in a directory without a `feather.yaml` must print "Config file not found" (not a Python stack trace). Regression guard for BUG-3.

- [ ] **Step 1: Write the test**

Create `tests/e2e/test_02_validate.py` with the following content exactly:

```python
"""Workflow stage 02: feather validate — config parsing and validation errors.

Scenarios in this file cover the CLI-visible behavior of `feather validate`:
friendly error messages, structural rejections, and happy-path smoke.
"""

from __future__ import annotations

from typer.testing import CliRunner

from feather_etl.cli import app


def test_validate_missing_config_shows_friendly_error(tmp_path, monkeypatch):
    """S13/BUG-3: running validate in a directory with no feather.yaml
    must print 'Config file not found', not a Python traceback.

    This test does NOT use the `project`/`cli` fixtures because the whole
    point is that there is no config at all — `cli` would pass --config
    pointing at a path that doesn't exist, which changes what's being tested.
    """
    runner = CliRunner()

    # Arrange: a completely empty directory.
    monkeypatch.chdir(tmp_path)
    assert not (tmp_path / "feather.yaml").exists()

    # Act: validate with no flags, so it uses CWD discovery.
    result = runner.invoke(app, ["validate"])

    # Assert: exits non-zero with a friendly message, not a traceback.
    assert result.exit_code != 0, result.output
    assert "Config file not found" in result.output
    assert "Traceback" not in result.output
```

- [ ] **Step 2: Run the test and confirm it passes**

Run:
```bash
uv run pytest tests/e2e/test_02_validate.py -v
```
Expected: `test_validate_missing_config_shows_friendly_error PASSED`.

- [ ] **Step 3: Verify the full suite is still green**

Run:
```bash
uv run pytest -q
```
Expected: green; count = previous baseline + 1.

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/test_02_validate.py
git commit -m "test(a): port S13 (missing feather.yaml friendly error) (#40)

Regression guard for BUG-3: running 'feather validate' in a directory
with no feather.yaml must print 'Config file not found', not a Python
traceback."
```

---

### Task 5: Port gap S16a — CSV source rejects a file path

**Files:**
- Modify: `tests/e2e/test_02_validate.py` (add one test function)

**Bash scenario this replaces** (`scripts/hands_on_test.sh:624-645`):
A config with `sources: - {type: csv, path: ./source.csv}` (pointing at a file, not a directory) must cause `feather validate` to exit non-zero.

- [ ] **Step 1: Append the test**

Append this function to the end of `tests/e2e/test_02_validate.py`:

```python


def test_csv_source_rejects_file_path(project, cli):
    """S16a: CSV source.path must be a directory, not a file.

    The CSV source type globs `path/*.csv`, so passing a file is a
    configuration error. validate must catch it (non-zero exit).
    """
    # Arrange: a file at the path (not a directory).
    csv_file = project.root / "source.csv"
    csv_file.write_text("a,b\n1,2\n")
    assert csv_file.is_file()

    project.write_config(
        sources=[{"type": "csv", "name": "csvs", "path": "./source.csv"}],
        destination={"path": "./feather_data.duckdb"},
    )

    # Act + assert: validate rejects the config.
    result = cli("validate")
    assert result.exit_code != 0, (
        f"validate unexpectedly succeeded; output was:\n{result.output}"
    )
```

- [ ] **Step 2: Run the test and confirm it passes**

Run:
```bash
uv run pytest tests/e2e/test_02_validate.py::test_csv_source_rejects_file_path -v
```
Expected: PASSED.

- [ ] **Step 3: Verify the full suite is still green**

Run:
```bash
uv run pytest -q
```
Expected: green; count = previous baseline + 1.

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/test_02_validate.py
git commit -m "test(a): port S16a (CSV source rejects file path) (#40)

CSV source type globs path/*.csv so path must be a directory. validate
must catch the misconfiguration at config-parse time."
```

---

### Task 6: Port gap S14 — error output not duplicated on stderr

**Files:**
- Create: `tests/e2e/test_10_error_handling.py`

**Bash scenario this replaces** (`scripts/hands_on_test.sh:558-582`):
Configure a table whose `source_table: erp.NOSUCH` doesn't exist; `feather run` must fail with the error text appearing on stdout only, not duplicated on stderr. Regression guard for BUG-1.

**Why subprocess is required:** `typer.testing.CliRunner` captures combined output in `result.output` and cannot distinguish stdout from stderr at the OS level (by default it merges them). This is the one test in Wave A that must shell out to real `feather`.

- [ ] **Step 1: Write the test**

Create `tests/e2e/test_10_error_handling.py` with the following content exactly:

```python
"""Workflow stage 10: error handling — isolation, exit codes, stream routing.

Scenarios here use real subprocess execution when they need OS-level stream
separation (stdout vs stderr). Tests that only care about combined output
should use the in-process `cli` fixture instead.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
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
```

- [ ] **Step 2: Run the test and confirm it passes**

Run:
```bash
uv run pytest tests/e2e/test_10_error_handling.py -v
```
Expected: PASSED. If `shutil.which("feather")` returns None, your dev env is broken; run `uv sync` and retry.

- [ ] **Step 3: Verify the full suite is still green**

Run:
```bash
uv run pytest -q
```
Expected: green; count = previous baseline + 1.

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/test_10_error_handling.py
git commit -m "test(a): port S14 (error output not duplicated on stderr) (#40)

Regression guard for BUG-1. Uses subprocess.run (not CliRunner) because
CliRunner merges stdout+stderr and cannot observe OS-level stream
separation."
```

---

### Task 7: Port gap S17 — SQLite source end-to-end

**Files:**
- Create: `tests/e2e/test_18_sources_e2e.py`

**Bash scenario this replaces** (`scripts/hands_on_test.sh:649-685`):
Configure a SQLite source pointing at `sample_erp.sqlite`, curate three tables, run `validate` (asserts "3 table" in output) and `run` (asserts "3/3" in output).

- [ ] **Step 1: Write the test**

Create `tests/e2e/test_18_sources_e2e.py` with the following content exactly:

```python
"""Workflow stage 18: non-default source types — end-to-end via CLI.

Scenarios here prove a source type works across the full validate-setup-run
cycle. They deliberately exercise the CLI (not a direct Python API call) to
catch wiring issues between the thin commands/ wrappers and the pure-core
modules.
"""

from __future__ import annotations

from tests.helpers import make_curation_entry, write_curation


def test_sqlite_source_validate_setup_run(project, cli):
    """S17: a SQLite source passes validate, setup, and run with 3/3 tables.

    The fixture `sample_erp.sqlite` contains three tables: orders, customers,
    products. After `feather run`, the destination DuckDB should have three
    populated bronze.* tables.
    """
    # Arrange.
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

    # Act: validate.
    validate_result = cli("validate")
    assert validate_result.exit_code == 0, validate_result.output
    # Hands_on S17 asserts "3 table" appears — CLI prints a count summary.
    assert "3 table" in validate_result.output, validate_result.output

    # Act: setup (creates state DB + destination schemas).
    setup_result = cli("setup")
    assert setup_result.exit_code == 0, setup_result.output

    # Act: run.
    run_result = cli("run")
    assert run_result.exit_code == 0, run_result.output
    assert "3/3" in run_result.output, run_result.output

    # Assert: destination has three bronze tables with data.
    for alias in ("orders", "customers", "products"):
        rows = project.query(f"SELECT count(*) FROM bronze.erp__{alias}")
        assert rows[0][0] > 0, f"bronze.erp__{alias} is empty"
```

- [ ] **Step 2: Run the test and confirm it passes**

Run:
```bash
uv run pytest tests/e2e/test_18_sources_e2e.py -v
```
Expected: PASSED.

> **If `"3 table"` or `"3/3"` is not found:** the CLI's summary string has
> evolved. Read `validate_result.output` and adjust the substring to match
> the current output (do not silently remove the assertion). Keep the row
> count assertions at the end — those are the strongest guarantees.

> **If bronze.erp__* table names differ:** inspect the destination DB with
> `duckdb project.data_db_path` and update the assertion to match the
> current bronze naming convention (source prefix + alias is the standard).

- [ ] **Step 3: Verify the full suite is still green**

Run:
```bash
uv run pytest -q
```
Expected: green; count = previous baseline + 1.

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/test_18_sources_e2e.py
git commit -m "test(a): port S17 (SQLite source end-to-end) (#40)

Validate + setup + run against a SQLite source, asserting 3/3 tables
extracted and bronze.erp__* populated."
```

---

### Task 8: Write `tests/README.md`

**Files:**
- Create: `tests/README.md`

- [ ] **Step 1: Write the README**

Create `tests/README.md` with the following content exactly:

````markdown
# feather-etl test suite

This directory is organised by **what a test exercises**, not by what source
file it happens to cover. The three-way layout mirrors the classic test
pyramid:

- `tests/e2e/` — CLI journeys; reading top-to-bottom = user story.
- `tests/integration/` — multi-module slices invoked via the Python API.
- `tests/unit/` — single-module tests, mirroring `src/feather_etl/`.

> **Migration status (2026-04-19):** Wave A of issue #40 is complete. The
> `e2e/`, `integration/`, and `unit/` trees exist but are mostly empty;
> most tests still live at `tests/test_*.py` and `tests/commands/test_*.py`
> and will be migrated in Waves B/C/D.

## The three-way decision rule

For any new or existing test, ask in order:

1. **Does it invoke the CLI?** (either `CliRunner.invoke(app, ...)` or
   spawns the `feather` binary via subprocess) → `tests/e2e/`. File chosen
   by workflow stage (`test_02_validate.py`, `test_04_extract_full.py`,
   etc. — see the list below).
2. **Does it exercise 2+ modules from `src/feather_etl/` through a
   pipeline-level API** (e.g., `pipeline.run_pipeline()`,
   `cache.run_cache()`)? → `tests/integration/`. File chosen by
   feature/capability (`test_incremental.py`, `test_schema_drift.py`,
   etc.).
3. **Otherwise — exercises a single module's functions/classes** →
   `tests/unit/`. File mirrors the source path:
   `src/feather_etl/sources/csv.py` → `tests/unit/sources/test_csv.py`.

`CliRunner` alone makes a test e2e even when it only tests one command;
that is intentional.

## Workflow-stage file layout (`tests/e2e/`)

Files are numbered so that reading them in order mirrors the user's
journey:

| File | Covers |
|---|---|
| `test_00_cli_structure.py` | CLI surface — commands registered, `--help` renders |
| `test_01_scaffold.py` | `feather init` |
| `test_02_validate.py` | `feather validate` |
| `test_03_discover.py` | `feather discover` (including multi-source and --explicit-name) |
| `test_04_extract_full.py` | `feather setup` + `feather run` happy path |
| `test_05_change_detection.py` | re-run skip, modify-and-re-extract |
| `test_06_incremental.py` | watermark advance, overlap, filter |
| `test_07_transforms.py` | silver views, gold materialization via CLI |
| `test_08_dq.py` | `not_null` / `unique` / `row_count` via CLI |
| `test_09_schema_drift.py` | added/removed/type-changed columns |
| `test_10_error_handling.py` | partial failure, exit codes, stream routing |
| `test_11_path_resolution.py` | CWD independence, absolute `--config` |
| `test_12_cache.py` | `feather cache` |
| `test_13_multi_source.py` | multiple `sources:` entries |
| `test_14_status.py` | `feather status` |
| `test_15_history.py` | `feather history` |
| `test_16_view.py` | `feather view` |
| `test_17_json_output.py` | `--json` flag across commands |
| `test_18_sources_e2e.py` | non-default source types (SQLite, Postgres, Excel, JSON) end-to-end |

Add new numbered files only when a wholly new workflow stage appears. If a
scenario fits an existing stage, add a test function to that file.

## `ProjectFixture` and `cli` — the e2e harness

Every test in `tests/e2e/` gets a `project` and a `cli` fixture from
`tests/e2e/conftest.py`.

### `project`: a `ProjectFixture`

A `ProjectFixture` represents "a feather project on disk, ready to use."
Its public API is small and closed:

| Attribute / method | Purpose |
|---|---|
| `project.root` | `Path` to the project directory (`tmp_path`). |
| `project.config_path` | `Path` to `feather.yaml`. |
| `project.data_db_path` | `Path` to the destination DuckDB. |
| `project.state_db_path` | `Path` to the state DuckDB. |
| `project.write_config(**fields)` | Write `fields` as YAML to `feather.yaml`. |
| `project.write_curation([(src, table, alias), ...])` | Write `discovery/curation.json` with simple entries. For richer entries call `tests.helpers.make_curation_entry` + `write_curation` directly. |
| `project.copy_fixture(name)` | Copy a file or directory from `tests/fixtures/` into the project root. Returns the destination path. |
| `project.query(sql)` | Execute `sql` against the data DB (read-only), return all rows as a list of tuples. |

### `cli`: a callable

`cli(*args)` invokes the feather Typer app via `CliRunner` and forwards
`--config` pointing at `project.config_path`. Returns the `CliRunner`
result:

```python
def test_validate_happy_path(project, cli):
    project.copy_fixture("sample_erp.sqlite")
    project.write_config(
        sources=[{"type": "sqlite", "name": "erp", "path": "./sample_erp.sqlite"}],
        destination={"path": "./feather_data.duckdb"},
    )
    project.write_curation([("erp", "orders", "orders")])
    result = cli("validate")
    assert result.exit_code == 0
```

For scenarios needing real OS-level stdout/stderr separation (CliRunner
merges streams), fall back to `subprocess.run` with the `feather` binary
— see `test_10_error_handling.py` for the pattern.

## Test style

- **Flat functions are the default.** `def test_foo(project, cli): ...` at
  module level.
- **Classes only when they add grouping value** — e.g., multiple tests
  share a `@pytest.fixture` defined inside the class, or a clear
  sub-concept exists (`class TestCsvGlobChangeDetection:`). When in doubt,
  prefer flat.
- **Never `unittest.TestCase`.** Plain `assert`, `pytest.raises`,
  `pytest.fixture`. `unittest.mock` is fine — that is the standard mock
  library.

## Regression tests and `BUG-N` labels

When a bug is discovered:

1. Write a test in the appropriate layer (`e2e/`, `integration/`, or
   `unit/`) that asserts the current wrong behaviour. Name it
   `test_BUG_<N>_<short_description>` and include a docstring:
   ```
   BUG-N: <one sentence on current wrong behaviour>.
   After fix: <one sentence on correct behaviour>.
   ```
   The test must PASS while the bug is open — i.e., it asserts the wrong
   behavior — acting as a regression guard.
2. When the bug is fixed: invert the assertion, rename the test (drop the
   `BUG-N` prefix), and — if it was in a "known bugs" group — move it into
   a positive-behavior file.

## Running

```bash
uv run pytest -q                # full suite
uv run pytest tests/e2e/ -q     # e2e layer only
uv run pytest tests/unit/ -q    # unit layer only
```
````

- [ ] **Step 2: Verify the README is valid markdown**

Run:
```bash
head -30 tests/README.md
```
Expected: well-formed output, no obvious truncation.

- [ ] **Step 3: Commit**

```bash
git add tests/README.md
git commit -m "docs(tests): add tests/README.md with three-way decision rule (#40)

Documents the e2e/integration/unit layout, the three-way decision rule
('CliRunner => e2e; multi-module Python API => integration; single
module => unit'), the ProjectFixture API, the workflow-stage file
naming convention, and the regression-test (BUG-N) pattern.

This is the written contract Waves B/C/D migrate against."
```

---

### Task 9: Create coverage-map skeleton

**Files:**
- Create: `docs/superpowers/specs/2026-04-19-test-restructure-coverage-map.md`

Wave E will fill every row of this table with the pytest test path equivalent to each bash check, then delete `scripts/hands_on_test.sh` only after the table has zero empty "Pytest test" cells.

- [ ] **Step 1: Write the skeleton**

Create `docs/superpowers/specs/2026-04-19-test-restructure-coverage-map.md` with the following content exactly:

```markdown
# Coverage map: scripts/hands_on_test.sh → pytest

Companion to [`2026-04-19-test-restructure-design.md`](2026-04-19-test-restructure-design.md).

This document is the **hard gate** before `scripts/hands_on_test.sh` is
deleted in Wave E. Every numbered check in the bash script must have a
non-empty `Pytest test path`. The gate check in the done-signal is:

```bash
# After Wave E, both must produce no output.
grep -E "^\| S[^|]+\|[^|]+\|\s*\|" docs/superpowers/specs/2026-04-19-test-restructure-coverage-map.md
```

Wave A seeds the table header only. Rows are filled incrementally during
Waves B/C/D as tests are migrated, and audited one-by-one during Wave E.

| Bash check ID | What it asserts | Pytest test path |
|---|---|---|
| S1.1 | `feather init` creates `feather.yaml` | |
| S1.2 | `feather init` creates `pyproject.toml` | |
| S1.3 | `feather init` creates `.gitignore` | |
| S1.4 | `feather init` creates `.env.example` | |
| S1.5 | `feather init` creates `README.md` | |
| S1.6 | `feather init` creates `discovery/` directory | |
| S2.* | `feather validate` — client fixture (8 checks) | |
| S3.* | `feather validate` — failure cases (8 checks) | |
| S5.* | `feather setup` + `run` + `status` — client fixture (9 checks) | |
| S6.* | Partial failure / error isolation (5 checks) | |
| S7 | `feather run` without prior setup auto-creates state and data DBs | |
| S8.* | sample_erp fixture (3 checks) | |
| S9.* | `tables/` directory merge (2 checks) | |
| S10 | `--config` absolute path from different CWD | tests/e2e/test_11_path_resolution.py::test_config_absolute_path_from_different_cwd |
| S11.* | BLOB columns / spaces in column names (3 checks) | |
| S12.* | `feather status` edge cases (3 checks) | |
| S13 | Missing `feather.yaml` shows friendly error | tests/e2e/test_02_validate.py::test_validate_missing_config_shows_friendly_error |
| S14 | Error output not duplicated on stderr | tests/e2e/test_10_error_handling.py::test_errors_not_duplicated_on_stderr |
| S15.* | CSV source validate + run (2 checks) | |
| S16a | CSV rejects file path (not directory) | tests/e2e/test_02_validate.py::test_csv_source_rejects_file_path |
| S17.* | SQLite source validate + run (2 checks) | tests/e2e/test_18_sources_e2e.py::test_sqlite_source_validate_setup_run |
| S18 | Hyphenated `target_table` rejected at validate | |
| S19 | Change detection: first run succeeds | |
| S20 | Change detection: second run (unchanged) skipped | |
| S21 | Change detection: modify source → re-extracts | |
| S22 | Change detection: touch (mtime changes, content identical) → skipped | |
| S-INCR-1 | Incremental: first run extracts all rows | |
| S-INCR-2 | Incremental: watermark is set | |
| S-INCR-3 | Incremental: second run, file unchanged → skipped | |
| S-INCR-4 | Incremental: new rows → only new rows + overlap extracted | |
| S-INCR-5 | Incremental: watermark advanced to new MAX | |
| S-INCR-6 | Incremental: destination has correct total row count | |
| S-INCR-7 | Incremental: filter excludes matching rows | |
| S-INCR-8 | Incremental: no filtered rows in destination | |

## How to read rows with a `.*`

Some bash stages bundle multiple `check()` calls under one numeric heading
(e.g., S5 has 9 checks). Wave E expands these into one row per check
before the deletion gate. Wave A lists them compactly for readability.

## Auditing

The authoritative bash stage numbering is in `scripts/hands_on_test.sh`.
Wave E audits by reading each `check "..."` call in the script and
confirming a pytest test exists that asserts the same thing.
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-04-19-test-restructure-coverage-map.md
git commit -m "docs(spec): seed hands_on_test.sh -> pytest coverage map (#40)

Skeleton table with rows for every bash check stage. Rows filled during
Waves B/C/D migrations; completeness audited in Wave E before the bash
script is deleted. Five rows already filled by the Wave A gap ports."
```

---

## Wave A completion checklist

After Task 9 commits, run:

- [ ] `uv run pytest -q` — green; test count = Task 1 baseline + 13 (8 smoke + 5 gaps).
- [ ] `bash scripts/hands_on_test.sh` — still 61/61 PASS (we did not touch any existing code path).
- [ ] `ls tests/e2e/` — shows `__init__.py`, `conftest.py`, `test_fixture_smoke.py`, `test_02_validate.py`, `test_10_error_handling.py`, `test_11_path_resolution.py`, `test_18_sources_e2e.py`.
- [ ] `ls tests/integration tests/unit tests/unit/sources tests/unit/destinations tests/unit/commands` — each directory exists and contains only `__init__.py`.
- [ ] `test -f tests/README.md` — exists.
- [ ] `test -f docs/superpowers/specs/2026-04-19-test-restructure-coverage-map.md` — exists.
- [ ] `git log --oneline feat/test-restructure ^main | wc -l` — 9 commits (one per task).
- [ ] `grep -l typer src/feather_etl/*.py | grep -v cli.py` — no output (post-#43 pure-core invariant still holds; Wave A did not touch `src/`, but worth a final check).

When every checkbox is ticked, Wave A is complete. Return to brainstorming
to plan Wave B (migrate e2e tests).

---

## Self-review notes

**Spec coverage for Wave A's slice:**
- Directory skeleton (spec §"Three-layer architecture") → Task 1 ✅
- `ProjectFixture` + `cli` (spec §"`ProjectFixture` and `cli` fixtures") → Task 2 ✅
- Gap test S10 → Task 3 ✅
- Gap test S13 → Task 4 ✅
- Gap test S16a → Task 5 ✅
- Gap test S14 → Task 6 ✅
- Gap test S17 → Task 7 ✅
- `tests/README.md` (spec §"Documentation to update") → Task 8 ✅
- Coverage-map skeleton (spec §"Coverage-equivalence proof") → Task 9 ✅
- Waves B/C/D/E are explicitly deferred to their own plans.

**No placeholders:** every code block above is complete and runnable; no
"TBD", no "similar to Task N", no "add appropriate error handling".

**Type consistency:** `ProjectFixture` methods (`write_config`,
`write_curation`, `copy_fixture`, `query`) match Task 2's smoke tests,
Task 3's SQLite scenario, Task 5's CSV scenario, and Task 7's full
end-to-end. `cli` is a callable; its return value is used via
`result.exit_code` and `result.output` consistently.
