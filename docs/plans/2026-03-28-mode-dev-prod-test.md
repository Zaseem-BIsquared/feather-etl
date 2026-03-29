# Mode: Dev/Prod/Test Pipeline Toggle

Created: 2026-03-28
Status: VERIFIED
Approved: Yes
Iterations: 0
Worktree: Yes
Type: Feature

## Summary

**Goal:** A single `mode` field in feather.yaml (dev/prod/test, default dev) controls pipeline behavior — extraction scope, target schema, gold materialization — without duplicating table or column definitions.

**Architecture:** Mode is parsed from YAML → env var → CLI flag (CLI wins). Pipeline derives `effective_target` from mode unless `target_table` is explicitly set. In prod mode, `column_map` drives column selection and renaming post-extraction via PyArrow. Silver SQL transforms are dev-only (views over bronze); in prod, silver is populated directly.

**Tech Stack:** Python dataclasses, PyArrow column ops, existing Typer CLI

## Scope

### In Scope

- `mode` field on FeatherConfig (dev/prod/test, default dev)
- Mode resolution: `--mode` CLI flag > `FEATHER_MODE` env var > YAML `mode:` field > default `dev`
- `row_limit` field on DefaultsConfig (default None)
- Pipeline derives target schema from mode (dev/test → bronze.{name}, prod → silver.{name})
- Explicit `target_table` in YAML overrides mode-derived target
- Prod mode: extract only `column_map` keys, rename post-extraction via PyArrow, load to silver
- Prod mode: gold transforms rebuilt as materialized tables after extraction
- Dev/test mode: gold transforms created as views only (no rebuild after extraction)
- Prod mode: skip silver SQL transforms in `setup` (silver populated directly by extraction)
- Test mode: apply `defaults.row_limit` to limit rows per table extraction
- `--mode` CLI option on `feather run` and `feather setup`
- Validation: reject invalid mode values
- Tests covering all three modes with sample_erp DuckDB fixture

### Out of Scope

- Config file per environment (feather.dev.yaml / feather.prod.yaml) — deferred, may never be needed
- Jinja-style conditional logic in YAML
- Mode affecting connection strings or destination paths (use env vars for that)
- Mode affecting change detection behavior

## Approach

**Chosen:** Single `mode` field with runtime behavior branching in pipeline.py

**Why:** Zero config duplication — tables, column_map, filters defined once. Mode only changes HOW the pipeline processes them. ~100 lines of production code.

**Alternatives considered:**
- Multiple config files (feather.dev.yaml etc.) — rejected: duplicates table definitions, painful maintenance
- Environment overrides section in YAML — rejected: complex deep-merge logic for marginal benefit
- Jinja in YAML — rejected: adds dependency, opaque errors, violates "readable by anyone" principle

## Context for Implementer

**Patterns to follow:**
- Config parsing: `config.py:278-281` — how `defaults` is parsed from raw YAML
- Pipeline branching: `pipeline.py:81-137` — how `strategy` already drives different code paths
- CLI options: `cli.py:51,84,102` — how `--config` option is declared

**Key files:**
- `src/feather/config.py` — config dataclasses + parsing + validation
- `src/feather/pipeline.py` — `run_table()` extraction logic, `run_all()` gold rebuild
- `src/feather/cli.py` — Typer commands with `--config` option
- `src/feather/transforms.py` — `execute_transforms()`, `rebuild_materialized_gold()`

**Gotchas:**
- `pipeline.py:128-129` — `table.target_table` is used directly in `load_incremental()`. Must use effective_target instead.
- `pipeline.py:137` — same for `load_full()`. Both call sites need the effective target.
- `config.py:90` — `target_table` defaults to `silver.{name}` during parsing. For mode-derived targets, we need to distinguish "explicitly set" from "defaulted". Change default to empty string and derive in pipeline.
- `config.py:164-180` — validation checks `target_table` schema prefix. Must skip this check when target is mode-derived (empty).
- PyArrow column rename: `table.rename_columns(new_names)` replaces ALL column names — need to build the full new name list, not just the mapped ones.
- `column_map` values are the TARGET names, keys are SOURCE names: `{SITYPE: invoice_type}` means extract `SITYPE`, rename to `invoice_type`.

**Domain context:**
- Dev mode = local iteration: extract everything into bronze, tweak silver SQL transforms, re-run setup — no re-extraction needed
- Prod mode = resource-constrained deployment: skip bronze, land only needed columns in silver, rebuild gold tables for dashboards
- Test mode = pytest: like dev but with row limits for fast test runs

## Assumptions

- `column_map` keys are valid source column names — if a key doesn't exist in source, extraction will fail with a clear error from the source. No pre-validation needed. Tasks 2, 3 depend on this.
- File sources (DuckDB, CSV, SQLite) can accept `columns` parameter even though current implementations ignore it. Task 2 uses post-extraction filtering so this isn't blocking, but prod mode extracts fewer columns. Task 2 depends on this.
- `row_limit` is applied post-extraction (slice PyArrow table) not in SQL. This is simpler and works for all source types. Task 4 depends on this.
- Existing tests use explicit `target_table` in configs and will continue to work unchanged due to "explicit overrides mode" behavior. Task 1 depends on this.

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Existing tests break from target_table derivation change | Medium | High | Keep explicit target_table as override — existing tests all have explicit values |
| Column rename produces wrong names when column_map is partial | Low | Medium | Validate: in prod mode, if column_map is set, extract ONLY mapped columns (no unmapped columns in result) |
| Gold transforms fail in prod mode because silver views don't exist | Medium | High | In prod, skip silver SQL transforms in setup. Gold transforms reference silver.{name} which IS a table (populated by extraction), not a view |

## Goal Verification

### Truths

1. A config with `mode: dev` extracts all columns into `bronze.{name}` — verified by querying bronze table column count matching source
2. A config with `mode: prod` and `column_map` extracts only mapped columns into `silver.{name}` with renamed columns — verified by querying silver table with new column names
3. A config with `mode: prod` without `column_map` extracts all columns into `silver.{name}` — verified by querying silver table
4. A config with `mode: test` and `row_limit: 10` extracts at most 10 rows per table — verified by row count
5. Gold transforms are materialized tables in prod mode, views in dev/test — verified by `information_schema.tables.table_type`
6. Explicit `target_table` overrides mode-derived target in any mode — verified by checking data lands in the explicit target
7. `--mode prod` CLI flag overrides `mode: dev` in YAML — verified by checking silver target used

### Artifacts

- `src/feather/config.py` — mode field, row_limit, mode resolution logic
- `src/feather/pipeline.py` — effective_target derivation, column_map extraction, row_limit
- `src/feather/cli.py` — `--mode` CLI option
- `tests/test_mode.py` — tests for all three modes

## Progress Tracking

- [x] Task 1: Config — mode field + row_limit + validation
- [x] Task 2: Pipeline — mode-driven target + column_map extraction + rename
- [x] Task 3: Pipeline — mode-driven gold materialization + skip silver transforms in prod
- [x] Task 4: Pipeline — row_limit for test mode
- [x] Task 5: CLI — --mode option on run and setup
- [x] Task 6: Tests — all three modes verified end-to-end

**Total Tasks:** 6 | **Completed:** 6 | **Remaining:** 0

## Implementation Tasks

### Task 1: Config — mode field + row_limit + validation

**Objective:** Add `mode` (dev/prod/test) and `row_limit` fields to config, with mode resolution from CLI > env var > YAML.
**Dependencies:** None
**Files:**
- Modify: `src/feather/config.py`

**Key Decisions / Notes:**
- Add `VALID_MODES = {"dev", "prod", "test"}` constant
- Add `mode: str = "dev"` to `FeatherConfig`
- Add `row_limit: int | None = None` to `DefaultsConfig`
- In `load_config()`: parse mode from `raw.get("mode", "dev")`, resolve env var `FEATHER_MODE` (env var overrides YAML)
- Add `mode_override: str | None = None` param to `load_config()` for CLI override (CLI > env var > YAML)
- In `_validate()`: check mode in VALID_MODES
- In `_validate()`: when `target_table` is empty AND mode is known, skip target_table schema prefix validation (it will be derived at runtime)
- Change `target_table` default from `f"silver.{t['name']}"` to `""` in `_parse_tables()` — empty means "derive from mode"
- Keep existing behavior: if `target_table` is explicitly set in YAML, use it as-is

**Definition of Done:**
- [ ] `FeatherConfig` has `mode` field defaulting to "dev"
- [ ] `DefaultsConfig` has `row_limit` field defaulting to None
- [ ] Mode resolution: CLI param > FEATHER_MODE env var > YAML mode > default "dev"
- [ ] Validation rejects `mode: invalid`
- [ ] Empty target_table is valid (mode-derived)
- [ ] Existing tests still pass (they use explicit target_table)

**Verify:** `uv run pytest tests/test_config.py -q`

### Task 2: Pipeline — mode-driven target + column_map extraction + rename

**Objective:** In `run_table()`, derive effective target from mode, apply column_map for prod mode.
**Dependencies:** Task 1
**Files:**
- Modify: `src/feather/pipeline.py`

**Key Decisions / Notes:**
- New helper: `_resolve_target(table: TableConfig, mode: str) -> str` — if `table.target_table` is set, return it; else derive from mode (`dev/test` → `bronze.{name}`, `prod` → `silver.{name}`)
- In all `source.extract()` calls: if `mode == "prod"` and `table.column_map`, pass `columns=list(table.column_map.keys())`
- After extraction, if `mode == "prod"` and `table.column_map`: rename columns via PyArrow `data.rename_columns([column_map.get(c, c) for c in data.column_names])`
- Replace all `table.target_table` references with `effective_target` variable
- This touches 4 code paths: incremental with watermark (line 128), incremental zero rows, full strategy (line 137), and the filter branch (line 134)

**Definition of Done:**
- [ ] Dev mode extracts all columns into bronze.{name}
- [ ] Prod mode with column_map extracts only mapped columns, renames, loads to silver.{name}
- [ ] Prod mode without column_map extracts all columns into silver.{name}
- [ ] Explicit target_table overrides mode in any mode
- [ ] All existing tests pass

**Verify:** `uv run pytest tests/test_pipeline.py -q`

### Task 3: Pipeline — mode-driven gold materialization + skip silver transforms in prod

**Objective:** In prod mode, rebuild gold as materialized tables. In dev/test, create gold as views. Skip silver SQL transforms in prod setup.
**Dependencies:** Task 1
**Files:**
- Modify: `src/feather/pipeline.py` (run_all gold rebuild logic)
- Modify: `src/feather/cli.py` (setup command transform logic)

**Key Decisions / Notes:**
- `run_all()`: after extraction, always execute transforms (views) in dev/test. In prod, only rebuild materialized gold.
- Current `run_all()` already calls `execute_transforms()` then `rebuild_materialized_gold()`. For dev/test, call `execute_transforms()` only (creates all views). For prod, call `rebuild_materialized_gold()` only.
- `cli.py setup`: in prod mode, filter transforms to gold-only before executing. Skip silver SQL transforms (silver is populated by extraction, not views).
- Pass `config.mode` through to the transform logic.

**Definition of Done:**
- [ ] Dev/test: gold transforms created as views after extraction
- [ ] Prod: gold transforms materialized as tables after extraction
- [ ] Prod setup: skips silver SQL transforms, only creates gold
- [ ] Dev/test setup: creates all transforms (silver views + gold views)

**Verify:** `uv run pytest tests/test_transforms.py -q`

### Task 4: Pipeline — row_limit for test mode

**Objective:** When `mode == "test"` and `defaults.row_limit` is set, limit extraction to N rows per table.
**Dependencies:** Task 2
**Files:**
- Modify: `src/feather/pipeline.py`

**Key Decisions / Notes:**
- After extraction (all `source.extract()` calls), if `config.defaults.row_limit` and `config.mode == "test"`: `data = data.slice(0, config.defaults.row_limit)`
- Apply BEFORE column rename (if any) — simpler, same result
- row_limit only takes effect in test mode — dev and prod always get all rows
- PyArrow `table.slice(offset, length)` is zero-copy — no performance concern

**Definition of Done:**
- [ ] Test mode with row_limit=10 extracts at most 10 rows
- [ ] Dev mode ignores row_limit even if set
- [ ] Prod mode ignores row_limit even if set

**Verify:** `uv run pytest tests/test_mode.py -q`

### Task 5: CLI — --mode option on run and setup

**Objective:** Add `--mode` CLI option to `feather run` and `feather setup` commands.
**Dependencies:** Task 1
**Files:**
- Modify: `src/feather/cli.py`

**Key Decisions / Notes:**
- Add `mode: str = typer.Option(None, "--mode")` to `run()` and `setup()` commands
- Pass `mode` to `load_config()` as override parameter
- `load_config()` applies CLI override after env var resolution (Task 1 handles precedence)
- Show mode in output: `typer.echo(f"Mode: {cfg.mode}")`

**Definition of Done:**
- [ ] `feather run --mode prod` uses prod behavior
- [ ] `feather setup --mode dev` uses dev behavior
- [ ] Mode shown in CLI output

**Verify:** `uv run pytest tests/test_cli.py -q`

### Task 6: Tests — all three modes verified end-to-end

**Objective:** Comprehensive tests for mode behavior using sample_erp DuckDB fixture.
**Dependencies:** Tasks 1-5
**Files:**
- Create: `tests/test_mode.py`

**Key Decisions / Notes:**
- Use `FIXTURES_DIR / "sample_erp.duckdb"` as source (small, 12 rows per table)
- Test matrix:

| Test | Mode | column_map | Expected target | Columns | Gold type |
|------|------|-----------|----------------|---------|-----------|
| test_dev_extracts_to_bronze | dev | No | bronze.{name} | all | — |
| test_dev_with_column_map_ignores_it | dev | Yes | bronze.{name} | all | — |
| test_prod_extracts_to_silver | prod | No | silver.{name} | all | — |
| test_prod_with_column_map | prod | Yes | silver.{name} | mapped only, renamed | — |
| test_prod_gold_materialized | prod | No | — | — | TABLE |
| test_dev_gold_is_view | dev | No | — | — | VIEW |
| test_test_mode_with_row_limit | test | No | bronze.{name} | all, ≤N rows | VIEW |
| test_explicit_target_overrides_mode | prod | No | bronze.audit (explicit) | all | — |
| test_cli_mode_overrides_yaml | dev(yaml) | No | silver.{name} | all | — |
| test_env_var_overrides_yaml | dev(yaml) | No | silver.{name} (FEATHER_MODE=prod) | all | — |

**Definition of Done:**
- [ ] All 10 test scenarios pass
- [ ] Full test suite (249+ existing tests) still green
- [ ] No ruff lint issues

**Verify:** `uv run pytest tests/test_mode.py -q && uv run pytest -q`

## Open Questions

None — all decisions resolved in Q&A.
