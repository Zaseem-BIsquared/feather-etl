# Thin-CLI Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `commands/discover.py`, `setup.py`, `validate.py`, `status.py`, `history.py` into thin Typer wrappers, with their orchestration extracted into pure top-level modules in `src/feather_etl/`. Behavior-preserving — every CLI invocation produces byte-identical output and exit codes.

**Architecture:** For each command, split into two layers. The top-level `<name>.py` module owns orchestration, returns dataclass results (or raises domain exceptions for fatal preconditions), and never imports `typer`. The `commands/<name>.py` module is a thin Typer wrapper that handles flag parsing, prompts, output formatting, and exit-code translation. The pattern is already proven by `commands/run.py` ↔ `pipeline.py` and `commands/cache.py` ↔ `cache.py`.

**Tech Stack:** Python 3.10+, Typer (CLI), DuckDB (state + destination), pytest + `typer.testing.CliRunner` (CLI tests), pytest with real fixtures (core unit tests, no `CliRunner`), `uv` for dep management.

**Spec:** `docs/superpowers/specs/2026-04-19-thin-cli-refactor-design.md`
**Issue:** [#43](https://github.com/siraj-samsudeen/feather-etl/issues/43)

---

## Preconditions

- [ ] **Run both test suites and confirm green before any edits.**

Run: `uv run pytest -q`
Expected: all tests pass (currently ~653 per `CLAUDE.md`).

Run: `bash scripts/hands_on_test.sh`
Expected: all 61 checks pass.

If anything is red before you start, stop and surface it — do not proceed.

---

## File structure

**New files:**

| Path | Responsibility |
|---|---|
| `src/feather_etl/exceptions.py` | Shared domain exceptions (`StateDBMissingError`). |
| `src/feather_etl/history.py` | `load_history()` — wraps `StateManager.get_history()` with the "no DB" precondition. |
| `src/feather_etl/status.py` | `load_status()` — wraps `StateManager.get_status()` with the "no DB" precondition. |
| `src/feather_etl/validate.py` | `run_validate()` + `ValidateReport` + `SourceCheckResult`. Iterates sources, calls `source.check()`, returns a report. |
| `src/feather_etl/setup.py` | `run_setup()` + `SetupResult`. Initializes state DB, creates schemas, runs transforms. |
| `src/feather_etl/discover.py` | `detect_renames_for_sources()`, `apply_rename_decision()`, `run_discover()` + `DiscoverReport`, `SourceDiscoveryResult`, `RenameDetection`. Pure orchestration with rename phase split out. |
| `tests/test_core_module_purity.py` | Parametrized assertion that no pure-core module imports `typer`. |
| `tests/test_history_core.py` | Direct unit tests for `load_history()`. No `CliRunner`. |
| `tests/test_status_core.py` | Direct unit tests for `load_status()`. No `CliRunner`. |
| `tests/test_validate_core.py` | Direct unit tests for `run_validate()`. No `CliRunner`. |
| `tests/test_setup_core.py` | Direct unit tests for `run_setup()`. No `CliRunner`. |
| `tests/test_discover_core.py` | Direct unit tests for the three discover top-level functions. No `CliRunner`. |

**Modified files:**

| Path | Change |
|---|---|
| `src/feather_etl/commands/history.py` | Shrink from 75 → ~40 lines; delegate to `feather_etl.history.load_history`. |
| `src/feather_etl/commands/status.py` | Shrink from 68 → ~40 lines; delegate to `feather_etl.status.load_status`. |
| `src/feather_etl/commands/validate.py` | Shrink from 66 → ~40 lines; delegate to `feather_etl.validate.run_validate`. |
| `src/feather_etl/commands/setup.py` | Shrink from 105 → ~50 lines; delegate to `feather_etl.setup.run_setup`. |
| `src/feather_etl/commands/discover.py` | Shrink from 274 → ~80 lines; delegate to `feather_etl.discover.{detect_renames_for_sources, apply_rename_decision, run_discover}`. |

**Untouched (must not edit):** `cli.py`, `commands/_common.py`, `commands/cache.py`, `commands/run.py`, `commands/init.py`, `commands/view.py`, `pipeline.py`, `cache.py`, `state.py`, `config.py`, `init_wizard.py`, `viewer_server.py`, `output.py`, all `sources/*`, `destinations/*`, `transforms.py`. (Exception: if Task 3's purity test surfaces an unexpected `typer` import in `viewer_server.py` or `init_wizard.py`, remove it in the same commit.)

---

## Task 1: Extract `history` core

**Files:**
- Create: `src/feather_etl/exceptions.py`
- Create: `src/feather_etl/history.py`
- Create: `tests/test_history_core.py`
- Modify: `src/feather_etl/commands/history.py` (shrink to thin wrapper)

- [ ] **Step 1.1: Write failing test for `load_history` happy path**

Create `tests/test_history_core.py` with the following content:

```python
"""Direct unit tests for feather_etl.history.load_history()."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest


def _make_state_with_runs(state_path: Path) -> None:
    """Create a state DB and insert two run rows."""
    from feather_etl.state import StateManager

    sm = StateManager(state_path)
    sm.init_state()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    sm.record_run(
        run_id="run-1",
        table_name="orders",
        started_at=now,
        ended_at=now,
        status="success",
        rows_loaded=10,
    )
    sm.record_run(
        run_id="run-2",
        table_name="customers",
        started_at=now,
        ended_at=now,
        status="success",
        rows_loaded=5,
    )


class TestLoadHistory:
    def test_returns_rows_from_state_db(self, tmp_path: Path):
        from feather_etl.history import load_history

        state_path = tmp_path / "feather_state.duckdb"
        _make_state_with_runs(state_path)

        rows = load_history(state_path)

        assert len(rows) == 2
        assert {r["table_name"] for r in rows} == {"orders", "customers"}
        assert all(r["status"] == "success" for r in rows)

    def test_filters_by_table_name(self, tmp_path: Path):
        from feather_etl.history import load_history

        state_path = tmp_path / "feather_state.duckdb"
        _make_state_with_runs(state_path)

        rows = load_history(state_path, table="orders")

        assert len(rows) == 1
        assert rows[0]["table_name"] == "orders"

    def test_respects_limit(self, tmp_path: Path):
        from feather_etl.history import load_history

        state_path = tmp_path / "feather_state.duckdb"
        _make_state_with_runs(state_path)

        rows = load_history(state_path, limit=1)

        assert len(rows) == 1


class TestLoadHistoryPreconditions:
    def test_raises_state_db_missing_when_no_db(self, tmp_path: Path):
        from feather_etl.exceptions import StateDBMissingError
        from feather_etl.history import load_history

        with pytest.raises(StateDBMissingError):
            load_history(tmp_path / "missing.duckdb")
```

- [ ] **Step 1.2: Run test to verify it fails**

Run: `uv run pytest tests/test_history_core.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'feather_etl.history'` (or `feather_etl.exceptions`).

- [ ] **Step 1.3: Create `exceptions.py`**

Create `src/feather_etl/exceptions.py`:

```python
"""Shared domain exceptions for feather-etl core modules."""

from __future__ import annotations


class StateDBMissingError(Exception):
    """Raised when an operation requires the state DB but it does not exist on disk."""
```

- [ ] **Step 1.4: Create `history.py`**

Create `src/feather_etl/history.py`:

```python
"""`feather history` core — orchestration without Typer."""

from __future__ import annotations

from pathlib import Path

from feather_etl.exceptions import StateDBMissingError


def load_history(
    state_path: Path,
    *,
    table: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Return recent run history rows from the state DB.

    Raises ``StateDBMissingError`` if the state DB does not exist.
    """
    if not state_path.exists():
        raise StateDBMissingError(str(state_path))

    from feather_etl.state import StateManager

    sm = StateManager(state_path)
    return sm.get_history(table_name=table, limit=limit)
```

- [ ] **Step 1.5: Run test to verify it passes**

Run: `uv run pytest tests/test_history_core.py -v`
Expected: 4 passed.

- [ ] **Step 1.6: Rewrite `commands/history.py` as thin wrapper**

Replace `src/feather_etl/commands/history.py` with:

```python
"""`feather history` command — thin Typer wrapper over feather_etl.history."""

from __future__ import annotations

from pathlib import Path

import typer

from feather_etl.commands._common import (
    _is_json,
    _load_and_validate,
)
from feather_etl.exceptions import StateDBMissingError
from feather_etl.history import load_history
from feather_etl.output import emit


def history(
    ctx: typer.Context,
    config: Path = typer.Option("feather.yaml", "--config"),
    table: str | None = typer.Option(None, "--table", help="Filter by table name."),
    limit: int = typer.Option(20, "--limit", help="Maximum number of runs to show."),
) -> None:
    """Show recent run history."""
    cfg = _load_and_validate(config)
    state_path = cfg.config_dir / "feather_state.duckdb"

    try:
        rows = load_history(state_path, table=table, limit=limit)
    except StateDBMissingError:
        typer.echo("No state DB found. Run 'feather run' first.", err=True)
        raise typer.Exit(code=1)

    if not rows:
        if not _is_json(ctx):
            typer.echo("No runs recorded yet.")
        return

    if _is_json(ctx):
        emit(
            [
                {
                    "run_id": row["run_id"],
                    "table_name": row["table_name"],
                    "started_at": str(row.get("started_at", "")),
                    "ended_at": str(row.get("ended_at", "")),
                    "status": row["status"],
                    "rows_loaded": row.get("rows_loaded"),
                    "error_message": row.get("error_message"),
                }
                for row in rows
            ],
            json_mode=True,
        )
    else:
        typer.echo(
            f"{'Table':<30} {'Status':<12} {'Rows':<10} {'Started':<28} {'Run ID'}"
        )
        typer.echo("-" * 100)
        for row in rows:
            typer.echo(
                f"{row['table_name']:<30} {row['status']:<12} "
                f"{row.get('rows_loaded', '-') or '-'!s:<10} "
                f"{str(row.get('started_at', '-')):<28} {row.get('run_id', '-')}"
            )
            if row.get("error_message"):
                error = str(row["error_message"])
                if len(error) > 80:
                    error = error[:77] + "..."
                typer.echo(f"  Error: {error}")


def register(app: typer.Typer) -> None:
    app.command(name="history")(history)
```

- [ ] **Step 1.7: Run full test suite**

Run: `uv run pytest -q`
Expected: all tests pass (now ~657 — gained 4 from `test_history_core.py`).

- [ ] **Step 1.8: Commit**

```bash
git add src/feather_etl/exceptions.py src/feather_etl/history.py \
        src/feather_etl/commands/history.py tests/test_history_core.py
git commit -m "refactor(history): extract pure core into feather_etl.history (#43)

Split commands/history.py into a thin Typer wrapper that delegates
to feather_etl.history.load_history(). Introduce
feather_etl.exceptions.StateDBMissingError as the precondition
exception, reused by status in the next task.

The wrapper preserves exact CLI behavior: same prompts, same error
messages, same exit codes, same JSON output. Verified by the existing
tests/commands/test_history.py suite plus four new direct unit tests
in tests/test_history_core.py that exercise the core without
CliRunner."
```

---

## Task 2: Extract `status` core

**Files:**
- Create: `src/feather_etl/status.py`
- Create: `tests/test_status_core.py`
- Modify: `src/feather_etl/commands/status.py` (shrink to thin wrapper)

- [ ] **Step 2.1: Write failing test for `load_status`**

Create `tests/test_status_core.py`:

```python
"""Direct unit tests for feather_etl.status.load_status()."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest


def _make_state_with_runs(state_path: Path) -> None:
    """Create a state DB and insert run rows for two tables."""
    from feather_etl.state import StateManager

    sm = StateManager(state_path)
    sm.init_state()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    sm.record_run(
        run_id="run-1",
        table_name="orders",
        started_at=now,
        ended_at=now,
        status="success",
        rows_loaded=10,
    )
    sm.record_run(
        run_id="run-2",
        table_name="customers",
        started_at=now,
        ended_at=now,
        status="success",
        rows_loaded=5,
    )


class TestLoadStatus:
    def test_returns_rows_for_each_table(self, tmp_path: Path):
        from feather_etl.status import load_status

        state_path = tmp_path / "feather_state.duckdb"
        _make_state_with_runs(state_path)

        rows = load_status(state_path)

        assert {r["table_name"] for r in rows} == {"orders", "customers"}

    def test_returns_empty_list_when_no_runs(self, tmp_path: Path):
        from feather_etl.state import StateManager
        from feather_etl.status import load_status

        state_path = tmp_path / "feather_state.duckdb"
        sm = StateManager(state_path)
        sm.init_state()

        rows = load_status(state_path)

        assert rows == []


class TestLoadStatusPreconditions:
    def test_raises_state_db_missing_when_no_db(self, tmp_path: Path):
        from feather_etl.exceptions import StateDBMissingError
        from feather_etl.status import load_status

        with pytest.raises(StateDBMissingError):
            load_status(tmp_path / "missing.duckdb")
```

- [ ] **Step 2.2: Run test to verify it fails**

Run: `uv run pytest tests/test_status_core.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'feather_etl.status'`.

- [ ] **Step 2.3: Create `status.py`**

Create `src/feather_etl/status.py`:

```python
"""`feather status` core — orchestration without Typer."""

from __future__ import annotations

from pathlib import Path

from feather_etl.exceptions import StateDBMissingError


def load_status(state_path: Path) -> list[dict]:
    """Return per-table last-run status rows from the state DB.

    Raises ``StateDBMissingError`` if the state DB does not exist.
    """
    if not state_path.exists():
        raise StateDBMissingError(str(state_path))

    from feather_etl.state import StateManager

    sm = StateManager(state_path)
    return sm.get_status()
```

- [ ] **Step 2.4: Run test to verify it passes**

Run: `uv run pytest tests/test_status_core.py -v`
Expected: 3 passed.

- [ ] **Step 2.5: Rewrite `commands/status.py` as thin wrapper**

Replace `src/feather_etl/commands/status.py` with:

```python
"""`feather status` command — thin Typer wrapper over feather_etl.status."""

from __future__ import annotations

from pathlib import Path

import typer

from feather_etl.commands._common import (
    _is_json,
    _load_and_validate,
)
from feather_etl.exceptions import StateDBMissingError
from feather_etl.output import emit
from feather_etl.status import load_status


def status(
    ctx: typer.Context, config: Path = typer.Option("feather.yaml", "--config")
) -> None:
    """Show last run status for all tables."""
    cfg = _load_and_validate(config)
    state_path = cfg.config_dir / "feather_state.duckdb"

    try:
        rows = load_status(state_path)
    except StateDBMissingError:
        typer.echo("No state DB found. Run 'feather setup' first.", err=True)
        raise typer.Exit(code=1)

    if not rows:
        if _is_json(ctx):
            return
        typer.echo("No runs recorded yet.")
        return

    if _is_json(ctx):
        emit(
            [
                {
                    "table_name": row["table_name"],
                    "last_run_at": str(row.get("ended_at", "")),
                    "status": row["status"],
                    "watermark": row.get("watermark"),
                    "rows_loaded": row.get("rows_loaded"),
                }
                for row in rows
            ],
            json_mode=True,
        )
    else:
        typer.echo(f"{'Table':<30} {'Status':<12} {'Rows':<10} {'Last Run'}")
        typer.echo("-" * 75)
        for row in rows:
            typer.echo(
                f"{row['table_name']:<30} {row['status']:<12} "
                f"{row.get('rows_loaded', '-'):<10} {row.get('ended_at', '-')}"
            )
            if row["status"] == "failure" and row.get("error_message"):
                error = str(row["error_message"])
                if len(error) > 80:
                    error = error[:77] + "..."
                typer.echo(f"  Error: {error}")


def register(app: typer.Typer) -> None:
    app.command(name="status")(status)
```

- [ ] **Step 2.6: Run full test suite**

Run: `uv run pytest -q`
Expected: all tests pass (now ~660).

- [ ] **Step 2.7: Commit**

```bash
git add src/feather_etl/status.py src/feather_etl/commands/status.py \
        tests/test_status_core.py
git commit -m "refactor(status): extract pure core into feather_etl.status (#43)

Mirror of Task 1 for the status command. Reuses StateDBMissingError
from feather_etl.exceptions. The wrapper preserves the exact
'No state DB found. Run feather setup first.' message and exit code
from the existing implementation."
```

---

## Task 3: Add core-module purity test

**Files:**
- Create: `tests/test_core_module_purity.py`

This task encodes the issue's "no `typer` import in core modules" constraint as an automated, regression-proof test instead of a manual `grep` check. Subsequent tasks add their new module to the parametrize list.

- [ ] **Step 3.1: Write the purity test**

Create `tests/test_core_module_purity.py`:

```python
"""Purity test: pure-core modules must not import Typer.

The split between `commands/<name>.py` (Typer-aware CLI wrapper) and
`<name>.py` (pure orchestration) is a load-bearing architectural
constraint enforced here. If you find yourself wanting to add `typer`
to a module in this list, the split is wrong — push the Typer concern
back into the corresponding `commands/<name>.py` wrapper instead.
"""

from __future__ import annotations

import importlib
import inspect

import pytest

CORE_MODULES = [
    "feather_etl.pipeline",
    "feather_etl.cache",
    "feather_etl.viewer_server",
    "feather_etl.init_wizard",
    "feather_etl.exceptions",
    "feather_etl.history",
    "feather_etl.status",
]


@pytest.mark.parametrize("module_name", CORE_MODULES)
def test_core_module_does_not_import_typer(module_name: str) -> None:
    module = importlib.import_module(module_name)
    source = inspect.getsource(module)
    assert "import typer" not in source, (
        f"{module_name} must not import typer — push the Typer concern "
        f"into the corresponding commands/<name>.py wrapper."
    )
    assert "from typer" not in source, (
        f"{module_name} must not import from typer — push the Typer concern "
        f"into the corresponding commands/<name>.py wrapper."
    )
```

- [ ] **Step 3.2: Run the purity test**

Run: `uv run pytest tests/test_core_module_purity.py -v`
Expected: 7 passed.

If `viewer_server` or `init_wizard` fails the test, remove the offending `import typer` / `from typer` line in the same commit. (Confirmed at plan-writing time: neither imports typer, so this should pass cleanly.)

- [ ] **Step 3.3: Run full test suite**

Run: `uv run pytest -q`
Expected: all tests pass (now ~667 — gained 7 parametrized cases).

- [ ] **Step 3.4: Commit**

```bash
git add tests/test_core_module_purity.py
git commit -m "test(core): assert pure-core modules do not import typer (#43)

Encode the issue's 'no typer in <name>.py' constraint as an
automated parametrized test, replacing the manual grep check in
the issue's done-when criteria. Initial parametrize list covers all
existing pure-core modules (pipeline, cache, viewer_server,
init_wizard, exceptions, history, status). Subsequent refactors
add their new core module to the list as part of the same commit."
```

---

## Task 4: Verify `init` is already conformant

**Files:** None modified (verification-only task).

This task confirms that `commands/init.py`'s only non-Typer logic is the project-name prompt and dir-exists guard, and that those belong in the CLI (UX/overwrite-prevention concern, not a scaffolding correctness rule). `init_wizard.scaffold_project()` should remain callable from any context without surprise prompts. The purity test from Task 3 already asserts `init_wizard` has no `typer` import.

- [ ] **Step 4.1: Read `commands/init.py` and `init_wizard.py`**

Open both files. Verify:
  - `commands/init.py` consists of: optional `typer.prompt` for project name, `Path(...).exists()` check with directory-not-empty check, call to `init_wizard.scaffold_project()`, JSON-or-text output, register function. ~44 lines total.
  - `init_wizard.py` exposes `scaffold_project(project_path: Path) -> list[str]` with no Typer dependency.

- [ ] **Step 4.2: Decide whether any change is needed**

The dir-exists guard (`if non_hidden: typer.echo(...) raise typer.Exit(1)`) is a UX decision: "don't silently overwrite a non-empty directory." Pushing it into `init_wizard.scaffold_project()` would force a non-CLI caller (future MCP/library) to also raise on non-empty dirs, which is an unwanted policy. **Leave it in the CLI.**

The `typer.prompt` for project name when no positional arg is given is also CLI-only (no equivalent for non-interactive callers). **Leave it in the CLI.**

- [ ] **Step 4.3: Outcome**

- If no tidy-up surfaces (expected outcome based on plan-writing-time review): **skip the commit.** Note in PR description: "Task 4 (init verify): no changes — `commands/init.py` is already a thin wrapper, `init_wizard.scaffold_project()` is already pure, and the dir-exists/prompt logic correctly stays in the CLI as a UX concern."
- If a tidy-up surfaces during execution, commit it with message `refactor(init): <one-line description> (#43)`.

---

## Task 5: Extract `validate` core

**Files:**
- Create: `src/feather_etl/validate.py`
- Create: `tests/test_validate_core.py`
- Modify: `src/feather_etl/commands/validate.py` (shrink to thin wrapper)
- Modify: `tests/test_core_module_purity.py` (add `feather_etl.validate` to parametrize list)

- [ ] **Step 5.1: Write failing tests for `run_validate`**

Create `tests/test_validate_core.py`:

```python
"""Direct unit tests for feather_etl.validate.run_validate()."""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from tests.conftest import FIXTURES_DIR


def _make_sqlite_project(tmp_path: Path, *, valid_path: bool = True) -> Path:
    """Build a minimal feather project with a SQLite source. Returns config path."""
    if valid_path:
        shutil.copy2(FIXTURES_DIR / "sample_erp.sqlite", tmp_path / "source.sqlite")
        source_path = "./source.sqlite"
    else:
        source_path = "./missing.sqlite"

    config = {
        "sources": [{"type": "sqlite", "path": source_path}],
        "destination": {"path": "./feather_data.duckdb"},
        "tables": [
            {
                "name": "orders",
                "source_table": "orders",
                "target_table": "bronze.orders",
                "strategy": "full",
            }
        ],
    }
    config_path = tmp_path / "feather.yaml"
    config_path.write_text(yaml.dump(config))
    return config_path


class TestRunValidate:
    def test_reports_each_source_status_when_all_ok(self, tmp_path: Path):
        from feather_etl.config import load_config
        from feather_etl.validate import run_validate

        cfg = load_config(_make_sqlite_project(tmp_path))
        report = run_validate(cfg)

        assert report.all_ok is True
        assert report.tables_count == 1
        assert len(report.sources) == 1
        assert report.sources[0].type == "sqlite"
        assert report.sources[0].ok is True
        assert report.sources[0].error is None

    def test_returns_all_ok_false_when_any_source_check_fails(self, tmp_path: Path):
        from feather_etl.config import load_config
        from feather_etl.validate import run_validate

        cfg = load_config(_make_sqlite_project(tmp_path, valid_path=False))
        report = run_validate(cfg)

        assert report.all_ok is False
        assert report.sources[0].ok is False

    def test_propagates_last_error_for_failed_sources(self, tmp_path: Path):
        from feather_etl.config import load_config
        from feather_etl.validate import run_validate

        cfg = load_config(_make_sqlite_project(tmp_path, valid_path=False))
        report = run_validate(cfg)

        assert report.sources[0].error is not None
        assert report.sources[0].error != ""

    def test_label_uses_path_for_file_sources(self, tmp_path: Path):
        from feather_etl.config import load_config
        from feather_etl.validate import run_validate

        cfg = load_config(_make_sqlite_project(tmp_path))
        report = run_validate(cfg)

        # File-based sources expose `path` — the label should be the path.
        assert "source.sqlite" in str(report.sources[0].label)
```

- [ ] **Step 5.2: Run tests to verify they fail**

Run: `uv run pytest tests/test_validate_core.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'feather_etl.validate'`.

- [ ] **Step 5.3: Create `validate.py`**

Create `src/feather_etl/validate.py`:

```python
"""`feather validate` core — orchestration without Typer."""

from __future__ import annotations

from dataclasses import dataclass

from feather_etl.config import FeatherConfig


@dataclass
class SourceCheckResult:
    """Connection-check result for a single source."""

    type: str
    label: str          # path or host, whichever the source exposes; "configured" otherwise
    ok: bool
    error: str | None   # source._last_error when ok is False


@dataclass
class ValidateReport:
    """Result of running `feather validate` against a loaded config."""

    sources: list[SourceCheckResult]
    tables_count: int
    all_ok: bool


def run_validate(cfg: FeatherConfig) -> ValidateReport:
    """Test connection for each configured source. Pure read; no side effects."""
    results: list[SourceCheckResult] = []
    for source in cfg.sources:
        ok = source.check()
        label = (
            getattr(source, "path", None)
            or getattr(source, "host", None)
            or "configured"
        )
        error = getattr(source, "_last_error", None) if not ok else None
        results.append(
            SourceCheckResult(
                type=source.type,
                label=str(label),
                ok=ok,
                error=error,
            )
        )

    return ValidateReport(
        sources=results,
        tables_count=len(cfg.tables),
        all_ok=all(r.ok for r in results),
    )
```

- [ ] **Step 5.4: Run tests to verify they pass**

Run: `uv run pytest tests/test_validate_core.py -v`
Expected: 4 passed.

- [ ] **Step 5.5: Rewrite `commands/validate.py` as thin wrapper**

Replace `src/feather_etl/commands/validate.py` with:

```python
"""`feather validate` command — thin Typer wrapper over feather_etl.validate."""

from __future__ import annotations

from pathlib import Path

import typer

from feather_etl.commands._common import (
    _is_json,
    _load_and_validate,
)
from feather_etl.output import emit_line
from feather_etl.validate import run_validate


def validate(
    ctx: typer.Context, config: Path = typer.Option("feather.yaml", "--config")
) -> None:
    """Validate config, test source connection, and write feather_validation.json."""
    cfg = _load_and_validate(config)

    report = run_validate(cfg)

    if not _is_json(ctx):
        for r in report.sources:
            conn_status = "connected" if r.ok else "FAILED"
            typer.echo(f"  Source: {r.type} ({r.label}) — {conn_status}")
            if not r.ok and r.error:
                typer.echo(f"    Details: {r.error}", err=True)

    if _is_json(ctx):
        emit_line(
            {
                "valid": True,
                "tables_count": report.tables_count,
                "source_type": cfg.sources[0].type,
                "destination": str(cfg.destination.path),
                "mode": cfg.mode,
                "source_connected": report.all_ok,
            },
            json_mode=True,
        )
    else:
        typer.echo(f"Config valid: {report.tables_count} table(s)")
        typer.echo(f"  Destination: {cfg.destination.path}")
        typer.echo(f"  State: {cfg.config_dir / 'feather_state.duckdb'}")
        for t in cfg.tables:
            typer.echo(f"  Table: {t.name} → {t.target_table} ({t.strategy})")

    if not report.all_ok:
        typer.echo("Source connection failed.", err=True)
        raise typer.Exit(code=2)


def register(app: typer.Typer) -> None:
    app.command(name="validate")(validate)
```

- [ ] **Step 5.6: Add `feather_etl.validate` to the purity test**

Edit `tests/test_core_module_purity.py`. Find the `CORE_MODULES` list and add `"feather_etl.validate"` after `"feather_etl.status"`:

```python
CORE_MODULES = [
    "feather_etl.pipeline",
    "feather_etl.cache",
    "feather_etl.viewer_server",
    "feather_etl.init_wizard",
    "feather_etl.exceptions",
    "feather_etl.history",
    "feather_etl.status",
    "feather_etl.validate",
]
```

- [ ] **Step 5.7: Run full test suite**

Run: `uv run pytest -q`
Expected: all tests pass (now ~671 — gained 4 from `test_validate_core.py` plus 1 new purity case). Specifically check `tests/commands/test_validate.py` is still green — it exercises CLI behavior end-to-end and is the contract for "no behavior change."

- [ ] **Step 5.8: Commit**

```bash
git add src/feather_etl/validate.py src/feather_etl/commands/validate.py \
        tests/test_validate_core.py tests/test_core_module_purity.py
git commit -m "refactor(validate): extract pure core into feather_etl.validate (#43)

First dataclass-shaped core. ValidateReport carries per-source
connection results, table count, and aggregate all_ok flag. The
wrapper preserves exact CLI output (per-source connection lines,
'Config valid: N table(s)' header, 'Source connection failed.'
error, exit code 2 on failure) and JSON shape.

Added feather_etl.validate to the core-module purity test."
```

---

## Task 6: Extract `setup` core

**Files:**
- Create: `src/feather_etl/setup.py`
- Create: `tests/test_setup_core.py`
- Modify: `src/feather_etl/commands/setup.py` (shrink to thin wrapper)
- Modify: `tests/test_core_module_purity.py` (add `feather_etl.setup`)

- [ ] **Step 6.1: Write failing tests for `run_setup`**

Create `tests/test_setup_core.py`:

```python
"""Direct unit tests for feather_etl.setup.run_setup()."""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from tests.conftest import FIXTURES_DIR


def _make_project(tmp_path: Path, *, mode: str | None = None) -> Path:
    """Build a minimal feather project. Returns config path."""
    shutil.copy2(FIXTURES_DIR / "sample_erp.sqlite", tmp_path / "source.sqlite")
    config: dict = {
        "sources": [{"type": "sqlite", "path": "./source.sqlite"}],
        "destination": {"path": "./feather_data.duckdb"},
        "tables": [
            {
                "name": "orders",
                "source_table": "orders",
                "target_table": "bronze.orders",
                "strategy": "full",
            }
        ],
    }
    if mode is not None:
        config["mode"] = mode
    config_path = tmp_path / "feather.yaml"
    config_path.write_text(yaml.dump(config))
    return config_path


def _write_silver_transform(tmp_path: Path) -> None:
    """Write a tiny silver view definition that depends on bronze.orders."""
    tdir = tmp_path / "transforms" / "silver"
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / "orders_clean.sql").write_text(
        "CREATE OR REPLACE VIEW silver.orders_clean AS "
        "SELECT * FROM bronze.orders;\n"
    )


class TestRunSetup:
    def test_initializes_state_db_and_destination(self, tmp_path: Path):
        from feather_etl.config import load_config
        from feather_etl.setup import run_setup

        cfg = load_config(_make_project(tmp_path))

        result = run_setup(cfg)

        assert result.state_db_path.exists()
        assert result.destination_path == cfg.destination.path
        assert result.transform_results is None  # no transforms in this project

    def test_returns_none_transforms_when_no_transforms_found(self, tmp_path: Path):
        from feather_etl.config import load_config
        from feather_etl.setup import run_setup

        cfg = load_config(_make_project(tmp_path))
        result = run_setup(cfg)

        assert result.transform_results is None

    def test_executes_transforms_when_present(self, tmp_path: Path):
        from feather_etl.config import load_config
        from feather_etl.setup import run_setup

        config_path = _make_project(tmp_path)
        _write_silver_transform(tmp_path)
        cfg = load_config(config_path)

        result = run_setup(cfg)

        assert result.transform_results is not None
        assert len(result.transform_results) >= 1
        assert any(
            t.name == "orders_clean" and t.schema == "silver"
            for t in result.transform_results
        )
```

- [ ] **Step 6.2: Run tests to verify they fail**

Run: `uv run pytest tests/test_setup_core.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'feather_etl.setup'`.

- [ ] **Step 6.3: Create `setup.py`**

Create `src/feather_etl/setup.py`:

```python
"""`feather setup` core — orchestration without Typer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from feather_etl.config import FeatherConfig
from feather_etl.transforms import TransformResult


@dataclass
class SetupResult:
    """Result of running `feather setup` against a loaded config."""

    state_db_path: Path
    destination_path: Path
    transform_results: list[TransformResult] | None  # None if no transforms found


def run_setup(cfg: FeatherConfig) -> SetupResult:
    """Initialize state DB, create destination schemas, execute transforms.

    Returns a ``SetupResult`` describing what was created. Transforms are
    executed if any are discovered in ``<config_dir>/transforms/``. In prod
    mode, only gold transforms are executed; in dev mode, all transforms are
    executed with ``force_views=True`` (matches the prior CLI behavior).
    """
    from feather_etl.destinations.duckdb import DuckDBDestination
    from feather_etl.state import StateManager
    from feather_etl.transforms import (
        build_execution_order,
        discover_transforms,
        execute_transforms,
    )

    state_path = cfg.config_dir / "feather_state.duckdb"
    sm = StateManager(state_path)
    sm.init_state()

    dest = DuckDBDestination(path=cfg.destination.path)
    dest.setup_schemas()

    transform_results: list[TransformResult] | None = None
    transforms = discover_transforms(cfg.config_dir)
    if transforms:
        ordered = build_execution_order(transforms)
        con = dest._connect()
        try:
            if cfg.mode == "prod":
                gold_only = [t for t in ordered if t.schema == "gold"]
                transform_results = execute_transforms(con, gold_only)
            else:
                transform_results = execute_transforms(con, ordered, force_views=True)
        finally:
            con.close()

    return SetupResult(
        state_db_path=state_path,
        destination_path=cfg.destination.path,
        transform_results=transform_results,
    )
```

- [ ] **Step 6.4: Run tests to verify they pass**

Run: `uv run pytest tests/test_setup_core.py -v`
Expected: 3 passed.

- [ ] **Step 6.5: Rewrite `commands/setup.py` as thin wrapper**

Replace `src/feather_etl/commands/setup.py` with:

```python
"""`feather setup` command — thin Typer wrapper over feather_etl.setup."""

from __future__ import annotations

from pathlib import Path

import typer

from feather_etl.commands._common import (
    _is_json,
    _load_and_validate,
)
from feather_etl.output import emit_line
from feather_etl.setup import run_setup


def setup(
    ctx: typer.Context,
    config: Path = typer.Option("feather.yaml", "--config"),
    mode: str | None = typer.Option(None, "--mode"),
) -> None:
    """Preview and initialize state DB and schemas. Optional — feather run creates them automatically."""
    cfg = _load_and_validate(config, mode_override=mode)
    if not _is_json(ctx):
        typer.echo(f"Mode: {cfg.mode}")

    result = run_setup(cfg)

    if not _is_json(ctx):
        typer.echo(f"State DB initialized: {result.state_db_path}")
        typer.echo(f"Schemas created in: {result.destination_path}")

    transforms_applied = 0
    if result.transform_results is not None:
        results = result.transform_results
        transforms_applied = sum(1 for r in results if r.status == "success")

        if not _is_json(ctx):
            silver_views = sum(
                1 for r in results if r.schema == "silver" and r.status == "success"
            )
            gold_views = sum(
                1
                for r in results
                if r.schema == "gold" and r.type == "view" and r.status == "success"
            )
            gold_tables = sum(
                1
                for r in results
                if r.schema == "gold" and r.type == "table" and r.status == "success"
            )
            parts = []
            if silver_views:
                parts.append(f"{silver_views} silver view(s)")
            if gold_views:
                parts.append(f"{gold_views} gold view(s)")
            if gold_tables:
                parts.append(f"{gold_tables} gold table(s)")
            typer.echo(f"Transforms applied: {', '.join(parts)}")

            errors = [r for r in results if r.status == "error"]
            for r in errors:
                typer.echo(
                    f"  Transform error: {r.schema}.{r.name} — {r.error}", err=True
                )

    if _is_json(ctx):
        emit_line(
            {
                "state_db": str(result.state_db_path),
                "destination": str(result.destination_path),
                "schemas_created": True,
                "transforms_applied": transforms_applied,
            },
            json_mode=True,
        )


def register(app: typer.Typer) -> None:
    app.command(name="setup")(setup)
```

- [ ] **Step 6.6: Add `feather_etl.setup` to the purity test**

Edit `tests/test_core_module_purity.py`. Add `"feather_etl.setup"` to `CORE_MODULES`.

- [ ] **Step 6.7: Run full test suite**

Run: `uv run pytest -q`
Expected: all tests pass. Specifically check `tests/commands/test_setup.py` is still green.

- [ ] **Step 6.8: Commit**

```bash
git add src/feather_etl/setup.py src/feather_etl/commands/setup.py \
        tests/test_setup_core.py tests/test_core_module_purity.py
git commit -m "refactor(setup): extract pure core into feather_etl.setup (#43)

SetupResult carries the state DB path, destination path, and
optional transform results. The wrapper preserves the exact CLI
output (Mode line, State DB initialized, Schemas created in,
Transforms applied summary, per-error lines) and JSON shape
including transforms_applied count.

Mode-aware transform execution preserved exactly: prod mode runs
gold-only; dev mode runs all transforms with force_views=True.

Added feather_etl.setup to the core-module purity test."
```

---

## Task 7: Extract `discover` core (the big one)

**Files:**
- Create: `src/feather_etl/discover.py`
- Create: `tests/test_discover_core.py`
- Modify: `src/feather_etl/commands/discover.py` (shrink to thin wrapper)
- Modify: `tests/test_core_module_purity.py` (add `feather_etl.discover`)

The discover refactor splits into three pure top-level functions: `detect_renames_for_sources`, `apply_rename_decision`, `run_discover`. The CLI wrapper computes the rename decision interactively (using `typer.confirm` and the `--yes`/`--no-renames` flags) and passes pre-resolved values to `apply_rename_decision`. The core never imports `typer`, never touches stdin, and never calls `serve_and_open` (that's the CLI's job, after `run_discover` returns).

- [ ] **Step 7.1: Write failing tests for `detect_renames_for_sources`**

Create `tests/test_discover_core.py`. Start with the rename-detection tests:

```python
"""Direct unit tests for feather_etl.discover top-level functions."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from tests.conftest import FIXTURES_DIR


def _make_sqlite_project(tmp_path: Path, source_name: str | None = None) -> Path:
    """Set up a tmp SQLite feather project. Returns config path."""
    shutil.copy2(FIXTURES_DIR / "sample_erp.sqlite", tmp_path / "source.sqlite")
    source: dict = {"type": "sqlite", "path": "./source.sqlite"}
    if source_name is not None:
        source["name"] = source_name
    cfg = {
        "sources": [source],
        "destination": {"path": "./feather_data.duckdb"},
        "tables": [
            {
                "name": "orders",
                "source_table": "orders",
                "target_table": "bronze.orders",
                "strategy": "full",
            }
        ],
    }
    config_path = tmp_path / "feather.yaml"
    config_path.write_text(yaml.dump(cfg))
    return config_path


class TestDetectRenamesForSources:
    def test_returns_empty_proposals_when_state_is_empty(self, tmp_path: Path):
        from feather_etl.config import load_config
        from feather_etl.discover import detect_renames_for_sources
        from feather_etl.discover_state import DiscoverState
        from feather_etl.sources.expand import expand_db_sources

        cfg = load_config(_make_sqlite_project(tmp_path))
        state = DiscoverState.load(tmp_path)
        sources = expand_db_sources(cfg.sources)

        detection = detect_renames_for_sources(state, sources)

        assert detection.proposals == []
        assert detection.ambiguous == []

    def test_finds_rename_when_fingerprint_matches_under_new_name(
        self, tmp_path: Path
    ):
        """Rename a source in YAML; same fingerprint → proposal."""
        from feather_etl.config import load_config
        from feather_etl.discover import detect_renames_for_sources
        from feather_etl.discover_state import DiscoverState
        from feather_etl.sources.expand import expand_db_sources

        # First load with name "old_db" — record state.
        config_path = _make_sqlite_project(tmp_path, source_name="old_db")
        cfg = load_config(config_path)
        state = DiscoverState.load(tmp_path)
        sources = expand_db_sources(cfg.sources)
        # Simulate a prior successful discover under "old_db".
        from feather_etl.discover import _fingerprint_for

        state.record_ok(
            name="old_db",
            type_=sources[0].type,
            fingerprint=_fingerprint_for(sources[0]),
            table_count=1,
            output_path=tmp_path / "schemas-sqlite-old_db.json",
        )

        # Now rename source to "new_db".
        config_path = _make_sqlite_project(tmp_path, source_name="new_db")
        cfg = load_config(config_path)
        sources = expand_db_sources(cfg.sources)

        detection = detect_renames_for_sources(state, sources)

        assert detection.proposals == [("old_db", "new_db")]
        assert detection.ambiguous == []
```

- [ ] **Step 7.2: Run tests to verify they fail**

Run: `uv run pytest tests/test_discover_core.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'feather_etl.discover'`.

- [ ] **Step 7.3: Create `discover.py` skeleton — dataclasses + helpers + `detect_renames_for_sources`**

Create `src/feather_etl/discover.py`:

```python
"""`feather discover` core — orchestration without Typer.

Three pure top-level functions:

* ``detect_renames_for_sources(state, sources) -> RenameDetection``
  Pure detection. Returns proposals + ambiguous list. No I/O.

* ``apply_rename_decision(state, accepted, rejected, sources, config_dir) -> None``
  Applies a pre-resolved decision. The CLI wrapper resolves the decision
  interactively (typer.confirm + --yes / --no-renames) and calls this.

* ``run_discover(cfg, config_dir, *, refresh, retry_failed, prune) -> DiscoverReport``
  Per-source discovery loop. Assumes renames already resolved.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from feather_etl.config import FeatherConfig, schema_output_path
from feather_etl.discover_state import (
    DiscoverState,
    apply_renames,
    classify,
    detect_renames,
)


@dataclass
class RenameDetection:
    """Output of ``detect_renames_for_sources``."""

    proposals: list[tuple[str, str]] = field(default_factory=list)
    ambiguous: list[tuple[str, list[str]]] = field(default_factory=list)


@dataclass
class SourceDiscoveryResult:
    """One source's outcome from ``run_discover``."""

    name: str
    decision: str       # "new" | "retry" | "rerun" | "cached" | "skip" | "removed"
    status: str         # "succeeded" | "failed" | "cached" | "skipped" | "pruned"
    table_count: int = 0
    output_path: Path | None = None
    error: str | None = None


@dataclass
class DiscoverReport:
    """Aggregate result of ``run_discover``."""

    results: list[SourceDiscoveryResult] = field(default_factory=list)
    succeeded_count: int = 0
    failed_count: int = 0
    cached_count: int = 0
    pruned_count: int = 0
    state_last_run_at: str | None = None


def _write_schema(source, target_dir: Path) -> tuple[Path, int]:
    """Discover ``source`` and write its schema JSON. Returns (path, table_count)."""
    schemas = source.discover()
    payload = [
        {
            "table_name": s.name,
            "columns": [{"name": c[0], "type": c[1]} for c in s.columns],
        }
        for s in schemas
    ]
    out = target_dir / schema_output_path(source)
    out.write_text(json.dumps(payload, indent=2))
    return out, len(schemas)


def _fingerprint_for(source) -> str:
    """Composition per spec §6.7.

    DB sources: '<type>:<host>:<port>:<database>'. File sources: '<type>:<absolute_path>'.
    """
    if hasattr(source, "host") and source.host is not None:
        return (
            f"{source.type}:{source.host}:{source.port or ''}:{source.database or ''}"
        )
    return f"{source.type}:{Path(source.path).resolve()}"


def detect_renames_for_sources(
    state: DiscoverState,
    sources: list,
) -> RenameDetection:
    """Pure detection. Returns proposals + ambiguous list. No I/O, no prompts."""
    current_pairs = [(source.name, _fingerprint_for(source)) for source in sources]
    proposals, ambiguous = detect_renames(state=state, current=current_pairs)
    return RenameDetection(proposals=list(proposals), ambiguous=list(ambiguous))
```

- [ ] **Step 7.4: Run rename-detection tests to verify they pass**

Run: `uv run pytest tests/test_discover_core.py::TestDetectRenamesForSources -v`
Expected: 2 passed.

- [ ] **Step 7.5: Add ambiguous-rename test, then run**

Append to `tests/test_discover_core.py` inside `TestDetectRenamesForSources`:

```python
    def test_returns_ambiguous_when_multiple_state_entries_match(
        self, tmp_path: Path
    ):
        """Two stale state entries with the same fingerprint as one current
        source → ambiguous (cannot decide which old name was renamed)."""
        from feather_etl.config import load_config
        from feather_etl.discover import _fingerprint_for, detect_renames_for_sources
        from feather_etl.discover_state import DiscoverState
        from feather_etl.sources.expand import expand_db_sources

        config_path = _make_sqlite_project(tmp_path, source_name="new_db")
        cfg = load_config(config_path)
        state = DiscoverState.load(tmp_path)
        sources = expand_db_sources(cfg.sources)
        fp = _fingerprint_for(sources[0])
        state.record_ok(
            name="old_a",
            type_=sources[0].type,
            fingerprint=fp,
            table_count=1,
            output_path=tmp_path / "schemas-sqlite-old_a.json",
        )
        state.record_ok(
            name="old_b",
            type_=sources[0].type,
            fingerprint=fp,
            table_count=1,
            output_path=tmp_path / "schemas-sqlite-old_b.json",
        )

        detection = detect_renames_for_sources(state, sources)

        assert detection.proposals == []
        assert len(detection.ambiguous) == 1
        new_name, candidates = detection.ambiguous[0]
        assert new_name == "new_db"
        assert set(candidates) == {"old_a", "old_b"}
```

Run: `uv run pytest tests/test_discover_core.py::TestDetectRenamesForSources -v`
Expected: 3 passed.

- [ ] **Step 7.6: Write failing tests for `apply_rename_decision`**

Append to `tests/test_discover_core.py`:

```python
class TestApplyRenameDecision:
    def test_renames_state_and_files_for_accepted_proposals(self, tmp_path: Path):
        from feather_etl.config import load_config
        from feather_etl.discover import (
            _fingerprint_for,
            apply_rename_decision,
        )
        from feather_etl.discover_state import DiscoverState
        from feather_etl.sources.expand import expand_db_sources

        config_path = _make_sqlite_project(tmp_path, source_name="new_db")
        cfg = load_config(config_path)
        state = DiscoverState.load(tmp_path)
        sources = expand_db_sources(cfg.sources)
        fp = _fingerprint_for(sources[0])
        old_path = tmp_path / "schemas-sqlite-old_db.json"
        old_path.write_text("[]")
        state.record_ok(
            name="old_db",
            type_=sources[0].type,
            fingerprint=fp,
            table_count=1,
            output_path=old_path,
        )

        apply_rename_decision(
            state,
            accepted=[("old_db", "new_db")],
            rejected=[],
            sources=sources,
            config_dir=tmp_path,
        )

        assert "new_db" in state.sources
        assert "old_db" not in state.sources

    def test_marks_orphaned_for_rejected_proposals(self, tmp_path: Path):
        from feather_etl.config import load_config
        from feather_etl.discover import _fingerprint_for, apply_rename_decision
        from feather_etl.discover_state import DiscoverState
        from feather_etl.sources.expand import expand_db_sources

        config_path = _make_sqlite_project(tmp_path, source_name="new_db")
        cfg = load_config(config_path)
        state = DiscoverState.load(tmp_path)
        sources = expand_db_sources(cfg.sources)
        fp = _fingerprint_for(sources[0])
        state.record_ok(
            name="old_db",
            type_=sources[0].type,
            fingerprint=fp,
            table_count=1,
            output_path=tmp_path / "schemas-sqlite-old_db.json",
        )

        apply_rename_decision(
            state,
            accepted=[],
            rejected=[("old_db", "new_db")],
            sources=sources,
            config_dir=tmp_path,
        )

        assert state.sources["old_db"].get("status") == "orphaned"
```

- [ ] **Step 7.7: Run apply-rename tests — verify they fail**

Run: `uv run pytest tests/test_discover_core.py::TestApplyRenameDecision -v`
Expected: FAIL with `AttributeError` or `ImportError` for `apply_rename_decision` (not yet defined).

- [ ] **Step 7.8: Add `apply_rename_decision` to `discover.py`**

Append to `src/feather_etl/discover.py`:

```python
def apply_rename_decision(
    state: DiscoverState,
    accepted: list[tuple[str, str]],
    rejected: list[tuple[str, str]],
    sources: list,
    config_dir: Path,
) -> None:
    """Apply a pre-resolved rename decision.

    ``accepted`` proposals are applied via ``apply_renames`` (state + files
    are renamed). ``rejected`` proposals are recorded as orphaned (the new
    name is treated as a fresh source on the next discovery pass).
    """
    if accepted:
        apply_renames(
            state=state,
            renames=accepted,
            config_dir=config_dir,
            sources=sources,
        )
    for old_name, new_name in rejected:
        state.record_orphaned(
            old_name,
            note=f"rename rejected; new source discovered as {new_name}",
        )
```

- [ ] **Step 7.9: Run apply-rename tests — verify they pass**

Run: `uv run pytest tests/test_discover_core.py::TestApplyRenameDecision -v`
Expected: 2 passed.

- [ ] **Step 7.10: Write failing tests for `run_discover`**

Append to `tests/test_discover_core.py`:

```python
class TestRunDiscover:
    def test_records_succeeded_sources_with_table_counts(self, tmp_path: Path):
        from feather_etl.config import load_config
        from feather_etl.discover import run_discover

        cfg = load_config(_make_sqlite_project(tmp_path))

        report = run_discover(
            cfg,
            tmp_path,
            refresh=False,
            retry_failed=False,
            prune=False,
        )

        assert report.succeeded_count == 1
        assert report.failed_count == 0
        assert len(report.results) == 1
        r = report.results[0]
        assert r.status == "succeeded"
        assert r.table_count > 0
        assert r.output_path is not None
        assert r.output_path.exists()

    def test_records_failed_sources_with_error_message(self, tmp_path: Path):
        """Source pointing at a missing file → failed, error captured in result."""
        from feather_etl.config import load_config
        from feather_etl.discover import run_discover

        # Build config with a deliberately missing SQLite file.
        cfg_dict = {
            "sources": [{"type": "sqlite", "path": "./missing.sqlite"}],
            "destination": {"path": "./feather_data.duckdb"},
            "tables": [
                {
                    "name": "orders",
                    "source_table": "orders",
                    "target_table": "bronze.orders",
                    "strategy": "full",
                }
            ],
        }
        config_path = tmp_path / "feather.yaml"
        config_path.write_text(yaml.dump(cfg_dict))
        # discover_mode skips table validation
        cfg = load_config(config_path, validate=False)

        report = run_discover(
            cfg,
            tmp_path,
            refresh=False,
            retry_failed=False,
            prune=False,
        )

        assert report.failed_count == 1
        assert report.succeeded_count == 0
        assert report.results[0].status == "failed"
        assert report.results[0].error is not None

    def test_with_refresh_ignores_cached_state(self, tmp_path: Path):
        """A second run with refresh=True re-discovers a previously-discovered source."""
        from feather_etl.config import load_config
        from feather_etl.discover import run_discover

        cfg = load_config(_make_sqlite_project(tmp_path))

        # First run — establishes state.
        run_discover(cfg, tmp_path, refresh=False, retry_failed=False, prune=False)

        # Second run with refresh — should re-discover, not return cached.
        report = run_discover(
            cfg, tmp_path, refresh=True, retry_failed=False, prune=False
        )

        assert report.succeeded_count == 1
        assert report.cached_count == 0

    def test_second_run_without_refresh_reports_cached(self, tmp_path: Path):
        from feather_etl.config import load_config
        from feather_etl.discover import run_discover

        cfg = load_config(_make_sqlite_project(tmp_path))

        run_discover(cfg, tmp_path, refresh=False, retry_failed=False, prune=False)
        report = run_discover(
            cfg, tmp_path, refresh=False, retry_failed=False, prune=False
        )

        assert report.cached_count == 1
        assert report.succeeded_count == 0

    def test_with_prune_removes_state_and_files_for_removed_sources(
        self, tmp_path: Path
    ):
        from feather_etl.config import load_config
        from feather_etl.discover import _fingerprint_for, run_discover
        from feather_etl.discover_state import DiscoverState

        cfg = load_config(_make_sqlite_project(tmp_path))

        # Seed a state entry for a now-removed source with a file on disk.
        state = DiscoverState.load(tmp_path)
        old_path = tmp_path / "schemas-sqlite-stale.json"
        old_path.write_text("[]")
        state.record_ok(
            name="stale",
            type_="sqlite",
            fingerprint="sqlite:/non/existent",
            table_count=1,
            output_path=old_path,
        )
        state.save()

        report = run_discover(
            cfg, tmp_path, refresh=False, retry_failed=False, prune=True
        )

        assert report.pruned_count >= 1
        assert not old_path.exists()

        state = DiscoverState.load(tmp_path)
        assert "stale" not in state.sources
```

- [ ] **Step 7.11: Run `run_discover` tests — verify they fail**

Run: `uv run pytest tests/test_discover_core.py::TestRunDiscover -v`
Expected: FAIL with `AttributeError` or `ImportError` for `run_discover` (not yet defined).

- [ ] **Step 7.12: Add `run_discover` to `discover.py`**

Append to `src/feather_etl/discover.py`:

```python
def run_discover(
    cfg: FeatherConfig,
    config_dir: Path,
    *,
    refresh: bool,
    retry_failed: bool,
    prune: bool,
) -> DiscoverReport:
    """Per-source discovery loop. Assumes renames already resolved.

    The CLI wrapper is responsible for:
      * resolving rename proposals (interactive or via --yes / --no-renames)
        and calling ``apply_rename_decision`` before invoking this function;
      * exiting with code 2 on ambiguous renames (using ``RenameDetection``);
      * calling ``serve_and_open`` after this function returns.
    """
    from feather_etl.sources.expand import expand_db_sources

    state = DiscoverState.load(config_dir)
    sources = expand_db_sources(cfg.sources)

    flag: str | None = None
    if refresh:
        flag = "refresh"
    elif retry_failed:
        flag = "retry-failed"
    elif prune:
        flag = "prune"

    names = [s.name for s in sources]
    decisions = classify(state=state, current_names=names, flag=flag)

    report = DiscoverReport(state_last_run_at=state.last_run_at)

    if flag == "prune":
        for name, dec in list(decisions.items()):
            entry = state.sources.get(name)
            if dec == "removed" or (
                entry and entry.get("status") in ("orphaned", "removed")
            ):
                if entry and entry.get("output_path"):
                    target = config_dir / Path(entry["output_path"]).name
                    if target.is_file():
                        target.unlink()
                state.sources.pop(name, None)
                report.pruned_count += 1
                report.results.append(
                    SourceDiscoveryResult(
                        name=name, decision=dec, status="pruned"
                    )
                )
        state.save()
        return report

    for source in sources:
        decision = decisions.get(source.name, "new")
        fingerprint = _fingerprint_for(source)

        if decision == "cached":
            entry = state.sources[source.name]
            report.cached_count += 1
            report.results.append(
                SourceDiscoveryResult(
                    name=source.name,
                    decision=decision,
                    status="cached",
                    table_count=entry.get("table_count", 0),
                )
            )
            continue
        if decision == "skip":
            report.results.append(
                SourceDiscoveryResult(
                    name=source.name, decision=decision, status="skipped"
                )
            )
            continue

        # Source came from expand_db_sources with a pre-set error.
        if hasattr(source, "_last_error") and source._last_error:
            report.failed_count += 1
            state.record_failed(
                name=source.name,
                type_=source.type,
                fingerprint=fingerprint,
                error=source._last_error,
                host=getattr(source, "host", None),
                database=getattr(source, "database", None),
            )
            report.results.append(
                SourceDiscoveryResult(
                    name=source.name,
                    decision=decision,
                    status="failed",
                    error=source._last_error,
                )
            )
            continue

        if not source.check():
            err = getattr(source, "_last_error", "connection failed")
            report.failed_count += 1
            state.record_failed(
                name=source.name,
                type_=source.type,
                fingerprint=fingerprint,
                error=err,
                host=getattr(source, "host", None),
                database=getattr(source, "database", None),
            )
            report.results.append(
                SourceDiscoveryResult(
                    name=source.name, decision=decision, status="failed", error=err
                )
            )
            continue

        try:
            out, count = _write_schema(source, config_dir)
        except Exception as e:  # noqa: BLE001 — preserve existing broad-catch behavior
            report.failed_count += 1
            state.record_failed(
                name=source.name,
                type_=source.type,
                fingerprint=fingerprint,
                error=str(e),
                host=getattr(source, "host", None),
                database=getattr(source, "database", None),
            )
            report.results.append(
                SourceDiscoveryResult(
                    name=source.name,
                    decision=decision,
                    status="failed",
                    error=str(e),
                )
            )
            continue

        report.succeeded_count += 1
        state.record_ok(
            name=source.name,
            type_=source.type,
            fingerprint=fingerprint,
            table_count=count,
            output_path=out,
            host=getattr(source, "host", None),
            database=getattr(source, "database", None),
        )
        report.results.append(
            SourceDiscoveryResult(
                name=source.name,
                decision=decision,
                status="succeeded",
                table_count=count,
                output_path=out,
            )
        )

    # Mark state-only entries as removed (preserves prior CLI behavior).
    for name, dec in decisions.items():
        if dec == "removed" and state.sources.get(name, {}).get("status") != "orphaned":
            state.record_removed(name)

    state.save()
    return report
```

- [ ] **Step 7.13: Run `run_discover` tests — verify they pass**

Run: `uv run pytest tests/test_discover_core.py::TestRunDiscover -v`
Expected: 5 passed.

- [ ] **Step 7.14: Run all discover-core tests together**

Run: `uv run pytest tests/test_discover_core.py -v`
Expected: 10 passed (3 detection + 2 apply-rename + 5 run_discover).

- [ ] **Step 7.15: Rewrite `commands/discover.py` as thin wrapper**

Replace `src/feather_etl/commands/discover.py` with:

```python
"""`feather discover` command — thin Typer wrapper over feather_etl.discover."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from feather_etl.commands._common import _load_and_validate
from feather_etl.discover import (
    apply_rename_decision,
    detect_renames_for_sources,
    run_discover,
)
from feather_etl.discover_state import DiscoverState
from feather_etl.sources.expand import expand_db_sources
from feather_etl.viewer_server import serve_and_open


def _resolve_rename_decision(
    proposals: list[tuple[str, str]],
    *,
    yes: bool,
    no_renames: bool,
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Echo proposals and resolve --yes / --no-renames / TTY confirm.

    Returns ``(accepted, rejected)``. May raise ``typer.Exit(3)`` if the
    decision is required but stdin is not a TTY.
    """
    proposal_err = not sys.stdin.isatty()
    for old_name, new_name in proposals:
        typer.echo(
            f"  Rename inferred: {old_name} -> {new_name}",
            err=proposal_err,
        )

    if no_renames:
        for old_name, new_name in proposals:
            typer.echo(f"  Kept {old_name} orphaned; treating {new_name} as new")
        return [], list(proposals)

    if yes:
        return list(proposals), []

    if sys.stdin.isatty():
        if typer.confirm("Accept all?", default=True):
            return list(proposals), []
        for old_name, new_name in proposals:
            typer.echo(f"  Kept {old_name} orphaned; treating {new_name} as new")
        return [], list(proposals)

    typer.echo(
        "Rename confirmation required in non-interactive mode. "
        "Re-run with --yes to accept or --no-renames to reject.",
        err=True,
    )
    raise typer.Exit(code=3)


def discover(
    config: Path = typer.Option("feather.yaml", "--config"),
    refresh: bool = typer.Option(
        False,
        "--refresh",
        help="Re-run discovery for every source, ignoring cached state.",
    ),
    retry_failed: bool = typer.Option(
        False, "--retry-failed", help="Only retry sources that previously failed."
    ),
    prune: bool = typer.Option(
        False,
        "--prune",
        help="Delete state entries and JSON files for removed/orphaned sources.",
    ),
    yes: bool = typer.Option(False, "--yes", help="Auto-accept inferred renames."),
    no_renames: bool = typer.Option(
        False,
        "--no-renames",
        help="Reject inferred renames; old entries become orphaned.",
    ),
) -> None:
    """Save each source's schema to an auto-named schema JSON file, then serve/open the schema viewer."""
    cfg = _load_and_validate(config, discover_mode=True)
    target_dir = Path(".")

    # Rename phase (only when not in refresh/prune mode — preserves prior behavior).
    if not (refresh or prune):
        state = DiscoverState.load(target_dir)
        sources = expand_db_sources(cfg.sources)
        detection = detect_renames_for_sources(state, sources)

        if detection.ambiguous:
            for new_name, candidates in detection.ambiguous:
                typer.echo(
                    f"Ambiguous rename for {new_name}: candidates "
                    f"{', '.join(candidates)}",
                    err=True,
                )
            raise typer.Exit(code=2)

        if detection.proposals:
            accepted, rejected = _resolve_rename_decision(
                detection.proposals, yes=yes, no_renames=no_renames
            )
            apply_rename_decision(
                state, accepted=accepted, rejected=rejected,
                sources=sources, config_dir=target_dir,
            )
            state.save()

    # Header line — match prior CLI exactly.
    state = DiscoverState.load(target_dir)
    if state.last_run_at:
        typer.echo(
            f"Discovering from {config.name} (state file found, "
            f"last run {state.last_run_at})..."
        )
    else:
        typer.echo(f"Discovering from {config.name}...")

    report = run_discover(
        cfg, target_dir,
        refresh=refresh, retry_failed=retry_failed, prune=prune,
    )

    # Per-source line output (match prior format).
    if prune:
        for r in report.results:
            if r.status == "pruned":
                # Find the file name to echo (matches "Pruned: <name>" prior format).
                # When state had output_path the file existed and was deleted.
                # Reconstruct from convention; fall back to source name.
                pass
        # Replicate the prior summary line exactly.
        typer.echo(f"\nPruned {report.pruned_count} removed/orphaned entries.")
        return

    total = len(report.results)
    for idx, r in enumerate(report.results, start=1):
        prefix = f"  [{idx}/{total}] {r.name}"
        if r.status == "cached":
            typer.echo(f"{prefix}  (cached, {r.table_count} tables)")
        elif r.status == "skipped":
            typer.echo(f"{prefix}  (skipped)")
        elif r.status == "failed":
            typer.echo(f"{prefix}  → FAILED: {r.error}", err=True)
        elif r.status == "succeeded":
            assert r.output_path is not None
            typer.echo(
                f"{prefix}  ({r.decision})  → {r.table_count} tables → ./{r.output_path.name}"
            )

    parts: list[str] = []
    if report.succeeded_count:
        parts.append(f"{report.succeeded_count} discovered")
    if report.cached_count:
        parts.append(f"{report.cached_count} cached")
    if report.failed_count:
        parts.append(f"{report.failed_count} failed")
    typer.echo(f"\n{', '.join(parts)}.")

    serve_and_open(target_dir.resolve(), preferred_port=8000)
    if report.failed_count > 0:
        raise typer.Exit(code=2)


def register(app: typer.Typer) -> None:
    app.command(name="discover")(discover)
```

- [ ] **Step 7.16: Fix the prune-output format to match prior CLI**

The prior CLI emitted `  Pruned: <output_filename>` per pruned file (when the file existed). The thin wrapper as written above has a placeholder `pass` for that. Replace the prune-output block with code that re-derives the filename from `DiscoverState` after `run_discover` returns:

- [ ] Edit `src/feather_etl/commands/discover.py`. Find the `if prune:` block in `discover()` and replace it with:

```python
    if prune:
        # Re-read state to find the output_paths that were just removed.
        # run_discover already deleted the files; we replay names for echo.
        # The simpler approach: emit "Pruned: <name>" using the names from results.
        for r in report.results:
            if r.status == "pruned":
                typer.echo(f"  Pruned: {r.name}")
        typer.echo(f"\nPruned {report.pruned_count} removed/orphaned entries.")
        return
```

If the existing CLI test in `tests/commands/test_discover.py` asserts the exact `Pruned: <filename>.json` format (including the schema filename), `run_discover` must populate `SourceDiscoveryResult.output_path` for pruned entries too. Check the test; if it requires the filename:

- [ ] Edit `src/feather_etl/discover.py`. In the `if flag == "prune":` block of `run_discover`, set the result's `output_path` from the deleted file:

```python
            if dec == "removed" or (
                entry and entry.get("status") in ("orphaned", "removed")
            ):
                output_path = None
                if entry and entry.get("output_path"):
                    target = config_dir / Path(entry["output_path"]).name
                    output_path = target
                    if target.is_file():
                        target.unlink()
                state.sources.pop(name, None)
                report.pruned_count += 1
                report.results.append(
                    SourceDiscoveryResult(
                        name=name, decision=dec, status="pruned",
                        output_path=output_path,
                    )
                )
```

And update the wrapper's prune-output block to:

```python
    if prune:
        for r in report.results:
            if r.status == "pruned" and r.output_path is not None:
                typer.echo(f"  Pruned: {r.output_path.name}")
        typer.echo(f"\nPruned {report.pruned_count} removed/orphaned entries.")
        return
```

- [ ] **Step 7.17: Add `feather_etl.discover` to the purity test**

Edit `tests/test_core_module_purity.py`. Add `"feather_etl.discover"` to `CORE_MODULES`.

- [ ] **Step 7.18: Run the full discover test suite (CLI + core)**

Run: `uv run pytest tests/test_discover_core.py tests/commands/test_discover.py tests/commands/test_discover_multi_source.py tests/commands/test_multi_source_guard.py -v`
Expected: all pass. The CLI tests are the contract for "no behavior change."

If any CLI test fails because of an output-format mismatch, fix the wrapper's formatter — never change the test (it's the contract). Walk the diff line-by-line against the original `commands/discover.py` to spot the missed wording.

- [ ] **Step 7.19: Run the full test suite**

Run: `uv run pytest -q`
Expected: all tests pass.

- [ ] **Step 7.20: Run the hands-on integration suite**

Run: `bash scripts/hands_on_test.sh`
Expected: all 61 checks pass.

- [ ] **Step 7.21: Final purity grep (matches the issue's done-when criterion)**

Run:
```bash
for f in discover setup validate status history; do
  if grep -q "typer" "src/feather_etl/$f.py"; then
    echo "$f: HAS TYPER ✗"; exit 1
  else
    echo "$f: pure ✓"
  fi
done
```
Expected: five "pure ✓" lines.

- [ ] **Step 7.22: Commit**

```bash
git add src/feather_etl/discover.py src/feather_etl/commands/discover.py \
        tests/test_discover_core.py tests/test_core_module_purity.py
git commit -m "refactor(discover): extract pure core into feather_etl.discover (#43)

Split commands/discover.py (274 lines, mixed concerns) into a thin
Typer wrapper (~120 lines) that delegates to three pure top-level
functions in feather_etl.discover:

* detect_renames_for_sources(state, sources) -> RenameDetection
* apply_rename_decision(state, accepted, rejected, sources, config_dir)
* run_discover(cfg, config_dir, *, refresh, retry_failed, prune)
    -> DiscoverReport

The CLI wrapper resolves the rename decision (typer.confirm + --yes /
--no-renames + TTY detection), echoes proposals, calls
apply_rename_decision with pre-resolved values, then invokes
run_discover. The viewer (serve_and_open) is started by the wrapper
after run_discover returns — the core never imports typer or touches
stdin.

Behavior preserved exactly: rename interaction, ambiguous-exit-2,
non-interactive-exit-3, per-source line format, summary line, prune
output, viewer launch, exit-2-on-failure. Verified by the existing
CLI test suites (tests/commands/test_discover.py,
test_discover_multi_source.py, test_multi_source_guard.py) plus 10
new direct unit tests in tests/test_discover_core.py.

Added feather_etl.discover to the core-module purity test."
```

---

## Done Signal

Run the full validation sequence and confirm all green:

```bash
uv run pytest -q && \
bash scripts/hands_on_test.sh && \
for f in discover setup validate status history; do
  grep -q typer "src/feather_etl/$f.py" && \
    { echo "$f: HAS TYPER ✗"; exit 1; } || echo "$f: pure ✓"
done && \
uv run pytest -q tests/test_core_module_purity.py tests/test_history_core.py \
  tests/test_status_core.py tests/test_validate_core.py \
  tests/test_setup_core.py tests/test_discover_core.py -v
```

Expected:
- `pytest -q`: all tests pass (~677 — 653 baseline + 4 history + 3 status + 7 purity + 4 validate + 3 setup + 10 discover; minor variance acceptable).
- `bash scripts/hands_on_test.sh`: all 61 checks pass.
- All five `pure ✓` lines.
- The targeted re-run of new tests shows them green and grouped under their respective files.

Bonus invariant for code review:
```bash
git log --oneline feat/thin-cli-refactor ^main
```
Expected: 6 or 7 commits (one per task; Task 4 may be skipped if no tidy-up surfaced), each scoped to one command.

---

## Out of Scope (do not do these in this plan)

- Adding features or new CLI flags.
- Changing the CLI surface — every command's `--flag` list and output stays identical.
- Touching `pipeline.py`, `cache.py`, `_common.py`, `state.py`, `config.py`, `init_wizard.py`, `viewer_server.py`, or `output.py` beyond pure imports. Exception: removing an unexpected `typer` import in `viewer_server.py` or `init_wizard.py` if Task 3 surfaces one.
- Refactoring `cache.py` or `commands/cache.py` (already conformant).
- Issue #40 (retiring `scripts/hands_on_test.sh`) — independent.
- Issue #15 follow-ups — independent.
- Performance optimizations.
- Adding type annotations beyond what the cores need to declare their public API.
