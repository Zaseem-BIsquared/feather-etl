# Multi-source `discover` — design

**Issue:** [#8 Support multiple sources per project](https://github.com/siraj-samsudeen/feather-etl/issues/8)
**Status:** Design approved, ready for implementation planning
**Date:** 2026-04-14

---

## 1. Problem

`feather.yaml` currently supports one source per project. A real client deployment needs multiple sources — e.g., a SQL Server ERP alongside CSV exports and Excel spreadsheets — feeding one DuckDB destination. The immediate operational driver is a SQL Server host with **multiple databases** on the same server; today `feather discover` can only target one database at a time, forcing users to rewrite `feather.yaml` repeatedly to enumerate schemas.

A secondary concern surfaced during design: if `discover` iterates ten databases and two fail (permissions, transient errors), re-running from scratch wastes time and re-queries eight already-good sources. The command needs **resumable** semantics.

A third concern, explicitly raised: per-source-type knowledge is spread across `config.py`, `registry.py`, and each source class. This is overdue for a cleanup — each concern should live in one place.

---

## 2. Scope

This slice delivers **config-schema multi-source** (issue #8's YAML design) but only **`feather discover` iterates multiple sources**. `run`, `validate`, `setup`, `status`, `history`, `init` continue to operate as single-source until a later slice.

**Rationale:** the schema change is the expensive migration (every fixture, every doc, every user's config). The pipeline rewire (tables pinned to specific sources, state watermarks per-source-table) is orthogonal and much larger. Shipping the schema now means users never have to rewrite their YAML a second time when the pipeline rewire lands.

---

## 3. Summary of decisions

| Area | Decision |
|------|----------|
| YAML schema | `sources:` list (required, non-empty); singular `source:` is a hard migration error |
| SQL Server / Postgres multi-DB | `database` XOR `databases: [...]` XOR neither-means-auto-enumerate |
| Source name | Derived from type+host/path when `len(sources) == 1`; required and unique when `> 1` |
| `tables[].source` field | Deferred (shipped when `run` iterates sources) |
| Source class refactor | C2: delete `SourceConfig`, each `Source` subclass self-describes via `from_yaml` |
| Registry | Lazy import via string paths; closes issue #4 as a side effect |
| Discover failure handling | One source's failure does not abort the whole run; exit 2 after all attempted |
| Discover permission error (E1) | Empty enumeration → error with remediation hint, not silent fallback |
| Discover `--json` mode | Dropped (no-op today; discover always writes files per #16) |
| Discover retry semantics (D1) | Resume by default: cached sources skipped, failed retried, new discovered |
| Add/remove detection (AD2) | Detect both; removed entries marked in state, cleaned with `--prune` |
| Flags | `--refresh`, `--retry-failed`, `--prune` (no `--yes`; scope of damage is recoverable) |
| Backward compatibility (BC1) | Hard migration; `source:` singular raises clear error |
| Testing (T1) | Per-code-unit edge-case tests in existing files + one new happy-path E2E file |

---

## 4. YAML schema

### 4.1 Final shape

```yaml
sources:
  - name: erp                # required when len > 1, optional when len == 1
    type: sqlserver
    host: ${DB_HOST}
    port: ${DB_PORT}         # optional: defaults to 1433 (sqlserver) / 5432 (postgres)
    user: ${DB_USER}
    password: ${DB_PASSWORD}
    # database: SALES        # single-database mode (today's behaviour)
    # databases: [A, B]      # explicit multi-database list
    # both omitted           # discover enumerates sys.databases automatically

  - name: spreadsheets
    type: csv
    path: ./data/csv/

  - name: local_sqlite
    type: sqlite
    path: ./data/erp.sqlite

destination:
  path: ./feather_data.duckdb

tables:
  - name: invoices
    source_table: icube.SALESINVOICE
    target_table: bronze.invoices
    strategy: full
    # source: erp            # NOT added in this slice — see deferrals D1, D2
```

### 4.2 Parse rules

1. `sources:` is required and must be a non-empty list.
2. Singular `source:` at the top level raises `ValueError` with exact text:
   > `feather.yaml now uses 'sources:' (list). Wrap your existing source in a list:`
   > `  sources:`
   > `    - name: ...`
   > `      type: ...`
3. `name` is resolved per entry:
   - If the list has exactly **one** entry and `name` is omitted → derive via existing `resolved_source_name()` (type+host/path).
   - If the list has **more than one** entry → `name` is required on every entry.
   - Names must be unique across the list. Duplicates raise `ValueError` citing the offending name.
4. SQL Server / Postgres `database` / `databases` rules:
   - `database: X` and `databases: [...]` in the same entry → error: *"database and databases are mutually exclusive; use one."*
   - Neither → auto-enumerate during `discover` (see §6).
   - `databases: []` (empty list) → error: *"databases list must be non-empty."*
5. File sources (`csv`, `duckdb`, `sqlite`, `excel`, `json`) accept `path` only; adding `database`/`databases` raises *"field not supported for source type X."*

### 4.3 Multi-source guard for non-discover commands

`run`, `validate`, `setup`, `status`, `history`, `init`: if `len(cfg.sources) > 1`, exit code 2 with message:
> *"Command X is single-source for now (issue #8). Use `feather discover` to enumerate multi-source schemas, or split into one feather.yaml per source for non-discover operations."*

When `len(cfg.sources) == 1`, these commands behave identically to today.

---

## 5. Source class self-description (C2 refactor)

### 5.1 Goal

Each `Source` subclass becomes the single place that knows its own YAML shape, validation rules, and connection construction. `config.py` shrinks to a thin YAML dispatcher. `registry.py` becomes a lazy type→class map.

### 5.2 Protocol additions

```python
# src/feather_etl/sources/__init__.py
class Source(Protocol):
    name: str                            # resolved display name
    type: ClassVar[str]                  # e.g. "sqlserver"

    @classmethod
    def from_yaml(cls, entry: dict, config_dir: Path) -> "Source":
        """Parse one `sources:` list entry and return a configured instance.

        All per-type rules live here: port defaults, conn-string template,
        path resolution, database/databases XOR validation.
        Side-effect free — does not open connections.
        """

    def validate_source_table(self, source_table: str) -> list[str]:
        """Return list of error messages for this source_table string.
        Each source class decides its own identifier rules."""

    # ... existing runtime methods unchanged: check, discover, extract, etc. ...
```

### 5.3 Example — SqlServerSource

```python
class SqlServerSource(DatabaseSource):
    type: ClassVar[str] = "sqlserver"

    def __init__(self, *, name: str, host: str, port: int = 1433,
                 user: str, password: str,
                 database: str | None = None,
                 databases: list[str] | None = None,
                 connection_string: str | None = None,
                 batch_size: int = 120_000) -> None:
        ...

    @classmethod
    def from_yaml(cls, entry: dict, config_dir: Path) -> "SqlServerSource":
        # Owns: port default, conn-string template, database XOR databases,
        # empty-list check, connection_string override logic.
        ...

    def list_databases(self) -> list[str]:
        """Query sys.databases, skipping system DBs (master, tempdb, model, msdb)."""
        ...

    def validate_source_table(self, source_table: str) -> list[str]:
        # SQL Server accepts 'schema.table' or plain 'table'; lenient rules.
        ...
```

### 5.4 What leaves `config.py`

- `DB_CONNECTION_BUILDERS` dict (lines 65-74) → distributed to each DB source's `from_yaml`.
- Per-type `source_table` validation branches (lines 289-313) → each source's `validate_source_table`.
- `FILE_SOURCE_TYPES` constant → replaced by class-level `requires_path: ClassVar[bool]` attribute or similar.
- `path.exists()` / `is_dir()` checks (lines 220-227) → each file source's `from_yaml` or `__init__`.

### 5.5 What `registry.py` becomes

```python
SOURCE_CLASSES: dict[str, str] = {
    "duckdb":    "feather_etl.sources.duckdb_file.DuckDBFileSource",
    "csv":       "feather_etl.sources.csv.CsvSource",
    "sqlite":    "feather_etl.sources.sqlite.SqliteSource",
    "sqlserver": "feather_etl.sources.sqlserver.SqlServerSource",
    "postgres":  "feather_etl.sources.postgres.PostgresSource",
    "excel":     "feather_etl.sources.excel.ExcelSource",
    "json":      "feather_etl.sources.json_source.JsonSource",
}

def get_source_class(type_name: str) -> type[Source]:
    """Lazy import — only loads the module when that type is used.
    Closes issue #4 (optional DB connectors)."""
    if type_name not in SOURCE_CLASSES:
        raise ValueError(...)
    module_path, cls_name = SOURCE_CLASSES[type_name].rsplit(".", 1)
    return getattr(importlib.import_module(module_path), cls_name)
```

`create_source()` is deleted. Callers use `get_source_class(entry["type"]).from_yaml(entry, config_dir)`.

### 5.6 `FeatherConfig` shape

```python
@dataclass
class FeatherConfig:
    sources: list[Source]                # was: source: SourceConfig
    destination: DestinationConfig
    tables: list[TableConfig]
    defaults: DefaultsConfig = field(default_factory=DefaultsConfig)
    config_dir: Path = field(default_factory=lambda: Path("."))
    mode: str = "dev"
    alerts: AlertsConfig | None = None
```

`SourceConfig` the dataclass is deleted.

---

## 6. `discover` command behaviour

### 6.1 Execution

1. Load config → `cfg.sources: list[Source]`.
2. Read `feather_discover_state.json` if present (same directory as `feather.yaml`).
3. For each source in `cfg.sources`:
   - If it's a DB source (SQL Server / Postgres) with neither `database` nor `databases` configured → call `source.list_databases()` to auto-enumerate. Each enumerated database becomes a scoped child source (same host/credentials, one concrete database). Child source names are `<parent_name>__<database>` (double underscore so they're unambiguous and filesystem-safe).
   - `list_databases()` is defined only on DB source classes. File sources inherit a base `NotImplementedError` — the auto-enumerate branch is gated on source type, so this is unreachable in practice but explicit.
   - Compare enumeration to `state.auto_enumeration[<parent_source_name>]["databases_seen"]` to classify each child as **cached / new / removed / failed**. Keying on the parent source name (not host) avoids collisions when two sources point at the same host with different credentials.
4. Decide per-source action based on flag and state (see flag matrix §6.3).
5. For each source to be discovered: `check()`, then `discover()` → write `schema_<sanitised_name>.json`.
6. Rewrite state file at end with all attempts (ok / failed / removed).
7. Exit with code `0` if all successful or skipped, else `2`.

### 6.2 Output (resume run)

```
Discovering from feather.yaml (state file found, last run 2026-04-14 10:30)...
  [1/6] erp_sales      (cached, 42 tables)
  [2/6] erp_inventory  (cached, 18 tables)
  [3/6] erp_legacy     (retry)    → FAILED: Login failed for user 'feather' (28000)
  [4/6] erp_audit      (new)      → 12 tables → ./schema_erp_audit.json
  [5/6] erp_archive    (removed)  → database no longer on server
  [6/6] spreadsheets   (cached, 5 tables)

4 succeeded (3 cached, 1 new), 1 failed, 1 removed. Exit code: 2.

Retry the failure:
  feather discover --retry-failed

Clean up the removed entry (deletes ./schema_erp_archive.json):
  feather discover --prune
```

### 6.3 Flag matrix

| Flag | cached | failed | new | removed |
|------|--------|--------|-----|---------|
| *(none)* | skip | retry | discover | mark in state |
| `--refresh` | re-run | re-run | discover | mark in state |
| `--retry-failed` | skip | retry | skip | ignore |
| `--prune` | skip | skip | skip | delete state entry + delete orphaned JSON file |

No `--yes` flag. `--prune` deletes immediately; the action is recoverable via `--refresh`.

### 6.4 Failure handling

- One source's `check()` or `discover()` failure does **not** abort the whole run.
- Record the error verbatim in state (`status: failed`, `error: <message>`, `attempt_count: N+1`).
- Continue with remaining sources.
- Exit `2` if any source failed; exit `0` otherwise.

### 6.5 Permission errors (E1)

If SQL Server `list_databases()` returns an empty list or fails with an auth error:
- Write one `status: failed` entry per source that required enumeration.
- Error message includes the remediation hint:
  > *"Found 0 databases on host <H>. Either grant VIEW ANY DATABASE to this login, or specify `database:` / `databases: [...]` explicitly in feather.yaml."*

### 6.6 `--json` mode

Dropped as a separate code path. The per-source JSON files ARE the JSON output. Global `--json` flag remains honored by `run`/`validate`/etc. For `discover`, it becomes a no-op; optionally emit a one-line JSON summary (`{written: [paths], failed: [...]}`) to stdout so scripts can still capture the result set.

---

## 7. State file

### 7.1 Location

`<config_dir>/feather_discover_state.json` — same directory as `feather.yaml`.

### 7.2 Shape

```json
{
  "schema_version": 1,
  "last_run_at": "2026-04-14T10:30:00Z",
  "sources": {
    "erp_sales": {
      "type": "sqlserver",
      "host": "192.168.2.62",
      "database": "SALES",
      "status": "ok",
      "discovered_at": "2026-04-14T10:30:12Z",
      "table_count": 42,
      "output_path": "./schema_erp_sales.json"
    },
    "erp_legacy": {
      "type": "sqlserver",
      "host": "192.168.2.62",
      "database": "LEGACY",
      "status": "failed",
      "attempted_at": "2026-04-14T10:30:15Z",
      "error": "Login failed for user 'feather' (SQLSTATE 28000)",
      "attempt_count": 1
    },
    "erp_archive": {
      "type": "sqlserver",
      "host": "192.168.2.62",
      "database": "ARCHIVE",
      "status": "removed",
      "discovered_at": "2026-04-10T09:00:00Z",
      "removed_detected_at": "2026-04-14T10:30:20Z",
      "output_path": "./schema_erp_archive.json"
    }
  },
  "auto_enumeration": {
    "erp": {
      "type": "sqlserver",
      "host": "192.168.2.62",
      "last_enumerated_at": "2026-04-14T10:30:10Z",
      "databases_seen": ["SALES", "INVENTORY", "HR", "LEGACY", "ZAKYA"]
    }
  }
}
```

### 7.3 Status vocabulary

- `ok` — last discover succeeded, JSON file present on disk.
- `failed` — last attempt failed. Retriable via `--retry-failed` or default resume.
- `removed` — previously seen, no longer on server. Cleaned by `--prune`.

### 7.4 Schema versioning

`schema_version: 1`. If the shape needs to change later, `schema_version: 2` triggers a migration (deferred — D15).

---

## 8. Testing approach (T1)

### 8.1 Principle — tests track with module of origin

> **Tests track with their module of origin, not with the feature that motivated them.**

A "feature" is a moment-in-time concept (the PR shipping it). The module endures. Tests co-located with modules survive feature reorganizations; feature-based test files age into incoherent grab-bags and eventually get deleted (as `tests/test_cli.py` and `tests/test_table_filter_and_history.py` were in the #19 split).

**Practical rule:** when you edit `SqlServerSource`, you read `tests/test_sqlserver.py` and see every test that constrains your change. When you edit the discover command, you read `tests/commands/test_discover.py` and see every flag combo. Nothing surprises you from a file elsewhere.

**The one exception:** happy-path E2E tests stand alone as "how does a user actually use this end-to-end." These are few in number, slow, and workflow-oriented. They live in a dedicated file per workflow.

This principle is documented in `docs/CONTRIBUTING.md` as a project convention. Future PRs should not create feature-named test files (e.g., `test_multi_source.py`) — tests belong with the code they exercise.

### 8.2 New file — `tests/commands/test_discover_multi_source.py`

Happy-path E2E scenarios (approx. 7 tests):

1. `test_single_csv_source_writes_one_file`
2. `test_heterogeneous_sources_write_one_file_per_source` (csv + sqlite + duckdb)
3. `test_sqlserver_multiple_databases_explicit` (Postgres as stand-in via `pg_ctl`)
4. `test_sqlserver_auto_enumerate` (omit database/databases)
5. `test_resume_skips_cached_succeeds` (second run = all cached)
6. `test_retry_failed_only` (simulate one failure; `--retry-failed` retries only that one)
7. `test_prune_removes_orphaned_state_and_file`

### 8.3 Edge cases — in per-code-unit files

| Concern | File |
|---------|------|
| `source:` singular migration error | `tests/test_config.py` |
| `sources:` name uniqueness, derivation | `tests/test_config.py` |
| `database` XOR `databases` validation | `tests/test_config.py` |
| `SqlServerSource.from_yaml`, port default, conn-string | `tests/test_sqlserver.py` |
| `SqlServerSource.list_databases()` query and filter | `tests/test_sqlserver.py` |
| `PostgresSource.from_yaml`, `list_databases()` | `tests/test_postgres.py` |
| File source `from_yaml` (path resolution, existence) | `tests/test_csv_glob.py`, `test_excel.py`, `test_json.py`, `test_sources.py` |
| Lazy import via registry (closes #4) | `tests/test_sources.py` |
| State file read/write, resume/retry/prune logic | `tests/commands/test_discover.py` |
| Discover output formatting, summary line | `tests/commands/test_discover.py` |

### 8.4 Fixtures

- Postgres via `pg_ctl` (already used in existing tests) is the stand-in for SQL Server multi-database scenarios in E2E tests.
- SQL Server-specific code paths (ODBC driver error, `sys.databases` query) get unit tests with a mocked `pyodbc.Cursor` in `tests/test_sqlserver.py`.
- `tests/commands/conftest.py` may grow a `multi_source_yaml(tmp_path, sources=[...])` helper.

---

## 9. Migration and blast radius

### 9.1 Source files touched

| File | Change | Rough LOC |
|------|--------|-----------|
| `src/feather_etl/config.py` | Trim DB templates + per-type branches; replace `source:` parse with `sources:` list parse; delete `SourceConfig`. | −200 / +60 |
| `src/feather_etl/sources/__init__.py` | Expand `Source` Protocol with `from_yaml`, `validate_source_table`. | +30 |
| `src/feather_etl/sources/registry.py` | Replace `create_source()` with lazy `get_source_class()`. | −15 / +25 |
| `src/feather_etl/sources/sqlserver.py` | Add `from_yaml`, `list_databases`, `validate_source_table`, `databases` param. | +80 |
| `src/feather_etl/sources/postgres.py` | Same. | +70 |
| `src/feather_etl/sources/csv.py`, `sqlite.py`, `duckdb_file.py`, `excel.py`, `json_source.py` | Each: `from_yaml`, `validate_source_table`. | +20 each |
| `src/feather_etl/commands/discover.py` | Rewrite: iterate sources, state file I/O, flags, summary. | −35 / +220 |
| `src/feather_etl/commands/validate.py` | Iterate `cfg.sources` for source validation. | +30 |
| `src/feather_etl/commands/run.py`, `status.py`, `history.py`, `setup.py`, `init.py` | Multi-source guard error. | +15 each |
| `src/feather_etl/pipeline.py` | Read from `cfg.sources[0]` until B2 ships. | +5 |
| `src/feather_etl/init_wizard.py` | Generate `sources:` list (single-entry). | +10 |

**Net source diff:** roughly +800 / −250 LOC.

### 9.2 Test files touched

- `tests/test_config.py` — update fixtures to `sources:`; add multi-source / migration tests.
- `tests/test_sqlserver.py`, `test_postgres.py` — add `from_yaml`, `list_databases()`, XOR tests.
- `tests/test_csv_glob.py`, `test_excel.py`, `test_json.py`, `test_sources.py`, `test_discover_io.py`, `test_integration.py`, `test_e2e.py` — update fixtures.
- `tests/commands/test_discover.py` — extend with state, resume, retry, prune, refresh tests.
- `tests/commands/test_discover_multi_source.py` — **new**, happy-path E2E (§8.2).
- `tests/commands/conftest.py` — may grow `multi_source_yaml()` helper.

### 9.3 Fixtures and docs

- `tests/fixtures/*.yaml` — mechanical rewrite `source:` → `sources: [...]`.
- `scripts/hands_on_test.sh` — update existing checks to keep green; do not extend (per project convention — hands_on_test.sh is deprecated in favor of pytest).
- `README.md`, `docs/prd.md` — every `source:` example → `sources: [...]`.
- `docs/CONTRIBUTING.md` — add the testing-co-location principle from §8.1 as a project convention.

### 9.4 Env vars and `.env`

Unchanged. `${VAR}` expansion still works per-value. Multi-source users use distinct env var names (`ERP_HOST`, `PG_HOST`, etc.). Per-source env-var prefixes (`FEATHER_ERP_HOST`) are deferred (D3).

### 9.5 Delivery — single PR, multiple atomic commits

Single PR at the end, no mid-review. Internal commit boundaries for reviewability (author-private, user does not review between):

1. **O2 refactor** — each source class gains `from_yaml` and `validate_source_table`; `config.py` delegates; `registry.py` becomes lazy. `source:` still singular. All existing tests pass.
2. **YAML migration** — `source:` → `sources:` list (single entry). Every fixture/doc updated in the same commit. Singular `source:` raises hard error.
3. **Discover iterates sources** — command rewritten to loop over `cfg.sources`. Auto-enumeration for DB sources without `database`/`databases`. No state file yet.
4. **State file + flags** — `feather_discover_state.json`, `--refresh`, `--retry-failed`, `--prune`. Adds `test_discover_multi_source.py`.

Each commit leaves the test suite green.

---

## 10. Deferred — tracked so nothing is forgotten

| # | Deferral | Ships with |
|---|----------|------------|
| D1 | `tables[].source: <name>` field | Future "B2" slice |
| D2 | `run`, `validate`, `setup`, `status`, `history` iterate multiple sources | Future "B2" slice |
| D3 | Per-source env-var prefixes (`FEATHER_ERP_HOST`, `FEATHER_SPREADSHEETS_PATH`) | Future slice |
| D4 | `database_exclude: [tempdb, msdb, ...]` | Needed when filter use cases arise |
| D5 | `database_include:` / glob patterns | Same |
| D6 | YAML anchor/template docs for credential dedup | Docs-only, any time |
| D7 | Per-source connection pool / retry config | Future |
| D8 | Per-source `schedule:` | When scheduler is built |
| D9 | Re-organize `tests/` to mirror `src/` (T3) | Not planned — see §8.1 |
| D10 | `feather view` / `discover --open` multi-source picker | Issue #17 |
| D11 | Migration warning UX polish (auto-rewrite YAML) | Future if pain reported |
| D12 | Bronze-only `target_table` validation | Issue #18 |
| D13 | Lazy imports for optional DB connectors | **Closed by this slice** (O2 side effect) |
| D14 | `--prune <name>` surgical cleanup | Future if needed |
| D15 | State file schema versioning / migration | When `schema_version: 2` is needed |
| D16 | `--since DURATION` staleness filter | Future if ops asks |
| D17 | Per-source retry limits / exponential backoff | Future if transient failures become common |

---

## 11. Interactions with other open issues

| Issue | Relationship |
|-------|--------------|
| #4 Lazy imports in source registry | **Closed** by this slice as a side effect of O2 |
| #14 Tests for `feather init` and `validate` | Orthogonal; not affected |
| #15 `feather snapshot` | Orthogonal |
| #16 `discover` auto-save JSON | **Already merged** — filename convention reused for per-source files |
| #17 `discover --open` + `feather view` | Blocks on this slice for multi-source file picker; deferred (D10) |
| #18 Bronze-only extraction validation | Orthogonal bug; separate PR |
| #19 Split `cli.py` into `commands/` | **Already merged** — this slice edits `commands/discover.py`, not `cli.py` |

---

## 12. Success criteria

A user with a SQL Server hosting five databases can write:

```yaml
sources:
  - name: erp
    type: sqlserver
    host: ${DB_HOST}
    user: ${DB_USER}
    password: ${DB_PASSWORD}

destination:
  path: ./feather_data.duckdb

tables: []
```

Run `feather discover` and get five JSON files (one per database), a state file recording what succeeded, and a summary line telling them which databases were enumerated. If two databases fail, re-running the command retries only those two. If a database is dropped from the server, the next run marks it as removed and prints the exact command to clean up.

Heterogeneous configs (SQL Server + CSV + SQLite in one `feather.yaml`) work with the same command.

No existing user of `feather.yaml` is silently broken: singular `source:` raises a clear migration error pointing to the list shape.
