# Design: View discovery across database sources (Issue #26)

**Version:** 1.0
**Date:** 2026-04-21
**Status:** Draft, pending user review
**Upstream issue:** [siraj-samsudeen/feather-etl#26](https://github.com/siraj-samsudeen/feather-etl/issues/26)
**Personas:** [`docs/personas.md`](../../personas.md) v1.1 — Builder and Analyst
**Requirements:** [`docs/issues/26-discover-views.md`](../../issues/26-discover-views.md)
**Branch:** `feature/discover-views`

---

## 1. Scope & boundaries

**In scope.** `feather discover` lists views from Postgres, SQL Server, and MySQL alongside base tables. Each view carries its full `CREATE VIEW` DDL text so the Builder can triage it (ignore vs. rebuild vs. copy verbatim) without opening a second tool. The schema JSON artifact and the schema viewer are extended to surface the table-vs-view distinction and the DDL. `StreamSchema` gains two descriptive fields.

**Out of scope — preserved here so they are not reopened mid-implementation.**

- DDL-change detection across discover runs (drift tracking).
- Automatic view-dependency resolution (parsing DDL to identify referenced tables).
- Dialect translation of view DDL (T-SQL / PL/pgSQL → DuckDB).
- Reconciliation tooling (source-vs-warehouse diff commands).
- Cache materialization policy for views (auto-replay, auto-materialize, etc.).
- A new `include_views` config knob. The viewer's filter toggle covers the "hide views" need; configure-time filtering is YAGNI until a Builder asks.

**Personas served.**

- **Builder** — R1: triage each view via DDL at discover time; extract view data on demand via existing `source_table: <view>` configuration.
- **Analyst** — R2: no direct effect from this issue, but the ability to *study* view DDL is the foundation for the Builder delivering information parity later.

---

## 2. User-facing contract

This is the surface that is hardest to change after shipping. Locking it now.

### 2.1 `feather discover` CLI behavior

No new flags. Running `feather discover` against a config that lists a Postgres, SQL Server, or MySQL source now returns tables and views intermixed in the discovery output. Existing stdout format is preserved — view entries are not called out on the terminal; the distinction surfaces in the viewer.

### 2.2 Schema JSON shape (written per source to `schema_<source>.json`)

Before:

```json
[
  {
    "table_name": "erp.orders",
    "columns": [{"name": "id", "type": "INTEGER"}, ...]
  }
]
```

After:

```json
[
  {
    "table_name": "erp.orders",
    "columns": [{"name": "id", "type": "INTEGER"}, ...],
    "table_type": "table",
    "ddl": null
  },
  {
    "table_name": "erp.high_value_orders",
    "columns": [{"name": "id", "type": "INTEGER"}, ...],
    "table_type": "view",
    "ddl": "CREATE VIEW erp.high_value_orders AS SELECT * FROM erp.orders WHERE total_amount > 1000"
  }
]
```

**Contract guarantees.**

- `table_type` is always one of `"table"` or `"view"`. Never `null`. Never `"materialized_view"` in this version.
- `ddl` is a string for views, `null` for tables.
- Old schema JSON files on disk (written before this change) remain readable by the new viewer — missing fields are handled gracefully.

### 2.3 Schema viewer HTML

The viewer now renders:

- A compact badge (`table` / `view`) next to each entry in the sidebar list.
- A filter toggle at the top of the sidebar: "Show tables", "Show views", "Show both" (default: both).
- For view entries, a collapsible "CREATE VIEW" section in the detail pane, under the column list, with a copy-to-clipboard affordance.

### 2.4 `feather.yaml` shape

Unchanged. No new keys. `source_table: <view_name>` continues to work as it has.

### 2.5 Python API (`StreamSchema`)

```python
@dataclass
class StreamSchema:
    name: str
    columns: list[tuple[str, str]]
    primary_key: list[str] | None
    supports_incremental: bool
    table_type: Literal["table", "view"] = "table"
    ddl: str | None = None
```

Both new fields have defaults. All existing `StreamSchema(...)` construction sites (19 sites, all keyword-based per the impact research) continue to work unchanged.

---

## 3. Integration surface

Which files change and why — ordered by blast radius.

| File | Change | Persona trace |
|---|---|---|
| `src/feather_etl/sources/__init__.py` | Add `table_type` and `ddl` fields to `StreamSchema`. | Foundation for R1. |
| `src/feather_etl/sources/postgres.py` | `discover()` includes views; captures DDL via `INFORMATION_SCHEMA.VIEWS.view_definition` and synthesizes `CREATE VIEW` prefix. | R1 triage. |
| `src/feather_etl/sources/sqlserver.py` | `discover()` includes views; captures DDL via `sys.sql_modules.definition` (full text). | R1 triage. |
| `src/feather_etl/sources/mysql.py` | `discover()` includes views; captures DDL via `SHOW CREATE VIEW` (full text). | R1 triage. |
| `src/feather_etl/discover.py` | Schema JSON payload grows `table_type` and `ddl` fields. | Bridges backend to viewer. |
| `src/feather_etl/resources/schema_viewer.html` | Badge, filter toggle, collapsible DDL rendering. | R1 triage UI. |
| `tests/e2e/test_03_discover.py` | Loosen strict key assertion (line 244) to superset. | Unblocks shape change. |
| `tests/fixtures/sample_erp.duckdb`, `sample_erp.sqlite` | Add one view to each, regenerated via the existing scripts. | Gives tests a view to observe. |
| `scripts/create_sample_erp_fixture.py`, `scripts/create_csv_sqlite_fixtures.py` | Add `CREATE VIEW` for `high_value_orders`. | Keeps fixtures reproducible. |
| `tests/unit/sources/test_postgres.py`, `test_sqlserver.py`, `test_mysql.py` | Add view-discovery unit tests (mocked or in-memory where possible). | Per-engine correctness. |
| `tests/e2e/test_discover_views.py` (new) | End-to-end: configure `source_table: <view>`, run pipeline, assert extraction + change detection. | Closes the "no view-extraction coverage" gap the research agent flagged. |
| `tests/integration/test_postgres.py`, `test_mysql.py`, `test_sqlserver.py` | Add live-connection view tests (skipif-guarded). | Per-engine real-DB correctness. |

File sources (CSV, SQLite, DuckDB, Excel, JSON) are **not** modified. They default `table_type` to `"table"` via the dataclass default and leave `ddl` as `None`. No view concept applies.

---

## 4. Task breakdown

Tasks are atomic and ordered so each one is testable in isolation. Each task follows TDD: the test is written first, the implementation makes it pass.

### Task 1 — Extend `StreamSchema`

- **What:** Add `table_type: Literal["table", "view"] = "table"` and `ddl: str | None = None` to the dataclass.
- **Why / risk:** Foundation. Low risk — all construction sites use keyword args, no snapshot comparisons on the whole dataclass.
- **TDD test:** Unit test: construct `StreamSchema(name="t", columns=[], primary_key=None, supports_incremental=True)` and assert `.table_type == "table"` and `.ddl is None`. Construct with `table_type="view", ddl="CREATE VIEW ..."` and assert the fields round-trip.
- **Code:** Two new fields on the dataclass in `src/feather_etl/sources/__init__.py`.

### Task 2 — Loosen the schema-JSON key assertion

- **What:** Update `tests/e2e/test_03_discover.py:244` from `== {"table_name", "columns"}` to explicitly include the new keys, or use a superset check.
- **Why / risk:** Unblocks every later task. Doing this first so the repo stays green step by step.
- **TDD test:** The existing assertion stays but is rewritten to validate the new shape.
- **Code:** Single-line test change.

### Task 3 — Extend the schema JSON writer

- **What:** In `src/feather_etl/discover.py`, update the payload comprehension to emit `table_type` and `ddl` for every entry.
- **Why / risk:** Bridges new `StreamSchema` fields to disk. Low risk — additive.
- **TDD test:** Unit test: `_write_schema` with a mock source returning one `StreamSchema(table_type="view", ddl="CREATE ...")`; assert the written JSON has the two new keys with correct values.
- **Code:** Add `table_type` and `ddl` to the dict comprehension in `_write_schema`.

### Task 4 — Postgres `discover()` includes views with DDL

- **What:** Change the `TABLE_TYPE` filter to include `'VIEW'`. For each view, issue a follow-up query against `INFORMATION_SCHEMA.VIEWS` to fetch `view_definition`, then synthesize `CREATE VIEW {qualified} AS {body}`. Populate `StreamSchema.table_type` and `.ddl` accordingly.
- **Why / risk:** Core R1 deliverable for Postgres. Low risk — existing discover flow is preserved for tables.
- **TDD test:** Integration test (skipif-guarded) against a live Postgres with one base table and one view. Assert `discover()` returns both, with correct `table_type` values and non-empty DDL for the view.
- **Code:** ~15 lines in `src/feather_etl/sources/postgres.py`.

### Task 5 — SQL Server `discover()` includes views with DDL

- **What:** Change the `TABLE_TYPE` filter. For each view, fetch DDL via `sys.sql_modules.definition` using `OBJECT_ID('{schema}.{name}')`. Full original text; no synthesis needed.
- **Why / risk:** Core R1 deliverable for SQL Server.
- **TDD test:** Integration test (skipif-guarded) against a live SQL Server. Same assertions as Task 4.
- **Code:** ~15 lines in `src/feather_etl/sources/sqlserver.py`.

### Task 6 — MySQL `discover()` includes views with DDL

- **What:** Change the `TABLE_TYPE` filter. For each view, fetch DDL via `SHOW CREATE VIEW {qualified}`. Full original text.
- **Why / risk:** Core R1 deliverable for MySQL. One extra risk: verify that `CHECKSUM TABLE` on a view either works or fails gracefully in the existing change-detection path. The existing code already falls through to `checksum_error` on any MySQL error, which is safe.
- **TDD test:** Integration test against live MySQL with a base table and a view. Additional test: configure `source_table: <view>` and run end-to-end extraction — confirm it completes (even if `CHECKSUM TABLE` errors, the fallback triggers a full extract which still succeeds).
- **Code:** ~15 lines in `src/feather_etl/sources/mysql.py`.

### Task 7 — Extend fixtures with a view

- **What:** Modify `scripts/create_sample_erp_fixture.py` and `scripts/create_csv_sqlite_fixtures.py` to add one `CREATE VIEW erp.high_value_orders AS SELECT * FROM erp.orders WHERE total_amount > 1000`. Regenerate `sample_erp.duckdb` and `sample_erp.sqlite`.
- **Why / risk:** Required for unit and e2e view tests. Low risk — existing tests reference tables by name, not count.
- **TDD test:** The regenerate-and-rerun command. No new test here; Task 8 consumes the fixture.
- **Code:** Two `CREATE VIEW` statements in the two scripts.

### Task 8 — Unit tests for per-engine view discovery

- **What:** Add `test_discover_returns_views` in `tests/unit/sources/test_postgres.py`, `test_sqlserver.py`, `test_mysql.py`. These can use mocks or an in-memory DuckDB stand-in where possible; live DB tests stay in `tests/integration/`.
- **Why / risk:** Per-engine correctness baseline.
- **TDD test:** The test itself.
- **Code:** One test per file, ~20 lines each.

### Task 9 — E2E test for view extraction

- **What:** `tests/e2e/test_discover_views.py` — configure a feather.yaml with `source_table: erp.high_value_orders`, run `feather run` against the new fixture, assert rows land in the destination and a second run is `unchanged` (change detection works on views in DuckDB too). Closes the coverage gap the research agent flagged.
- **Why / risk:** Confirms the research agent's "already works" finding holds in CI.
- **TDD test:** The test itself.
- **Code:** One new file, ~50 lines.

### Task 10 — Schema viewer: badge + DDL collapsible

- **What:** Update `src/feather_etl/resources/schema_viewer.html` to render a `table` / `view` badge in the sparklist and treemap entries, and a collapsible DDL section in the detail pane for view entries.
- **Why / risk:** R1 UI deliverable. Vanilla JS, low risk.
- **TDD test:** The existing `tests/unit/test_viewer_server.py` covers the packaging flow. Add one test that writes a schema JSON containing a view entry and asserts the rendered HTML (or a DOM-level selector via a lightweight parser) contains the expected badge and DDL section. If that proves unwieldy for vanilla-JS, a snapshot test of the served HTML string is acceptable.
- **Code:** ~30 lines of HTML/JS/CSS.

### Task 11 — Schema viewer: filter toggle

- **What:** Add a filter control at the top of the sidebar — "Show tables / Show views / Show both" (default both) — and wire it to `state.sources[si].tables` rendering.
- **Why / risk:** Handles R1's "in deployments with many hack views, let me hide them" case without a config knob.
- **TDD test:** Minimal DOM test: simulate a click on the toggle and assert the rendered sidebar entries update.
- **Code:** ~15 lines.

---

## 5. Dependency chain

```
Task 1 (StreamSchema fields)
   ↓
Task 2 (loosen JSON assertion) — can run in parallel with Task 1
   ↓
Task 3 (JSON writer emits new fields)
   ↓
Tasks 4, 5, 6 (Postgres, SQL Server, MySQL discover) — parallelizable; each independent
   ↓
Task 7 (fixtures) — must precede Tasks 8 and 9
   ↓
Task 8 (unit tests), Task 9 (e2e test) — parallelizable after Task 7
   ↓
Tasks 10, 11 (viewer UI) — parallelizable; depend on Task 3 but not on 4/5/6 functionally (can be tested with hand-written JSON)
```

Critical path: 1 → 3 → 4/5/6 → 9.

---

## 6. Done signal

The single end-to-end scenario that proves all eleven tasks landed correctly:

1. Start from a clean feather-etl clone on `feature/discover-views`.
2. Run `uv run pytest -q` — all 720+ tests pass, including the new view tests.
3. Run `uv run feather discover --config tests/fixtures/sample_erp.yaml` against a config pointing at `sample_erp.duckdb` (or `.sqlite`) — the terminal reports discovery succeeded; the schema JSON file contains both `erp.orders` (with `table_type: "table"`) and `erp.high_value_orders` (with `table_type: "view"` and a populated `ddl`).
4. The schema viewer opens in the browser. The sidebar shows badges on each entry. The view entry reveals a collapsible "CREATE VIEW" section with the DDL. The filter toggle hides/shows views.
5. Against a live Postgres, SQL Server, or MySQL with at least one view (optional — skipif-guarded): `uv run feather discover` lists the view with correct DDL captured.

When all five steps succeed, the issue is complete.

---

## 7. Notable decisions preserved against re-opening

- **`table_type` is purely descriptive metadata.** It does not gate extraction behavior. Whether a view is extracted is determined by whether `source_table: <view>` appears in the user's config, same as for tables. Rationale: keeps the pipeline uniform and avoids a second code path. Persona trace: R1 derived constraint ("data extraction from views is a supported production pattern, not an escape hatch").
- **Star-schema naming is the default for ported logic.** Preserving a source view's name in the warehouse is a supported per-view Builder decision via a compatibility view on top of gold — not a platform default. Rationale: `personas.md` §Design discipline, retraction list. Persona trace: R2 information parity is the invariant, not name preservation.
- **No `include_views` config knob in this issue.** Viewer-side filtering is sufficient. Revisit only if a Builder reports a concrete pain point. Persona trace: YAGNI against R1.
- **No data preview at discover time.** Builder extracts view data by configuring `source_table: <view>` and running `feather run`. Rationale: keeps discover fast and uniform; avoids a second data-access path with different semantics. Persona trace: R1 derived constraint.
- **Postgres DDL is synthesized, not preserved verbatim.** `INFORMATION_SCHEMA.VIEWS.view_definition` returns only the SELECT body; we prefix `CREATE VIEW <qualified> AS ` to produce the full DDL. SQL Server and MySQL return full original text. Rationale: R1 does not mandate exact formatting preservation, only that DDL be readable for triage.
- **Change detection already works on views for Postgres and SQL Server.** MySQL's `CHECKSUM TABLE` may error on views, but the existing error path falls through to `checksum_error` and a safe re-extract. Verified in Task 6's integration test. Rationale: research agent finding; no new code needed.
