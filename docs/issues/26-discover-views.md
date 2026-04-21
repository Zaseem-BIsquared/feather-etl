# Issue #26: View discovery across DB sources — Requirements

**Upstream:** [siraj-samsudeen/feather-etl#26](https://github.com/siraj-samsudeen/feather-etl/issues/26)
**Personas reference:** [`docs/personas.md` v1.1](../personas.md)
**Status:** Requirements captured during brainstorming; design spec pending.

---

## Problem restatement

All three database sources (`postgres`, `sqlserver`, `mysql`) currently filter `discover()` to `TABLE_TYPE = 'BASE TABLE'`, hiding views from `feather discover`. This is wrong because views in source ERPs carry business logic the Builder may need to study, port, or extract directly — and the Analyst relies on that logic being preserved (in some form) in the warehouse.

---

## Persona-driven requirements

### R1 — Builder: see both DDL and data for every view

The Builder must be able to **triage** each source view into one of three buckets:

1. **Ignore** — the view is a hack, a one-off, or not relevant to the warehouse. No further action.
2. **Rebuild in silver/gold** — the view encodes real logic worth porting into a star-schema equivalent. Source data is needed as ground truth to validate the rebuild produces matching output.
3. **Copy verbatim** — the view is too complex (or too opaque) to rebuild safely. Extract its rows directly as a warehouse table or compatibility view, and live with the fact that we are not rebuilding the logic.

For this triage to happen in reasonable time, the Builder needs:

- **The view's full DDL** at discovery time. DDL complexity is the primary signal: simple DDLs route to bucket (2) easily; complex DDLs force a choice between (2) and (3).
- **Access to the view's data** — at least on demand — for the (2)/(3) decision and for post-port validation. Data access does not need to happen at discover time, but it must be a first-class path (not an escape hatch).

> **Derived design constraint.** Data extraction from views is a supported production pattern, not an escape hatch. A view configured as an extraction target in `feather.yaml` flows through the same extraction, change-detection, and incremental machinery as a table.

### R2 — Analyst: information parity is the binding invariant

Whatever information the Analyst can extract from the ERP today — by querying a source view, reading a report, running a saved query — must remain reachable from the warehouse tomorrow. The Analyst does not weigh in on the access path.

Two valid porting outcomes, both acceptable:

- **(a) Same view name, same data.** For a source view the Builder judges thoughtful and worth preserving under its original name, expose it in the warehouse as a compatibility view on top of the star schema (gold layer). The Analyst's existing SQL against the view name continues to resolve.
- **(b) Same data via a different path.** The view's logic is decomposed into fact/dimension tables and (optionally) a curated data mart. The Analyst learns the new model. The information is still reachable; the access path is different.

Either outcome satisfies R2. The choice is the Builder's per-view decision, informed by how thoughtful the view appears to be and the cost of maintaining a compatibility layer.

> **Derived design constraint.** The warehouse must not regress information compared to source. Porting decisions that drop information (a view that encodes a calculation the star schema does not reproduce) must be flagged, not silently accepted.

---

## Out-of-scope for this issue

These are real follow-on concerns but deliberately deferred:

- **DDL-change detection across runs** — knowing when a view's definition has drifted between discovers. Useful for the Builder's regression-detection supporting JTBD, but a separate workstream.
- **Automatic view-dependency resolution** — parsing DDL to identify which tables a view reads, and auto-including those tables in extraction. Valuable but requires a SQL parser; separate workstream.
- **Dialect translation** — converting T-SQL / PL/pgSQL view DDL to DuckDB. Large problem with its own design requirements.
- **Reconciliation tooling** — source-vs-warehouse diff commands that prove ported logic produces matching output. The Builder's primary JTBD from `personas.md` points toward this, but it is a dedicated feature in its own right.
- **`feather cache` materialization of views** — whether the local dev cache replays source views as DuckDB views over bronze, or materializes them as tables, or ignores them. Answered on a case-by-case basis by whatever the Builder configures; no platform-wide automation in this issue.

These items are listed here so they are not forgotten, and so the current issue stays narrow.

---

## Summary of what this issue must deliver

Narrow, focused, traceable:

1. `discover()` in `postgres.py`, `sqlserver.py`, `mysql.py` returns views alongside base tables.
2. `StreamSchema` gains a `table_type` field — descriptive metadata only; does not itself gate extraction behavior.
3. Each discovered view carries its full `CREATE VIEW` DDL text.
4. The schema JSON written by `feather discover` persists `table_type` and DDL for views.
5. The schema viewer distinguishes tables from views and exposes the DDL.
6. The extraction machinery (change detection, incremental watermarks, full-strategy checksums) already works on any `source_table` the user configures — this issue does not change that behavior, but does confirm via test that configuring `source_table: some_view` continues to work end-to-end.

Persona traceability for each deliverable is spelled out in the design spec (pending).


# Issue #26 — Implementation Handoff Addendum

**Companion to:** [26-discover-views.md](26-discover-views.md) (requirements)
**Date captured:** 2026-04-21
**Status:** Brainstorming notes for the implementing agent

This document supplements the view-discovery requirements with three pieces of context that emerged during design brainstorming but are **not** captured in the requirements doc. An implementing agent should read both documents before starting the spec.

---

## 1. Discovery output feeds an AI agent, not just a human

After `feather discover` runs, its output is consumed by an **AI agent** whose job is per-view triage. Given the full metadata for each view, the agent recommends which of the three buckets from R1 applies:

1. **Ignore** — not relevant to the warehouse.
2. **Rebuild in silver/gold** — port the view's logic into star-schema equivalents. Source data is the ground truth for validating the rebuild.
3. **Copy verbatim** — materialize the view's rows as a warehouse table (or re-create the view on bronze). The DDL is too complex or opaque to safely rebuild.

The Builder then accepts, edits, or overrides the agent's recommendations.

### Design consequences

- **DDL must be materialized eagerly at discover time.** Lazy-fetch ("retrieve each DDL on demand") is incompatible with this workflow for three reasons:
  1. The agent's recommendations depend on **cross-view pattern recognition**. It cannot spot "these ten views share structure and should be rebuilt as a single fact table" if it sees DDLs one at a time.
  2. Per-view round-trips burn tokens — hundreds of tool calls for a 200-view source.
  3. **Offline review breaks** if the discovery artifact requires a live source connection. Sending the artifact to a second agent or a teammate for a second opinion must just work.
- **Discovery output must be self-contained and shippable.** One artifact, no live-connection dependency to interpret it.
- **The agent is a first-class consumer of this artifact.** Treat it as part of the design audience, not an afterthought.

---

## 2. A SQLite metadata DB is the near-term destination for discovery + curation

There is a **parallel workstream** (separate issue / thread) to migrate feather-etl's metadata artifacts from per-purpose JSON files into a unified SQLite metadata DB. Today's metadata surface — `schema_<source>.json` from discover, curation tables, and other metadata — is growing, and SQLite consolidates it into one file-portable, queryable database.

### Design consequences for this issue

- **DDL ultimately lives as a TEXT column on a `streams` row** (or equivalent), not as a sidecar `.sql` file, not as a separate artifact.
- **Sidecar `.sql` files are explicitly out of scope.** They would sprawl the filesystem pattern we're about to consolidate.
- **`StreamSchema` gains `table_type: str` and `ddl: str | None`.** The in-memory contract is unchanged by the persistence migration; only the write path changes.
- **Curation can later record the Builder's per-view triage decision as a column adjacent to the DDL.** That's post-migration, but the data model should be designed now so the join is cheap.

---

## 3. Sequencing: S3 — ship against JSON now, forward-compatible with SQLite

The SQLite migration is a separate thread and may not land imminently. The views-issue does **not** wait for it. Instead:

- **Land view discovery against the existing JSON artifact** (`schema_<source>.json`).
- **Structure the JSON so it maps 1-to-1 onto the future SQLite schema.** Concretely: a top-level `streams` array, where each entry is a prospective SQLite row carrying `name`, `table_type`, `ddl`, plus columns as a sub-array (or a sibling array keyed by stream).
- **No premature `CREATE TABLE` in this issue.** The SQLite migration will land that and perform a mechanical translation — roughly `INSERT INTO streams SELECT ... FROM json_each(...)`.

This protects the two threads from blocking each other. The views-issue ships value now; the SQLite migration picks up the new fields as columns when it lands.

### What "forward-compatible JSON" rules out

- Nested structures that do not translate cleanly to relational rows (e.g., deeply recursive per-view metadata).
- Fields that duplicate information already represented elsewhere in the row.
- Free-form metadata blobs that would need re-parsing during migration.

---

## Scope confirmed: all five DB-shaped sources

Reinforcing the requirements doc but making the full list explicit — the following sources are all in scope and must have uniform behavior:

| Source        | Current filter                    | Change required                                                                                               |
| ------------- | --------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `postgres`    | `WHERE TABLE_TYPE = 'BASE TABLE'` | Drop filter; capture `TABLE_TYPE`; fetch DDL from `INFORMATION_SCHEMA.VIEWS`                                  |
| `sqlserver`   | `WHERE TABLE_TYPE = 'BASE TABLE'` | Drop filter; capture `TABLE_TYPE`; fetch DDL from `INFORMATION_SCHEMA.VIEWS` or `sys.sql_modules`             |
| `mysql`       | `AND TABLE_TYPE = 'BASE TABLE'`   | Drop filter; capture `TABLE_TYPE`; fetch DDL from `INFORMATION_SCHEMA.VIEWS`                                  |
| `sqlite`      | `WHERE type = 'table'`            | Change to `WHERE type IN ('table', 'view')`; DDL from `sqlite_master.sql`                                     |
| `duckdb_file` | *(no type filter today)*          | Keep broad read; **add** `table_type` classification; DDL from `duckdb_views()` or `information_schema.views` |

The `duckdb_file` entry is handled under the principle **Chesterton's Commit** (see cross-project vault) — it is not a bug, it is inherited pre-convention code. Framing matters: the spec should say "reconcile asymmetry" not "fix bug."

---
