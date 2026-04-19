# `feather cache` — dev-ergonomic local bronze cache

Created: 2026-04-19
Status: DRAFT
Issue: [#15](https://github.com/siraj-samsudeen/feather-etl/issues/15)

---

## 1. Problem

During active development against client ERPs, every round-trip to the source
database is slow, VPN-gated, and sometimes rate-sensitive. The PRD (§499)
already describes the intended workflow: pull a local bronze copy once, then
iterate on silver/gold transforms offline.

Today the only command that pulls source data is `feather run`. It is a
production pipeline: it requires curation entries to carry `strategy`,
`primary_key`, and `timestamp_column`, runs DQ checks, rebuilds transforms, and
shares state with production runs. Operators doing exploratory dev work feel
the weight of that ceremony on every iteration.

`feather cache` is a narrow dev-only command that does exactly one thing: pull
curated source tables into `bronze.*` with minimum ceremony, skipping unchanged
sources on re-run, and never touching production state.

## 2. Scope

**In**

- New `feather cache` command — pulls curated tables into `bronze.<source_db>_<alias>` using full-strategy extraction against all columns.
- Per-table change detection via existing `Source.detect_changes()`. Cache-isolated watermarks prevent any state shared with `feather run`.
- `--table` and `--source` comma-separated selectors; intersect when both are given.
- `--refresh` forces re-pull, ignoring change detection.
- Hard error when the effective mode is `prod` (via `feather.yaml`, `FEATHER_MODE`, or `--mode`).
- Grouped-by-source human output with failures expanded; no per-table success noise.
- Docs: `README.md` CLI section + `docs/prd.md` §499. `CLAUDE.md` test-count bump after new pytest tests land.

**Out**

- No fallback when `discovery/curation.json` is missing. `feather cache` errors with the same guidance `feather run` gives today.
- No transforms — cache never creates or materializes silver/gold. First-time users run `feather run` or `feather setup` separately to build views.
- No cache run history — `_cache_runs` table, `record_cache_run`, and `feather history --trigger cache` are not part of this work. Only a `_cache_watermarks` table is added.
- No DQ checks, no schema-drift handling, no overlap windows, no retry backoff, no boundary dedup, no column filtering — cache is full-strategy, all-columns, single path.
- No `--yes`, `--json`, `--verbose` flags.
- No refactor of other command modules. The thin-CLI pattern sweep (including `commands/discover.py`) is a separate follow-up issue.
- No changes to `scripts/hands_on_test.sh`. The shell script's deletion and test-migration plan lives in [#40](https://github.com/siraj-samsudeen/feather-etl/issues/40) and is sequenced independently of this work.
- No MotherDuck sync; no per-table cache strategy override.

## 3. Summary of decisions

| Area | Decision | Rationale |
|---|---|---|
| Command name | `feather cache` | `snapshot` already has three conflicting meanings in the codebase (schema snapshots, Kimball fact snapshots, full-strategy "swap a snapshot"). `cache` names the purpose precisely. |
| Target | `bronze.<source_db>_<alias>` | Same layer and naming as `feather run --mode dev`. Cache writes are indistinguishable from dev-run writes at the data level. |
| Strategy | Always `full` (drop + recreate) | Cache is a snapshot. Full-strategy handles added columns implicitly (recreate picks up new shape), so schema drift needs no extra code. |
| Curation requirements | `source_db` + `source_table` + `target_table` only | `strategy`, `primary_key`, `timestamp_column`, `schedule` are irrelevant for cache. The existing curation loader already treats these as optional. |
| Mode | Always `dev` internally; hard error when effective mode is `prod` | Cache is a dev tool by definition. Silent overrides confuse. |
| State isolation | New `_cache_watermarks` table, sibling methods on `StateManager` (not a scope flag) | Isolation guaranteed by the API surface — `run_cache` only calls `*_cache_*` methods, so there is no code path from cache to production tables. |
| Re-run semantics | Skip sources whose `Source.detect_changes()` returns unchanged; `--refresh` forces re-pull | Reuses existing per-source change detection (file mtime+hash, CHECKSUM_AGG, md5(row_to_json), etc.). No new fingerprint logic. |
| Selector grain | `--source` filters by `source_db` (curation field), not YAML source `name` | Matches the user mental model ("I want the afans tables") and works naturally for multi-db sources like MySQL with `databases: [afans, nimbalyst, ...]`. |
| No-curation behaviour | Error with guidance | Keeps the command narrow. The "auto-run discover" idea added non-trivial coupling for a minor convenience. |
| Human output | Grouped by `source_db`; failures expanded; no per-table success lines | Fallback pulls could be 100+ tables; per-table logging becomes a wall of text. |
| Transforms | Never run from cache | User explicitly chose this. First-run users must run `feather run` or `feather setup` to get silver views. Documented in README. |

## 4. User-facing contract

### CLI surface

```
feather cache                                  # all curated tables, skip unchanged
feather cache --table sales,customer           # comma-separated, by bronze name
feather cache --source afans,nimbalyst         # comma-separated, by source_db
feather cache --table sales --source afans     # intersect
feather cache --refresh                        # force re-pull of all tables
feather cache --refresh --table sales          # force re-pull of specific tables
feather cache --config feather.yaml            # shared config flag
```

Exit codes:

- `0` — all tables succeeded (including all-skipped).
- `1` — one or more tables failed. Successes still committed.
- `2` — config error, prod mode, missing `curation.json`, or unknown selector value.

### Workflow resolution (exact order)

1. Load `feather.yaml` with `_load_and_validate` (no `mode_override` — `feather cache` does not accept a `--mode` flag). Reject if the effective mode is `prod` (YAML `mode: prod` or `FEATHER_MODE=prod`) — exit 2 with:
   > `feather cache is a dev-only tool. Remove 'mode: prod' or unset FEATHER_MODE=prod to use it.`
2. Load curated tables via existing `curation.load_curation_tables()`. Missing `curation.json` → exit 2 with the same error message `feather run` gives today.
3. Resolve `--table` and `--source` filters:
   - `--table` matches on `TableConfig.name` (the sanitized bronze name).
   - `--source` matches on `TableConfig.database` (equivalent to `source_db` in curation).
   - If both are given, intersect.
   - Any unknown value → exit 2 listing valid options.
4. Call `run_cache(config, resolved_tables, working_dir, refresh=<flag>)`.
5. Format grouped output per § 4.3. Exit 0 if all results are `success` or `cached`; exit 1 otherwise.

### Human output

```
Mode: dev (cache)
  afans        (duckdb-erp):   3 extracted, 1 cached
  nimbalyst    (mysql-primary): 2 extracted, 2 failed
    ✗ invoice — connection reset by peer
    ✗ journal — permission denied on ERP.dbo.journal

8 tables: 5 extracted, 1 cached, 2 failed.
```

Rules:

- One line per `source_db`, prefixed with source `name` in parens.
- Counts: `extracted` (`status=='success'`), `cached` (`status=='cached'`), `failed` (`status=='failure'`). Zero-count labels are omitted.
- Failures listed beneath the group line, one per row, as `  ✗ <bronze_name> — <error>`. Error message is the first line of `error_message`, truncated to 120 chars.
- Terminal summary line sums across all groups.
- The word `cached` replaces the usual `skipped (unchanged)` terminology. `feather run` continues to say `skipped`.

### State shape

One new table in `feather_state.duckdb`:

```sql
CREATE TABLE IF NOT EXISTS _cache_watermarks (
    table_name       VARCHAR PRIMARY KEY,   -- bronze name, e.g. "afans_sales"
    source_db        VARCHAR,
    last_file_mtime  DOUBLE,
    last_file_hash   VARCHAR,
    last_checksum    VARCHAR,                -- DB-source fingerprint (CHECKSUM_AGG / md5 / row_count)
    last_row_count   INTEGER,
    last_run_at      TIMESTAMP
);
```

- Created by `StateManager.init_state()` with `CREATE TABLE IF NOT EXISTS`. Pre-existing state DBs auto-upgrade on first use.
- No schema-version bump — purely additive.
- `_watermarks` and `_runs` are untouched by anything in this work.

### Interaction with `feather run`

Both commands write to the same physical bronze tables. `feather run --mode dev` followed by `feather cache` — or the reverse — leaves `bronze.<name>` as whatever the last command produced. This is acceptable because:

- Both produce the same thing: full-strategy, all-columns dev bronze.
- Watermarks are fully isolated: `feather run` reads/writes `_watermarks`; `feather cache` reads/writes `_cache_watermarks`. Neither command can short-circuit based on the other's state.

## 5. Integration surface

### New files

| File | Purpose | Approx size |
|---|---|---|
| `src/feather_etl/cache.py` | `run_cache()` orchestrator. Loop: resolve source → detect changes → extract all columns → load_full → write cache watermark. | ~120 LOC |
| `src/feather_etl/commands/cache.py` | Typer command. Flag parsing, mode guard, selector resolution, dispatch, grouped output. | ~120 LOC |
| `tests/test_cache_command.py` | CLI-level tests (selectors, prod-mode rejection, exit codes, output format). | ~250 LOC |
| `tests/test_cache_orchestrator.py` | `run_cache` unit tests (state isolation, skip/refresh, partial failure). | ~200 LOC |

### Files that change

| File | Change | Risk |
|---|---|---|
| `src/feather_etl/state.py` | Add `_cache_watermarks` DDL to `init_state()`. Add `read_cache_watermark` + `write_cache_watermark` methods. Existing methods untouched. | Low — additive |
| `src/feather_etl/cli.py` | Import + `register_cache(app)`. | Low |
| `CLAUDE.md` | Bump `uv run pytest -q` count to final total after new cache tests land. | Low |
| `README.md` | Add "Dev cache" subsection to the CLI reference with examples from § 4.1. | Low |
| `docs/prd.md` | §499 — add a sentence: *"The canonical command for this workflow is `feather cache`."* | Low |

### Files explicitly NOT touched

- `pipeline.py` — `run_all`, `run_table`, and all helpers. Cache is a separate module.
- `curation.py` — reused as-is (`load_curation_tables`, `resolve_source`, `_sanitize_bronze_name`).
- `config.py` — reused as-is (`load_config` with default `validate=True`).
- All source modules — reused via the `Source` protocol (`detect_changes`, `extract`).
- `commands/discover.py`, `commands/run.py`, `commands/setup.py`, etc. — untouched. Thin-CLI refactor is a separate follow-up.
- `commands/history.py` — no `--trigger` flag, no cache history.
- `scripts/hands_on_test.sh` — its lifecycle is tracked in [#40](https://github.com/siraj-samsudeen/feather-etl/issues/40).
- `.claude/rules/feather-etl-project.md`, `docs/CONTRIBUTING.md` — reference removals happen in [#40](https://github.com/siraj-samsudeen/feather-etl/issues/40) as part of the script retirement.

### StateManager API shape

```python
# Existing (unchanged)
state.read_watermark(table_name)          -> dict | None
state.write_watermark(table_name, ...)
state.record_run(run_id, ...)
state.get_history(table_name, limit)      -> list[dict]

# New — cache-scoped siblings. No scope parameter.
state.read_cache_watermark(table_name)    -> dict | None
state.write_cache_watermark(
    table_name: str,
    source_db: str,
    last_run_at: datetime,
    last_file_mtime: float | None = None,
    last_file_hash: str | None = None,
    last_checksum: str | None = None,
    last_row_count: int | None = None,
) -> None
```

`run_cache` only ever calls `read_cache_watermark` / `write_cache_watermark`. There is no code path from `run_cache` to the production tables.

### `run_cache` signature

```python
# src/feather_etl/cache.py

@dataclass
class CacheResult:
    table_name: str
    source_db: str
    status: str              # "success" | "cached" | "failure"
    rows_loaded: int = 0
    error_message: str | None = None

def run_cache(
    config: FeatherConfig,
    tables: list[TableConfig],
    working_dir: Path,
    refresh: bool = False,
) -> list[CacheResult]:
    """Pull curated tables into bronze. Dev-only. No transforms, no DQ, no drift."""
```

Per-table loop (pseudocode):

```
state = StateManager(working_dir / "feather_state.duckdb")
state.init_state()
dest = DuckDBDestination(path=config.destination.path)
dest.setup_schemas()              # ensure bronze/silver/gold schemas exist

for table in tables:
    source = resolve_source(table.database, config.sources)
    wm = state.read_cache_watermark(table.name)
    change = source.detect_changes(table.source_table, last_state=wm)
    if not change.changed and not refresh:
        record CacheResult(status="cached")
        continue
    try:
        data = source.extract(table.source_table)     # all columns, no filter
        rows = dest.load_full(f"bronze.{table.name}", data, run_id)
        state.write_cache_watermark(
            table.name,
            source_db=table.database,
            last_run_at=now,
            last_file_mtime=change.metadata.get("file_mtime"),
            last_file_hash=change.metadata.get("file_hash"),
            last_checksum=change.metadata.get("checksum"),
            last_row_count=change.metadata.get("row_count"),
        )
        record CacheResult(status="success", rows_loaded=rows)
    except Exception as e:
        record CacheResult(status="failure", error_message=str(e))
```

No retry backoff, no schema drift, no DQ, no transforms, no boundary hashes, no overlap, no column mapping. One pass per table, nothing else.

## 6. Task breakdown

| # | Task | Why / Risk | Key tests |
|---|---|---|---|
| 1 | Add `_cache_watermarks` table to `StateManager.init_state()` | Backing table must exist before methods that use it. | `test_init_state_creates_cache_watermarks`; idempotent; prod tables still created |
| 2 | Add `read_cache_watermark` + `write_cache_watermark` to `StateManager` | Sibling API that isolates cache from prod. | Round-trip; `test_write_cache_watermark_does_not_touch_watermarks` |
| 3 | Build `cache.run_cache()` orchestrator | Core of the command. | `writes_bronze_all_columns`; `writes_only_to_cache_state`; `skips_unchanged_on_second_run`; `refresh_forces_repull`; `partial_failure_returns_failure_result_and_continues` |
| 4 | Build `commands/cache.py` CLI | User-facing entry point. | `rejects_prod_mode`; `errors_when_curation_missing`; `selector_table_filter`; `selector_source_filter`; `selector_intersect`; `unknown_table_errors_with_valid_list`; `unknown_source_errors_with_valid_list`; `refresh_flag_propagates`; `grouped_output_format` |
| 5 | Register `cache` in `cli.py` | Wire the command. | `feather --help` lists `cache`; `feather cache --help` renders |
| 6 | Docs — `README.md`, `docs/prd.md` §499, `CLAUDE.md` test-count bump | Ship usable documentation alongside the feature. | Manual review against live CLI help |
| 7 | (post-merge, non-code) File follow-up GH issue | Capture deferred thin-CLI work. | Thin-CLI refactor for all 8 command modules, matching the `commands/run.py` ↔ `pipeline.py` pattern. |

### Dependency chain

```
Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6
Task 7 — post-merge, not a code task
```

Recommended commit order: `1, 2, 3, 4, 5, 6`, each its own atomic commit on the feature branch.

## 7. Done signal

From a project with one DuckDB file + one CSV source and three tables marked `include` in `discovery/curation.json`:

```bash
# First run — cold cache
uv run feather cache
#   Mode: dev (cache)
#     afans        (duckdb-erp):   2 extracted
#     csv-data     (csv-dir):      1 extracted
#   3 tables: 3 extracted.

# Second run — smart skip
uv run feather cache
#   Mode: dev (cache)
#     afans        (duckdb-erp):   2 cached
#     csv-data     (csv-dir):      1 cached
#   3 tables: 3 cached.

# Forced re-pull of one table
uv run feather cache --refresh --table afans_sales
#   Mode: dev (cache)
#     afans        (duckdb-erp):   1 extracted
#   1 table: 1 extracted.

# State isolation proof
duckdb feather_state.duckdb "SELECT COUNT(*) FROM _watermarks"         # 0 (no prod run has happened)
duckdb feather_state.duckdb "SELECT COUNT(*) FROM _cache_watermarks"   # 3

# Prod-mode guard
FEATHER_MODE=prod uv run feather cache
#   feather cache is a dev-only tool. Remove 'mode: prod' or unset
#   FEATHER_MODE=prod to use it.
#   exit 2

# Missing curation guard
rm discovery/curation.json
uv run feather cache
#   discovery/curation.json not found ...  Run 'feather discover' ...
#   exit 2

# Full test suite green
uv run pytest -q
```

## 8. Related and follow-up issues

- [#40 — Replace `scripts/hands_on_test.sh` with pytest E2E tests](https://github.com/siraj-samsudeen/feather-etl/issues/40) — already open. The cache work does not touch the shell script; #40 owns its retirement and the pytest E2E restructure.
- **Thin-CLI pattern sweep** (to be filed after this merges) — refactor `commands/run.py`, `setup.py`, `status.py`, `validate.py`, `init.py`, `history.py`, `view.py`, and `discover.py` so each is a thin Typer wrapper over a top-level core module, matching the pattern `commands/run.py` already follows with `pipeline.py`.
