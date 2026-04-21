# View discovery across database sources

Created: 2026-04-21
Status: DRAFT
Issue: [#26](https://github.com/siraj-samsudeen/feather-etl/issues/26)

**Personas:** [`docs/personas.md`](../../personas.md) v1.2 — Builder, Analyst, and the Artifact consumers catalog.
**Requirements source:** [`docs/issues/26-discover-views.md`](../../issues/26-discover-views.md) (includes the Implementation Handoff Addendum).
**Branch:** `feature/discover-views`.

| Version | Changes |
|---|---|
| 1.0 | Initial draft. Scope: three DB sources. Flat-array schema JSON. Human-viewer-only consumer. |
| 1.1 | Scope expanded to five DB-shaped sources. JSON shape migrated to `{streams: [...]}` for forward-compat with the planned SQLite metadata DB. AI triage agent promoted to first-class artifact consumer. |
| 2.0 | Restructured to fit [`docs/conventions/spec-template.md`](../../conventions/spec-template.md): requirements/design split, counterfactual Key decisions, declarative integration surface. Implementation procedure (per-task TDD breakdown, dependency chain) moved out of the spec entirely — it belongs in the plan doc that `writing-plans` will produce next. |

---

# Part I — Requirements

## 1. Problem

Every feather-etl client deployment points at an ERP. Every ERP of meaningful age has accumulated views alongside its base tables — some are thoughtful, curated business logic the client's power users query daily; others are temporary hacks nobody cleaned up. The mix is always present; the ratio varies by client.

Today, `feather discover` makes all of that invisible. The three database sources (`postgres`, `sqlserver`, `mysql`) filter `INFORMATION_SCHEMA.TABLES` to `BASE TABLE` only. `sqlite` filters to `type = 'table'`. The DuckDB file source makes no classification at all — it returns tables and views as an undifferentiated list with no way for a downstream consumer to tell which is which.

The cost to the Builder is immediate and concrete. View-level business logic is free research material — sometimes literally the specification for what the warehouse's gold layer should produce. Without a listing, the Builder either rediscovers that logic by reading the ERP's source SQL manually (slow, error-prone, forgotten) or skips views entirely and risks shipping a warehouse that silently regresses information the Analyst was pulling from views just yesterday. The Analyst's binding invariant — *whatever I could answer from the ERP today, I can answer from the warehouse tomorrow* — starts eroding the moment a view becomes invisible.

A second, newer cost is that feather-etl's discovery output now feeds an AI triage agent. The agent's job is to recommend, per view, whether to ignore it, rebuild it in silver/gold, or copy its rows verbatim into the warehouse. The agent cannot recommend on what it cannot see. It also needs every view's DDL materialized in one artifact, offline-readable, because cross-view pattern recognition ("these ten views share structure") is impossible if DDL arrives one round-trip at a time.

The problem, in a sentence: the discovery artifact is silently hiding the source information the Builder, the Analyst, and the triage agent all depend on.

## 2. Goal

After this ships, `feather discover` lists views alongside base tables across every DB-shaped source, and each discovered view carries its full `CREATE VIEW` DDL text, captured eagerly into a single self-contained schema JSON file per source. The JSON is shaped as a dict keyed by `streams`, with each entry a prospective row for the forthcoming SQLite metadata database — so the eventual migration is a mechanical `INSERT INTO streams SELECT ... FROM json_each(...)`, not a re-design. The schema viewer renders a table/view badge, a filter toggle, and a collapsible DDL block for view entries; the AI triage agent processes the same JSON to produce bucketed recommendations the Builder reviews. No new CLI commands, no new YAML keys — the change lives entirely inside existing paths.

## 3. Acceptance criteria

- `feather discover` against a `postgres`, `sqlserver`, `mysql`, `sqlite`, or `duckdb_file` source returns views intermixed with base tables.
- Every view entry reports `table_type: "view"` and a populated `ddl` string.
- Every table entry reports `table_type: "table"` and `ddl: null`.
- The written `schema_<source>.json` file is a JSON dict whose top-level key `streams` holds an array; each entry is an object with exactly `name`, `table_type`, `ddl`, and `columns` fields.
- `columns` is a one-level sub-array of `{name, type}` objects — no deeper nesting, no duplicated information elsewhere in the entry.
- The schema viewer displays a `table` or `view` badge next to each sidebar entry.
- The schema viewer provides a three-state filter (show tables / show views / show both, default both).
- The schema viewer renders a collapsible `CREATE VIEW` block under each view's column list, with a copy-to-clipboard affordance.
- An older `schema_<source>.json` written in the previous flat-array shape continues to render in the new viewer without errors — badges and DDL sections are absent, but nothing crashes.
- A `feather.yaml` configured with `source_table: <view_name>` runs through `feather run` end-to-end: rows land in the destination on the first run, and a second run reports the table unchanged (or reports `checksum_error` and safely re-extracts, per engine).
- Live-DB integration tests (skipif-guarded by existing live-connection markers) assert view discovery works against each of postgres, sqlserver, and mysql.

### End-to-end verification

A single concrete exemplar the reader can run by hand to confirm the criteria hold.

```bash
# Against the DuckDB fixture with a newly-added view
uv run feather discover --config tests/fixtures/sample_erp.yaml

# Inspect the shape
python -c "import json; d=json.load(open('schema_sample_erp.json')); \
  assert 'streams' in d and isinstance(d['streams'], list); \
  print([(s['name'], s['table_type'], bool(s.get('ddl'))) for s in d['streams']])"
# Expected output includes:
#   ('erp.orders', 'table', False)
#   ('erp.high_value_orders', 'view', True)

# Open the viewer; confirm badges, filter toggle, and DDL collapsible render
open http://127.0.0.1:8000
```

---

# Part II — Design

## 4. Scope

Lives across `src/feather_etl/sources/*.py`, `src/feather_etl/discover.py`, `src/feather_etl/resources/schema_viewer.html`, two fixture-generator scripts, and the test suite. No new top-level CLI commands, no new `feather.yaml` keys, no new external dependencies.

**In**

- Every DB-shaped source reports views alongside base tables from `discover()`.
- Every discovered view carries its full DDL, materialized at discover time (not lazily).
- The discovery artifact serves both the human viewer and the AI triage agent from a single JSON file; the shape works equally well for both.
- `StreamSchema` carries two new descriptive fields (`table_type`, `ddl`) usable across all sources.
- The schema JSON on disk is a dict keyed by `streams`, with entries shaped for direct mechanical migration to a future SQLite `streams` row.
- The schema viewer distinguishes tables from views, lets the user filter one category at a time, and surfaces each view's DDL without leaving the page.
- Existing schema JSON files on disk (flat-array shape) continue to render in the updated viewer.
- A Builder who configures `source_table: <view_name>` extracts the view's rows through the existing pipeline with no additional configuration.

**Out**

- `CREATE TABLE streams` and any SQLite metadata schema. That work lives in a parallel workstream.
- Sidecar `.sql` files for DDL.
- DDL-drift detection across discover runs.
- Automatic view-dependency resolution (parsing DDL to infer referenced tables).
- Dialect translation of view DDL (T-SQL / PL/pgSQL → DuckDB).
- Source-vs-warehouse reconciliation tooling.
- Cache-materialization policy for views.
- A new `include_views` config knob.
- Recording the Builder's per-view triage decision anywhere in the artifact.

**Outside this scope**

- `src/feather_etl/sources/csv.py`, `excel.py`, `json_source.py` — file-shaped sources with no view concept. They inherit the new `StreamSchema` defaults transparently and need no code changes.
- `src/feather_etl/cli.py`, `src/feather_etl/config.py` — no new commands, no new YAML keys.
- `src/feather_etl/state.py`, `discover_state.py` — existing state tracking is unchanged; view entries increment the existing `table_count` alongside tables.

## 5. Key decisions

### Artifact shape — flat array vs dict keyed by `streams`

**Chose:** A dict whose top-level `streams` key holds the array of entries; each entry carries `name`, `table_type`, `ddl`, and a one-level `columns` sub-array.

**Why not preserve the existing flat array?** The near-term workstream consolidates feather-etl's metadata into a unified SQLite database. A flat array forces either a breaking re-serialization at migration time or a permanent translation layer between disk shape and in-memory model. The keyed-by-`streams` shape maps 1-to-1 onto the future `streams` row schema — migration becomes `INSERT INTO streams SELECT ... FROM json_each(...)`. The cost today is one viewer compat shim; the savings at migration are a full redesign avoided.

### DDL capture timing — eager at discover time vs lazy on demand

**Chose:** Eager, inlined in each stream entry.

**Why not lazy?** Lazy fetch (viewer or agent asks; discover replies with column count only) breaks three consumer constraints documented in `personas.md` v1.2. (1) The AI triage agent's cross-view pattern recognition is a one-pass operation over the whole artifact — it cannot observe patterns across per-view round trips. (2) Offline review by a second agent or a teammate breaks if the artifact needs a live source connection to interpret. (3) Per-view round trips burn tokens linearly in view count — a 200-view ERP becomes a 200-tool-call exercise. Eager capture pays a small one-time cost at discover for a large compound benefit at every consumer.

### Non-human artifact consumer — first-class or afterthought

**Chose:** The AI triage agent is a first-class artifact consumer, co-equal with the human viewer. Design choices must satisfy both.

**Why not treat the agent as "just another tool the Builder sometimes uses"?** That framing would license pretty-printed human-readable JSON, lazy DDL fetching, and other humans-first choices that fail the agent. Elevating the agent forces the artifact to stay machine-parseable, self-contained, and offline-capable. Those properties also make the artifact more robust for humans — nothing in the agent's constraints conflicts with what the viewer needs.

### DuckDB file source — "fix bug" vs "reconcile asymmetry"

**Chose:** The DuckDB file source change is framed as reconciling an inherited asymmetry, not fixing a bug.

**Why not call it a bug fix?** The existing no-type-filter behavior was pre-convention code written before `table_type` existed in the product. Framing matters: "bug" invites blame-seeking and tempts over-correction ("while we're in there, let's also…"). "Reconcile asymmetry" orients the change as aligning one source with the others — a smaller, more focused edit with clearer stopping criteria. This is a Chesterton's Commit principle: treat inherited pre-convention code as inherited, not as bug.

### Postgres DDL — verbatim vs synthesized

**Chose:** Synthesized — capture the SELECT body from `INFORMATION_SCHEMA.VIEWS.view_definition`, then wrap with `CREATE VIEW <qualified> AS <body>`.

**Why not preserve verbatim via a Postgres-native function?** No Postgres surface returns the verbatim original `CREATE VIEW` text. Both `pg_get_viewdef()` and `INFORMATION_SCHEMA.VIEWS.view_definition` return the SELECT body only; the engine does not persist the original statement. Synthesized text is sufficient for triage-readability — the only requirement R1 places on DDL. SQL Server (`sys.sql_modules.definition`) and MySQL (`SHOW CREATE VIEW`) do return full original text and are used verbatim.

### Backwards-compat for old JSON files

**Chose:** The viewer normalizes old flat-array JSON on load (three lines of JavaScript).

**Why not require users to re-run `feather discover` after upgrading?** Discover is not a hot path; users may go months between runs. A compat shim in the consumer costs almost nothing and preserves continuity for anyone who upgrades feather without immediately re-discovering.

### `include_views` config knob — now or later

**Chose:** Not now. Filtering lives in the viewer (a three-state toggle), not in the source config.

**Why not add a YAML knob for Builders who deploy against ERPs with many hack views?** Viewer-side filtering is additive and reversible (toggle at any time, no re-discover). A YAML knob is configure-once-and-forget and asymmetric (easy to forget; hard to notice the view you wanted is hidden). The viewer toggle covers the stated use case. If a Builder reports the toggle is insufficient — for example, wanting to skip DDL capture for hundreds of hack views to cut discovery time — the knob lands as a follow-on against that concrete signal.

## 6. How it works

`feather discover` iterates the sources from `feather.yaml`, calling each source's `discover()`. Each DB-shaped source now issues two information-schema queries rather than one: a broadened tables-and-views listing, then a follow-up per view to capture its DDL (verbatim where the engine preserves original text, synthesized where it only returns the body). Each source returns a list of `StreamSchema` objects carrying the per-entry `name`, `columns`, `primary_key`, `supports_incremental`, `table_type`, and `ddl`. The list flows into `_write_schema` in `discover.py`, which serializes to `schema_<source>.json` in the new `{"streams": [...]}` shape.

From that artifact, two parallel consumption paths run:

```
                 schema_<source>.json   (single artifact)
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
      Human viewer              AI triage agent
      (schema_viewer.html)       (consumes offline)
      ─ badge per entry          ─ one-pass read
      ─ filter toggle            ─ cross-view patterns
      ─ collapsible DDL          ─ recommendation output
```

The viewer is vanilla JavaScript with no framework — new code plugs into the existing sparklist and treemap renderers. On load, it detects whether the JSON is a raw array (old shape) or a dict keyed by `streams` (new shape) and normalizes to the latter internally so all downstream rendering sees one shape. The DDL collapsible uses a native `<details>` element; no new dependencies.

Two quirks future maintainers will need to know. (1) For Postgres, the "DDL" stored in the artifact is a synthesized string assembled from `INFORMATION_SCHEMA.VIEWS.view_definition`; comparing it to what a DBA sees via `pg_dump` will show formatting differences (no comments, no original whitespace). (2) For MySQL, `CHECKSUM TABLE` — used by the existing full-strategy change detector — returns an error code when invoked on a view. The existing error path already converts that into `ChangeResult(changed=True, reason="checksum_error")` which safely triggers a full re-extract; no new code is needed, but the live-DB integration test should exercise this path to keep the fallback honest.

## 7. Integration surface

**New**

- `tests/e2e/test_discover_views.py` — end-to-end test exercising a view as a first-class extraction target: discover lists it, pipeline extracts rows, second run reports unchanged (or checksum_error safely).

**Modified**

- `src/feather_etl/sources/__init__.py` — currently defines `StreamSchema` with four fields (name, columns, primary_key, supports_incremental); becomes home of two additional descriptive fields (`table_type`, `ddl`) carrying their defaults.
- `src/feather_etl/discover.py` — currently writes a flat-array schema JSON with `table_name` and `columns`; becomes home of the `streams`-keyed writer producing the four canonical per-entry fields.
- `src/feather_etl/sources/postgres.py` — currently discovers base tables only; becomes home of a combined tables-and-views listing with DDL synthesized from `INFORMATION_SCHEMA.VIEWS.view_definition`.
- `src/feather_etl/sources/sqlserver.py` — currently discovers base tables only; becomes home of the combined listing with DDL captured verbatim from `sys.sql_modules.definition`.
- `src/feather_etl/sources/mysql.py` — currently discovers base tables only; becomes home of the combined listing with DDL captured verbatim from `SHOW CREATE VIEW`.
- `src/feather_etl/sources/sqlite.py` — currently filters `sqlite_master` to `type = 'table'`; becomes home of the broadened filter with DDL captured from `sqlite_master.sql`.
- `src/feather_etl/sources/duckdb_file.py` — currently returns tables and views undifferentiated; becomes home of explicit classification via DuckDB's view surface and per-view DDL capture. The change is framed as reconciling asymmetry with peer sources.
- `src/feather_etl/resources/schema_viewer.html` — currently consumes a flat-array payload and renders a table-only sidebar; becomes home of a shape-compat reader, a table/view badge, a three-state filter toggle, and a collapsible DDL block per view.
- `tests/e2e/test_03_discover.py` — currently asserts an exact-key set on the old schema JSON; becomes home of the assertion for the new `streams`-keyed shape.
- `tests/unit/sources/test_postgres.py`, `test_sqlserver.py`, `test_mysql.py`, `test_sqlite.py`, `test_duckdb_file.py` — each currently covers table discovery only; each becomes home of a view-discovery assertion verifying `table_type="view"` and a populated DDL.
- `tests/integration/test_postgres.py`, `test_mysql.py`, `test_sqlserver.py` — each becomes home of a skipif-guarded live-DB view-discovery test exercising the per-engine DDL query path.
- `scripts/create_sample_erp_fixture.py`, `scripts/create_csv_sqlite_fixtures.py` — each generator becomes home of one `CREATE VIEW erp.high_value_orders AS SELECT * FROM erp.orders WHERE total_amount > 1000` statement; `sample_erp.duckdb` and `sample_erp.sqlite` are regenerated.

**Outside this scope**

- `src/feather_etl/sources/csv.py`, `excel.py`, `json_source.py` — no view concept in these formats; they inherit the new `StreamSchema` defaults transparently and need no code changes.
- `src/feather_etl/cli.py`, `src/feather_etl/config.py` — no new commands, no new YAML keys.
- `src/feather_etl/state.py`, `discover_state.py` — change-detection paths are already view-compatible for Postgres and SQL Server, and fail safely for MySQL; no state-tracking code changes are required.

## 8. Test design

Organized by layer. Project convention is real fixtures over mocks; unit tests for sources that require a live DB (postgres, sqlserver, mysql) follow the existing `tests/unit/sources/*` patterns — lightweight stand-ins where available, otherwise minimal assertions on the SQL constructed.

**Unit tests** (real fixtures or minimal stand-ins, no live DB):

- `StreamSchema` construction with new defaults round-trips correctly: `table_type` defaults to `"table"`, `ddl` defaults to `None`; explicit `table_type="view"` + `ddl="CREATE VIEW ..."` preserves values.
- `_write_schema` emits the new `{streams: [...]}` shape with exactly `{name, table_type, ddl, columns}` per entry for a mixed table-and-view input.
- Per-source: `discover()` returns a view entry with `table_type="view"` and a populated `ddl`. SQLite and DuckDB file sources use the regenerated fixtures; Postgres, SQL Server, and MySQL use the project's existing patterns for sources requiring engine calls.
- Viewer: loading a JSON payload with a mixed table-and-view `streams` array produces a sidebar containing the expected badge markers and a `<details>` DDL block. Loading a raw-array (old-shape) payload produces a sidebar that renders without errors.

**Integration tests** (real live-DB connections, gated by existing skipif markers):

- Per engine (postgres, sqlserver, mysql): discover against a pre-seeded DB containing at least one base table and at least one view. Assert both are returned with correct `table_type` and non-empty DDL for the view.
- MySQL-specific: configure `source_table: <view>` against a live MySQL, run end-to-end extraction and change detection. Assert the pipeline completes — either the `CHECKSUM TABLE` path succeeds, or the `checksum_error` fallback triggers a full re-extract cleanly.

**End-to-end test** (local DuckDB/SQLite fixtures, no live DB):

- `tests/e2e/test_discover_views.py`: feather.yaml configured with `source_table: erp.high_value_orders` against the updated DuckDB fixture. Run `feather run`. Assert rows land in the destination and a second run reports the view unchanged.

**Manual acceptance** (done by the Builder before merging):

- Run `feather discover` against a live Postgres, SQL Server, or MySQL containing at least one view.
- Open the viewer; confirm the view appears with a badge, DDL is populated, the filter toggle hides/shows views correctly, and the copy-to-clipboard affordance works.
- Confirm an older (pre-migration) `schema_<source>.json` file on disk still renders in the updated viewer without errors.
