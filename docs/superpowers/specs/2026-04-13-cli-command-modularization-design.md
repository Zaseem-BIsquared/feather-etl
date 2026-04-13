# CLI Command Modularization Design (`#19`)

- **Issue:** [#19](https://github.com/siraj-samsudeen/feather-etl/issues/19)
- **Date:** 2026-04-13
- **Status:** Design approved, ready for implementation planning
- **Scope:** Refactor CLI structure only (strict no behavior change)

## Goal

Split the monolithic `src/feather_etl/cli.py` into one module per command so command ownership, feature traceability, and test mapping are explicit. Keep runtime behavior exactly aligned with current `upstream/main` (which already includes `#16` changes).

## Non-Negotiable Constraints

1. No command behavior changes.
2. No output wording changes.
3. No flag/option/default changes.
4. No exit-code changes.
5. No backing-logic changes (`pipeline.py`, `state.py`, `config.py`, etc. remain functionally untouched).

## Architecture

### Target file layout

```text
src/feather_etl/
  cli.py
  commands/
    __init__.py
    _common.py
    init.py
    validate.py
    discover.py
    setup.py
    run.py
    history.py
    status.py
```

### `cli.py` responsibilities

- Own `app = typer.Typer(...)`.
- Own global callback for `--json` context wiring.
- Import command-module `register(app)` functions.
- Register commands explicitly in one place (audit-friendly inventory).

### `commands/_common.py` responsibilities

- Host shared helpers moved from current `cli.py`:
  - `_is_json(ctx: typer.Context) -> bool`
  - `_load_and_validate(config_path: Path, mode_override: str | None = None)`
- Preserve helper behavior and error paths exactly.

### `commands/<cmd>.py` responsibilities

Each command module owns:
- The command implementation function (copied from current `cli.py` with minimal movement edits).
- A `register(app: typer.Typer) -> None` function that binds the command.

Registration style is explicit `register(app)` (not import side effects), to maximize traceability.

## Behavioral Baseline (Must Match Exactly)

Behavior must remain identical to current `upstream/main` at implementation time, including:

- `discover` behavior from closed `#16` (write auto-named JSON file and print summary line).
- Existing command signatures (including commands that accept `ctx` and those that do not).
- Existing error conditions and exit codes:
  - Validation/config errors (`1`)
  - Source connection failures where currently used (`2`)
  - State/history/status current no-data/no-db behavior unchanged

## Data Flow

1. CLI process starts through `cli.py`.
2. Callback stores `json_mode` in Typer context object.
3. Registered command executes from its module.
4. Command uses `_common` helpers and existing backend modules.
5. Outputs/errors propagate exactly as before.

Only code location changes; runtime flow semantics do not.

## Testing Strategy

## Commit A: CLI split only

- Move command code into `src/feather_etl/commands/*`.
- Keep tests in current locations.
- Run tests and confirm green without assertion edits.

## Commit B: test reorganization only

Move command-facing tests into:

```text
tests/commands/
  test_init.py
  test_validate.py
  test_discover.py
  test_setup.py
  test_run.py
  test_history.py
  test_status.py
```

Keep non-command helper tests outside `tests/commands` where appropriate (example: `discover` config helper unit tests can remain in their domain-focused file if they do not validate CLI command behavior directly).

No assertion/behavior changes in this commit; organization-only movement and imports.

## PR / Commit Structure

Single PR, two commits:

1. `refactor(cli): split commands into feather_etl.commands modules (no behavior change)`
2. `test(cli): reorganize command tests into tests/commands (no assertion changes)`

This improves review quality and rollback safety.

## Risks and Mitigations

### Risk 1: accidental behavior drift during move

- **Mitigation:** copy-paste move with minimal edits; preserve signatures and decorators; run tests after Commit A.

### Risk 2: registration mismatch/missing command

- **Mitigation:** explicit centralized registration list in `cli.py`; verify `--help` command list and CLI tests.

### Risk 3: test reorg introduces path/import breakage

- **Mitigation:** keep test logic unchanged; move in one focused commit; run targeted CLI tests plus full suite.

## Rollback Plan

- If Commit B has issues: revert only Commit B (retain modularized CLI).
- If Commit A has issues: revert Commit A to restore single-file CLI.
- Two-commit split ensures fast, low-risk rollback granularity.

## Acceptance Checklist

- `src/feather_etl/cli.py` contains only app/callback/registration concerns.
- One module per command exists under `src/feather_etl/commands/`.
- Shared helpers live in `commands/_common.py`.
- Command behavior/output/exit codes match current baseline exactly.
- Tests pass after Commit A and after Commit B.
- Command-to-test traceability is clear in `tests/commands/`.
