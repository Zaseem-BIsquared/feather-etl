# Test suite restructure: pytest-only, three-layer architecture

Created: 2026-04-19
Status: DRAFT
Approved: Pending
Issue: https://github.com/siraj-samsudeen/feather-etl/issues/40
Type: Refactor

## Summary

Replace `scripts/hands_on_test.sh` (902 lines, 61 bash checks) with pytest-only
coverage, and reorganize the existing 46-file flat `tests/` tree into a
three-layer structure (`tests/e2e/`, `tests/integration/`, `tests/unit/`) so a
reader can locate any test by what it exercises rather than by historical
filename.

The end state is a single PR that:

- removes `scripts/hands_on_test.sh`,
- moves every existing test into `tests/e2e/`, `tests/integration/`, or
  `tests/unit/` per a written rule,
- introduces a `ProjectFixture` + `cli` pair that becomes the standard harness
  for end-to-end tests,
- keeps the suite green at every commit so the branch is bisectable.

## Background

### What exists today

- `scripts/hands_on_test.sh` — 902 lines, 61 bash `check()` calls grouped into
  ~15 numbered stages (S1–S22, S-INCR). It shells out to `feather`, asserts
  with `grep`/`run_ok`/`run_fail`, and uses inline YAML strings.
- `tests/` — flat layout, 46 files, ~656 tests by file-level count
  (CLAUDE.md says 653; small drift is normal). 42 of 46 files group tests
  with `class TestFoo:` (no `unittest.TestCase` anywhere — only
  `unittest.mock` is imported, which is pytest-compatible). 4 files use flat
  function style.
- `tests/commands/` — one subfolder, 11 files, all using `CliRunner` to
  exercise individual CLI commands.
- `tests/conftest.py` — five data fixtures (`client_db`, `config_path`,
  `csv_data_dir`, `sqlite_db`, `sample_erp_db`) that copy `tests/fixtures/*`
  into `tmp_path`.
- `src/feather_etl/` — clean module tree (`commands/`, `sources/`,
  `destinations/`, plus top-level modules for `config`, `state`, `pipeline`,
  `transforms`, `cache`, `dq`, `schema_drift`, `alerts`, etc.). Easy to mirror.

### What's broken about the current shape

1. **Duplicate coverage with a maintenance tax.** Per issue #40, ~90% of the
   bash checks are already covered by pytest tests. Updating CLI output
   requires editing both bash greps and pytest assertions. The bash script's
   stage count drifted (CLAUDE.md said 72 checks; actual is 61) and nobody
   noticed because nobody reads bash test scripts line by line.
2. **The flat `tests/` directory hides the level of every test.**
   `test_integration.py` (811 lines) mixes regression bugs, error-isolation
   integration tests, CLI validation, and full-pipeline e2e. `test_transforms.py`
   (869 lines) mixes parser unit tests, transform-execution integration tests,
   and CLI-level e2e. A reader cannot tell what layer they're in without
   reading the test body.
3. **Source tests are split across two axes.** `test_sources.py` (734 lines,
   70 tests) holds the source protocol + file sources + registry; per-source
   files (`test_postgres.py`, `test_mysql.py`, `test_sqlserver.py`,
   `test_excel.py`, `test_json.py`, `test_csv_glob.py`) hold the rest.
4. **Cross-cutting feature tests have no directory grouping.**
   `test_incremental.py`, `test_schema_drift.py`, `test_dedup.py`,
   `test_boundary_dedup.py`, `test_append.py`, `test_retry.py`,
   `test_cache.py`, `test_alerts.py`, `test_dq.py`, `test_curation.py` all
   sit flat next to unit tests for `test_config.py`, `test_state.py`.
5. **No shared end-to-end harness.** Every e2e test re-derives the project
   directory layout, hand-writes config and curation, and re-implements the
   `duckdb.connect` boilerplate to query results. There is no Playwright-style
   `page` equivalent — i.e., no single object that represents "a feather
   project ready to run."

## Design

### Three-layer architecture

```
tests/
  e2e/                          # CLI journeys; reads top-to-bottom = user story
    conftest.py                 # ProjectFixture, project, cli fixtures
    test_00_cli_structure.py
    test_01_scaffold.py
    test_02_validate.py
    test_03_discover.py
    test_04_extract_full.py
    test_05_change_detection.py
    test_06_incremental.py
    test_07_transforms.py
    test_08_dq.py
    test_09_schema_drift.py
    test_10_error_handling.py
    test_11_path_resolution.py
    test_12_cache.py
    test_13_multi_source.py
    test_14_status.py
    test_15_history.py
    test_16_view.py
    test_17_json_output.py
    test_18_sources_e2e.py      # SQLite/Postgres/etc. via CLI
  integration/                  # Multi-module Python-API slices (no CLI)
    test_pipeline.py
    test_change_detection.py
    test_incremental.py
    test_schema_drift.py
    test_transforms.py
    test_dq.py
    test_cache.py
    test_dedup.py
    test_append.py
    test_retry.py
    test_alerts.py
    test_curation_pipeline.py
    test_error_isolation.py
    test_multi_source.py
  unit/                         # Single-module; mirrors src/feather_etl/
    test_config.py
    test_state.py
    test_curation.py
    test_pipeline_helpers.py    # only if pipeline has unit-testable bits
    test_transforms.py          # parse, discover, build_execution_order
    test_cache.py               # unit-level cache helpers
    test_dq.py                  # unit-level dq config parsing
    test_schema_drift.py        # unit-level drift detection
    test_alerts.py              # unit-level alert config + dispatch
    test_discover_state.py
    test_discover_io.py
    test_output.py
    test_viewer_server.py
    sources/
      test_registry.py
      test_protocol.py
      test_file_source.py
      test_database_source.py
      test_csv.py
      test_excel.py
      test_json.py
      test_sqlite.py
      test_duckdb_file.py
      test_postgres.py
      test_mysql.py
      test_sqlserver.py
      test_expand.py
    destinations/
      test_duckdb.py
    commands/                   # ONLY if a command has internals worth
                                # testing in isolation. Most commands' tests
                                # live in tests/e2e/. Likely empty initially.
  fixtures/                     # unchanged; data files
  conftest.py                   # session-level (pg_ctl bootstrap); keep
  helpers.py                    # shared module helpers; keep
  README.md                     # documents the rule below
```

### The three-way decision rule

For any test, ask in order:

1. **Does it invoke the CLI?** (either `CliRunner.invoke(app, ...)` or
   spawns the `feather` binary via subprocess) → `tests/e2e/`. File chosen
   by workflow stage.
2. **Does it exercise 2+ `src/feather_etl/` modules through a pipeline-level
   API** (e.g., `pipeline.run_pipeline()`, `cache.run_cache()`)? →
   `tests/integration/`. File chosen by feature/capability.
3. **Otherwise — exercises a single module's functions/classes** →
   `tests/unit/`. File mirrors the source path
   (`src/feather_etl/sources/csv.py` → `tests/unit/sources/test_csv.py`).

The rule has no carve-outs. `CliRunner` alone makes a test e2e even when it
only tests one command; that is intentional, because the current
`tests/commands/` files are already exercising the full CLI dispatch path.

### Test style within files

- **Flat function style by default.** `def test_foo(project, cli): ...` at
  module level. Pytest's standard idiom.
- **Class groupings allowed only when they add real grouping value:** several
  tests share a `@pytest.fixture` defined inside the class, or a clear
  sub-concept exists (e.g., `class TestCsvGlobChangeDetection:`). When in
  doubt, prefer flat.
- **No `unittest.TestCase`.** Use plain `assert`, `pytest.raises`,
  `pytest.fixture`. `unittest.mock` is fine — that is the standard mock
  library.

### `ProjectFixture` and `cli` fixtures

A `ProjectFixture` is a small object representing "a feather project on
disk, ready to use." It bundles together the directory, the config path,
the data DB path, the state DB path, and helpers for the things every e2e
test does. The `cli` fixture is a callable that runs feather commands
against that project.

```python
# tests/e2e/conftest.py
class ProjectFixture:
    def __init__(self, root: Path):
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

    def write_config(self, **fields) -> None:
        self.config_path.write_text(yaml.dump(fields, default_flow_style=False))

    def write_curation(self, entries: list[tuple[str, str, str]]) -> None:
        # entries: [(source_name, source_table, target_name), ...]
        write_curation(self.root, [make_curation_entry(*e) for e in entries])

    def copy_fixture(self, name: str) -> Path:
        src = FIXTURES_DIR / name
        dst = self.root / name
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        return dst

    def query(self, sql: str) -> list[tuple]:
        with duckdb.connect(str(self.data_db_path), read_only=True) as con:
            return con.execute(sql).fetchall()


@pytest.fixture
def project(tmp_path) -> ProjectFixture:
    return ProjectFixture(tmp_path)


@pytest.fixture
def cli(project):
    runner = CliRunner()
    def run(*args: str):
        return runner.invoke(app, list(args) + ["--config", str(project.config_path)])
    return run
```

This is the **complete day-one API**. Methods are added only when a test
that needs them is written; we do not pre-add `assert_table_rows`,
`add_source`, or `run` shortcuts speculatively.

The fixture lives in `tests/e2e/conftest.py` so existing tests under
`tests/test_*.py` and `tests/commands/` are not affected by its presence
during early waves.

### What happens to existing fixtures

`tests/conftest.py` keeps its session-level `pytest_configure` /
`pytest_unconfigure` hooks (Postgres bootstrap) and the data-copy fixtures
(`client_db`, `config_path`, `csv_data_dir`, `sqlite_db`, `sample_erp_db`).
These continue to serve `tests/integration/` and `tests/unit/` tests.
`tests/e2e/` tests use `ProjectFixture` and reach for raw fixture data via
`project.copy_fixture(name)`.

When integration/unit tests are migrated, they keep using the existing
data fixtures unless adopting `ProjectFixture` is trivially better. We do
not refactor working tests for purity.

### The 5 gap tests

Per issue #40 the bash script covers exactly five scenarios that pytest
does not:

| Gap | What | Lands in |
|---|---|---|
| 1 (S10) | `feather run --config /abs/path` from a different CWD | `tests/e2e/test_11_path_resolution.py` |
| 2 (S13) | Missing `feather.yaml` produces "Config file not found" | `tests/e2e/test_02_validate.py` |
| 3 (S14) | Error message appears on stdout only, not duplicated on stderr (BUG-1 regression) — uses `subprocess.run` because `CliRunner` merges streams. The exact subprocess invocation (`uv run feather …` vs direct binary path vs adding a `__main__.py`) is decided in the implementation plan; the test must drive the real `feather` entry point. | `tests/e2e/test_10_error_handling.py` |
| 4 (S16a) | CSV `source.path` must be a directory, not a file | `tests/e2e/test_02_validate.py` |
| 5 (S17) | SQLite source: `validate` + `setup` + `run` end-to-end | `tests/e2e/test_18_sources_e2e.py` |

These are the canonical first tests that exercise `ProjectFixture`/`cli`.

### Coverage-equivalence proof

Before deletion, every numbered check in the bash script must be mapped to
a pytest test. The mapping lives at
`docs/superpowers/specs/2026-04-19-test-restructure-coverage-map.md` and
is structured as:

```
| Bash check | What it asserts | Pytest test path |
|---|---|---|
| S1.1 | `feather init` creates feather.yaml | tests/e2e/test_01_scaffold.py::test_init_creates_feather_yaml |
| S1.2 | ... | ... |
| ... |
```

The map is updated as migration waves land. Wave E does not delete the
bash script until every row has a non-empty `Pytest test path`.

### Documentation to update

- `CLAUDE.md`: the "Before you write a single line of code" block currently
  references both `uv run pytest -q` and `bash scripts/hands_on_test.sh`.
  The bash line is removed; the test count is corrected.
- `docs/CONTRIBUTING.md`:
  - "Rules for the fixing agent" item 4 (about updating
    `scripts/hands_on_test.sh` BUG-labelled checks) is rewritten to point at
    `tests/e2e/` (and at integration/unit if the bug lives there).
  - "Rules for the fixing agent" item 5 (running both suites) is reduced to
    a single pytest invocation.
  - Re-review section's references to "New hands-on scenarios to add to
    `scripts/hands_on_test.sh`" are rewritten to point at `tests/e2e/`.
  - The subsection titled `### scripts/hands_on_test.sh` is replaced with
    `### tests/e2e/` documenting the BUG-labelled regression test pattern
    (write a failing test under e2e, mark it `BUG-N`, invert when fixed).
- `tests/README.md` is created. Contents: the three-way decision rule, the
  `ProjectFixture` API, the test-style guidance, and a table mapping each
  workflow stage file (`test_00_…` … `test_18_…`) to the user-facing
  command(s) it covers.

## Delivery: waves on a single branch

The work happens on one branch and lands as one PR. Internally it is broken
into five waves; each wave's commits are atomic and bisectable, and each
wave ends with `uv run pytest -q` green.

### Wave A — Foundation

1. Create directory skeletons: `tests/e2e/`, `tests/integration/`,
   `tests/unit/`, `tests/unit/sources/`, `tests/unit/destinations/`,
   `tests/unit/commands/`, each with `__init__.py`.
2. Create `tests/e2e/conftest.py` with `ProjectFixture`, `project`, `cli`.
3. Create `tests/e2e/test_fixture_smoke.py` exercising each public method
   of `ProjectFixture` and `cli('--help')`.
4. Port gap #1 → `tests/e2e/test_11_path_resolution.py`.
5. Port gap #2 + gap #4 → `tests/e2e/test_02_validate.py`.
6. Port gap #3 → `tests/e2e/test_10_error_handling.py` (uses
   `subprocess.run`, not `CliRunner`).
7. Port gap #5 → `tests/e2e/test_18_sources_e2e.py`.
8. Create `tests/README.md` (decision rule + `ProjectFixture` API).
9. Create the empty coverage-map file with the table header.

End of Wave A: bash script still exists; existing 46 files are untouched;
`uv run pytest -q` shows ~5 more tests than before Wave A (the gap tests).

### Wave B — Migrate e2e

For each existing file below, the migration task is: read the file,
identify which tests are e2e (uses `CliRunner` or spawns `feather`), move
them to the appropriate `tests/e2e/test_0X_*.py` file (creating it if
needed), refactor to use `project`/`cli`, run `uv run pytest -q`, commit.

Files migrated (or split) in Wave B:

- `tests/commands/test_init.py` → `tests/e2e/test_01_scaffold.py`
- `tests/commands/test_validate.py` → `tests/e2e/test_02_validate.py`
- `tests/commands/test_discover.py` + `tests/commands/test_discover_multi_source.py` → `tests/e2e/test_03_discover.py`
- `tests/commands/test_setup.py` + `tests/commands/test_run.py` → `tests/e2e/test_04_extract_full.py`
- `tests/commands/test_status.py` → `tests/e2e/test_14_status.py`
- `tests/commands/test_history.py` → `tests/e2e/test_15_history.py`
- `tests/commands/test_view.py` → `tests/e2e/test_16_view.py`
- `tests/commands/test_cache.py` → `tests/e2e/test_12_cache.py`
- `tests/commands/test_multi_source_guard.py` → `tests/e2e/test_13_multi_source.py`
- `tests/test_e2e.py` → `tests/e2e/test_04_extract_full.py` (merge)
- `tests/test_multi_source_e2e.py` → `tests/e2e/test_13_multi_source.py` (merge)
- `tests/test_json_output.py` → `tests/e2e/test_17_json_output.py`
- `tests/test_cli_structure.py` → `tests/e2e/test_00_cli_structure.py`
- `tests/test_explicit_name_flag.py` → `tests/e2e/test_03_discover.py` (merge)
- `tests/test_integration.py` (e2e portions only — `TestSampleErpFullPipeline`, `TestCsvFullPipeline`, `TestSqliteFullPipeline`, `TestValidationGuards`) → split into `tests/e2e/test_04_extract_full.py` + `tests/e2e/test_02_validate.py` + `tests/e2e/test_18_sources_e2e.py`
- `tests/test_transforms.py` (e2e portions — `TestE2ETransformPipeline`, `TestCLISetupTransforms`) → `tests/e2e/test_07_transforms.py`

End of Wave B: `tests/commands/` directory removed; the listed flat files
either deleted (if fully migrated) or reduced to their non-e2e portions.
`uv run pytest -q` green.

### Wave C — Migrate integration

For each existing file, identify integration-level tests (multi-module
Python-API, not CLI), move into `tests/integration/test_<feature>.py`,
delete from origin file when fully drained.

Files migrated (or split) in Wave C:

- `tests/test_incremental.py` → `tests/integration/test_incremental.py`
- `tests/test_schema_drift.py` → `tests/integration/test_schema_drift.py`
- `tests/test_dedup.py` → `tests/integration/test_dedup.py`
- `tests/test_boundary_dedup.py` → `tests/integration/test_change_detection.py` (or its own file if size warrants)
- `tests/test_append.py` → `tests/integration/test_append.py`
- `tests/test_retry.py` → split: integration parts → `tests/integration/test_retry.py`; unit parts deferred to Wave D
- `tests/test_curation_config_integration.py` → `tests/integration/test_curation_pipeline.py`
- `tests/test_pipeline.py` → `tests/integration/test_pipeline.py`
- `tests/test_csv_glob.py` → split: integration (full glob pipeline) → `tests/integration/test_change_detection.py`; unit (CSV parsing) deferred to Wave D
- `tests/test_transforms.py` (integration portions — `TestExecuteTransforms`, `TestRebuildMaterializedGold`, `TestPipelineTransformRebuild`) → `tests/integration/test_transforms.py`
- `tests/test_integration.py` (integration portions — `TestErrorIsolation`, `TestPipelineReturnsOnFailure`, `TestKnownBugs` if integration-level) → `tests/integration/test_error_isolation.py` + appropriate file
- `tests/test_dq.py` (integration portions) → `tests/integration/test_dq.py`
- `tests/test_cache.py` (integration portions) → `tests/integration/test_cache.py`
- `tests/test_alerts.py` (integration portions if any) → `tests/integration/test_alerts.py`

End of Wave C: cross-cutting feature files moved or substantially drained.
`uv run pytest -q` green.

### Wave D — Migrate unit

Move what's left into `tests/unit/`, mirroring `src/feather_etl/`.

Files migrated (or split) in Wave D:

- `tests/test_config.py` → `tests/unit/test_config.py`
- `tests/test_state.py` → `tests/unit/test_state.py`
- `tests/test_curation.py` → `tests/unit/test_curation.py`
- `tests/test_destinations.py` → `tests/unit/destinations/test_duckdb.py`
- `tests/test_discover_state.py` → `tests/unit/test_discover_state.py`
- `tests/test_discover_io.py` → `tests/unit/test_discover_io.py`
- `tests/test_discover_expansion.py` + `tests/test_expand_db_sources.py` → `tests/unit/sources/test_expand.py` (consolidate)
- `tests/test_sources.py` → split into `tests/unit/sources/test_registry.py`, `tests/unit/sources/test_protocol.py`, `tests/unit/sources/test_file_source.py`, `tests/unit/sources/test_database_source.py`
- `tests/test_postgres.py` → `tests/unit/sources/test_postgres.py`
- `tests/test_mysql.py` → `tests/unit/sources/test_mysql.py`
- `tests/test_sqlserver.py` → `tests/unit/sources/test_sqlserver.py`
- `tests/test_excel.py` → `tests/unit/sources/test_excel.py`
- `tests/test_json.py` → `tests/unit/sources/test_json.py`
- `tests/test_csv_glob.py` (unit remainder) → `tests/unit/sources/test_csv.py`
- `tests/test_mode.py` → `tests/unit/test_mode.py` (or split if it touches multiple modules)
- `tests/test_viewer_server.py` → `tests/unit/test_viewer_server.py`
- `tests/test_retry.py` (unit remainder) → `tests/unit/test_retry.py` (or merge into `tests/unit/test_state.py` if all about StateManager)
- `tests/test_transforms.py` (unit remainder — `TestParseTransformFile`, `TestDiscoverTransforms`, `TestBuildExecutionOrder`) → `tests/unit/test_transforms.py`
- `tests/test_dq.py`, `tests/test_cache.py`, `tests/test_alerts.py` (unit remainders) → `tests/unit/test_dq.py`, `tests/unit/test_cache.py`, `tests/unit/test_alerts.py`

End of Wave D: zero flat `test_*.py` files under `tests/`. Tree contains
only `tests/e2e/`, `tests/integration/`, `tests/unit/`, `tests/fixtures/`,
`tests/conftest.py`, `tests/helpers.py`, `tests/README.md`.

### Wave E — Coverage proof, deletion, doc updates

1. Complete the coverage-map document — every numbered bash check has a
   non-empty pytest test path. Run `bash scripts/hands_on_test.sh` one last
   time, confirm 61/61 PASS, run `uv run pytest -q`, confirm green.
2. Delete `scripts/hands_on_test.sh`.
3. Update `CLAUDE.md` (remove bash line; correct test count).
4. Update `docs/CONTRIBUTING.md` (rewrite items 4 + 5 of "Rules for the
   fixing agent"; replace `### scripts/hands_on_test.sh` subsection with
   `### tests/e2e/`; remove all other `hands_on_test` references).
5. Final `uv run pytest -q` green; final grep for `hands_on_test` returns
   nothing in active docs (only specs/plans/reviews).

## Per-task discipline

Every task that moves or splits a test file follows this protocol:

1. Read the source file. Categorize each test (e2e / integration / unit)
   per the rule.
2. For each test:
   - if e2e and the destination file does not yet exist, create it with a
     module docstring explaining the workflow stage;
   - if e2e, refactor to use `project`/`cli`;
   - if integration or unit, leave the test largely as-is (only fix imports
     and adopt `ProjectFixture` if trivially better).
3. Use `git mv` when moving a whole file unchanged so blame is preserved.
   For split moves, copy + delete in separate commits is acceptable.
4. Add a one-line comment at the top of the new file: `# Migrated from
   tests/<old_path>.py` (per migration; can be removed after Wave E).
5. Run `uv run pytest -q`. Must be green.
6. Commit with format: `test(<wave-letter>): migrate <old_path> -> <new_path>`.

## Risks and mitigations

- **`ProjectFixture` API turns out wrong-shape mid-migration.** This is the
  reason migration is in the same logical unit as foundation. If a Wave B/C
  file needs a method we don't have, we add it to `ProjectFixture` (atomic
  commit), refactor only the affected tests, continue. No "Phase 2 found
  problems with Phase 1" gap.
- **Splitting large mixed files (`test_integration.py`,
  `test_transforms.py`) introduces subtle behavior changes.** Mitigation:
  per-task discipline keeps each split atomic; class-level fixtures are
  preserved when classes survive; `uv run pytest -q` green is the gate
  before commit.
- **Test count drifts from claims in `CLAUDE.md`.** Mitigation: Wave E
  recomputes and rewrites the count; do not hardcode counts elsewhere.
- **Bash script deletion before coverage map is honest.** Mitigation: Wave E
  ordering — coverage map must be 100% complete with non-empty pytest paths
  before `rm scripts/hands_on_test.sh` commit.
- **Long-running branch accumulates merge conflicts.** Mitigation: rebase
  on main after each wave. Test files rarely conflict with `src/` work, so
  conflicts should be limited.

## Done signal

A reviewer or future agent can confirm "this is done" by running these
commands and seeing the matching outputs:

```bash
# 1. All tests pass (existing count + 5 new gap tests, minus any consolidated
#    duplicates revealed during migration). Run before deletion of bash script
#    AND after, both green.
uv run pytest -q

# 2. The bash script is gone
test ! -f scripts/hands_on_test.sh && echo OK

# 3. No flat test files remain at tests/ root (only conftest.py, helpers.py,
#    README.md, and the e2e/integration/unit/fixtures directories)
ls tests/test_*.py 2>/dev/null | wc -l   # expected: 0

# 4. tests/commands/ is gone
test ! -d tests/commands && echo OK

# 5. The new layout exists and is non-empty
test -d tests/e2e && test -d tests/integration && test -d tests/unit && echo OK
ls tests/e2e/test_*.py tests/integration/test_*.py tests/unit/test_*.py | wc -l
# expected: many

# 6. No active doc references the deleted script
grep -rn "hands_on_test" CLAUDE.md docs/CONTRIBUTING.md README.md \
  | grep -v "docs/superpowers/specs/" \
  | grep -v "docs/plans/" \
  | grep -v "docs/reviews/"
# expected: no output

# 7. The coverage map is complete
grep -c "^| S" docs/superpowers/specs/2026-04-19-test-restructure-coverage-map.md
# expected: 61 (one row per bash check)
grep -E "^\| S[^|]+\|[^|]+\|\s*\|" docs/superpowers/specs/2026-04-19-test-restructure-coverage-map.md
# expected: no output (no row with empty pytest path)
```

If all seven pass, the migration is complete and the issue can be closed.

## Open questions

None. All design choices are committed (Strategy B three-layer; flat
function style by default; minimal `ProjectFixture`; one PR; coverage-map
gate before deletion).
