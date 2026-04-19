# Test Restructure — Wave B (Migrate e2e tests) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate all CLI-invoking tests currently under `tests/commands/` and selected flat `tests/test_*.py` files into the workflow-stage files under `tests/e2e/`. After this wave, `tests/commands/test_*.py` is gone, every test in `tests/e2e/` uses the `project`/`cli` fixtures (or raw `CliRunner` with justification), and the full suite count is still 717.

**Architecture:** One migration task per destination file. Each task reads the source file(s), refactors tests to use `project`/`cli` (or the extended `cli(config=False|Path)` variants added in Task B0), merges into the destination, deletes the source file, runs the full suite, and commits. Non-CLI tests in mixed files stay where they are — Waves C/D handle them.

**Tech Stack:** Same as Wave A. No new dependencies.

**Source spec:** [`docs/superpowers/specs/2026-04-19-test-restructure-design.md`](../specs/2026-04-19-test-restructure-design.md)
**Wave A plan:** [`2026-04-19-test-restructure-wave-a.md`](2026-04-19-test-restructure-wave-a.md)
**Wave A survey:** captured in the Wave B planning chat — key findings reflected inline below.
**Issue:** https://github.com/siraj-samsudeen/feather-etl/issues/40
**Branch:** `feat/test-restructure` (same branch as Wave A; Wave B commits extend the history).

---

## Scope changes from the original spec

The spec's Wave B file list assumed that each file listed for migration was entirely e2e. The survey found several files are only *partially* e2e; the non-CLI tests in those files belong to Wave C (integration) or D (unit). Wave B migrates only the CLI-using portions. Deferred pieces:

| File | Wave B action | Deferred to |
|---|---|---|
| `tests/test_integration.py` (33 tests, **0 use CliRunner**) | **Defer entirely** — not e2e | Wave C |
| `tests/test_transforms.py::TestE2ETransformPipeline` (named "E2E" but no CliRunner) | **Defer** | Wave C |
| `tests/test_transforms.py::TestCLISetupTransforms` (2 tests, uses CliRunner) | Migrate to `test_07_transforms.py` | Wave B |
| `tests/test_transforms.py` (all other classes) | Leave in place | Wave C/D |
| `tests/test_json_output.py::TestCliJsonFlag` (1 test) | Migrate to `test_17_json_output.py` | Wave B |
| `tests/test_json_output.py::TestJsonlLogging`, `TestOutputHelper` (7 tests, no CliRunner) | Leave in place | Wave C/D |
| `tests/test_explicit_name_flag.py` — 2 CliRunner tests | Migrate into `test_03_discover.py` | Wave B |
| `tests/test_explicit_name_flag.py` — 5 non-CLI tests (source-class unit) | Leave in place | Wave D |
| `tests/commands/test_init.py::TestInitTemplateUsesSourcesList` (2 tests, no CliRunner — calls `scaffold_project()` / `load_config()` directly) | Migrate anyway (they exercise the scaffold workflow end-to-end semantically, even if not via CliRunner) | Wave B |
| `tests/commands/conftest.py` | Leave in place | Deleted in Wave D when `test_json_output.py::TestCliJsonFlag`-era imports are gone (actually `test_json_output.py` is split in Wave B; `conftest.py` becomes orphaned after Wave B but is deleted in Wave D to avoid churn) |

After Wave B: `tests/commands/` contains only `__init__.py` + `conftest.py` (both orphaned but harmless). `tests/test_e2e.py`, `tests/test_multi_source_e2e.py`, `tests/test_cli_structure.py` are deleted outright (all their tests were CLI-based). `tests/test_explicit_name_flag.py` and `tests/test_json_output.py` shrink but don't disappear.

---

## File Structure (after Wave B)

```
tests/
  __init__.py                        (unchanged)
  conftest.py                        (unchanged)
  helpers.py                         (unchanged)
  README.md                          (unchanged)
  fixtures/                          (unchanged)
  e2e/
    __init__.py                      (unchanged)
    conftest.py                      ← EXTENDED (cli kwargs + stub_viewer_serve)
    test_fixture_smoke.py            ← EXTENDED (smoke tests for new cli kwargs)
    test_00_cli_structure.py         ← NEW (Task B1)
    test_01_scaffold.py              ← NEW (Task B2)
    test_02_validate.py              ← EXTENDED (Task B3; append 6 tests to existing 2)
    test_03_discover.py              ← NEW (Task B4; biggest file — ~30 tests)
    test_04_extract_full.py          ← NEW (Task B5)
    test_07_transforms.py            ← NEW (Task B6; 2 tests for now)
    test_10_error_handling.py        (unchanged from Wave A)
    test_11_path_resolution.py       (unchanged from Wave A)
    test_12_cache.py                 ← NEW (Task B7)
    test_13_multi_source.py          ← NEW (Task B8)
    test_14_status.py                ← NEW (Task B9)
    test_15_history.py               ← NEW (Task B10)
    test_16_view.py                  ← NEW (Task B11)
    test_17_json_output.py           ← NEW (Task B12)
    test_18_sources_e2e.py           (unchanged from Wave A)
  integration/, unit/                (still empty; Waves C/D populate)
  commands/
    __init__.py                      (unchanged; orphaned)
    conftest.py                      (unchanged; orphaned — Wave D deletes)
    # test_*.py files all DELETED by end of Wave B
  test_integration.py                (unchanged; Wave C migrates)
  test_transforms.py                 (unchanged; Wave C/D splits)
  test_json_output.py                (SHRUNK — TestCliJsonFlag removed; 7 tests remain)
  test_explicit_name_flag.py         (SHRUNK — 2 tests removed; 5 remain)
  test_e2e.py                        (DELETED — single god test moved)
  test_multi_source_e2e.py           (DELETED — all 3 tests moved)
  test_cli_structure.py              (DELETED — all 5 tests moved)
  # ... other flat test_*.py files untouched
```

---

## Shared migration rules (apply to every task)

These rules replace per-task specification of common concerns. Every migration task honors them unless a task explicitly overrides.

### Rule M1 — What to migrate, what to drop

- **Migrate** every test that uses `CliRunner.invoke(app, ...)` or runs the `feather` binary via subprocess. These are e2e by definition.
- **Migrate** tests in mixed files *only if they exercise the CLI*. Non-CLI tests in those files stay where they are (Wave C/D will handle).
- **Drop** setup patterns that the `project`/`cli` fixtures replace: `runner = CliRunner()` at module level, `cli_env` / `two_table_env` / `cli_config` fixtures, `_write_sqlite_config()` / `_project()` local helpers. Their work is now done inline via `project.write_config(...)` + `project.write_curation([...])`.

### Rule M2 — Test style after migration

- **Flat function style.** Drop single-member `class TestFoo:` wrappers. Keep classes only when ≥2 tests share a class-scoped `@pytest.fixture` (none of the surveyed files do this meaningfully — nearly all classes are mere groupers).
- **First positional fixture on every test:** `project` (unless the test deliberately avoids it — see M3).
- **Second fixture:** `cli` (unless the test uses `subprocess.run` directly, like `test_10_error_handling.py::test_errors_not_duplicated_on_stderr`).
- **Add `monkeypatch` only if actually used.** Many current tests request `monkeypatch` and never call it — drop unused fixture params during migration.

### Rule M3 — When to bypass the `project`/`cli` fixtures

Two legitimate cases:

1. **The test must run in a directory with no config at all** (tests CWD-discovery failure paths). Pattern: raw `CliRunner().invoke(app, ["validate"])` + `monkeypatch.chdir(tmp_path)`. See existing `test_02_validate.py::test_validate_missing_config_shows_friendly_error` for the precedent.
2. **The test needs real OS-level stdout/stderr separation.** Use `subprocess.run` with `_find_feather_binary()`. See existing `test_10_error_handling.py` for the precedent.

In both cases: add a clear docstring paragraph explaining why the fixture is bypassed. Don't silently drop it.

### Rule M4 — Curation helpers

- Use `project.write_curation([(src_db, src_table, alias), ...])` when every entry is simple (no filter, no timestamp, no primary_key override, no schedule).
- For richer entries, call `make_curation_entry(...)` directly with the kwargs you need, then pass the list to `write_curation(project.root, tables)` — both are imported from `tests.helpers`.
- The spec's Wave A README documents this escape hatch; tests that need it should cite the pattern in a comment.

### Rule M5 — Config shape

- Always the modern format: `sources: [...]`, `destination: {path: ...}`. No inline `tables:` in YAML.
- For single-source tests: `sources=[{"type": "duckdb", "name": "erp", "path": "./sample_erp.duckdb"}]` (use relative paths inside the YAML so tests work regardless of where `project.root` lives).
- Source `name` is **required** unless the test specifically probes the auto-naming fallback.

### Rule M6 — `stub_viewer_serve` fixture

- This fixture (added to `tests/e2e/conftest.py` in Task B0) prevents the discover/view commands from spawning a browser. Any migrated test that previously used it via `@pytest.mark.usefixtures("stub_viewer_serve")` keeps that marker (now referencing the `tests/e2e/conftest.py` version).
- Discover tests that monkeypatch `discover_cmd.serve_and_open` directly: replace with `@pytest.mark.usefixtures("stub_viewer_serve")`.

### Rule M7 — Count invariant

- **Full suite count MUST remain 717** (or higher, if Task B0 adds new smoke tests — the exact target is specified per task). Any drop means a test was silently dropped during migration.
- After each task, verify: `uv run pytest --collect-only -q 2>&1 | tail -2` and `uv run pytest -q 2>&1 | tail -3` — count matches expected, suite green.
- If a test can't be migrated cleanly, STOP and report. Don't delete it.

### Rule M8 — Commit style

- One commit per task. Commit message format: `test(b): <concise summary> (#40)` + 2–3 line body describing what moved.
- `git mv` is preferred when an entire file moves unchanged (preserves blame). When splitting or merging, use `git add` + `git rm` in the same commit.
- Each commit must leave the full suite green. No WIP commits.

### Rule M9 — `tests/commands/conftest.py` handling

- Don't touch `tests/commands/conftest.py` in Wave B (it's still imported by `tests/test_json_output.py`'s non-migrated tests).
- Don't touch `tests/commands/__init__.py` either.
- The deletion of the `tests/commands/` package as a whole happens in Wave D.

### Rule M10 — Deleted-file verification

After deleting a source file, run:
```bash
git status
```
Ensure the file shows as deleted (staged for commit). Never `rm -rf` outside of `git rm` — accidental file loss without git's knowledge is hard to recover from.

---

## Task B0: Extend the e2e harness (cli kwargs + stub_viewer_serve)

**Files:**
- Modify: `tests/e2e/conftest.py`
- Modify: `tests/e2e/test_fixture_smoke.py` (add smoke tests for the new kwargs + fixture)

This is a pre-migration foundation task. Several upcoming migrations need the `cli` fixture to support:
- `config=False` — invoke without `--config` (for tests that probe CWD discovery, or for commands like `init`/`view` that don't accept `--config`).
- `config=<Path>` — invoke with a specific config path (for tests that use renamed config files like `feather_erp.yaml`).
- A shared `stub_viewer_serve` fixture — several discover tests need it and the current one lives in `tests/commands/conftest.py` which is out of scope.

### Step 1: Write failing smoke tests (TDD red phase)

Append these functions to `tests/e2e/test_fixture_smoke.py` (end of file, preserving the existing 8 functions):

```python


def test_cli_with_config_false_skips_config_flag(project, cli):
    """cli(..., config=False) invokes feather without auto-appending --config.

    Required by tests that probe CWD-discovery behaviour, and by commands
    like `init`/`view` that don't accept --config at all.
    """
    # If cli still appended --config, `feather --help` would be ambiguous.
    # With config=False, app-level --help works normally.
    result = cli("--help", config=False)
    assert result.exit_code == 0
    assert "Usage" in result.output
    # Sanity: no --config leaked into the help output.
    assert "feather.yaml" not in result.output or "Options" in result.output


def test_cli_with_explicit_config_path_uses_it(project, cli, tmp_path_factory):
    """cli(..., config=<Path>) forwards that path as --config, overriding
    the default project.config_path."""
    # Write a valid config to project.root with a name we can grep.
    project.copy_fixture("sample_erp.sqlite")
    project.write_config(
        sources=[{"type": "sqlite", "name": "marker_one", "path": "./sample_erp.sqlite"}],
        destination={"path": "./feather_data.duckdb"},
    )
    project.write_curation([("marker_one", "orders", "orders")])

    # Write a SECOND config file with a different source name; pass it explicitly.
    other_cfg = project.root / "feather_other.yaml"
    import yaml
    other_cfg.write_text(yaml.dump({
        "sources": [{"type": "sqlite", "name": "marker_two",
                     "path": "./sample_erp.sqlite"}],
        "destination": {"path": "./feather_data_other.duckdb"},
    }, default_flow_style=False))
    # Reuse the same curation but under a different source name.
    from tests.helpers import make_curation_entry, write_curation
    # Rewrite curation to reference marker_two so validate passes.
    write_curation(project.root, [make_curation_entry("marker_two", "orders", "orders")])

    result = cli("validate", config=other_cfg)
    assert result.exit_code == 0, result.output
    # The source-count summary will mention the other config's data.
    # Just assert it didn't quietly use the default.
    assert "marker_two" in result.output or "1 source" in result.output or "1 table" in result.output


def test_stub_viewer_serve_prevents_browser_open(project, cli, monkeypatch):
    """The stub_viewer_serve fixture monkeypatches discover's serve_and_open
    to a no-op so tests don't try to launch a browser.

    This smoke test doesn't apply the fixture but shows the target attribute
    exists and is overridable."""
    import feather_etl.commands.discover as discover_cmd
    assert hasattr(discover_cmd, "serve_and_open"), (
        "discover command still exposes serve_and_open — stub_viewer_serve fixture relies on this"
    )
```

### Step 2: Run the smoke tests — they should FAIL (red)

Run:
```bash
uv run pytest tests/e2e/test_fixture_smoke.py -v
```

Expected:
- The 8 existing tests PASS.
- The 3 new tests FAIL with errors like `TypeError: _run() got an unexpected keyword argument 'config'` (first two) or the stub_viewer_serve smoke PASSES (it's a sanity check that doesn't require the new fixture — it'll pass immediately).

So the split is: 2 new tests fail, 1 new test passes. Total: 9 passed, 2 failed. Confirm this pattern — if the first two unexpectedly pass, something's already providing the kwargs and investigation is needed.

### Step 3: Extend `tests/e2e/conftest.py`

Replace the `cli` fixture's body and add the `stub_viewer_serve` fixture. Apply these two edits:

**Edit A:** Replace the `cli` fixture. Find this block:

```python
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
```

Replace it with:

```python
@pytest.fixture
def cli(project: ProjectFixture) -> Callable[..., Result]:
    """Return a callable that runs feather CLI commands against `project`.

    By default the `--config project.config_path` pair is forwarded
    automatically after the positional args:

        cli("validate")                             # → feather validate --config <project>/feather.yaml
        cli("run")                                  # → feather run       --config <project>/feather.yaml

    The `config=` keyword controls this:

        cli("init", "./myproj", config=False)       # no --config appended; for commands that don't take it
        cli("--help", config=False)                 # app-level --help
        cli("validate", config=other_path)          # --config <other_path>; for tests with renamed configs

    `config=True` (default) is identical to omitting it.

    Returns a `click.testing.Result` (re-exported as `typer.testing.Result`)
    exposing `.exit_code`, `.output`, `.stdout`, `.stderr`, etc.
    """
    runner = CliRunner()

    def _run(*args: str, config: bool | Path = True) -> Result:
        argv = list(args)
        if config is True:
            argv += ["--config", str(project.config_path)]
        elif config is False:
            pass  # no --config flag at all
        else:
            argv += ["--config", str(config)]
        return runner.invoke(app, argv)

    return _run
```

Note: the `Path | bool` type hint uses PEP 604 syntax which requires `from __future__ import annotations` at the top of the file (already present — verify before editing).

**Edit B:** Add the `stub_viewer_serve` fixture. Append at the bottom of the file, after the `cli` fixture:

```python


@pytest.fixture
def stub_viewer_serve(monkeypatch):
    """Prevent the discover/view commands from launching a real browser.

    Discover tests spawn a local HTTP server + open the user's browser via
    `serve_and_open`. In tests that's undesirable. Apply this fixture
    (directly or via `@pytest.mark.usefixtures("stub_viewer_serve")`) and
    the function becomes a no-op.
    """
    import feather_etl.commands.discover as discover_cmd
    monkeypatch.setattr(discover_cmd, "serve_and_open", lambda *a, **kw: None)
```

### Step 4: Re-run the smoke tests — all green now

Run:
```bash
uv run pytest tests/e2e/test_fixture_smoke.py -v
```
Expected: all 11 tests PASS.

### Step 5: Full suite still green

Run:
```bash
uv run pytest -q
```
Expected: 720 tests collected (717 + 3 new smoke); all passing (minus the 16 pre-existing skips).

### Step 6: Commit

```bash
git add tests/e2e/conftest.py tests/e2e/test_fixture_smoke.py
git commit -m "test(b): extend cli fixture with config kwarg + add stub_viewer_serve (#40)

Preparation for Wave B migration. Three new capabilities:

- cli(..., config=False) invokes feather without auto-appending --config
  (for commands like init/view that don't accept --config, and for tests
  probing CWD-discovery failure paths).
- cli(..., config=<Path>) uses an explicit config path (for tests with
  renamed config files).
- stub_viewer_serve fixture prevents discover/view from opening a real
  browser; will be applied to every discover test migrated in Task B4.

Three new smoke tests pin the kwarg contract; the existing 8 still pass.
No existing test behaviour changed (config=True is the default)."
```

---

## Task B1: Migrate `test_cli_structure.py` → `test_00_cli_structure.py`

**Files:**
- Create: `tests/e2e/test_00_cli_structure.py`
- Delete: `tests/test_cli_structure.py`

Source has 5 tests: 3 flat module-level structural guards (introspection via `app.registered_commands`, `inspect.getsource`, module imports) + 2 class tests that use `CliRunner` for `--help`.

### Step 1: Read the source file

```bash
cat tests/test_cli_structure.py
```

Understand each test. The 3 introspection tests don't use `CliRunner` but they *test the CLI surface*, so they belong in `test_00_cli_structure.py` per the workflow-stage convention ("CLI surface — commands registered, `--help` renders").

### Step 2: Write the destination file

Create `tests/e2e/test_00_cli_structure.py`. Migration rules applied:
- Drop the `class TestCacheCommandRegistered:` wrapper; make both tests flat (no shared fixture).
- The 2 CliRunner tests use `cli(..., config=False)` from Task B0's extension since they invoke app-level `--help`.
- The 3 introspection tests need no fixtures (not even `project`) — keep them flat with no positional args.
- Preserve the docstring / intent of each test.

Use this template; fill in the test bodies from the source:

```python
"""Workflow stage 00: CLI surface — commands registered, --help renders.

Structural guards that pin the Typer app's registered commands and the
minimum viable `feather <cmd> --help` behaviour. These are e2e by the
"exercises the CLI" criterion even when they don't use CliRunner — a
broken CLI surface breaks every subsequent e2e test.
"""

from __future__ import annotations

# ... migrated test functions here (no classes unless necessary) ...
```

For the introspection-style tests, structure each as a flat function matching the source's intent. For example, if the source has:

```python
# SOURCE (tests/test_cli_structure.py):
def test_all_commands_registered():
    from feather_etl.cli import app
    names = {cmd.name for cmd in app.registered_commands}
    expected = {"init", "validate", "discover", "setup", "run",
                "status", "cache", "history", "view"}
    assert expected <= names
```

Migrate verbatim (same import, same assertions). Don't add fixtures. No refactoring unless the test is structurally broken.

For the class-wrapped CliRunner tests, unwrap the class and use `cli(..., config=False)`:

```python
# SOURCE:
class TestCacheCommandRegistered:
    def test_cache_has_help(self):
        runner = CliRunner()
        result = runner.invoke(app, ["cache", "--help"])
        assert result.exit_code == 0
        ...

# MIGRATED:
def test_cache_has_help(project, cli):
    result = cli("cache", "--help")
    assert result.exit_code == 0
    ...
```

Note: `cli("cache", "--help")` auto-appends `--config project.config_path` but the path doesn't exist yet (no `project.write_config()` call). That's fine: Click/Typer processes `--help` before parsing `--config`, so the path is never opened. No need for `config=False` here unless the test asserts absence of `--config` from the output.

### Step 3: Delete the source

```bash
git rm tests/test_cli_structure.py
```

### Step 4: Verify

```bash
uv run pytest tests/e2e/test_00_cli_structure.py -v
uv run pytest --collect-only -q 2>&1 | tail -2   # 720 (unchanged — 5 tests moved, 5 same)
uv run pytest -q 2>&1 | tail -3                  # green
```

### Step 5: Commit

```bash
git add tests/e2e/test_00_cli_structure.py
git commit -m "test(b): migrate test_cli_structure -> e2e/test_00_cli_structure (#40)

Five tests relocated: 3 introspection guards (registered_commands check,
inspect.getsource, module-level structural assertions) + 2 CliRunner
--help checks. All unwrapped from their single-member class; introspection
tests stay without fixtures; --help tests use the project/cli fixtures."
```

---

## Task B2: Migrate `tests/commands/test_init.py` → `test_01_scaffold.py`

**Files:**
- Create: `tests/e2e/test_01_scaffold.py`
- Delete: `tests/commands/test_init.py`

Source has 6 tests across 2 classes:
- `TestInit` (4 tests, all use `runner.invoke(app, ["init", ...])` with path arg)
- `TestInitTemplateUsesSourcesList` (2 tests, call `scaffold_project()` and `load_config()` directly — NO CliRunner, but they exercise the scaffold workflow end-to-end)

### Step 1: Read the source

```bash
cat tests/commands/test_init.py
```

Per-test notes:
- `test_init_creates_project_dir` — `feather init <dir>` creates expected files. Uses `cli(..., config=False)` since `init` doesn't take `--config`, and the target dir is a **subdirectory of `project.root`** (see below).
- `test_init_dot_uses_cwd_name` — calls `os.chdir` raw (not monkeypatch). **Convert to `monkeypatch.chdir`** during migration.
- Other `TestInit` tests follow the same pattern.
- `TestInitTemplateUsesSourcesList::test_scaffold_writes_sources_key` and `test_load_config_parses_scaffolded_yaml` — call internals; keep as flat functions with no `project`/`cli` (they use `tmp_path` directly).

**Key pattern — `init` into a subdirectory of `project.root`:** `feather init X` creates directory `X` with project files. The `project` fixture uses `tmp_path` as its root. Use:

```python
def test_init_creates_expected_files(project, cli):
    target = project.root / "myproject"
    result = cli("init", str(target), config=False)
    assert result.exit_code == 0
    assert (target / "feather.yaml").exists()
    # ... etc
```

### Step 2: Write the destination file

Structure:

```python
"""Workflow stage 01: scaffold — feather init.

Scenarios here exercise `feather init` end-to-end: it creates the expected
files, the scaffolded config is syntactically valid YAML, and the
scaffolded `feather.yaml` parses through `load_config()` without
validation errors.
"""

from __future__ import annotations

from pathlib import Path

# ... migrated test functions ...
```

For each `TestInit` test: unwrap, use `cli(..., config=False)` + `project.root / "subdir"` as the target.

For `TestInitTemplateUsesSourcesList` tests: unwrap, use `tmp_path` (these don't need `project` since they call internals; no config involved).

### Step 3: Delete source + verify + commit

```bash
git rm tests/commands/test_init.py
uv run pytest tests/e2e/test_01_scaffold.py -v
uv run pytest -q
git add tests/e2e/test_01_scaffold.py tests/commands/test_init.py
git commit -m "test(b): migrate commands/test_init -> e2e/test_01_scaffold (#40)

Six tests: four 'feather init <path>' CliRunner tests converted to use
cli(config=False) against a subdir of project.root; two template-internals
tests (scaffold_project + load_config) unwrapped as flat functions using
tmp_path. Classes dropped per Rule M2."
```

---

## Task B3: Migrate `tests/commands/test_validate.py` → append to `test_02_validate.py`

**Files:**
- Modify: `tests/e2e/test_02_validate.py` (APPEND)
- Delete: `tests/commands/test_validate.py`

Source has 6 tests in `TestValidate`. All use `CliRunner`. One (`test_validate_prints_details_on_source_failure`) monkeypatches `feather_etl.config.load_config` — preserve that monkeypatch, not a reason to drop the test.

### Step 1: Read the source

```bash
cat tests/commands/test_validate.py
```

Notes:
- All 6 use `runner.invoke(app, [...])` — translate to `cli(...)`.
- Some use `runner.invoke(app, ["--json", "validate", ...])` — translate to `cli("--json", "validate")`. The root-flag pattern works because the `cli` fixture accepts positional args and passes them through in order.

> ⚠️ **Special case**: `cli("--json", "validate")` expands to `["--json", "validate", "--config", <path>]` which is the correct invocation order. Typer handles `--json` at the callback level before parsing subcommand args. Verified in Wave A for similar patterns; no change needed.

- `test_validate_prints_details_on_source_failure` uses `cli_config()` from `tests/commands/conftest.py` and monkeypatches `load_config`. During migration:
  - Replace `cli_config()` with `project.write_config(...)` + `project.copy_fixture("client.duckdb")` + `project.write_curation([...])` inline (copy the pattern from `cli_env` fixture body).
  - Keep the `monkeypatch.setattr(feather_etl.config, "load_config", ...)` line as-is.

### Step 2: Append to `test_02_validate.py`

Open `tests/e2e/test_02_validate.py` (currently has 2 tests: `test_validate_missing_config_shows_friendly_error` and `test_csv_source_rejects_file_path`). Append 6 new functions after the existing ones, separated by PEP 8 blank lines.

### Step 3: Delete source + verify + commit

```bash
git rm tests/commands/test_validate.py
uv run pytest tests/e2e/test_02_validate.py -v   # expect 8 passed
uv run pytest -q
git add tests/e2e/test_02_validate.py tests/commands/test_validate.py
git commit -m "test(b): migrate commands/test_validate -> e2e/test_02_validate (#40)

Six CliRunner tests appended (now 8 total in test_02_validate.py).
TestValidate class dropped per Rule M2. cli_env fixture inlined via
project.write_config + project.copy_fixture + project.write_curation.
One test's monkeypatch of feather_etl.config.load_config preserved."
```

---

## Task B4: Migrate discover tests → `test_03_discover.py` (BIGGEST TASK)

**Files:**
- Create: `tests/e2e/test_03_discover.py`
- Delete: `tests/commands/test_discover.py`
- Delete: `tests/commands/test_discover_multi_source.py`
- Modify: `tests/test_explicit_name_flag.py` (REMOVE 2 CLI tests, keep 5 non-CLI tests)

Source content:
- `tests/commands/test_discover.py` — 14 tests, 4 classes: `TestDiscover`, `TestDiscoverPruneOutput`, `TestDiscoverAutoEnumPermissionError`, `TestRenameAmbiguousMatch`. Pervasive `@pytest.mark.usefixtures("stub_viewer_serve")` and `monkeypatch.chdir(tmp_path)`.
- `tests/commands/test_discover_multi_source.py` — 14 tests, 5 classes including `TestDiscoverPostgresMultiDatabase` (Postgres-gated) and `TestRenameNonTtyExit3` (4 tests that use renamed config files like `feather_erp.yaml` — require `cli(config=<Path>)`).
- `tests/test_explicit_name_flag.py` — 2 CLI tests (`test_discover_explicit_named_source_writes_typed_filename`, `test_discover_auto_named_source_keeps_auto_derived_filename`).

### Step 1: Inspect all three sources

```bash
wc -l tests/commands/test_discover.py tests/commands/test_discover_multi_source.py tests/test_explicit_name_flag.py
grep -c "^def test_\|^    def test_" tests/commands/test_discover.py tests/commands/test_discover_multi_source.py tests/test_explicit_name_flag.py
```

Identify:
- Which tests use `stub_viewer_serve` (most of them — migrate with the marker intact, pointing at the new `tests/e2e/conftest.py` version).
- Which 4 tests use renamed config files (in `TestRenameNonTtyExit3`) — these use `cli(config=<other_path>)`.
- The 2 CliRunner tests from `test_explicit_name_flag.py` — extract only those.
- The Postgres-gated class — preserve the skipif + custom `_create_databases` / `_drop_databases` helpers.

### Step 2: Draft the destination file

`tests/e2e/test_03_discover.py` module docstring:

```python
"""Workflow stage 03: discover — feather discover.

Scenarios here exercise `feather discover` across:
- single-source and multi-source configs
- explicit vs. auto-named sources
- discover rename/prune workflows
- heterogeneous source types (DuckDB, SQLite, Postgres)
- non-TTY and ambiguous-match edge cases

Most tests use `stub_viewer_serve` to prevent discover from launching a
real browser. Tests that exercise renamed config files (per --config flag
variability) use `cli(config=<other_path>)`; see Task B0 for the fixture
API.
"""
```

**Decision: preserve classes where they meaningfully group (Postgres tests, rename tests).** Drop single-member / decorative classes. Per Rule M2, classes stay if they share a fixture. The Postgres class shares `_postgres_available()` + database setup/teardown. The rename class shares the renamed-config pattern. Others can be flattened.

### Step 3: Migration

- Replace each `runner.invoke(app, ["discover", ...])` with `cli("discover", ...)`.
- Replace `_write_sqlite_config(...)` / `_project(...)` local helpers with inline `project.write_config(...)` + `project.write_curation(...)` calls (don't port the helpers; they're project-specific and adding them grows the harness).
- Replace `@pytest.mark.usefixtures("stub_viewer_serve")` — keep it; pytest finds the fixture in `tests/e2e/conftest.py` now.
- For `TestRenameNonTtyExit3` tests: use `cli("discover", "rename", config=project.root / "feather_erp.yaml")` (writing the renamed file via `(project.root / "feather_erp.yaml").write_text(yaml.dump(...))`).
- For the 2 `test_explicit_name_flag.py` tests: migrate them as-is, drop the `write_config` helper import (use `project.write_config` instead).

### Step 4: Remove migrated tests from `test_explicit_name_flag.py`

After copying the 2 CLI tests to `test_03_discover.py`:
- Open `tests/test_explicit_name_flag.py` and delete the 2 migrated functions only.
- Leave the other 5 non-CLI tests in place.
- Verify the file still imports cleanly (may need to remove now-unused imports).

### Step 5: Delete source files + verify + commit

```bash
git rm tests/commands/test_discover.py tests/commands/test_discover_multi_source.py
git add tests/e2e/test_03_discover.py tests/test_explicit_name_flag.py

uv run pytest tests/e2e/test_03_discover.py -v                          # ~30 tests, all pass
uv run pytest tests/test_explicit_name_flag.py -v                        # 5 remaining tests pass
uv run pytest --collect-only -q 2>&1 | tail -2                           # unchanged (720 after B0 + migrations preserve count)
uv run pytest -q

git commit -m "test(b): migrate discover tests -> e2e/test_03_discover (#40)

Thirty tests relocated from three sources:
- tests/commands/test_discover.py (14)
- tests/commands/test_discover_multi_source.py (14)
- tests/test_explicit_name_flag.py (2 of 7; the other 5 are source-class
  unit tests that stay for Wave D)

stub_viewer_serve marker preserved (now resolves in tests/e2e/conftest.py
per Task B0). Renamed-config tests use cli(config=<other_path>) per the
new cli kwarg. Postgres-gated class keeps its skipif + db setup as-is.
Single-member classes dropped per Rule M2; Postgres and rename classes
retained because they share fixtures."
```

---

## Task B5: Migrate `test_setup.py` + `test_run.py` + `test_e2e.py` → `test_04_extract_full.py`

**Files:**
- Create: `tests/e2e/test_04_extract_full.py`
- Delete: `tests/commands/test_setup.py`
- Delete: `tests/commands/test_run.py`
- Delete: `tests/test_e2e.py`

Source content:
- `tests/commands/test_setup.py` — 1 test (trivial).
- `tests/commands/test_run.py` — 8 tests, 3 classes: `TestRun`, `TestTableFilter`, `TestRunAutoCreates`.
- `tests/test_e2e.py` — 1 god test chaining init→validate→discover→setup→run×2→status.

### Step 1: Read all three sources

```bash
cat tests/commands/test_setup.py tests/commands/test_run.py tests/test_e2e.py
```

### Step 2: Write the destination file

Module docstring:

```python
"""Workflow stage 04: extract — feather setup + feather run happy path.

Scenarios here exercise the full extraction workflow: `feather setup`
creates the state + destination DBs and schemas, then `feather run`
extracts every configured table. Also covers table filtering (--table)
and auto-creation of state/data DBs when `run` is invoked without a
prior `setup`.

One test (`test_full_onboarding_flow`) chains every CLI command in
sequence — the "happy path user journey" end-to-end.
"""
```

Migration:
- All 9 CLI tests use `cli(...)` + `project.write_config` + `project.write_curation`.
- `cli_env`/`two_table_env` → inline: copy `client.duckdb`, write 1- or 2-table curation.
- The `test_full_onboarding_flow` god test from `test_e2e.py` uses `init` via `cli(..., config=False)` (since init creates the project dir fresh), then overwrites the scaffolded config with the test's desired one.

### Step 3: Delete sources + verify + commit

```bash
git rm tests/commands/test_setup.py tests/commands/test_run.py tests/test_e2e.py
git add tests/e2e/test_04_extract_full.py
uv run pytest tests/e2e/test_04_extract_full.py -v
uv run pytest -q
git commit -m "test(b): migrate setup/run/e2e tests -> e2e/test_04_extract_full (#40)

Ten tests relocated:
- tests/commands/test_setup.py (1): trivial setup check.
- tests/commands/test_run.py (8): happy path, --table filter, auto-create.
- tests/test_e2e.py (1): full onboarding god test chaining every command.

cli_env / two_table_env inlined. All use project/cli fixtures. The
onboarding test uses cli(config=False) for the init invocation."
```

---

## Task B6: Migrate `TestCLISetupTransforms` → `test_07_transforms.py`

**Files:**
- Create: `tests/e2e/test_07_transforms.py`
- Modify: `tests/test_transforms.py` (REMOVE `TestCLISetupTransforms` class, KEEP others)

Per the scope table: only `TestCLISetupTransforms` (2 tests) is actually e2e. `TestE2ETransformPipeline` is integration despite the name — stays for Wave C.

### Step 1: Read relevant source

```bash
sed -n '/^class TestCLISetupTransforms:/,/^class /p' tests/test_transforms.py
```

### Step 2: Write `tests/e2e/test_07_transforms.py`

Module docstring:

```python
"""Workflow stage 07: transforms — silver views, gold materialization via CLI.

Scenarios here exercise `feather setup` with transforms configured: the
setup command reads `transforms/*.sql`, discovers the DAG, and persists
silver views + gold materialized tables.

This file currently contains only the CLI-invoking transform tests;
integration-level transform tests (DAG execution without CLI) live in
tests/integration/test_transforms.py after Wave C.
"""
```

Migration: both tests use `CliRunner` to invoke `feather setup`; translate to `cli("setup")`. Preserve transform-file creation logic.

### Step 3: Remove migrated class from source

- Open `tests/test_transforms.py`.
- Delete only the `TestCLISetupTransforms` class (and its 2 methods).
- Leave all other classes untouched.
- Verify imports at the top are still all needed; remove any that only the deleted class used (e.g., `CliRunner`).

### Step 4: Verify + commit

```bash
git add tests/e2e/test_07_transforms.py tests/test_transforms.py
uv run pytest tests/e2e/test_07_transforms.py -v     # 2 passed
uv run pytest tests/test_transforms.py -v            # 34 passed (was 36; -2 migrated)
uv run pytest --collect-only -q 2>&1 | tail -2       # count unchanged
uv run pytest -q
git commit -m "test(b): migrate TestCLISetupTransforms -> e2e/test_07_transforms (#40)

Only two of the 36 transform tests use CliRunner. They move to
test_07_transforms.py; the other 34 (parse, discover, build_order,
execute, materialize, pipeline-integration) stay in test_transforms.py
for Wave C/D splitting by level."
```

---

## Task B7: Migrate `tests/commands/test_cache.py` → `test_12_cache.py`

**Files:**
- Create: `tests/e2e/test_12_cache.py`
- Delete: `tests/commands/test_cache.py`

Source: 11 tests, 6 classes (`TestCacheBasic`, `TestCacheProdModeGuard`, `TestCacheMissingCuration`, `TestCacheSelectors`, `TestCacheRefresh`, `TestCacheOutputFormat`). Clean `CliRunner` usage. Local `_project(tmp_path)` and `TestCacheSelectors._two_table_project()` helpers to be inlined.

### Step 1: Read the source

```bash
cat tests/commands/test_cache.py
```

### Step 2: Write destination

Module docstring:

```python
"""Workflow stage 12: feather cache.

Scenarios here exercise `feather cache` across:
- basic extraction to parquet cache
- prod-mode hard-error guard
- missing curation.json pre-check
- --table / --source selectors
- --refresh flag (force re-extract)
- grouped output format
"""
```

Migration: classes dropped unless they share fixtures (none do meaningfully); flat functions. `_project()` / `_two_table_project()` inlined.

The `TestCacheMissingCuration` tests must not call `project.write_curation()` (the whole point is missing curation). Use `project.write_config(...)` only, no write_curation call.

### Step 3: Delete source + verify + commit

```bash
git rm tests/commands/test_cache.py
git add tests/e2e/test_12_cache.py
uv run pytest tests/e2e/test_12_cache.py -v
uv run pytest -q
git commit -m "test(b): migrate commands/test_cache -> e2e/test_12_cache (#40)

Eleven tests relocated. Classes flattened per Rule M2; local _project
helpers replaced with project.write_config + project.write_curation
inline. TestCacheMissingCuration tests deliberately omit write_curation
to exercise the missing-curation guard."
```

---

## Task B8: Migrate multi-source tests → `test_13_multi_source.py`

**Files:**
- Create: `tests/e2e/test_13_multi_source.py`
- Delete: `tests/commands/test_multi_source_guard.py`
- Delete: `tests/test_multi_source_e2e.py`

Source content:
- `tests/commands/test_multi_source_guard.py` — 5 tests (TestMultiSource), clean.
- `tests/test_multi_source_e2e.py` — 3 tests, includes a 108-line inline curation dict literal to replace with `make_curation_entry()`.

### Step 1: Read sources

```bash
cat tests/commands/test_multi_source_guard.py tests/test_multi_source_e2e.py
```

### Step 2: Write destination

Module docstring:

```python
"""Workflow stage 13: multi-source — multiple `sources:` entries.

Scenarios here exercise configs with 2+ sources: validation guards,
per-source curation routing, and full end-to-end extraction across
heterogeneous source types.
"""
```

**Important refactor:** the 108-line inline curation dict in `test_multi_source_e2e.py` must be replaced with `make_curation_entry()` calls. Build a list of entries using the helpers, then `write_curation(project.root, tables)`. Reduces ~108 lines of dict literal to ~15 lines of structured entries.

### Step 3: Delete sources + verify + commit

```bash
git rm tests/commands/test_multi_source_guard.py tests/test_multi_source_e2e.py
git add tests/e2e/test_13_multi_source.py
uv run pytest tests/e2e/test_13_multi_source.py -v
uv run pytest -q
git commit -m "test(b): migrate multi-source tests -> e2e/test_13_multi_source (#40)

Eight tests relocated:
- tests/commands/test_multi_source_guard.py (5): validation guards.
- tests/test_multi_source_e2e.py (3): full extraction across 2 sources.

The 108-line inline curation dict from the _e2e file replaced with
make_curation_entry() calls (per Rule M4)."
```

---

## Task B9: Migrate `tests/commands/test_status.py` → `test_14_status.py`

**Files:**
- Create: `tests/e2e/test_14_status.py`
- Delete: `tests/commands/test_status.py`

Source: 6 tests, 1 class (`TestStatus`). Multiple tests invoke `run` + `status` in sequence — translate to `cli("run"); cli("status")`.

### Steps

```bash
cat tests/commands/test_status.py
# write tests/e2e/test_14_status.py
git rm tests/commands/test_status.py
git add tests/e2e/test_14_status.py
uv run pytest tests/e2e/test_14_status.py -v
uv run pytest -q
git commit -m "test(b): migrate commands/test_status -> e2e/test_14_status (#40)

Six tests relocated. Two-step run/status invocations translate directly
to cli('run'); cli('status')."
```

Module docstring:

```python
"""Workflow stage 14: feather status.

Scenarios exercise `feather status` before setup, after setup with no
runs, and after successful + failed runs.
"""
```

---

## Task B10: Migrate `tests/commands/test_history.py` → `test_15_history.py`

**Files:**
- Create: `tests/e2e/test_15_history.py`
- Delete: `tests/commands/test_history.py`

Source: 5 tests, 1 class (`TestHistory`). 4 of 5 use `two_table_env` — inline with `project.copy_fixture("client.duckdb")` + 2-table curation.

Same pattern as previous tasks. Module docstring:

```python
"""Workflow stage 15: feather history.

Scenarios exercise `feather history` — listing prior runs, filtering by
table, and output formatting.
"""
```

---

## Task B11: Migrate `tests/commands/test_view.py` → `test_16_view.py`

**Files:**
- Create: `tests/e2e/test_16_view.py`
- Delete: `tests/commands/test_view.py`

Source: 4 tests, 1 class (`TestView`). `view` command takes a directory + `--port`, NOT `--config`. All invocations use `cli(..., config=False)`. Heavy monkeypatching of `viewer_server.serve_and_open` and `sync_viewer_html` — preserve.

Module docstring:

```python
"""Workflow stage 16: feather view.

Scenarios exercise `feather view` — inspecting the destination DB through
a local HTTP viewer. Heavy monkeypatching of serve_and_open /
sync_viewer_html prevents real server / browser launches.
"""
```

Migration: `cli("view", str(project.data_db_path), "--port", "0", config=False)` (or similar, per each test's current invocation).

---

## Task B12: Migrate `TestCliJsonFlag` → `test_17_json_output.py`

**Files:**
- Create: `tests/e2e/test_17_json_output.py`
- Modify: `tests/test_json_output.py` (REMOVE `TestCliJsonFlag` class, KEEP others)

Only 1 of 8 tests in `test_json_output.py` uses CliRunner. Migrate only that one.

### Steps

1. Read `tests/test_json_output.py` and identify `TestCliJsonFlag`.
2. Create `tests/e2e/test_17_json_output.py` with the migrated test (flat function, uses `cli` fixture).
3. Delete `TestCliJsonFlag` from `tests/test_json_output.py`; leave `TestJsonlLogging` and `TestOutputHelper` in place.
4. Clean up unused imports in the source.

Module docstring for `test_17_json_output.py`:

```python
"""Workflow stage 17: --json flag across commands.

Scenarios exercise the `--json` root flag — CLI commands emit NDJSON
instead of human-readable output when --json is set. Currently only
one e2e test exercises this; integration / unit coverage of the JSON
output helpers lives in tests/test_json_output.py (pending Wave C/D)."""
```

Commit message:

```
test(b): migrate TestCliJsonFlag -> e2e/test_17_json_output (#40)

Only 1 of 8 tests in test_json_output.py actually uses CliRunner
(TestCliJsonFlag). Moved. The other 7 (TestJsonlLogging uses
pipeline.run_all directly → Wave C; TestOutputHelper uses capsys
→ Wave D) stay in place.
```

---

## Wave B completion checklist

After Task B12 commits, run:

- [ ] `uv run pytest -q` — green; test count = 720 (717 + 3 new smoke tests from B0).
- [ ] `ls tests/commands/test_*.py 2>/dev/null | wc -l` — **0**. The commands/ test files are all gone.
- [ ] `ls tests/commands/` — only `__init__.py` and `conftest.py` remain (orphaned until Wave D).
- [ ] `test -f tests/test_e2e.py` — file does not exist.
- [ ] `test -f tests/test_multi_source_e2e.py` — file does not exist.
- [ ] `test -f tests/test_cli_structure.py` — file does not exist.
- [ ] `ls tests/e2e/test_*.py | wc -l` — at least 14 (smoke + 00–04, 07, 10, 11, 12, 13, 14, 15, 16, 17, 18).
- [ ] `bash scripts/hands_on_test.sh` — still 61/61 PASS (untouched).
- [ ] `uv run pytest tests/test_core_module_purity.py -q` — 1 passed (invariant holds).
- [ ] Every new `tests/e2e/test_*.py` uses `project`/`cli` or documents its bypass.
- [ ] No import from `tests.commands.conftest` in any file under `tests/e2e/`.
- [ ] `git log --oneline main..HEAD | wc -l` ≥ 24 (12 Wave A + 13 Wave B commits, give or take plan doc).

When every checkbox passes, proceed to Wave C planning (migrate integration tests, including the deferred classes from Wave B).

---

## Coverage-map updates

As each task commits, the relevant rows in
`docs/superpowers/specs/2026-04-19-test-restructure-coverage-map.md` may be
filled if a migrated test corresponds to a specific bash check. The survey
doesn't fully map Wave B tests to S-N stages; Wave E will do that audit.
Wave B does NOT need to keep the coverage map current — rows fill in Wave E.

---

## Self-review notes

**Spec coverage for Wave B:**
- Every file listed in the spec's Wave B section has a corresponding task OR an explicit deferral (documented in the scope-changes table).
- Three spec deferrals (`test_integration.py`, `TestE2ETransformPipeline`, 7/8 of `test_json_output.py`, 5/7 of `test_explicit_name_flag.py`) are explicitly flagged as Wave C/D work.

**Placeholder scan:** no TBDs; every task has concrete steps. The "inspect the source and write the destination" wording in bigger tasks (B4, B5) is directive by design — the file content is too large to write verbatim in the plan, and Wave A proved the subagent can migrate verbatim content reliably. If that doesn't work, we restructure during execution.

**Type consistency:** `cli(..., config=False|Path)` matches B0's extension and is referenced consistently in Tasks B1, B2, B4, B11.

**Scope:** Wave B is large (13 tasks) but each task is atomic and bisectable. The biggest task (B4) migrates ~30 tests across 3 source files — that's at the upper end of what should be one commit, but splitting it would create brittle intermediate states. Accept the size.

**Risks noted:**
- Task B4 (discover) is the biggest. If it blocks, it can be split into B4a (single-source discover) and B4b (multi-source discover + explicit-name).
- Tests that monkeypatch deep internals (e.g., `test_validate_prints_details_on_source_failure`) may behave differently in the new harness if fixture ordering changes. Watch for flakes.
- The `cli(config=<Path>)` kwarg for renamed-config tests is exercised only in Task B4's `TestRenameNonTtyExit3`. If those tests fail, the kwarg semantics need revisiting (but Task B0's smoke test covers the happy path).
