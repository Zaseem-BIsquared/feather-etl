# Test Restructure — Wave D (Migrate unit tests) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move every remaining flat `tests/test_*.py` file into `tests/unit/` (mirroring `src/feather_etl/`). After this wave, `tests/` root contains only `conftest.py`, `helpers.py`, `README.md`, `fixtures/`, and the three layer directories (`e2e/`, `integration/`, `unit/`). `tests/commands/` is deleted.

**Architecture:** One migration task per destination file. Most are whole-file migrations (source is unit-only post-Wave-C splits). A few require splitting large source files (`test_sources.py` → per-source-type files). No `project` fixture use — unit tests take `tmp_path` only.

**Tech Stack:** Same as A/B/C. No new dependencies.

**Source spec:** [`docs/superpowers/specs/2026-04-19-test-restructure-design.md`](../specs/2026-04-19-test-restructure-design.md)
**Prior waves:** [`wave-a.md`](2026-04-19-test-restructure-wave-a.md), [`wave-b.md`](2026-04-19-test-restructure-wave-b.md), [`wave-c.md`](2026-04-19-test-restructure-wave-c.md)
**Issue:** https://github.com/siraj-samsudeen/issue
**Branch:** `feat/test-restructure` (same branch; Wave D commits extend history).

---

## Scope

### In scope

- **Whole-file migrations to `tests/unit/`** (28 source files → ~22 destination files, some merged):
  - Mirrors `src/feather_etl/` layout. Sources go under `tests/unit/sources/`, destinations under `tests/unit/destinations/`.
- **`tests/commands/` deletion** (only `__init__.py` + `conftest.py` remain; deleted as final Wave D task).

### Out of scope

- E2E tests (Wave B); integration tests (Wave C).
- `scripts/hands_on_test.sh` deletion (Wave E).
- Documentation updates (Wave E).

### End state after Wave D

- `tests/` root contains only `conftest.py`, `helpers.py`, `README.md`, `fixtures/`, `e2e/`, `integration/`, `unit/`.
- `tests/unit/` mirrors `src/feather_etl/`:
  ```
  tests/unit/
    test_config.py, test_state.py, test_curation.py, test_alerts.py,
    test_retry.py, test_output.py, test_dq.py, test_discover_io.py,
    test_discover_state.py, test_viewer_server.py, test_transforms.py,
    test_incremental.py, test_schema_drift.py, test_dedup.py,
    test_append.py, test_mode.py, test_boundary_dedup.py,
    commands/      (empty — kept as skeleton per Wave A; commands tested e2e)
    destinations/
      test_duckdb.py
    sources/
      test_csv.py, test_excel.py, test_json.py, test_postgres.py,
      test_mysql.py, test_sqlserver.py, test_registry.py, test_protocol.py,
      test_file_source.py, test_database_source.py, test_expand.py
  ```
- `tests/commands/` gone.
- Test count: 720 → 720 (invariant preserved).

---

## File Structure

**Migration mapping (source → destination):**

| Source (in `tests/`) | Destination | Tests | Notes |
|---|---|---:|---|
| `test_config.py` | `tests/unit/test_config.py` | 43 | Whole-file. Biggest config test file. |
| `test_state.py` | `tests/unit/test_state.py` | 25 | Whole-file. StateManager unit. |
| `test_curation.py` | `tests/unit/test_curation.py` | 15 | Whole-file. Replace local `_write_curation` / `_make_include` with `tests.helpers`. |
| `test_destinations.py` | `tests/unit/destinations/test_duckdb.py` | 7 | Mirror src path (`src/feather_etl/destinations/duckdb.py`). |
| `test_alerts.py` | `tests/unit/test_alerts.py` | 12 | Whole-file. Mock-heavy; preserve `@patch` decorators. |
| `test_retry.py` (shrunk) | `tests/unit/test_retry.py` | 15 | Whole-file post-Wave-C. 5 unit classes. |
| `test_dq.py` (shrunk) | `tests/unit/test_dq.py` | 9 | Whole-file post-Wave-C. 4 unit classes. |
| `test_discover_io.py` | `tests/unit/test_discover_io.py` | 20 | Whole-file. |
| `test_discover_state.py` | `tests/unit/test_discover_state.py` | 20 | Whole-file. |
| `test_viewer_server.py` | `tests/unit/test_viewer_server.py` | 9 | Whole-file. |
| `test_transforms.py` (shrunk) | `tests/unit/test_transforms.py` | 31 | Whole-file post-Wave-B + Wave-C. 6 unit classes. |
| `test_incremental.py` (shrunk) | `tests/unit/test_incremental.py` | 10 | Whole-file post-Wave-C. 3 unit classes. |
| `test_schema_drift.py` (shrunk) | `tests/unit/test_schema_drift.py` | 10 | Whole-file post-Wave-C. 2 unit classes. |
| `test_dedup.py` (shrunk) | `tests/unit/test_dedup.py` | 1 | Single test. |
| `test_append.py` (shrunk) | `tests/unit/test_append.py` | 3 | TestLoadAppend. |
| `test_mode.py` (shrunk) | `tests/unit/test_mode.py` | 8 | Config-parsing + env-var tests. |
| `test_boundary_dedup.py` | `tests/unit/test_boundary_dedup.py` | 10 | Whole-file. 3 classes, all unit. |
| `test_json_output.py` (shrunk) | `tests/unit/test_output.py` | 4 | TestOutputHelper. Rename to match src module (`src/feather_etl/output.py`). |
| `test_explicit_name_flag.py` (shrunk) | **Merge into** `tests/unit/sources/test_duckdb_file.py` + `tests/unit/sources/test_postgres.py` | 5 | 2 tests for `DuckDBFileSource._explicit_name`, 3 for `PostgresSource._explicit_name`. Or combined into one `test_explicit_name_flag.py` — see Task D17. |
| `test_sources.py` | **Split** into `tests/unit/sources/test_registry.py` (`TestSourceRegistry` + `TestLazyRegistry`), `tests/unit/sources/test_protocol.py` (`TestSourceProtocol`), `tests/unit/sources/test_file_source.py` (`TestFileSource` + `TestFileSourceFromYaml` + `TestFileSourceValidateSourceTable` + `TestFileSourcesRejectDbFields`), `tests/unit/sources/test_database_source.py` (`TestSourceDataclasses`), `tests/unit/sources/test_duckdb_file.py` (`TestDuckDBFileSource`), `tests/unit/sources/test_csv.py` (`TestCsvSource`), `tests/unit/sources/test_sqlite.py` (`TestSqliteSource`) | 70 | **Largest single migration.** 11 classes split by source type. |
| `test_excel.py` | `tests/unit/sources/test_excel.py` | 17 | Whole-file. |
| `test_json.py` | `tests/unit/sources/test_json.py` | 18 | Whole-file. |
| `test_postgres.py` | `tests/unit/sources/test_postgres.py` | 35 | Whole-file. Postgres-gated. |
| `test_mysql.py` | `tests/unit/sources/test_mysql.py` | 31 | Whole-file. MySQL-gated. |
| `test_sqlserver.py` | `tests/unit/sources/test_sqlserver.py` | 34 | Whole-file. pyodbc mocked. |
| `test_csv_glob.py` (shrunk) | `tests/unit/sources/test_csv.py` | 1 | **Merge** TestCsvGlobDiscover into `tests/unit/sources/test_csv.py` (created by Task D13b). |
| `test_discover_expansion.py` + `test_expand_db_sources.py` | `tests/unit/sources/test_expand.py` | 4 + 3 | **Merge** two files into one (both test `sources.expand`). |

Plus final cleanup:

| Task | Action |
|---|---|
| **D-final** | Delete `tests/commands/__init__.py` + `tests/commands/conftest.py` + `tests/commands/` directory. No test file is using `cli_env` / `cli_config` / `two_table_env` / `multi_source_yaml` after Waves B/C. |

**Total Wave D tasks: ~25** (22 migrations + 3 merges/splits + 1 cleanup).

---

## Shared migration rules

All prior-wave rules apply. Wave-D-specific clarifications:

### Rule D1 — Unit tests don't use `project` or `cli` fixtures

Unit tests test a single module. They use:
- `tmp_path` for any filesystem needs
- `pytest.fixture` / `pytest.raises` / `monkeypatch` / `capsys` / `caplog` as appropriate
- Module imports directly (e.g., `from feather_etl.config import load_config`)

### Rule D2 — Whole-file migrations are simple moves

For whole-file migrations (most of Wave D):
1. `git mv tests/test_<name>.py tests/unit/<path>.py` (or `git mv` into `tests/unit/sources/` etc.).
2. **Do not refactor the tests** unless they reference deleted helpers (like `cli_env`). Preserve tests as-is for blame continuity and to minimize risk.
3. Update any imports that changed path (e.g., if a test imports from `tests.helpers` — that still works; if it imports from `tests.commands.conftest` — replace with inline setup, but this shouldn't happen in unit tests).
4. Run the file: `uv run pytest tests/unit/.../test_X.py -v` — must match pre-move pass count.
5. Verify full suite: 720 green.
6. Commit.

### Rule D3 — Split migrations (only `test_sources.py`)

`test_sources.py` is the only file Wave D splits. The 11 classes go to 7 destination files by source type. Treat as **one task** (Task D19) — the split is atomic.

### Rule D4 — Merge migrations

Three merges in Wave D:
- `test_csv_glob.py` (1 test) + `test_sources.py::TestCsvSource` → `tests/unit/sources/test_csv.py` (handled in Task D19's split).
- `test_discover_expansion.py` (4 tests) + `test_expand_db_sources.py` (3 tests) → `tests/unit/sources/test_expand.py` (Task D22).
- `test_explicit_name_flag.py` (5 tests) → 2 or 3 per-source files per survey. **Simplification:** merge all 5 into `tests/unit/test_explicit_name_flag.py` (flat file under unit/, not sources/) since they test a cross-source feature flag (Task D17).

### Rule D5 — Module docstrings

Each new `tests/unit/test_X.py` file should retain the source file's docstring if present. If the source file had no docstring, add a brief one:

```python
"""Unit: feather_etl.<module> — <one-line summary>."""
```

### Rule D6 — No conftest needed for `tests/unit/`

Unit tests don't need the `project` fixture. `tests/unit/` can have no `conftest.py` — pytest will happily collect from there with no setup. If a unit test somehow needs `project` (unlikely — it would then be integration, not unit), the test was misclassified; report.

### Rule D7 — Count invariant

720 → 720 throughout.

### Rule D8 — Commit style

`test(d):` prefix. Whole-file migration commits:

```
test(d): migrate test_<name>.py -> unit/<path>.py (#40)

<N> tests relocated (whole-file move). No refactoring.
```

Split/merge commits:

```
test(d): split test_sources.py -> unit/sources/* (#40)

Seventy tests across 11 classes split by source type into 7 files
under tests/unit/sources/: test_registry, test_protocol, test_file_source,
test_database_source, test_duckdb_file, test_csv, test_sqlite. Source
file deleted.
```

### Rule D9 — `tests/commands/` cleanup

The final Wave D task removes the orphaned `tests/commands/` package:
- `tests/commands/__init__.py` — delete.
- `tests/commands/conftest.py` — delete (all its fixtures are either unused now or inlined in Waves B/C).
- `tests/commands/` directory should be empty after those two deletions; `git status` might still show the directory marker — `rmdir tests/commands` to clean up.

Before deleting, verify nothing imports from `tests.commands.conftest`:

```bash
grep -rn "tests.commands.conftest\|from tests.commands" tests/ --include='*.py'
```

Expected: no results.

---

## Task Order

1. **D1-D18**: Whole-file migrations, simplest first (smallest files).
2. **D19**: `test_sources.py` split (biggest, risky — do alone).
3. **D20**: Merge `test_discover_expansion.py` + `test_expand_db_sources.py` → `test_expand.py`.
4. **D21**: `tests/commands/` cleanup.

---

## Tasks D1-D17: Whole-file migrations (in size order, small first)

For each whole-file task, use this template:

**Files:**
- Move: `tests/test_X.py` → `<destination path>`

**Steps:**
1. `cat <source>` — briefly understand.
2. `git mv <source> <destination>` (or `git add <destination>` + `git rm <source>` if a filename changes meaningfully).
3. If filename/path changes, any imports in the destination referencing the old location must be updated — but unit tests typically don't cross-reference other test files.
4. Verify: `uv run pytest <destination> -v` — same pass count as pre-move; `uv run pytest -q` — 720 green; `git status --short` — 2 entries (A + D, or R if rename detected).
5. Commit with format above.

### Task D1: `test_csv_glob.py` (1 test) → `tests/unit/sources/test_csv_glob.py`

(Temporary destination — Task D19 may consolidate with `test_sources.py::TestCsvSource`; defer the merge to D19.)

### Task D2: `test_dedup.py` (1 test) → `tests/unit/test_dedup.py`

### Task D3: `test_append.py` (3 tests) → `tests/unit/test_append.py`

### Task D4: `test_expand_db_sources.py` (3 tests) → leave in place for Task D20 merge

(Skip in the D1-D17 loop; merged in D20.)

### Task D5: `test_discover_expansion.py` (4 tests) → leave for D20 merge

(Skip in the D1-D17 loop.)

### Task D6: `test_json_output.py` (4 tests) → `tests/unit/test_output.py`

Note filename change — destination mirrors `src/feather_etl/output.py`. The `TestOutputHelper` class tests `feather_etl.output.emit` / `emit_line`.

### Task D7: `test_explicit_name_flag.py` (5 tests) → `tests/unit/test_explicit_name_flag.py`

### Task D8: `test_destinations.py` (7 tests) → `tests/unit/destinations/test_duckdb.py`

Filename change — mirrors `src/feather_etl/destinations/duckdb.py`.

### Task D9: `test_mode.py` (8 tests) → `tests/unit/test_mode.py`

### Task D10: `test_dq.py` (9 tests) → `tests/unit/test_dq.py`

### Task D11: `test_viewer_server.py` (9 tests) → `tests/unit/test_viewer_server.py`

### Task D12: `test_boundary_dedup.py` (10 tests) → `tests/unit/test_boundary_dedup.py`

### Task D13: `test_incremental.py` (10 tests) → `tests/unit/test_incremental.py`

### Task D14: `test_schema_drift.py` (10 tests) → `tests/unit/test_schema_drift.py`

### Task D15: `test_alerts.py` (12 tests) → `tests/unit/test_alerts.py`

### Task D16: `test_curation.py` (15 tests) → `tests/unit/test_curation.py`

Replace any local `_write_curation` / `_make_include` helpers with `tests.helpers.write_curation` / `make_curation_entry`.

### Task D17: `test_retry.py` (15 tests) → `tests/unit/test_retry.py`

### Task D18: `test_excel.py` (17 tests) → `tests/unit/sources/test_excel.py`

### Task D19: `test_json.py` (18 tests) → `tests/unit/sources/test_json.py`

### Task D20: `test_discover_io.py` (20 tests) → `tests/unit/test_discover_io.py`

### Task D21: `test_discover_state.py` (20 tests) → `tests/unit/test_discover_state.py`

### Task D22: `test_state.py` (25 tests) → `tests/unit/test_state.py`

### Task D23: `test_mysql.py` (31 tests) → `tests/unit/sources/test_mysql.py`

### Task D24: `test_transforms.py` (31 tests) → `tests/unit/test_transforms.py`

### Task D25: `test_sqlserver.py` (34 tests) → `tests/unit/sources/test_sqlserver.py`

### Task D26: `test_postgres.py` (35 tests) → `tests/unit/sources/test_postgres.py`

### Task D27: `test_config.py` (43 tests) → `tests/unit/test_config.py`

---

## Task D28 (SPLIT): `test_sources.py` → 7 files under `tests/unit/sources/`

**Files:**
- Create: 7 new files under `tests/unit/sources/`
- Delete: `tests/test_sources.py`

Source: 734 lines, 70 tests, 11 classes. Split by source type:

| Class | Destination | Tests |
|---|---|---:|
| `TestSourceDataclasses` | `tests/unit/sources/test_database_source.py` | ~3 |
| `TestFileSource` | `tests/unit/sources/test_file_source.py` | ~N |
| `TestDuckDBFileSource` | `tests/unit/sources/test_duckdb_file.py` | ~N |
| `TestCsvSource` | `tests/unit/sources/test_csv.py` | ~N (+ 1 from Task D1 merge) |
| `TestSqliteSource` | `tests/unit/sources/test_sqlite.py` | ~N |
| `TestSourceRegistry` + `TestLazyRegistry` | `tests/unit/sources/test_registry.py` | ~N |
| `TestSourceProtocol` | `tests/unit/sources/test_protocol.py` | ~N |
| `TestFileSourceFromYaml` + `TestFileSourceValidateSourceTable` + `TestFileSourcesRejectDbFields` | `tests/unit/sources/test_file_source.py` (merge) | ~N |

Confirm class sizes during implementation; adjust merges/splits if a class is small enough to fold.

### Steps

1. `grep -n "^class " tests/test_sources.py` — see the 11 classes.
2. For each destination file, create it with the classes it receives. Flatten single-member classes per Rule M2. Preserve class-grouped ones where they share fixtures.
3. Merge `tests/unit/sources/test_csv_glob.py` (1 test from Task D1) into `tests/unit/sources/test_csv.py` if you choose to consolidate. OR leave as a sibling. Use judgment.
4. `git rm tests/test_sources.py`.
5. Verify: each destination passes standalone; full suite 720 green.
6. Commit:
```
test(d): split test_sources.py -> unit/sources/* (#40)

Seventy tests across 11 classes split by source type into 7 files
under tests/unit/sources/ (test_registry, test_protocol, test_file_source,
test_database_source, test_duckdb_file, test_csv, test_sqlite). Source
file deleted. Optional merge of test_csv_glob.py (1 test) into
test_csv.py.
```

---

## Task D29 (MERGE): `test_discover_expansion.py` + `test_expand_db_sources.py` → `tests/unit/sources/test_expand.py`

**Files:**
- Create: `tests/unit/sources/test_expand.py`
- Delete: `tests/test_discover_expansion.py`
- Delete: `tests/test_expand_db_sources.py`

Sources: 4 tests + 3 tests = 7 tests. Both exercise `sources.expand.expand_db_sources`.

### Steps

1. Read both sources.
2. Create `tests/unit/sources/test_expand.py` combining both files' tests (flatten, preserve classes only where fixtures are shared).
3. Delete both sources.
4. Verify: 7 passed; 720 green; 3 staged (1 add, 2 delete).
5. Commit:
```
test(d): merge test_discover_expansion + test_expand_db_sources -> unit/sources/test_expand.py (#40)

Seven tests combined (4 + 3) — both files tested sources.expand.expand_db_sources.
```

---

## Task D30 (FINAL): Delete `tests/commands/`

**Files:**
- Delete: `tests/commands/__init__.py`
- Delete: `tests/commands/conftest.py`
- Delete: `tests/commands/` directory

### Steps

1. Verify nothing imports from `tests/commands/conftest.py`:
```bash
grep -rn "tests.commands.conftest\|from tests.commands" tests/ --include='*.py'
```
Expect: no results.

2. Verify directory is almost empty:
```bash
ls tests/commands/
```
Expect: `__init__.py`, `conftest.py`, possibly `__pycache__/`.

3. Delete:
```bash
git rm tests/commands/__init__.py tests/commands/conftest.py
rmdir tests/commands  # OK if __pycache__ prevents this; rm -rf tests/commands/__pycache__ first if needed
```

4. Verify: `test ! -d tests/commands` — directory gone; 720 green; 2 staged.

5. Commit:
```
test(d): delete orphaned tests/commands/ package (#40)

Wave B migrated all tests/commands/test_*.py files to tests/e2e/;
Wave C migrations don't reference any fixtures in tests/commands/conftest.py;
Wave D (this commit) removes the empty package (__init__.py + conftest.py)
that was preserved as a stepping-stone.

Verifies end-of-Wave-D tree layout: tests/ root contains only
conftest.py, helpers.py, README.md, fixtures/, and the three layer
directories (e2e/, integration/, unit/).
```

---

## Wave D completion checklist

After Task D30:

- [ ] `uv run pytest -q` — green; 720 total.
- [ ] `ls tests/test_*.py 2>/dev/null | wc -l` — **0**. No flat test files at `tests/` root.
- [ ] `test ! -d tests/commands` — directory gone.
- [ ] `ls tests/unit/` — shows `test_*.py` files + subdirs (`sources/`, `destinations/`, `commands/`).
- [ ] `ls tests/unit/sources/` — shows `test_csv.py`, `test_excel.py`, `test_json.py`, etc.
- [ ] `ls tests/` — exactly `__init__.py`, `conftest.py`, `helpers.py`, `README.md`, `e2e/`, `integration/`, `unit/`, `fixtures/`.
- [ ] `bash scripts/hands_on_test.sh` — still 61/61 PASS (untouched).
- [ ] `uv run pytest tests/integration/test_architecture_purity.py -q` — 10 passed (#43 invariant holds).

When every checkbox passes, proceed to Wave E (coverage proof + bash-script deletion + docs).

---

## Risks

1. **`test_sources.py` split (Task D28) is the biggest Wave D task.** 70 tests, 11 classes. The split could miscount or mis-assign if rushed. Mitigation: verify each destination file's count matches the class's contribution; the sum across 7 destinations must equal 70.

2. **Path mirror rule** may not have obvious answers for every module. `test_json_output.py` → `test_output.py` is judgment (the `output` module lives at `src/feather_etl/output.py`). Document such decisions in commit messages.

3. **No `tests/unit/conftest.py`** by default. If a migrated test fails because of a missing fixture, the source file may have depended on a root `tests/conftest.py` fixture (like `client_db`, `sample_erp_db`) — those remain available since they're defined at `tests/conftest.py`, which is the parent of `tests/unit/`. No change needed.

4. **`tests/commands/conftest.py` deletion (Task D30)** assumes nothing imports from it. Wave B + Wave C should have drained everything, but a double-check via grep is required.

5. **Live-DB tests** (`test_postgres.py`, `test_mysql.py`) continue to skip when their DB is unavailable. `tests/conftest.py` already handles Postgres bootstrap. No Wave D changes needed to conftest.

---

## Self-review

**Spec coverage for Wave D:** every remaining flat `tests/test_*.py` file has a destination in this plan. `tests/commands/` cleanup is the explicit final task.

**Placeholder scan:** the task list has 27 whole-file migration entries (D1-D27) using a shared template. The template is specified once; per-task entries list source/destination/count. This is concise but NOT a placeholder — each task is executable.

**Type consistency:** `git mv` preferred for whole-file; `git add` + `git rm` for splits. Commit message format standardized.

**Scope:** Wave D has the most tasks (~30), but they're mostly `git mv`. The one risky task is D28 (test_sources.py split); the merge tasks (D29) and cleanup (D30) are mechanical.

**Wave E handoff:** unchanged — update `CLAUDE.md`, `docs/CONTRIBUTING.md`, delete `scripts/hands_on_test.sh` after verifying the coverage map.
