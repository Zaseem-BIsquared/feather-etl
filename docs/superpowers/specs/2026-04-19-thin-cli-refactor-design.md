# Thin-CLI Refactor Design (`#43`)

- **Issue:** [#43](https://github.com/siraj-samsudeen/feather-etl/issues/43)
- **Date:** 2026-04-19
- **Status:** Design approved, ready for implementation planning
- **Type:** Refactor (behavior-preserving)
- **Scope:** Refactor `commands/<name>.py` modules to follow the thin-CLI ↔ pure-core pattern already used by `commands/run.py` ↔ `pipeline.py` and `commands/cache.py` ↔ `cache.py`.

## Goal

Split each command module into two layers so the orchestration logic is reusable and directly testable without going through `CliRunner`:

| Layer | Responsibility | Typer-aware? |
|---|---|---|
| `commands/<name>.py` | Flag parsing, prompts, output formatting, exit-code translation. | Yes |
| `<name>.py` (top-level) | Pure orchestration / IO / data flow. Returns values or raises domain exceptions. | **No** |

## Non-Negotiable Constraints

1. **No CLI behavior changes.** Every `feather <cmd> --flag` invocation produces byte-identical stdout/stderr, identical exit codes, identical prompts, identical JSON output.
2. **No flag/option/default changes.** The CLI surface is frozen.
3. **No edits outside the named scope.** `pipeline.py`, `cache.py`, `state.py`, `config.py`, `init_wizard.py`, `viewer_server.py`, `commands/_common.py`, `commands/run.py`, and `commands/cache.py` are not touched. The only exception is if Task 3's purity test surfaces an unexpected `typer` import in `viewer_server.py` or `init_wizard.py`, in which case that import is removed in the same commit.
4. **No new features during refactor.** Scope discipline matters; this is a structural change only.
5. **One commit per command refactor.** Per the issue's explicit requirement.
6. **Top-level core modules must not import `typer`.** Enforced by an automated purity test (see Task 3).
7. **Existing test suites stay green.** `uv run pytest -q` (653 tests) and `bash scripts/hands_on_test.sh` (61 checks) are the safety net.

## Reference Pattern

Two modules already follow the target shape and serve as references:

- `commands/run.py` (74 lines, thin Typer wrapper) ↔ `pipeline.py` (`run_all() -> list[ExtractResult]`)
- `commands/cache.py` (154 lines, thin Typer wrapper with rich grouped output) ↔ `cache.py` (`run_cache() -> list[CacheResult]`)

Both demonstrate the convention this refactor generalizes:

- Per-item failures across many items (one source failed, one table failed) are captured as `status="failure"` entries in the result list. Cores do not raise for per-item failures.
- The CLI sums failures and decides exit codes.
- The CLI is purely a formatter for the data the core returns.

## Convention for the New Cores

To keep the refactor from drifting, every new core in this work follows these rules:

| Concern | How the core handles it |
|---|---|
| Per-item failure across many items | Capture as `status="failure"` entry in the result list. Don't raise. CLI sums and decides exit code. (Matches `pipeline`, `cache`.) |
| Fatal preconditions (config not found, validation errors, state DB missing, prod-mode guard tripped) | Raise a domain exception. CLI catches and translates to `typer.echo(err) + typer.Exit(code)`. |
| Pure read-through (history, status) | Return `list[dict]` straight from `StateManager`. The "no state DB" precondition raises `StateDBMissingError`. |
| Multi-stage orchestration with structured output (discover, setup, validate) | Return a small dataclass that carries the counts/items the CLI needs to format. |
| User interaction (prompts, `typer.confirm`) | Stays in the CLI wrapper. The core takes a pre-resolved decision as a value, never a callback. |

Domain exceptions live in `src/feather_etl/exceptions.py` if more than one core needs them. If only one core needs an exception, define it inline in that core. Decided in Task 1 when `StateDBMissingError` is introduced; Task 2 reuses it (so it lives in `exceptions.py`).

## Architecture

### Target file layout (additions only — no removals)

```text
src/feather_etl/
  exceptions.py            # NEW: shared domain exceptions (StateDBMissingError, ...)
  discover.py              # NEW: detect_renames_for_sources, apply_rename_decision, run_discover
  setup.py                 # NEW: run_setup, SetupResult
  validate.py              # NEW: run_validate, ValidateReport, SourceCheckResult
  status.py                # NEW: load_status
  history.py               # NEW: load_history
  commands/
    discover.py            # SHRUNK from 274 → ~80 lines
    setup.py               # SHRUNK from 105 → ~50 lines
    validate.py            # SHRUNK from 66 → ~40 lines
    status.py              # SHRUNK from 68 → ~40 lines
    history.py             # SHRUNK from 75 → ~40 lines
    init.py                # VERIFIED only (likely no change)
    view.py                # VERIFIED only (already conformant)

tests/
  test_core_module_purity.py   # NEW: parametrized "no typer import" assertion
  test_history_core.py         # NEW: direct unit tests, no CliRunner
  test_status_core.py          # NEW
  test_validate_core.py        # NEW
  test_setup_core.py           # NEW
  test_discover_core.py        # NEW
```

### Untouched (do not edit)

`cli.py`, `commands/_common.py`, `commands/cache.py`, `commands/run.py`, `pipeline.py`, `cache.py`, `state.py`, `config.py`, `init_wizard.py`, `viewer_server.py`, all `sources/*`, `destinations/*`, `transforms.py`, `dq.py`, `alerts.py`, `schema_drift.py`, `output.py`, `curation.py`. Plus all existing tests except for any that incidentally need import-path updates (none expected — all existing tests go through `CliRunner` or import from `pipeline`/`cache`).

### Concrete API shapes for the new cores

```python
# src/feather_etl/exceptions.py
class StateDBMissingError(Exception):
    """Raised when an operation requires the state DB but it does not exist."""

# src/feather_etl/history.py
def load_history(state_path: Path, *, table: str | None = None,
                 limit: int = 20) -> list[dict]:
    """Return recent run history rows. Raises StateDBMissingError if no DB."""

# src/feather_etl/status.py
def load_status(state_path: Path) -> list[dict]:
    """Return per-table last-run status rows. Raises StateDBMissingError if no DB."""

# src/feather_etl/validate.py
@dataclass
class SourceCheckResult:
    type: str
    label: str           # path or host, whichever the source exposes
    ok: bool
    error: str | None    # source._last_error when ok is False

@dataclass
class ValidateReport:
    sources: list[SourceCheckResult]
    tables_count: int
    all_ok: bool         # True iff every source.ok is True

def run_validate(cfg: FeatherConfig) -> ValidateReport: ...

# src/feather_etl/setup.py
@dataclass
class SetupResult:
    state_db_path: Path
    destination_path: Path
    transform_results: list[TransformResult] | None  # None if no transforms found

def run_setup(cfg: FeatherConfig) -> SetupResult: ...

# src/feather_etl/discover.py
@dataclass
class RenameDetection:
    proposals: list[tuple[str, str]]   # (old_name, new_name)
    ambiguous: list[tuple[str, list[str]]]  # (new_name, [candidate_old_names])

@dataclass
class SourceDiscoveryResult:
    name: str
    decision: str        # "new" | "retry" | "rerun" | "cached" | "skip" | "removed"
    status: str          # "succeeded" | "failed" | "cached" | "skipped" | "pruned"
    table_count: int = 0
    output_path: Path | None = None
    error: str | None = None

@dataclass
class DiscoverReport:
    results: list[SourceDiscoveryResult]
    succeeded_count: int
    failed_count: int
    cached_count: int
    pruned_count: int
    state_last_run_at: str | None  # for the "state file found, last run X" header

def detect_renames_for_sources(state, sources) -> RenameDetection: ...

def apply_rename_decision(state, accepted: list[tuple[str, str]],
                          rejected: list[tuple[str, str]],
                          sources, config_dir: Path) -> None: ...

def run_discover(cfg: FeatherConfig, config_dir: Path, *,
                 refresh: bool, retry_failed: bool, prune: bool) -> DiscoverReport: ...
```

The CLI wrappers handle prompt UX and translate `DiscoverReport`/`SetupResult`/`ValidateReport` into the existing per-line output and exit codes.

## Task Breakdown

Each task = one commit. TDD: the direct unit test for the new core is written first and demonstrates the core works without `CliRunner`; only then is the CLI wrapper rewritten to delegate.

### Task 1 — Extract `history` core

- **What:** Create `src/feather_etl/exceptions.py` with `StateDBMissingError`. Create `src/feather_etl/history.py` with `load_history()`. Rewrite `commands/history.py` to delegate.
- **TDD test:** `tests/test_history_core.py::test_load_history_returns_rows_from_state_db`, `test_raises_state_db_missing_when_no_db`. Both use a real DuckDB fixture, no Typer.
- **Code:** `load_history` is ~10 lines: existence check → `StateManager(path).get_history(table_name=..., limit=...)`. Wrapper catches `StateDBMissingError` and translates to the existing `"No state DB found. Run 'feather run' first."` message + `Exit(1)`.

### Task 2 — Extract `status` core

- **What:** Create `src/feather_etl/status.py` with `load_status()` reusing `StateDBMissingError`. Rewrite `commands/status.py`.
- **TDD test:** `tests/test_status_core.py::test_load_status_returns_rows`, `test_raises_state_db_missing_when_no_db`.
- **Code:** ~8 lines for the core. Wrapper preserves the existing `"No state DB found. Run 'feather setup' first."` message + `Exit(1)`.

### Task 3 — Add core-module purity test

- **What:** Create `tests/test_core_module_purity.py` with a parametrized test that asserts each pure-core module has no `typer` import in its source. Initially populate with the modules that already exist as pure cores: `pipeline`, `cache`, `viewer_server`, `init_wizard`, plus the two added in Tasks 1–2: `history`, `status`, `exceptions`.
- **Why this exists:** The issue specifies the no-`typer`-import constraint as a manual `grep` check. Encoding it as a test makes it self-enforcing and regression-proof. Subsequent tasks add their new module to the parametrize list as part of the same commit.
- **TDD test:** The test itself is the new test. Implementation:
  ```python
  import importlib, inspect
  import pytest
  CORE_MODULES = ["feather_etl.pipeline", "feather_etl.cache",
                  "feather_etl.viewer_server", "feather_etl.init_wizard",
                  "feather_etl.history", "feather_etl.status",
                  "feather_etl.exceptions"]
  @pytest.mark.parametrize("module_name", CORE_MODULES)
  def test_core_module_does_not_import_typer(module_name):
      module = importlib.import_module(module_name)
      source = inspect.getsource(module)
      assert "import typer" not in source, f"{module_name} imports typer"
      assert "from typer" not in source, f"{module_name} imports from typer"
  ```
- **Risk:** If `viewer_server` or `init_wizard` fails the test, fix the offending import in the same commit.

### Task 4 — Verify `init` is already conformant

- **What:** Review `commands/init.py`. Confirm the dir-exists guard belongs in the CLI (it's a UX/overwrite-prevention concern, not a scaffolding correctness rule — `init_wizard.scaffold_project()` should remain callable from any context without surprise prompts). Confirm `init_wizard` passes the purity test from Task 3.
- **Outcome:** If no tidy-up surfaces, **skip the commit and note in PR description "Task 4: verified, no changes needed."** Empty commits are noise; the spec + PR description are the audit trail. If a tidy-up surfaces, commit it.

### Task 5 — Extract `validate` core

- **What:** Create `src/feather_etl/validate.py` with `ValidateReport`, `SourceCheckResult`, and `run_validate()`. Rewrite `commands/validate.py` to call it and format output. Add `feather_etl.validate` to the purity test parametrize list.
- **TDD test:** `tests/test_validate_core.py::test_run_validate_reports_each_source_status`, `test_returns_all_ok_false_when_any_source_check_fails`, `test_propagates_last_error_for_failed_sources`.
- **Code:** Iterate `cfg.sources`, call `source.check()`, build `SourceCheckResult(type, label, ok, error)` for each. Set `all_ok = all(r.ok for r in results)`. ~30 lines including the dataclasses. The config-load + validation-write step (`commands/_common._load_and_validate()`) stays as-is — it's a CLI concern that writes the user-visible JSON and raises `typer.Exit`.

### Task 6 — Extract `setup` core

- **What:** Create `src/feather_etl/setup.py` with `SetupResult` and `run_setup()`. Move state init, schema setup, and transform execution out of `commands/setup.py`. Add `feather_etl.setup` to the purity test parametrize list.
- **TDD test:** `tests/test_setup_core.py::test_run_setup_initializes_state_and_destination`, `test_run_setup_executes_transforms_when_present`, `test_run_setup_in_prod_mode_runs_gold_only`, `test_run_setup_returns_none_transforms_when_no_transforms_found`.
- **Code:** ~50 lines. The conditional transform discovery + mode-aware execution (prod-mode runs gold-only; non-prod uses `force_views=True`) must be preserved exactly. Wrapper formats the existing summary lines (silver/gold/views/tables counts) from `SetupResult.transform_results`.

### Task 7 — Extract `discover` core (the big one)

- **What:** Create `src/feather_etl/discover.py` with three top-level functions:
  - `detect_renames_for_sources(state, sources) -> RenameDetection` (pure detection, no I/O)
  - `apply_rename_decision(state, accepted, rejected, sources, config_dir) -> None` (applies a pre-resolved decision)
  - `run_discover(cfg, config_dir, *, refresh, retry_failed, prune) -> DiscoverReport` (per-source discovery loop; assumes renames already resolved)

  Move `_fingerprint_for()` and `_write_schema()` helpers into the new module. The CLI wrapper handles the `typer.confirm` interactively, translates `--yes`/`--no-renames`/TTY-state into the call to `apply_rename_decision`, and calls `serve_and_open()` after `run_discover()` returns. Add `feather_etl.discover` to the purity test parametrize list.

- **Why this shape:** Splitting rename handling out of `run_discover` makes each function pure and value-driven. The rename phase and the per-source discovery loop are logically independent — they were always two phases stapled together. A callback parameter (`confirm_renames: Callable | None`) was rejected because callbacks let the core do arbitrary I/O via the callback, defeating purity, and they're harder to test than pre-resolved values.

- **TDD tests** (`tests/test_discover_core.py`):
  - `test_detect_renames_for_sources_finds_proposals_when_fingerprints_match`
  - `test_detect_renames_for_sources_returns_ambiguous_when_multiple_candidates`
  - `test_apply_rename_decision_renames_state_and_files_for_accepted`
  - `test_apply_rename_decision_marks_orphaned_for_rejected`
  - `test_run_discover_records_succeeded_sources_with_table_counts`
  - `test_run_discover_records_failed_sources_with_error_message`
  - `test_run_discover_with_prune_removes_state_and_files`
  - `test_run_discover_with_refresh_ignores_cached_state`
  - `test_run_discover_with_retry_failed_only_retries_failed`
  - `test_run_discover_handles_pre_set_last_error_from_expand_db_sources`

- **Code:** ~150 lines for the core (vs. 274 mixed). Wrapper ~80 lines: flag parsing → rename decision computation (the `--yes` / `--no-renames` / TTY logic) → `run_discover()` call → output formatting → `serve_and_open()` → exit code (2 if any failures).

## Dependency Chain

Strict linear order, one commit per task:

```
Task 1 (history) → Task 2 (status) → Task 3 (purity test) → Task 4 (init verify)
                                                                  ↓
                                       Task 5 (validate) → Task 6 (setup) → Task 7 (discover)
```

**Ordering rationale:**

- **Task 1 → 2:** `status` reuses `StateDBMissingError` defined by `history`. Doing `history` first means it decides where the exception lives (`exceptions.py`).
- **Task 2 → 3:** Purity test arrives after the two simplest cores so it has more entries from day one and any drift in the convention has already surfaced.
- **Task 3 → 4:** Purity test must exist before `init` verification because the verification *is* "does `init_wizard` pass the purity test."
- **Task 4 → 5:** `validate` is the first dataclass-shaped core. Doing it before `setup` lets the `ValidateReport` / `SourceCheckResult` shape stabilize before `setup` / `discover` adopt the same convention.
- **Task 5 → 6 → 7:** Increasing complexity. `setup` introduces side-effecting dataclasses; `discover` is the boss fight. Each prior task de-risks the next.

No parallelism. Every task touches a different file in `src/feather_etl/` and a different test file, but they share the convention contract that's still solidifying. Sequential execution lets each task refine the convention for the next.

## Done Signal

The single command sequence that proves it all works end-to-end:

```bash
uv run pytest -q && bash scripts/hands_on_test.sh && \
  for f in discover setup validate status history; do
    grep -L typer "src/feather_etl/$f.py" >/dev/null && echo "$f: pure ✓" || echo "$f: HAS TYPER ✗"
  done && \
  uv run pytest -q tests/test_core_module_purity.py tests/test_*_core.py -v
```

When this runs clean — pytest green (653+ tests, including the new direct-unit-test files), 61 hands-on checks green, all five new core modules grep-clean of `typer`, and the new direct-unit-test files for each core module pass without any `CliRunner` import — the refactor is done.

**Bonus invariant for code review:** `git log --oneline <branch> ^main` shows exactly 6 or 7 commits (one per task, possibly skipping Task 4), each scoped to one command.

## Out of Scope

- Adding features or new CLI flags while refactoring.
- Changing the CLI surface — every command's `--flag` list stays identical.
- Touching `pipeline.py`, `cache.py`, `_common.py`, or other core modules beyond the extractions described.
- Refactoring `cache.py` or `commands/cache.py` (already conformant).
- Issue #40 (retiring `scripts/hands_on_test.sh` in favor of pytest E2E) — independent.
- Issue #15 follow-ups — independent.
- Performance optimizations.
- Adding type annotations beyond what the cores need to declare their public API.

## Open Questions

None at design time. The two design-level open questions raised during brainstorming were resolved:

1. **Rename handling in `discover` extraction:** Split into three pure top-level functions (`detect_renames_for_sources`, `apply_rename_decision`, `run_discover`) rather than a callback parameter. The CLI wrapper holds prompt UX in one place.
2. **`view`/`init` verify-only tasks:** Encoded as an automated purity test (Task 3) that turns the issue's manual `grep` check into a self-enforcing assertion. Empty commits are avoided; verification audit trail lives in spec + PR description.
