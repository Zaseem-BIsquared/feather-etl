# Multi-source pipeline + curation-driven extraction — design

**Issues:** [#8 Support multiple sources per project](https://github.com/siraj-samsudeen/feather-etl/issues/8), [#15 Introduce feather snapshot](https://github.com/siraj-samsudeen/feather-etl/issues/15)
**Depends on:** [#29 Curation manifest schema v2](https://github.com/siraj-samsudeen/feather-etl/issues/29) (validator being built in parallel — pipeline validation rules posted as comment)
**Closes:** #27 (DatabaseSource isinstance refactor)
**Status:** Design approved, ready for implementation planning
**Date:** 2026-04-18

---

## 1. Problem

The config layer already supports `sources:` (list) and `feather discover` handles multi-source + multi-database expansion. But the pipeline (`feather run`) and all other non-discover commands are hard-gated to single-source:

- `_enforce_single_source()` in `_common.py` exits with code 2 for multi-source configs.
- `pipeline.py:run_table()` hardcodes `source = config.sources[0]`.
- `TableConfig` has no field to route a table to its source.

Separately, the `tables:` section in `feather.yaml` requires manual specification of every table to extract. The `discovery/curation.json` manifest (already in use in client projects) captures table selection decisions with richer metadata — strategy, primary key, timestamp, alias, table type — making the YAML `tables:` section redundant.

---

## 2. Scope

**In:**
- Pipeline gains multi-source routing — each table extracts from the correct source.
- `curation.json` replaces `tables:` as the table manifest for `feather run`.
- Source resolution: `source_db` in curation entries resolves against `sources:` in `feather.yaml`.
- Bronze target naming derived from `source_db` + `alias`.
- `_enforce_single_source` gate removed from all commands.
- `_expand_db_sources` extracted to shared utility using `DatabaseSource` base class (closes #27).

**Out:**
- Bronze file strategy / configurable file splitting (#31).
- Configurable layer architecture (#30).
- Silver/gold generation, SCD, mapping table handling (#32, #33, #34, #35).
- Curation manifest JSON Schema validator (#29 — built in parallel).
- Change preview / confirmation UX (deferred to a follow-up on #15).

---

## 3. Summary of decisions

| Area | Decision | Rationale |
|------|----------|-----------|
| Table manifest | `discovery/curation.json` is the sole table source. `tables:` section in feather.yaml removed. | Tables come from discover → curate workflow. Manual YAML tables was interim. |
| Source reference | Each curation entry has `source_db` which resolves against feather.yaml sources' `database:` / `databases:` fields. | Users reference what they declared in `sources:`. Internal naming (`Rama__Gofrugal`) stays internal. |
| Database reference | Explicit `source_db` field in curation.json, not encoded in `source_table`. | Unambiguous. Avoids misparse when schema name looks like a database name. |
| Bronze target naming | `bronze.<source_db>_<alias>` (lowercased, sanitized). | `alias` is human-curated in curation.json. Prefixing with `source_db` prevents collisions across sources. |
| Source resolution | Done in config layer at parse time. | Fail-fast: typos caught before extraction starts. Single validation path for all commands. |
| Backward compat | No fallback to `tables:` section. If `curation.json` missing → error with guidance to run `feather discover`. | Clean cut. Dual-path logic adds complexity for a transition that should be one-time. |
| DuckDB layout | Single DuckDB file, single `bronze` schema. | Cross-source JOINs stay trivial. Configurable splitting deferred to #31. |
| `_expand_db_sources` | Extracted to `src/feather_etl/sources/expand.py`, uses `DatabaseSource` base class. | Shared between discover and pipeline. Closes #27. |

---

## 4. User-facing contract

### feather.yaml (simplified)

```yaml
sources:
  - name: Rama
    type: sqlserver
    host: ${SQLSERVER_HOST}
    databases: [Gofrugal, Portal, SAP, ZAKYA]

  - name: RamaMySQL
    type: mysql
    host: ${MYSQL_HOST}
    databases: [allinc_stg, allsrc_stg, allzak_stg, core_db]

destination:
  path: ./feather_data.duckdb

# No tables: section — tables come from discovery/curation.json
```

### discovery/curation.json (v2 — table manifest)

Each entry with `decision: "include"` is extracted. Fields consumed by the pipeline:

| Field | Pipeline use |
|---|---|
| `source_db` | Resolves to the correct source + database |
| `source_table` | Passed to `source.extract()` |
| `decision` | Only `"include"` entries are extracted |
| `strategy` | `full`, `incremental`, or `append` |
| `primary_key` | Passed to pipeline for dedup / boundary detection |
| `timestamp.column` | Watermark column for incremental extraction |
| `alias` | Used to derive bronze target: `bronze.<source_db>_<alias>` |

All other v2 fields (`table_type`, `grain`, `scd`, `mapping`, `load_contract`, `dq_policy`) are parsed but not consumed by the bronze pipeline — they are reserved for future silver/gold generators.

### Source resolution rules

| Scenario | Behavior |
|---|---|
| `source_db` matches a source's `database:` field | Use that source |
| `source_db` is in a source's `databases:` list | Create a scoped source instance with that database |
| `source_db` matches no source | Validation error |
| `source_db` matches multiple sources | Validation error (ambiguous) |
| File sources (no `database` concept) | `source_db` matches the source `name` directly (e.g., source named `"erp"` with `type: duckdb` → curation uses `source_db: "erp"`) |

### CLI

No new commands. Existing commands work unchanged:

- `uv run feather run` — extracts all `include` tables from curation.json across all sources
- `uv run feather run --table gofrugal_sales` — extract single table by bronze name
- `uv run feather status`, `uv run feather setup` — gate removed, work with multi-source

---

## 5. Integration surface

### Files that change

| File | Change | Risk |
|---|---|---|
| `config.py` | Add curation.json loader. `TableConfig` gains `source` + `database` fields. Source resolution logic. Remove `tables:` parsing. | Medium — core change |
| `pipeline.py` | `run_table()` accepts source as parameter instead of `sources[0]`. | Low — mechanical |
| `commands/_common.py` | Remove `_enforce_single_source()`. | Low — deleting code |
| `commands/run.py` | Remove gate call. Adapt table filter for curation-derived names. | Low |
| `commands/setup.py`, `status.py` | Remove gate call. | Low |
| `commands/discover.py` | Extract `_expand_db_sources` to shared utility. | Low — moving code |

### New files

| File | Purpose |
|---|---|
| `curation.py` | Load `discovery/curation.json`, filter to `include`, resolve `source_db` → source, produce `TableConfig` list. |
| `sources/expand.py` | Shared `_expand_db_sources` using `DatabaseSource` base class. Used by discover and pipeline. |

---

## 6. Task breakdown

| # | Task | Why / Risk |
|---|---|---|
| 1 | Extract `_expand_db_sources` to shared utility, use `DatabaseSource` base class | Prerequisite for pipeline source scoping. Closes #27. |
| 2 | Add `source` and `database` fields to `TableConfig` | Pipeline needs to know which source each table belongs to. Additive, backward-safe. |
| 3 | Build curation.json loader (`curation.py`) | Core new module. Parses manifest, filters to include, resolves source_db, produces TableConfig list. |
| 4 | Wire curation loader into `load_config()` | Config layer reads curation.json as the sole table source. Remove `tables:` parsing. |
| 5 | Update `run_table()` to accept source as parameter | Remove `sources[0]` hardcode. |
| 6 | Remove `_enforce_single_source` from all commands | Unlocks multi-source for run, setup, status. |
| 7 | End-to-end tests with file-based multi-source | Prove multi-source extraction works using DuckDB + SQLite + CSV as sources. No database server dependencies (requires client VPN). |

### Dependency chain

```
Task 1 (expand utility) ──┐
Task 2 (TableConfig fields) ──┼──→ Task 3 (curation loader) ──→ Task 4 (wire into load_config)
                               │
                               └──→ Task 5 (run_table param) ──→ Task 6 (remove gates)
                                                                          │
                                                                  Task 7 (e2e tests)
```

Tasks 1 and 2 are independent (parallel). Task 3 depends on both. Tasks 5 and 6 can start after Task 2. Task 7 validates the full integration.

---

## 7. Done signal

```bash
# From a test project directory with:
#   feather.yaml — 2+ file-based sources (e.g., DuckDB + SQLite + CSV), no tables: section
#   discovery/curation.json — include entries across multiple source_dbs

uv run feather run

# Output shows tables extracted from different file sources into bronze:
#   erp_orders: success (12 rows)
#   erp_customers: success (5 rows)
#   csvdata_products: success (10 rows)

uv run pytest -q   # all tests pass
```

---

## 8. Related issues

| Issue | Relationship |
|---|---|
| #8 | Core of this design — multi-source pipeline routing |
| #15 | Curation-driven extraction (snapshot) |
| #27 | Closed by Task 1 — DatabaseSource isinstance refactor |
| #29 | Parallel — validator enforces rules pipeline depends on (comment posted) |
| #31 | Future — bronze file strategy builds on this foundation |
| #30 | Future — layer architecture builds on this foundation |
| #18 | Naturally addressed — curation entries target bronze only |
