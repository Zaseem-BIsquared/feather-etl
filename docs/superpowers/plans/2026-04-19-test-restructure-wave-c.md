# Test Restructure — Wave C (Migrate integration tests) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move every cross-module Python-API test from flat `tests/test_*.py` files into the `tests/integration/` tree. After this wave, `tests/integration/` is populated, tests that were waiting for a home have one, and every remaining test in `tests/` root is a single-module unit test (or belongs to a file that Wave D will fully drain).

**Architecture:** One migration task per destination file. Whole-file migrations are straightforward `git mv`+refactor; mixed-file splits move integration portions to new files under `tests/integration/` while unit portions stay in place for Wave D. One pre-task addresses a missed Wave B CLI test. No `ProjectFixture` API changes needed — tests call `pipeline.run_all` / `config.load_config` / `cache.run_cache` / etc. directly, using `project` for directory+config scaffolding and `project.query()` for destination assertions.

**Tech Stack:** Same as Wave A/B. No new dependencies.

**Source spec:** [`docs/superpowers/specs/2026-04-19-test-restructure-design.md`](../specs/2026-04-19-test-restructure-design.md)
**Wave A plan:** [`2026-04-19-test-restructure-wave-a.md`](2026-04-19-test-restructure-wave-a.md)
**Wave B plan:** [`2026-04-19-test-restructure-wave-b.md`](2026-04-19-test-restructure-wave-b.md)
**Issue:** https://github.com/siraj-samsudeen/feather-etl/issues/40
**Branch:** `feat/test-restructure` (same branch; Wave C commits extend history).

---

## Scope

### In scope for Wave C

- **Wave B leftover:** migrate the one CliRunner test in `tests/test_mode.py` to `tests/e2e/test_04_extract_full.py` (Task C0).
- **Whole-file migrations to `tests/integration/`:**
  - `tests/test_pipeline.py` (13 tests)
  - `tests/test_cache.py` (5 tests; file naming collides with the e2e `test_12_cache.py` — use distinct path)
  - `tests/test_curation_config_integration.py` (3 tests)
  - `tests/test_discover_core.py` (10 tests)
  - `tests/test_validate_core.py` (4 tests)
  - `tests/test_setup_core.py` (3 tests)
  - `tests/test_status_core.py` + `tests/test_history_core.py` (7 tests combined into one file)
  - `tests/test_integration.py` (33 tests)
  - `tests/test_core_module_purity.py` (1 parametrized test × 10 modules)
- **Split migrations (integration portions only; unit stays for Wave D):**
  - `tests/test_incremental.py` — `TestPipelineIncremental` + `TestIncrementalWithFixture`
  - `tests/test_schema_drift.py` — `TestPipelineIntegration`
  - `tests/test_dedup.py` — `TestDedupExtraction`
  - `tests/test_append.py` — `TestPipelineAppendDispatch`
  - `tests/test_retry.py` — `TestRetryPipelineIntegration`
  - `tests/test_csv_glob.py` — `TestCsvGlobExtraction` + `TestCsvGlobChangeDetection`
  - `tests/test_dq.py` — `TestPipelineIntegration`
  - `tests/test_transforms.py` — `TestPipelineTransformRebuild`
  - `tests/test_json_output.py` — `TestJsonlLogging`
  - `tests/test_mode.py` — integration portions (10 tests)

### Out of scope for Wave C

- Unit tests (Wave D).
- `tests/commands/conftest.py` deletion (Wave D).
- `scripts/hands_on_test.sh` deletion and coverage-map completion (Wave E).
- Documentation updates to `CLAUDE.md` / `docs/CONTRIBUTING.md` (Wave E).

### End state after Wave C

- `tests/integration/` contains ~18 files, ~120 tests.
- `tests/integration/__init__.py` is no longer just a package marker — folder has real content.
- Flat `tests/test_*.py` files have either been deleted (whole-file migrations) or shrunk to only their unit portions (split migrations). Wave D will drain and delete the remaining shrunken files.
- `tests/e2e/` gains one more test function (the migrated mode CLI test).
- Test count invariant: **720 → 720** (tests move, not add).

---

## File Structure (after Wave C)

```
tests/
  __init__.py
  conftest.py
  helpers.py
  README.md
  fixtures/                          (unchanged)
  e2e/                               (Wave A + B; extended in C0)
    __init__.py, conftest.py, README.md
    test_fixture_smoke.py
    test_00_cli_structure.py ... test_18_sources_e2e.py
    test_04_extract_full.py          ← EXTENDED (Task C0 adds one test)
  integration/                       (Wave C populates)
    __init__.py
    test_pipeline.py                 (Task C1)
    test_cache.py                    (Task C2)
    test_curation_config.py          (Task C3)
    test_discover.py                 (Task C4)
    test_validate.py                 (Task C5)
    test_setup.py                    (Task C6)
    test_readonly_commands.py        (Task C7 — merges status + history cores)
    test_incremental.py              (Task C8 — split from flat)
    test_schema_drift.py             (Task C9 — split)
    test_dedup.py                    (Task C10 — split)
    test_append.py                   (Task C11 — split)
    test_retry.py                    (Task C12 — split)
    test_csv_glob.py                 (Task C13 — split)
    test_dq.py                       (Task C14 — split)
    test_transforms.py               (Task C15 — split)
    test_jsonl_logging.py            (Task C16 — split)
    test_mode.py                     (Task C17 — split)
    test_integration.py              (Task C18 — whole-file, renamed)
    test_architecture_purity.py      (Task C19 — whole-file, relocated)
  unit/                              (still empty skeletons; Wave D populates)
  commands/                          (still has orphaned __init__.py + conftest.py; Wave D deletes)
  test_incremental.py                (SHRUNK — Wave C moved 2 classes; unit classes remain)
  test_schema_drift.py               (SHRUNK)
  test_dedup.py                      (SHRUNK)
  test_append.py                     (SHRUNK)
  test_retry.py                      (SHRUNK)
  test_csv_glob.py                   (SHRUNK)
  test_dq.py                         (SHRUNK)
  test_transforms.py                 (SHRUNK — post-Wave-B + Wave-C)
  test_json_output.py                (SHRUNK — post-Wave-B + Wave-C)
  test_mode.py                       (SHRUNK — post-Wave-B + Wave-C)
  test_config.py, test_state.py, test_curation.py, test_destinations.py,
  test_sources.py, test_excel.py, test_json.py, test_postgres.py,
  test_mysql.py, test_sqlserver.py, test_viewer_server.py,
  test_alerts.py, test_explicit_name_flag.py,
  test_discover_io.py, test_discover_state.py, test_discover_expansion.py,
  test_expand_db_sources.py
                                     (ALL Wave D — untouched by Wave C)
  test_pipeline.py                   (DELETED — whole-file migrated)
  test_cache.py                      (DELETED — whole-file migrated)
  test_curation_config_integration.py (DELETED)
  test_discover_core.py              (DELETED)
  test_validate_core.py              (DELETED)
  test_setup_core.py                 (DELETED)
  test_status_core.py                (DELETED)
  test_history_core.py               (DELETED)
  test_integration.py                (DELETED)
  test_core_module_purity.py         (DELETED)
```

---

## Shared migration rules (apply to every task)

All rules from Wave B carry forward. Wave-C-specific additions and clarifications:

### Rule I1 — Integration tests don't use the `cli` fixture

- Tests that call `pipeline.run_all(cfg, config_path)` or similar Python-API functions should take `project` as the fixture but NOT `cli`.
- Use `project.write_config(...)` and `project.write_curation([...])` for setup, then call the relevant `feather_etl.*` API directly.
- `cfg = load_config(project.config_path)` is the standard preamble.
- `results = run_all(cfg, project.config_path)` is the standard invocation.
- Post-run assertions use `project.query("SELECT ...")` for destination rows.

### Rule I2 — Richer curation entries inline

- `project.write_curation([(src, table, alias)])` only covers the simple three-tuple case.
- For tests needing `strategy`, `primary_key`, `timestamp`, `filter`, `dq_checks`, `dq_policy`, `dedup`, `dedup_columns`, `column_map`, `schedule`:
  ```python
  from tests.helpers import make_curation_entry, write_curation
  write_curation(project.root, [
      make_curation_entry(
          "erp", "erp.orders", "orders",
          strategy="incremental",
          primary_key=["order_id"],
          timestamp_column="created_at",
      ),
      make_curation_entry("erp", "erp.products", "products", dedup=True, dedup_columns=["sku"]),
  ])
  ```
- **Do NOT** port domain-specific curation helpers from source files (e.g., `_make_include_entry` in `test_curation_config_integration.py`) — use `make_curation_entry` directly. This unifies on a single canonical builder.

### Rule I3 — Source-DB writes use raw `duckdb.connect`

- When a test needs to mutate the source DB (e.g., `ALTER TABLE`, `INSERT INTO`), use:
  ```python
  import duckdb
  with duckdb.connect(str(project.root / "source.duckdb")) as con:
      con.execute("INSERT INTO erp.orders VALUES (...)")
  ```
- The `project.query()` method stays read-only against the destination DB. Don't extend it for source mutations.

### Rule I4 — Split migrations — procedure

For files where Wave C migrates only the integration portion:

1. **Read** the source file; identify integration classes/tests per the survey.
2. **Create** the destination file under `tests/integration/` with the relevant module docstring.
3. **Copy** the integration tests into the destination. Refactor to use `project` fixture (drop `tmp_path`-only patterns, use `project.write_config`, etc.). Update imports at the top of the destination file.
4. **Delete** the migrated tests from the source file. Leave the file if it still has unit tests (even just one). If the source file is now empty of tests, delete it.
5. **Clean up unused imports** in both source and destination.
6. **Verify**: `uv run pytest tests/integration/test_X.py -v` passes; `uv run pytest tests/test_source.py -v` still passes (reduced count); `uv run pytest -q` green; collection count unchanged at 720.
7. **Commit** with format `test(c): split test_source.py integration -> integration/test_X.py (#40)`.

### Rule I5 — Whole-file migrations — procedure

For files where Wave C moves the entire file:

1. **Read** the source file.
2. **Create** `tests/integration/test_X.py` with the migrated content (refactored to use `project`).
3. **`git rm`** the source file (if nothing remains) OR leave the `__init__.py`-equivalent if the file was a package marker.
4. **Verify and commit** as above with format `test(c): migrate test_source.py -> integration/test_X.py (#40)`.

### Rule I6 — Module docstrings

Every new `tests/integration/test_X.py` file must open with:

```python
"""Integration: <one-line summary>.

<2-3 sentences describing what cross-module behavior this file covers.
Mention which modules are exercised if it helps the reader (e.g.,
'Exercises the pipeline + state + destination interaction.').>
"""

from __future__ import annotations
```

### Rule I7 — Fixture inlining

- **`sample_erp_db` / `client_db_copy` / `csv_data_dir` / `sqlite_db` / `sample_erp_db`** (from `tests/conftest.py`) — KEEP using these where convenient; they work transparently with `project` via `tmp_path` sharing.
- **Local fixtures defined in source files** (e.g., per-class `config` fixture, `setup_env`, `dq_db`) — inline via `project.write_config` + `project.write_curation` + `project.copy_fixture`. Do NOT port local fixtures to `tests/integration/conftest.py` — Wave C establishes integration-layer hygiene with no magic.
- If multiple tests in a destination file share substantial setup, a file-local `_setup_X_project(project)` helper is acceptable (precedent: Wave B's `_one_table_project`, `_two_table_env`).

### Rule I8 — Count invariant

- Full suite count stays at 720. Split migrations preserve count (tests move, not added). Whole-file migrations preserve count.
- The Wave-B leftover migration (Task C0) also preserves count (1 test moves from `test_mode.py` to `test_04_extract_full.py`).

### Rule I9 — Commit style

- One commit per task (Rule M8 from Wave B still applies).
- Commit subjects for Wave C use `test(c):` prefix.
- `git mv` for whole-file migrations when content stays broadly similar (preserves blame).
- `git rm` + `git add` for splits (git can't track partial moves).

---

## Task order and dependencies

Tasks are listed in recommended execution order:

1. **C0** first — fixes the Wave B leftover, which should be absorbed into the same branch before anything else.
2. **C1–C7** — whole-file migrations (easier, build momentum).
3. **C8–C17** — split migrations (more complex; survey judgment was that unit portions are straightforward to leave behind).
4. **C18** — `test_integration.py` whole-file migration (biggest single file, 33 tests; defer until after the mechanical whole-file moves).
5. **C19** — `test_core_module_purity.py` relocation (the architectural invariant).

Tasks within each group are independent and can be reordered. Splits that involve the same file pattern (e.g., C8 test_incremental, C11 test_append) use the same procedure so running them back-to-back helps consistency.

---

## Task C0: Wave B leftover — migrate `test_cli_mode_flag_via_runner` to e2e

**Files:**
- Modify: `tests/e2e/test_04_extract_full.py` (APPEND one test)
- Modify: `tests/test_mode.py` (REMOVE the migrated test)

The Wave B survey missed a CliRunner-using test in `tests/test_mode.py`. Relocate it now as part of the Wave-C branch.

### Steps

1. `grep -n "test_cli_mode_flag_via_runner\|CliRunner\|feather_etl.cli" tests/test_mode.py` — locate the test (around line 463-497).
2. Read the test carefully. It configures a prod-mode project + calls `feather run --mode prod` via `CliRunner`, then queries `silver.erp_customers`.
3. Append a migrated version to `tests/e2e/test_04_extract_full.py`:
   - Use `project` + `cli(...)`.
   - `project.write_config(...)` sets up the prod-mode config.
   - `project.write_curation([...])` writes the curation.
   - `cli("run", "--mode", "prod")` is the invocation.
   - Post-run: `project.query("SELECT count(*) FROM silver.erp_customers")` for the assertion.
4. Delete the original test from `tests/test_mode.py`. Remove unused imports at the top if any (e.g., `CliRunner` if only this test used it).
5. Verify:
   ```bash
   uv run pytest tests/e2e/test_04_extract_full.py -v    # 11 passed (was 10)
   uv run pytest tests/test_mode.py -v                    # 19 passed (was 20)
   uv run pytest --collect-only -q 2>&1 | tail -2         # 720 unchanged
   uv run pytest -q
   ```
6. Commit:
   ```bash
   git add tests/e2e/test_04_extract_full.py tests/test_mode.py
   git commit -m "test(c): migrate missed cli mode test -> e2e/test_04_extract_full (#40)

   Wave B survey missed test_cli_mode_flag_via_runner in tests/test_mode.py;
   the Wave B review caught it. Relocate now as Task C0 so test_mode.py
   has zero CliRunner usage going into its Wave C split."
   ```

---

## Task C1: Migrate `tests/test_pipeline.py` → `tests/integration/test_pipeline.py`

**Files:**
- Create: `tests/integration/test_pipeline.py`
- Delete: `tests/test_pipeline.py`

Source: 238 lines, 13 tests in `TestRunTable` + `TestRunAll`. All integration (pipeline + state + config).

### Steps

1. Read `tests/test_pipeline.py`. Note the `setup_env` local fixture (copies client.duckdb + writes config + curation) — inline using `project`.
2. Write `tests/integration/test_pipeline.py`:
   - Module docstring (Rule I6): `"""Integration: feather_etl.pipeline — run_table and run_all orchestration across sources, destinations, and state."""`
   - Drop classes per Rule M2 (unless they share fixtures meaningfully; survey says no).
   - Each test: use `project.copy_fixture("client.duckdb")` + `project.write_config(...)` + `project.write_curation([(...)])`, then `cfg = load_config(project.config_path)` + `run_all(cfg, project.config_path)`.
   - Preserve the L-1 invariant test (`test_run_all_does_not_write_validation_json`) verbatim — it's checking that `pipeline.run_all` doesn't write `feather_validation.json` (that's the CLI's job).
3. `git rm tests/test_pipeline.py`.
4. Verify: 13 passed in integration/test_pipeline.py, 720 total, green.
5. Commit: `test(c): migrate test_pipeline.py -> integration/test_pipeline.py (#40)`.

---

## Task C2: Migrate `tests/test_cache.py` → `tests/integration/test_cache_pipeline.py`

**Files:**
- Create: `tests/integration/test_cache_pipeline.py`
- Delete: `tests/test_cache.py`

Source: 156 lines, 5 tests (`TestRunCacheBasic`, `TestRunCacheStateIsolation`, `TestRunCacheSkip`, `TestRunCachePartialFailure`). All exercise `cache.run_cache` + config + state + destinations.

**Naming note:** `tests/e2e/test_12_cache.py` already exists (Wave B). Use `tests/integration/test_cache_pipeline.py` to avoid naming collision.

### Steps

1. Read source. Note it already has e2e sibling at `tests/e2e/test_12_cache.py` (Wave B).
2. Write `tests/integration/test_cache_pipeline.py`:
   - Module docstring: `"""Integration: feather_etl.cache.run_cache — parquet cache builder. Exercises cache + config + state + destinations cross-module behavior."""`
   - Drop classes.
   - Each test: inline setup via `project.copy_fixture(...)` + `project.write_config(...)` + `project.write_curation([...])`, then call `cache.run_cache(cfg, project.config_path)`.
   - Assertions use `project.root / "_cache" / ...` for parquet paths; real file inspections.
3. `git rm tests/test_cache.py`.
4. Verify and commit: `test(c): migrate test_cache.py -> integration/test_cache_pipeline.py (#40)`.

---

## Task C3: Migrate `tests/test_curation_config_integration.py` → `tests/integration/test_curation_config.py`

**Files:**
- Create: `tests/integration/test_curation_config.py`
- Delete: `tests/test_curation_config_integration.py`

Source: 142 lines, 3 tests in `TestLoadConfigWithCuration`. Tests `load_config` reading `discovery/curation.json` across real DuckDB sources.

### Steps

1. Read source. Note local helpers `_write_curation` and `_make_include` duplicate `tests.helpers` — replace with the shared helpers.
2. Write `tests/integration/test_curation_config.py`:
   - Module docstring: `"""Integration: config.load_config + curation.load_curation_tables reading discovery/curation.json from real project directories."""`
   - Drop class.
   - Replace `_write_curation` / `_make_include` with `write_curation` / `make_curation_entry` from `tests.helpers`.
   - Each test: build source DBs via `duckdb.connect` directly (or use fixtures where possible), write config, write curation, call `load_config`.
3. `git rm tests/test_curation_config_integration.py`.
4. Verify and commit.

---

## Task C4: Migrate `tests/test_discover_core.py` → `tests/integration/test_discover.py`

**Files:**
- Create: `tests/integration/test_discover.py`
- Delete: `tests/test_discover_core.py`

Source: 310 lines, 10 tests across 3 classes. Tests `discover.run_discover` + `discover.detect_renames_for_sources` + `discover.apply_rename_decision` — all cross-module (config + discover + discover_state + sources.expand).

### Steps

1. Read source.
2. Write `tests/integration/test_discover.py`:
   - Module docstring: `"""Integration: feather_etl.discover — run_discover, detect_renames_for_sources, apply_rename_decision. Exercises discover + config + discover_state + sources cross-module behavior."""`
   - Drop classes unless they share fixtures (survey says no).
   - Use `project` fixture to create project directories, then call `discover.run_discover(cfg, ...)` directly.
3. `git rm tests/test_discover_core.py`.
4. Verify and commit.

---

## Task C5: Migrate `tests/test_validate_core.py` → `tests/integration/test_validate.py`

**Files:**
- Create: `tests/integration/test_validate.py`
- Delete: `tests/test_validate_core.py`

Source: 93 lines, 4 tests in `TestRunValidate`. Tests `validate.run_validate` orchestrating config + sources.

### Steps

1. Read source. Note one test patches `cfg.sources[0]` with a `FakeFailingSource` — preserve.
2. Write `tests/integration/test_validate.py`:
   - Module docstring: `"""Integration: feather_etl.validate.run_validate — exercises validate + config + sources connection probing."""`
   - Drop class.
   - Each test: `project` setup + `cfg = load_config(...)` + `validate.run_validate(cfg)`.
3. `git rm tests/test_validate_core.py`.
4. Verify and commit.

---

## Task C6: Migrate `tests/test_setup_core.py` → `tests/integration/test_setup.py`

**Files:**
- Create: `tests/integration/test_setup.py`
- Delete: `tests/test_setup_core.py`

Source: 83 lines, 3 tests in `TestRunSetup`. Tests `setup.run_setup` (state + destination + transforms).

### Steps

1. Read source.
2. Write `tests/integration/test_setup.py`:
   - Module docstring: `"""Integration: feather_etl.setup.run_setup — orchestrates state init + destination creation + transform execution."""`
   - Drop class.
3. `git rm tests/test_setup_core.py`.
4. Verify and commit.

---

## Task C7: Merge status + history cores → `tests/integration/test_readonly_commands.py`

**Files:**
- Create: `tests/integration/test_readonly_commands.py`
- Delete: `tests/test_status_core.py`
- Delete: `tests/test_history_core.py`

Sources:
- `tests/test_status_core.py` — 66 lines, 3 tests (`TestLoadStatus`, `TestLoadStatusPreconditions`)
- `tests/test_history_core.py` — 77 lines, 4 tests (`TestLoadHistory`, `TestLoadHistoryPreconditions`)

Both are thin orchestrators over `StateManager`. Combined in one file per survey recommendation.

### Steps

1. Read both sources.
2. Write `tests/integration/test_readonly_commands.py`:
   - Module docstring: `"""Integration: feather_etl.status.load_status + feather_etl.history.load_history. Both are thin orchestrators over StateManager; grouped here since they share shape."""`
   - All 7 tests as flat functions. Keep name disambiguation (e.g., `test_status_after_successful_run` vs `test_history_after_successful_run`).
3. `git rm tests/test_status_core.py tests/test_history_core.py`.
4. Verify and commit.

---

## Task C8: Split `tests/test_incremental.py` — integration portion to `tests/integration/test_incremental.py`

**Files:**
- Create: `tests/integration/test_incremental.py`
- Modify: `tests/test_incremental.py` (REMOVE `TestPipelineIncremental` + `TestIncrementalWithFixture`; KEEP 3 unit classes)

Source: 419 lines, 5 classes. Per survey:
- `TestBuildWhereClause` (unit, Wave D — stays)
- `TestLoadIncremental` (unit, Wave D — stays)
- `TestWatermarkLastValue` (unit, Wave D — stays)
- `TestPipelineIncremental` (integration, Wave C — migrate)
- `TestIncrementalWithFixture` (integration, Wave C — migrate)

Expected: ~10 tests migrate, ~8 stay for Wave D.

### Steps (follow Rule I4 split procedure)

1. Read source. Identify the two integration classes.
2. Create `tests/integration/test_incremental.py`:
   - Module docstring: `"""Integration: incremental extraction — watermarks, overlap, pipeline.run_table with strategy=incremental."""`
   - Copy the two classes (or flatten their tests) to the new file.
   - Refactor to use `project` fixture: replace local `_make_source_db` helper with `project.copy_fixture(...)` or inline duckdb setup.
3. Delete the two migrated classes from `tests/test_incremental.py`. Clean up unused imports.
4. Verify: integration file passes, source file still passes (fewer tests), 720 total, green.
5. Commit: `test(c): split test_incremental.py integration -> integration/test_incremental.py (#40)`.

---

## Task C9: Split `tests/test_schema_drift.py` — `TestPipelineIntegration` to integration

**Files:**
- Create: `tests/integration/test_schema_drift.py`
- Modify: `tests/test_schema_drift.py`

Source: 193 lines, 3 classes. `TestPipelineIntegration` (2 tests) is the integration part; other 2 classes are unit (Wave D).

### Steps (Rule I4)

1. Move `TestPipelineIntegration` to `tests/integration/test_schema_drift.py` with docstring: `"""Integration: schema drift detection — pipeline re-runs after ALTER TABLE on source DB."""`
2. The test uses `time.sleep` + `os.utime` for mtime manipulation — preserve.
3. Delete from source, verify, commit.

---

## Task C10: Split `tests/test_dedup.py` — `TestDedupExtraction` to integration

**Files:**
- Create: `tests/integration/test_dedup.py`
- Modify: `tests/test_dedup.py`

Source: 137 lines, 2 classes. `TestDedupExtraction` (4 tests, uses `pipeline.run_table`) is integration; `TestDedupConfig` (1 test) is unit.

### Steps (Rule I4)

1. Move 4 tests. Module docstring: `"""Integration: dedup strategy — pipeline.run_table with dedup enabled against CSV and JSON sources."""`
2. Delete, verify, commit.

---

## Task C11: Split `tests/test_append.py` — `TestPipelineAppendDispatch` to integration

**Files:**
- Create: `tests/integration/test_append.py`
- Modify: `tests/test_append.py`

Source: 192 lines, 2 classes. `TestPipelineAppendDispatch` (3 tests) is integration (pipeline + INSERT mutations); `TestLoadAppend` (3 tests) is unit (destinations module only, pyarrow).

### Steps (Rule I4)

1. Move 3 tests. Module docstring: `"""Integration: append strategy — pipeline.run_table + run_all dispatch to DuckDBDestination.load_append."""`
2. The integration class mutates source DB (`INSERT INTO erp.customers`) — preserve with raw `duckdb.connect`.
3. Delete, verify, commit.

---

## Task C12: Split `tests/test_retry.py` — `TestRetryPipelineIntegration` to integration

**Files:**
- Create: `tests/integration/test_retry.py`
- Modify: `tests/test_retry.py`

Source: 393 lines, 6 classes. `TestRetryPipelineIntegration` (3 tests) is integration; other 5 classes are unit (state only + mock-heavy connection cleanup).

### Steps (Rule I4)

1. Move 3 tests. Module docstring: `"""Integration: retry policy + StateManager — pipeline.run_table blocks retries after backoff."""`
2. Integration tests use intentionally-broken curation (`icube.nonexistent_table_xyz`) — preserve.
3. Delete, verify, commit.

---

## Task C13: Split `tests/test_csv_glob.py` — extraction + change-detection to integration

**Files:**
- Create: `tests/integration/test_csv_glob.py`
- Modify: `tests/test_csv_glob.py`

Source: 156 lines, 3 classes. `TestCsvGlobExtraction` + `TestCsvGlobChangeDetection` (4 tests) are integration; `TestCsvGlobDiscover` (2 tests) is unit (CsvSource only).

### Steps (Rule I4)

1. Move 4 tests. Module docstring: `"""Integration: CSV glob extraction + change detection — pipeline runs across multiple CSV files with mtime tracking."""`
2. Preserve `time.sleep(0.1)` and fixture dir manipulation.
3. Delete, verify, commit.

---

## Task C14: Split `tests/test_dq.py` — `TestPipelineIntegration` to integration

**Files:**
- Create: `tests/integration/test_dq.py`
- Modify: `tests/test_dq.py`

Source: 249 lines, 5 classes. `TestPipelineIntegration` (2 tests) is integration; other 4 classes are unit (dq module only against hand-built DuckDB).

### Steps (Rule I4)

1. Move 2 tests. Module docstring: `"""Integration: data quality checks — pipeline.run_table with dq_checks applied to bronze tables."""`
2. Delete, verify, commit.

---

## Task C15: Split `tests/test_transforms.py` — `TestPipelineTransformRebuild` to integration

**Files:**
- Create: `tests/integration/test_transforms.py`
- Modify: `tests/test_transforms.py`

Source: 786 lines, 7 classes remaining after Wave B. Only `TestPipelineTransformRebuild` (3 tests) is integration; other 6 classes are unit (transforms module, some hand-built DuckDB).

### Steps (Rule I4)

1. Move 3 tests. Module docstring: `"""Integration: transforms + pipeline — rebuild_materialized_gold invoked from pipeline.run_all."""`
2. The integration tests use `pipeline.run_all` to trigger transform rebuild. Preserve.
3. Delete, verify, commit.

---

## Task C16: Split `tests/test_json_output.py` — `TestJsonlLogging` to integration

**Files:**
- Create: `tests/integration/test_jsonl_logging.py`
- Modify: `tests/test_json_output.py`

Source: 133 lines (after Wave B), 2 classes. `TestJsonlLogging` (3 tests, uses `pipeline.run_all`) is integration; `TestOutputHelper` (4 tests) is unit (`output` module + `capsys`).

### Steps (Rule I4)

1. Move 3 tests. Module docstring: `"""Integration: NDJSON logging via pipeline.run_all — asserts feather_run.jsonl structure."""`
2. Delete, verify, commit.

---

## Task C17: Split `tests/test_mode.py` — integration portion to `tests/integration/test_mode.py`

**Files:**
- Create: `tests/integration/test_mode.py`
- Modify: `tests/test_mode.py` (already shrunk by Task C0)

Source (after C0): 19 tests (no classes, flat functions). Per survey: ~8 config-parsing tests (unit, Wave D), ~10 pipeline tests (integration, Wave C), 1 env-var test (unit).

### Steps (Rule I4)

1. Identify the ~10 pipeline tests by name (they use `_run_pipeline` / `_run_with_transforms` helpers; they invoke `pipeline.run_all`). The survey's rough count should match what's in the file after C0.
2. Create `tests/integration/test_mode.py` with module docstring: `"""Integration: mode flag semantics — pipeline.run_all behavior across dev/prod/test modes, row_limit, transforms."""`
3. Move the integration tests. Keep the local helpers (`_run_pipeline`, `_run_with_transforms`) — they're substantial and worth copying.
4. Delete from source. Clean up unused imports.
5. Verify, commit.

---

## Task C18: Migrate `tests/test_integration.py` → `tests/integration/test_integration.py`

**Files:**
- Create: `tests/integration/test_integration.py`
- Delete: `tests/test_integration.py`

Source: 811 lines, 33 tests across 9 classes. Per survey, all 33 tests are integration. One class (`TestValidationGuards`, 6 tests) is borderline unit but can stay with the rest for simplicity.

### Steps (Rule I5 — whole-file)

1. Read source.
2. Write `tests/integration/test_integration.py`:
   - Module docstring: `"""Integration: end-to-end pipeline scenarios against client and sample_erp DuckDB fixtures. Covers full-pipeline runs, error isolation, validation guards, CSV sources, SQLite sources, and the open-bug regression suite."""`
   - Keep classes (this file uses them meaningfully for grouping across ~9 concerns; flattening 33 tests would hurt readability).
   - Use `project.copy_fixture(...)` + `project.write_config(...)` + `project.write_curation([...])` in place of per-class `config` fixtures.
3. `git rm tests/test_integration.py`.
4. Verify (33 passed in integration file), commit.

---

## Task C19: Relocate `tests/test_core_module_purity.py` → `tests/integration/test_architecture_purity.py`

**Files:**
- Create: `tests/integration/test_architecture_purity.py`
- Delete: `tests/test_core_module_purity.py`

Source: 42 lines, 1 parametrized test (10 core modules). The issue-#43 architectural invariant.

### Steps (Rule I5 — whole-file)

1. Read source. It's a single parametrized test that asserts no `typer` imports in the 10 core modules.
2. Write `tests/integration/test_architecture_purity.py`:
   - Module docstring: `"""Integration: architectural invariants. Tests that load-bearing structural constraints hold across the codebase — currently the #43 no-typer-in-pure-cores rule."""`
   - Move the test verbatim.
3. `git rm tests/test_core_module_purity.py`.
4. Verify (1 passed × 10 params), commit.

---

## Wave C completion checklist

After Task C19:

- [ ] `uv run pytest -q` — green; 720 total (count invariant).
- [ ] `ls tests/integration/test_*.py | wc -l` — **18+** (one per Wave C destination file, counting the merged readonly_commands).
- [ ] `ls tests/test_*_core.py 2>/dev/null | wc -l` — **0** (discover/validate/setup/status/history cores all migrated).
- [ ] `test ! -f tests/test_pipeline.py && test ! -f tests/test_cache.py && test ! -f tests/test_curation_config_integration.py && test ! -f tests/test_integration.py && test ! -f tests/test_core_module_purity.py` — whole-file migrations gone.
- [ ] `grep -rn "CliRunner\|subprocess.run" tests/ --include='test_*.py' | grep -v "tests/e2e/\|tests/integration/test_architecture_purity" | grep -v "import " | head` — no stray CLI usages outside `tests/e2e/`.
- [ ] Shrunken files still exist and still pass: `test_incremental.py`, `test_schema_drift.py`, `test_dedup.py`, `test_append.py`, `test_retry.py`, `test_csv_glob.py`, `test_dq.py`, `test_transforms.py`, `test_json_output.py`, `test_mode.py`.
- [ ] `uv run pytest tests/integration/ -q` — all integration tests pass standalone.

When every checkbox passes, proceed to Wave D planning (drain remaining flat `test_*.py` files + delete `tests/commands/`).

---

## Risks

1. **Test count drift during splits.** Every split must produce `integration_count + remaining_source_count == original_count`. The subagent must verify after each split task. If not matching, stop and investigate.

2. **Shared helpers in source files** (e.g., `_run_pipeline` in `test_mode.py`, `setup_env` in `test_pipeline.py`). Inlining vs file-local helper vs shared helper is a per-task judgment. Follow Rule I7.

3. **Imports at shared file top.** Splits may leave unused imports in the source file. Always run the source file standalone after removal (`uv run pytest tests/test_source.py -v`) to catch missing imports at collection time.

4. **`tests/test_integration.py` is 811 lines, 33 tests.** The single biggest whole-file migration. Consider splitting further (sub-files per concern: fixtures / pipeline / validation / bugs / CSV / SQLite) if the destination file becomes unwieldy. Survey's recommendation: keep whole for now.

5. **`test_mode.py` already shrank by Task C0** (1 test). After Task C17, it shrinks further. Not a risk per se — just note the sequencing.

---

## Self-review

**Spec coverage for Wave C:**
- Every source file identified in the design spec's Wave C section has a corresponding task or an explicit deferral.
- The Wave B leftover (Task C0) is called out as such.
- The `test_core_module_purity.py` relocation (Task C19) is new scope; the spec doesn't explicitly place this test anywhere, but the reviewer recommended `tests/integration/test_architecture_purity.py` and this plan honors that.

**Placeholder scan:** no TBDs, no "similar to Task N". Each migration task follows Rule I4 or Rule I5 uniformly, which is the "shared procedure" that scales across 20 tasks.

**Type consistency:** module docstring template from Rule I6 is consistent; `project.write_config` + `project.write_curation` + `load_config(project.config_path)` + `run_all(cfg, project.config_path)` is the standard preamble across tasks.

**Scope:** 20 tasks is large but atomic. One PR at the end delivers all waves (per the original decision). Bisectability across Wave A (12) + Wave B (14) + Wave C (~20) + Wave D + Wave E commits is preserved by one-commit-per-task discipline.

**Wave D handoff:** Wave D's scope is now clearer — drain every file listed in the Wave D candidates table (survey), plus the unit halves of every split migration. `tests/commands/` deletion is Wave D's final act.

**Wave E handoff:** unchanged.
