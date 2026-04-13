# CLI Command Modularization (#19) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split `src/feather_etl/cli.py` into one module per command under `src/feather_etl/commands/` and reorganize CLI command tests by command ownership, with zero runtime behavior change.

**Architecture:** Keep `cli.py` as the Typer app + callback + explicit command registration inventory. Move shared command helpers (`_is_json`, `_load_and_validate`) to `commands/_common.py`. Move each command body into `commands/<command>.py` with `register(app)` for explicit wiring. In a second commit, reorganize command-facing tests into `tests/commands/test_<command>.py` while preserving assertions and behavior checks.

**Tech Stack:** Python 3.10+, Typer, pytest, `typer.testing.CliRunner`, `pathlib.Path`, git.

**Source spec:** [docs/superpowers/specs/2026-04-13-cli-command-modularization-design.md](../specs/2026-04-13-cli-command-modularization-design.md)

---

## Scope Check

This spec has one bounded subsystem: CLI command modularization with associated command-test reorganization. No decomposition is required.

---

## File Structure

### Commit A (Code Refactor Only)

| File | Change | Responsibility |
|---|---|---|
| `src/feather_etl/cli.py` | Modify | Typer app + callback + explicit `register(app)` calls only |
| `src/feather_etl/commands/__init__.py` | Create | Command module package marker |
| `src/feather_etl/commands/_common.py` | Create | Shared `_is_json` and `_load_and_validate` helpers |
| `src/feather_etl/commands/init.py` | Create | `init` command + `register(app)` |
| `src/feather_etl/commands/validate.py` | Create | `validate` command + `register(app)` |
| `src/feather_etl/commands/discover.py` | Create | `discover` command + `register(app)` |
| `src/feather_etl/commands/setup.py` | Create | `setup` command + `register(app)` |
| `src/feather_etl/commands/run.py` | Create | `run` command + `register(app)` |
| `src/feather_etl/commands/history.py` | Create | `history` command + `register(app)` |
| `src/feather_etl/commands/status.py` | Create | `status` command + `register(app)` |
| `tests/test_cli_structure.py` | Create | Architecture guard that CLI uses registration modules |

### Commit B (Test Reorganization Only)

| File | Change | Responsibility |
|---|---|---|
| `tests/commands/__init__.py` | Create | Package marker |
| `tests/commands/conftest.py` | Create | Shared fixtures (`cli_env`, `two_table_env`, helpers) |
| `tests/commands/test_init.py` | Create | `init` command tests |
| `tests/commands/test_validate.py` | Create | `validate` command tests (+ `--json validate`) |
| `tests/commands/test_discover.py` | Create | `discover` command tests (from `test_cli.py` + existing `test_discover.py`) |
| `tests/commands/test_setup.py` | Create | `setup` command tests |
| `tests/commands/test_run.py` | Create | `run` command tests (+ `--json run`, `--table` filter tests) |
| `tests/commands/test_history.py` | Create | `history` command tests (+ `--json history`) |
| `tests/commands/test_status.py` | Create | `status` command tests (+ `--json status`) |
| `tests/test_cli.py` | Modify | Remove moved command tests |
| `tests/test_discover.py` | Delete | Replaced by `tests/commands/test_discover.py` |
| `tests/test_table_filter_and_history.py` | Delete | Replaced by `tests/commands/test_run.py` + `tests/commands/test_history.py` |
| `tests/test_json_output.py` | Modify | Keep logging/output helper tests, remove moved CLI `--json` command tests |
| `tests/test_discover_io.py` | No change | Keep helper-unit tests in current location |

---

### Task 1: Add Architecture Guard Test (Red)

**Files:**
- Create: `tests/test_cli_structure.py`
- Test: `tests/test_cli_structure.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli_structure.py`:

```python
"""Structural guard tests for modular CLI command registration."""

from __future__ import annotations

import inspect


def test_cli_has_no_inline_app_command_decorators():
    import feather_etl.cli as cli

    source = inspect.getsource(cli)
    assert "@app.command" not in source


def test_command_modules_expose_register_functions():
    from feather_etl.commands import (
        discover,
        history,
        init,
        run,
        setup,
        status,
        validate,
    )

    for module in (init, validate, discover, setup, run, history, status):
        assert hasattr(module, "register")
        assert callable(module.register)
```

- [ ] **Step 2: Run test and verify fail**

Run: `uv run pytest tests/test_cli_structure.py -q`

Expected: FAIL because `feather_etl.commands` does not exist and `cli.py` currently contains `@app.command` decorators.

- [ ] **Step 3: Commit the failing test**

```bash
git add tests/test_cli_structure.py
git commit -m "test(cli): add structural guard for command modularization"
```

---

### Task 2: Create `commands` package and shared helpers (Green)

**Files:**
- Create: `src/feather_etl/commands/__init__.py`
- Create: `src/feather_etl/commands/_common.py`
- Modify: `src/feather_etl/cli.py`
- Test: `tests/test_cli_structure.py`

- [ ] **Step 1: Create package marker**

Create `src/feather_etl/commands/__init__.py`:

```python
"""CLI command modules for feather-etl."""
```

- [ ] **Step 2: Move shared helpers into `_common.py`**

Create `src/feather_etl/commands/_common.py`:

```python
"""Shared CLI command helpers."""

from __future__ import annotations

from pathlib import Path

import typer


def _is_json(ctx: typer.Context) -> bool:
    """Read --json flag from Typer context."""
    return ctx.ensure_object(dict).get("json_mode", False)


def _load_and_validate(config_path: Path, mode_override: str | None = None):
    """Load config, validate, write validation JSON. Raises on failure."""
    from feather_etl.config import load_config, write_validation_json

    try:
        cfg = load_config(config_path, mode_override=mode_override)
        write_validation_json(config_path, cfg)
        return cfg
    except (ValueError, FileNotFoundError) as e:
        if isinstance(e, FileNotFoundError):
            typer.echo(f"Config file not found: {config_path}", err=True)
        else:
            write_validation_json(config_path, None, errors=[str(e)])
            typer.echo(f"Validation failed: {e}", err=True)
        raise typer.Exit(code=1)
```

- [ ] **Step 3: Keep `cli.py` callback + app only for now**

At top of `src/feather_etl/cli.py`, keep:

```python
app = typer.Typer(name="feather", help="feather-etl: config-driven ETL")


@app.callback()
def main(
    ctx: typer.Context,
    json: bool = typer.Option(False, "--json", help="Output as NDJSON"),
) -> None:
    """feather-etl: config-driven ETL."""
    ctx.ensure_object(dict)["json_mode"] = json
```

Keep command functions temporarily until Task 3 and Task 4 migration is complete.

- [ ] **Step 4: Run structure test (still red for decorator assertion)**

Run: `uv run pytest tests/test_cli_structure.py -q`

Expected: still FAIL at `"@app.command" not in source`, but import for `feather_etl.commands` should now work.

- [ ] **Step 5: Commit package + helper extraction**

```bash
git add src/feather_etl/commands/__init__.py src/feather_etl/commands/_common.py src/feather_etl/cli.py
git commit -m "refactor(cli): add commands package and shared helper module"
```

---

### Task 3: Move `init`, `validate`, `discover` commands

**Files:**
- Create: `src/feather_etl/commands/init.py`
- Create: `src/feather_etl/commands/validate.py`
- Create: `src/feather_etl/commands/discover.py`
- Modify: `src/feather_etl/cli.py`
- Test: `tests/test_cli.py`, `tests/test_discover.py`, `tests/test_json_output.py`

- [ ] **Step 1: Write command module files with `register(app)`**

Create `src/feather_etl/commands/init.py`:

```python
"""Init command."""

from __future__ import annotations

from pathlib import Path

import typer

from feather_etl.commands._common import _is_json
from feather_etl.output import emit_line


def init(
    ctx: typer.Context,
    project_name: str | None = typer.Argument(None, help="Project directory name."),
) -> None:
    """Scaffold a new client project with template files."""
    if project_name is None:
        project_name = typer.prompt("Project name")

    project_path = Path(project_name).resolve()
    if project_path.exists():
        non_hidden = [f for f in project_path.iterdir() if not f.name.startswith(".")]
        if non_hidden:
            typer.echo(
                f"Directory '{project_name}' already exists and is not empty.",
                err=True,
            )
            raise typer.Exit(code=1)

    from feather_etl.init_wizard import scaffold_project

    files_created = scaffold_project(project_path)
    if _is_json(ctx):
        emit_line(
            {"project": str(project_path), "files_created": files_created},
            json_mode=True,
        )
    else:
        typer.echo(f"Project scaffolded at {project_path}")


def register(app: typer.Typer) -> None:
    app.command(name="init")(init)
```

Create `src/feather_etl/commands/validate.py`:

```python
"""Validate command."""

from __future__ import annotations

from pathlib import Path

import typer

from feather_etl.commands._common import _is_json, _load_and_validate
from feather_etl.output import emit_line


def validate(
    ctx: typer.Context, config: Path = typer.Option("feather.yaml", "--config")
) -> None:
    """Validate config, test source connection, and write feather_validation.json."""
    from feather_etl.sources.registry import create_source

    cfg = _load_and_validate(config)
    source = create_source(cfg.source)
    source_ok = source.check()

    if _is_json(ctx):
        emit_line(
            {
                "valid": True,
                "tables_count": len(cfg.tables),
                "source_type": cfg.source.type,
                "destination": str(cfg.destination.path),
                "mode": cfg.mode,
                "source_connected": source_ok,
            },
            json_mode=True,
        )
    else:
        typer.echo(f"Config valid: {len(cfg.tables)} table(s)")
        source_label = cfg.source.path or cfg.source.host or "configured"
        conn_status = "connected" if source_ok else "FAILED"
        typer.echo(f"  Source: {cfg.source.type} ({source_label}) — {conn_status}")
        typer.echo(f"  Destination: {cfg.destination.path}")
        typer.echo(f"  State: {cfg.config_dir / 'feather_state.duckdb'}")
        for t in cfg.tables:
            typer.echo(f"  Table: {t.name} → {t.target_table} ({t.strategy})")

    if not source_ok:
        typer.echo("Source connection failed.", err=True)
        err = getattr(source, "_last_error", None)
        if err:
            typer.echo(f"  Details: {err}", err=True)
        raise typer.Exit(code=2)


def register(app: typer.Typer) -> None:
    app.command(name="validate")(validate)
```

Create `src/feather_etl/commands/discover.py`:

```python
"""Discover command."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from feather_etl.commands._common import _load_and_validate


def discover(config: Path = typer.Option("feather.yaml", "--config")) -> None:
    """Save source schema (tables + columns) to an auto-named JSON file in the current directory."""
    from feather_etl.config import schema_output_path
    from feather_etl.sources.registry import create_source

    cfg = _load_and_validate(config)
    source = create_source(cfg.source)

    if not source.check():
        typer.echo("Source connection failed.", err=True)
        raise typer.Exit(code=2)

    schemas = source.discover()
    payload = [
        {
            "table_name": s.name,
            "columns": [{"name": c[0], "type": c[1]} for c in s.columns],
        }
        for s in schemas
    ]
    out_path = schema_output_path(cfg.source)
    out_path.write_text(json.dumps(payload, indent=2))
    typer.echo(f"Wrote {len(schemas)} table(s) to ./{out_path}")


def register(app: typer.Typer) -> None:
    app.command(name="discover")(discover)
```

- [ ] **Step 2: Wire explicit registration in `cli.py`**

Add imports in `src/feather_etl/cli.py`:

```python
from feather_etl.commands.discover import register as register_discover
from feather_etl.commands.init import register as register_init
from feather_etl.commands.validate import register as register_validate
```

Then register:

```python
register_init(app)
register_validate(app)
register_discover(app)
```

Remove inline `@app.command()` functions for `init`, `validate`, `discover` from `cli.py`.

- [ ] **Step 3: Run focused tests**

Run:

```bash
uv run pytest tests/test_cli.py::TestInit -q
uv run pytest tests/test_cli.py::TestValidate -q
uv run pytest tests/test_cli.py::TestDiscover -q
uv run pytest tests/test_discover.py -q
uv run pytest tests/test_json_output.py::TestCliJsonFlag::test_validate_json_outputs_json -q
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add src/feather_etl/cli.py src/feather_etl/commands/init.py src/feather_etl/commands/validate.py src/feather_etl/commands/discover.py
git commit -m "refactor(cli): move init/validate/discover into command modules"
```

---

### Task 4: Move `setup`, `run`, `history`, `status` and finish registration-only `cli.py`

**Files:**
- Create: `src/feather_etl/commands/setup.py`
- Create: `src/feather_etl/commands/run.py`
- Create: `src/feather_etl/commands/history.py`
- Create: `src/feather_etl/commands/status.py`
- Modify: `src/feather_etl/cli.py`
- Test: `tests/test_cli.py`, `tests/test_table_filter_and_history.py`, `tests/test_json_output.py`, `tests/test_cli_structure.py`

- [ ] **Step 1: Add remaining command modules**

For each module (`setup.py`, `run.py`, `history.py`, `status.py`), copy the command function body from current `cli.py` without functional edits and add:

```python
def register(app: typer.Typer) -> None:
    app.command(name="<command-name>")(<function-name>)
```

Import shared helpers from `_common` and output helpers from `feather_etl.output` exactly as needed.

- [ ] **Step 2: Convert `cli.py` to registration-only module**

Final `src/feather_etl/cli.py` shape:

```python
"""feather CLI — thin wrapper over config, pipeline, state, and sources."""

from __future__ import annotations

import typer

from feather_etl.commands.discover import register as register_discover
from feather_etl.commands.history import register as register_history
from feather_etl.commands.init import register as register_init
from feather_etl.commands.run import register as register_run
from feather_etl.commands.setup import register as register_setup
from feather_etl.commands.status import register as register_status
from feather_etl.commands.validate import register as register_validate

app = typer.Typer(name="feather", help="feather-etl: config-driven ETL")


@app.callback()
def main(
    ctx: typer.Context,
    json: bool = typer.Option(False, "--json", help="Output as NDJSON"),
) -> None:
    """feather-etl: config-driven ETL."""
    ctx.ensure_object(dict)["json_mode"] = json


register_init(app)
register_validate(app)
register_discover(app)
register_setup(app)
register_run(app)
register_history(app)
register_status(app)
```

- [ ] **Step 3: Run focused command suites**

Run:

```bash
uv run pytest tests/test_cli.py -q
uv run pytest tests/test_table_filter_and_history.py -q
uv run pytest tests/test_json_output.py::TestCliJsonFlag -q
uv run pytest tests/test_cli_structure.py -q
```

Expected: all pass, and `tests/test_cli_structure.py` now green.

- [ ] **Step 4: Run full suite for Commit A confidence**

Run: `uv run pytest -q`

Expected: full pass.

- [ ] **Step 5: Squash Commit A into one refactor commit (interactive alternative: reset + recommit)**

If you followed atomic commits in Tasks 2-4, create one final Commit A by soft-resetting Task 2-4 commits and recommitting:

```bash
git reset --soft HEAD~3
git commit -m "refactor(cli): split commands into feather_etl.commands modules"
```

If you do not want to rewrite local history, keep Task 2-4 commits as-is and continue.

---

### Task 5: Create command-test scaffold and shared fixtures

**Files:**
- Create: `tests/commands/__init__.py`
- Create: `tests/commands/conftest.py`
- Test: `tests/commands/conftest.py` (import + fixture smoke through first moved tests)

- [ ] **Step 1: Create package marker**

Create `tests/commands/__init__.py`:

```python
"""Command-level CLI tests."""
```

- [ ] **Step 2: Create shared fixture module**

Create `tests/commands/conftest.py`:

```python
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from tests.conftest import FIXTURES_DIR

runner = CliRunner()


@pytest.fixture
def cli_env(tmp_path: Path) -> tuple[Path, Path]:
    client_db = tmp_path / "client.duckdb"
    shutil.copy2(FIXTURES_DIR / "client.duckdb", client_db)

    config = {
        "source": {"type": "duckdb", "path": str(client_db)},
        "destination": {"path": str(tmp_path / "feather_data.duckdb")},
        "tables": [
            {
                "name": "inventory_group",
                "source_table": "icube.InventoryGroup",
                "target_table": "bronze.inventory_group",
                "strategy": "full",
            },
        ],
    }
    config_path = tmp_path / "feather.yaml"
    config_path.write_text(yaml.dump(config, default_flow_style=False))
    return config_path, tmp_path


@pytest.fixture
def two_table_env(tmp_path: Path) -> tuple[Path, Path]:
    client_db = tmp_path / "client.duckdb"
    shutil.copy2(FIXTURES_DIR / "client.duckdb", client_db)

    config = {
        "source": {"type": "duckdb", "path": str(client_db)},
        "destination": {"path": str(tmp_path / "feather_data.duckdb")},
        "tables": [
            {
                "name": "inventory_group",
                "source_table": "icube.InventoryGroup",
                "target_table": "bronze.inventory_group",
                "strategy": "full",
            },
            {
                "name": "customer_master",
                "source_table": "icube.CUSTOMERMASTER",
                "target_table": "bronze.customer_master",
                "strategy": "full",
            },
        ],
    }
    config_path = tmp_path / "feather.yaml"
    config_path.write_text(yaml.dump(config, default_flow_style=False))
    return config_path, tmp_path


def cli_config(tmp_path: Path) -> Path:
    client_db = tmp_path / "client.duckdb"
    shutil.copy2(FIXTURES_DIR / "client.duckdb", client_db)
    config = {
        "source": {"type": "duckdb", "path": str(client_db)},
        "destination": {"path": str(tmp_path / "feather_data.duckdb")},
        "tables": [
            {
                "name": "inventory_group",
                "source_table": "icube.InventoryGroup",
                "target_table": "bronze.inventory_group",
                "strategy": "full",
            }
        ],
    }
    config_file = tmp_path / "feather.yaml"
    config_file.write_text(yaml.dump(config, default_flow_style=False))
    return config_file
```

- [ ] **Step 3: Commit scaffold**

```bash
git add tests/commands/__init__.py tests/commands/conftest.py
git commit -m "test(cli): add tests/commands scaffold and shared fixtures"
```

---

### Task 6: Move command tests from `test_cli.py`, `test_discover.py`, and `test_table_filter_and_history.py`

**Files:**
- Create: `tests/commands/test_init.py`
- Create: `tests/commands/test_validate.py`
- Create: `tests/commands/test_discover.py`
- Create: `tests/commands/test_setup.py`
- Create: `tests/commands/test_run.py`
- Create: `tests/commands/test_history.py`
- Create: `tests/commands/test_status.py`
- Modify: `tests/test_cli.py`
- Delete: `tests/test_discover.py`
- Delete: `tests/test_table_filter_and_history.py`

- [ ] **Step 1: Create per-command files and move test classes unchanged**

Move classes with no assertion changes:

- `TestInit` -> `tests/commands/test_init.py`
- `TestValidate` -> `tests/commands/test_validate.py`
- `TestDiscover` (from `tests/test_cli.py`) + all tests from old `tests/test_discover.py` -> `tests/commands/test_discover.py`
- `TestSetup` -> `tests/commands/test_setup.py`
- `TestRun` + `TestRunAutoCreates` + `TestTableFilter` -> `tests/commands/test_run.py`
- `TestHistory` -> `tests/commands/test_history.py`
- `TestStatus` -> `tests/commands/test_status.py`

Each file should import `runner` and fixtures from `tests.commands.conftest`.

- [ ] **Step 2: Trim old files**

- Remove moved classes from `tests/test_cli.py`.
- Delete `tests/test_discover.py` after confirming all tests are moved.
- Delete `tests/test_table_filter_and_history.py` after confirming all tests are moved.

- [ ] **Step 3: Run per-command tests**

Run:

```bash
uv run pytest tests/commands/test_init.py -q
uv run pytest tests/commands/test_validate.py -q
uv run pytest tests/commands/test_discover.py -q
uv run pytest tests/commands/test_setup.py -q
uv run pytest tests/commands/test_run.py -q
uv run pytest tests/commands/test_history.py -q
uv run pytest tests/commands/test_status.py -q
```

Expected: all pass.

- [ ] **Step 4: Commit moved tests**

```bash
git add tests/commands/test_init.py tests/commands/test_validate.py tests/commands/test_discover.py tests/commands/test_setup.py tests/commands/test_run.py tests/commands/test_history.py tests/commands/test_status.py tests/test_cli.py
git rm tests/test_discover.py tests/test_table_filter_and_history.py
git commit -m "test(cli): split command tests into tests/commands by command"
```

---

### Task 7: Move CLI `--json` command tests to command-specific files and finalize Commit B

**Files:**
- Modify: `tests/commands/test_validate.py`
- Modify: `tests/commands/test_run.py`
- Modify: `tests/commands/test_history.py`
- Modify: `tests/commands/test_status.py`
- Modify: `tests/test_json_output.py`

- [ ] **Step 1: Move `TestCliJsonFlag` methods to matching command files**

Move methods unchanged:

- `test_validate_json_outputs_json` -> `tests/commands/test_validate.py`
- `test_run_json_outputs_ndjson` -> `tests/commands/test_run.py`
- `test_history_json_outputs_ndjson` -> `tests/commands/test_history.py`
- `test_status_json_outputs_ndjson` -> `tests/commands/test_status.py`

Keep helper-only tests in `tests/test_json_output.py`:

- `TestJsonlLogging`
- `TestOutputHelper`
- `test_default_output_unchanged` (keep here since it validates default output behavior globally)

- [ ] **Step 2: Run json-focused suites**

Run:

```bash
uv run pytest tests/test_json_output.py -q
uv run pytest tests/commands/test_validate.py -q
uv run pytest tests/commands/test_run.py -q
uv run pytest tests/commands/test_history.py -q
uv run pytest tests/commands/test_status.py -q
```

Expected: all pass.

- [ ] **Step 3: Run full suite**

Run: `uv run pytest -q`

Expected: full pass.

- [ ] **Step 4: Create single Commit B for test reorganization**

If needed, soft-reset all Task 5-7 commits into one commit:

```bash
git reset --soft HEAD~3
git commit -m "test(cli): reorganize command tests by command ownership"
```

If you kept exactly one commit already for Tasks 5-7, skip reset and keep that commit.

---

## Final Verification Checklist

- [ ] `src/feather_etl/cli.py` has no `@app.command` decorators.
- [ ] All seven commands are registered through explicit `register(app)` calls.
- [ ] `tests/test_cli_structure.py` passes.
- [ ] CLI outputs and exit codes are unchanged from pre-refactor baseline.
- [ ] Commit A contains only CLI code structure refactor.
- [ ] Commit B contains only test reorganization.
- [ ] Full test suite passes.

---

## Self-Review

### 1) Spec coverage

- Architecture split to `commands/*`: covered in Tasks 2-4.
- Explicit registration strategy (`register(app)`): covered in Tasks 3-4.
- No behavior-change guarantee: covered by focused and full test runs in Tasks 3-4 and 6-7.
- Test reorganization in separate commit: covered in Tasks 5-7.

No coverage gaps found.

### 2) Placeholder scan

Searched plan content for `TODO`, `TBD`, `implement later`, and generic "add tests" language. No placeholders remain.

### 3) Type/signature consistency

- Command registration uses `register(app: typer.Typer) -> None` uniformly.
- Command function names match command module names.
- Shared helper names `_is_json` and `_load_and_validate` are used consistently.

No type/signature mismatches found.
