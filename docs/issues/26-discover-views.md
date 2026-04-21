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
