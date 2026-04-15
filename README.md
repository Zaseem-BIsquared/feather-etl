# feather-etl

A config-driven Python ETL platform for deploying data pipelines across multiple clients with heterogeneous ERP source systems — SQL Server, SAP B1, SAP S4 HANA, and custom Indian ERPs.

feather-etl is the entire data platform for clients who have none. For clients who already have a data warehouse, it is a lightweight extraction and local transform layer that feeds only clean, curated gold tables to the cloud.

## Why feather-etl?

Enterprise ETL stacks (dlt + dbt/SQLMesh + Dagster) introduce a complexity tax — hundreds of transitive dependencies, proprietary abstractions, steep learning curves — that makes them unsuitable for Indian SMBs who need a working data pipeline, not a data engineering career.

feather-etl replaces the full stack with a single Python package (~1,200 LOC, 7 dependencies), deployable by a small team, configurable in YAML, and understandable by anyone who can read SQL.

| Heavy Stack | feather-etl equivalent |
|------------|----------------------|
| dlt (extraction) | `sources/` — Protocol-based connectors |
| dbt / SQLMesh (transforms) | Plain `.sql` files executed in local DuckDB |
| Dagster / Airflow (orchestration) | APScheduler + CLI |
| 3 tools, hundreds of deps | 1 package, 7 deps |

## Design Principles

- **Multi-client by design** — Each client is an independent `feather.yaml`. Same package, different config. One team deploys across dozens of clients.
- **Config-driven** — YAML defines sources, tables, schedules, transforms. Adding a table means editing YAML, not writing Python.
- **Local-first** — Extract and transform in local DuckDB (free compute). Push only gold tables to MotherDuck (minimal cloud cost).
- **Layers are optional** — Skip bronze for SMB clients who don't need it. Use bronze as a dev cache or compliance audit trail when you do.
- **Testable** — Full pipeline testable end-to-end with file-based sources. No mocking needed for core pipeline tests.
- **Package-first** — Reusable library. Client projects import and configure it. The v2 connector library (`feather-connectors`) will provide canonical silver mappings per ERP system — reusable across all clients on the same source.

## Layer Model

```
Source ERP (SQL Server / SAP B1 / SAP S4 HANA / custom)
    |
    v  column_map applied (zero-copy rename + select)
    |
Local DuckDB
    |
    |-- bronze  (optional)
    |     Raw ERP data, all columns.
    |     Use as dev cache (iterate transforms without hitting source DB)
    |     or compliance audit trail (strategy: append, insert-only).
    |
    |-- silver  (primary working layer)
    |     Canonical names, selected columns, light cleaning.
    |     Always views — lazy, always current, no pipeline step.
    |     Client analysts + LLM agents work here.
    |
    |-- gold    (dashboard layer)
    |     KPIs, aggregations, denormalized tables.
    |     Views by default; materialized tables where performance requires.
    |     Only layer synced to MotherDuck.
    |
    v  (optional sync)
MotherDuck → Rill Data / BI tools
```

## Supported Sources

| Source | Reader | Change Detection | Incremental |
|--------|--------|-----------------|-------------|
| CSV | `read_csv()` | mtime + MD5 hash | — |
| DuckDB file | ATTACH | mtime + MD5 hash | ✓ |
| SQLite | `sqlite_scan()` | mtime + MD5 hash | ✓ |
| Excel `.xlsx` | `read_xlsx()` (excel ext) | mtime + MD5 hash | — |
| Excel `.xls` | openpyxl fallback | mtime + MD5 hash | — |
| JSON | `read_json()` | mtime + MD5 hash | — |
| SQL Server | pyodbc → PyArrow | CHECKSUM_AGG + COUNT(*) | ✓ |
| PostgreSQL | psycopg2 → PyArrow | md5(row_to_json) + COUNT(*) | ✓ |

**CSV note:** `source_table` must include the `.csv` extension (e.g., `orders.csv` not `orders`).

**Change detection** is file-level — for multi-table sources like DuckDB, modifying any table in the file triggers re-extraction of all tables from that file.

New sources: implement the `Source` Protocol (~30 lines for file sources, ~80 lines for database sources) and register in the source registry.

## Load Strategies

| Strategy | Behavior | When to use |
|----------|----------|-------------|
| `full` | Atomic swap (drop + recreate) | Small reference tables, no history needed |
| `incremental` | Partition overwrite (delete + insert on watermark window) | Large transactional tables |
| `append` | Insert only, never delete | Audit trail, compliance, full history |

All three strategies are idempotent — safe to re-run after partial failures.

## This Repo vs Client Projects

**feather-etl** (this repo) is a Python package only — no client config, no client data. See [Installation](#installation) for install options.

Each client lives in its own GitHub repository, scaffolded with `feather init`:

```bash
feather init client-abc
# → creates client-abc/ with feather.yaml, pyproject.toml, .gitignore, .env.example
# → creates transforms/silver/, transforms/gold/, tables/, extracts/ directories
```

## Installation

> The PyPI package is named `feather-etl`; the installed command is `feather`.

### Recommended — global CLI tool

For most users (scaffolding clients, running pipelines locally), install feather-etl as a global `uv` tool:

```bash
uv tool install feather-etl
feather --help
```

Upgrade or pin to a specific version:

```bash
uv tool upgrade feather-etl
uv tool install feather-etl@X.Y.Z
```

### Alternative — project dependency

For teams that need per-project version pinning or reproducibility, add feather-etl to a client project's `pyproject.toml`:

```bash
uv add feather-etl
uv run feather --help
```

Every command then runs via `uv run feather …`.

### One-off — no install

Run any feather command without installing, using `uvx`:

```bash
uvx feather-etl init client-abc     # scaffold a new client
uvx feather-etl validate            # validate a config
uvx feather-etl run                 # run the pipeline
```

`uvx` downloads feather-etl into a throwaway environment for each invocation, so nothing is left on your PATH and there's no `feather` command afterwards — every call must be prefixed with `uvx feather-etl …`. Good for CI, quick trials, and scaffolding the very first client. For day-to-day use, prefer the global install above.

## CLI

```bash
# New client setup
feather init client-abc                # scaffold a new client project directory

# Configuration
feather validate                       # validate config, resolve paths — no execution
feather discover                       # discover source schema, write JSON, and auto-open the bundled schema viewer
feather view [PATH] [--port 8000]      # serve an existing schema output folder manually

# Pipeline operations
feather setup                          # init state DB + schemas + apply transforms (optional — run creates them automatically)
feather run                            # run all tables
feather run --table sales              # run a single table only
feather status                         # last run status per table (all-time history)
feather history                        # show run history (recent runs, filterable)
```

All commands accept `--config PATH` (default: `feather.yaml`). `run` and `setup` accept `--mode dev|prod|test` to override the config mode. `history` accepts `--table` and `--limit`.

**Note:** `feather setup --mode prod` applies gold transforms as materialized tables, which requires bronze/silver data to already exist. Run `feather run` first, then `feather setup --mode prod` to materialize gold.

### Browsing a source schema

Primary flow:

`feather discover` discovers the source schema, writes an auto-named `schema_*.json` in the current working directory, and auto-serves/opens the bundled schema viewer.

```bash
feather discover
```

It uses the schema output directory as the viewer root, prefers port `8000` first, and falls back automatically if that port is busy.

Manual hosting is still possible when you want to serve an existing schema folder yourself:

```bash
feather view
feather view ./schemas
feather view ./schemas --port 8010
```

`feather view` serves an existing directory, so the path must already exist. It uses the same smart port selection as discover: prefer the requested port, then fall back automatically if needed.

## Client Project Layout

`feather init` generates this structure (one repo per client):

```
client-abc/                         # separate GitHub repo per client
├── .gitignore                      # excludes *.duckdb, .env
├── pyproject.toml                  # depends on feather-etl
├── .env.example                    # credential placeholders
├── feather.yaml                    # source, destination, sync, schedules, alerts
├── tables/                         # optional — split by domain
│   ├── sales.yaml
│   └── inventory.yaml
├── transforms/
│   ├── silver/                     # canonical mapping views
│   │   └── sales_invoice.sql       # -- depends_on: (none)
│   └── gold/                       # client-specific output
│       └── sales_summary.sql       # -- materialized: true
└── extracts/                       # optional — custom source SELECT queries
    └── sales_invoice.sql
```

`feather_state.duckdb` and `feather_data.duckdb` are created at runtime, gitignored.

## Configuration

### SMB client — silver-direct (no bronze)

Small clients land data directly into silver with column selection at extraction time. No bronze layer needed.

```yaml
source:
  type: sqlserver
  connection_string: "${SQL_SERVER_CONNECTION_STRING}"

destination:
  path: ./feather_data.duckdb

sync:
  type: motherduck
  token: "${MOTHERDUCK_TOKEN}"
  database: "client_analytics"

alerts:
  smtp_host: "smtp.gmail.com"
  smtp_port: 587
  smtp_user: "${ALERT_EMAIL_USER}"
  smtp_password: "${ALERT_EMAIL_PASSWORD}"
  alert_to: "operator@example.com"

schedule_tiers:
  hot: "twice daily"
  cold: weekly

tables:
  - name: sales_invoice
    source_table: dbo.SALESINVOICE
    target_table: silver.sales_invoice
    strategy: incremental
    timestamp_column: ModifiedDate
    schedule: hot
    primary_key: [ID]
    column_map:                       # select 8 of 120 columns, rename to canonical
      ID: invoice_id
      SI_NO: invoice_no
      Custome_Code: customer_code
      NetAmount: net_amount
      ModifiedDate: modified_date
    quality_checks:
      not_null: [invoice_id, customer_code]
```

### Enterprise client — bronze + append (compliance)

```yaml
tables:
  - name: sales_invoice
    source_table: dbo.SALESINVOICE
    target_table: bronze.sales_invoice   # raw, all columns
    strategy: append                     # insert-only, full audit trail
    timestamp_column: ModifiedDate
    schedule: hot
    primary_key: [ID]
```

Silver views over bronze live in `transforms/silver/sales_invoice.sql`. Transform files contain only the SELECT query — the system wraps it in the appropriate `CREATE OR REPLACE VIEW` or `CREATE OR REPLACE TABLE` DDL based on mode and the `-- materialized` flag:

```sql
-- depends_on: (none — reads from bronze directly)
SELECT
    ID           AS invoice_id,
    SI_NO        AS invoice_no,
    Custome_Code AS customer_code,
    NetAmount    AS net_amount,
    ModifiedDate AS modified_date,
    _etl_loaded_at,
    _etl_run_id
FROM bronze.sales_invoice
```

### Table splitting (large deployments)

```
client-project/
├── feather.yaml
└── tables/
    ├── sales.yaml       # 8 sales tables
    ├── inventory.yaml   # 6 inventory tables
    └── hr.yaml          # 4 HR tables
```

feather-etl auto-discovers and merges all `.yaml` files in the `tables/` directory.

## Transform Dependencies

Declare dependencies with a SQL comment — the system builds the execution order automatically:

```sql
-- depends_on: silver.sales_invoice
-- depends_on: silver.customer_master
-- materialized: true
SELECT ...
FROM silver.sales_invoice si
JOIN silver.customer_master cm ON si.customer_code = cm.customer_code
```

Transform files contain only the SELECT body plus header comments. The system generates the DDL: silver transforms become VIEWs, gold transforms with `-- materialized: true` become TABLEs in prod mode (VIEWs in dev/test).

## Dependencies

| Package | Purpose |
|---------|---------|
| duckdb | Local processing, file readers, MotherDuck sync |
| pyarrow | Zero-copy data interchange |
| pyyaml | Config parsing |
| typer | CLI |
| pyodbc | SQL Server / SAP B1 extraction |
| apscheduler | Built-in scheduling |
| openpyxl | Excel `.xls` fallback (`.xlsx` handled natively by DuckDB) |

Alerting uses Python stdlib `smtplib` — no extra dependency.

## Alerting

SMTP email via Python stdlib — works with Gmail, any corporate SMTP relay, or transactional email services. No Slack account, no webhook setup.

| Severity | Trigger |
|----------|---------|
| `[CRITICAL]` | Pipeline failure, load error, type cast quarantine |
| `[WARNING]` | DQ check failure, schema drift |
| `[INFO]` | Schema drift (informational) |

No-op if `alerts` section is not configured.

## Observability

Every run is recorded in `feather_state.duckdb`:

```sql
-- What happened in the last 24 hours?
SELECT table_name, status, rows_extracted, rows_loaded, duration_sec
FROM _runs
WHERE started_at > now() - INTERVAL 1 DAY
ORDER BY started_at DESC;

-- Any DQ failures?
SELECT * FROM _dq_results WHERE result = 'fail';

-- Schema drift detected?
SELECT table_name, schema_changes FROM _runs
WHERE schema_changes IS NOT NULL;
```

## Documentation

- [PRD v1.5](docs/prd.md) — Full requirements, EARS spec, design decisions
- [Research](docs/research.md) — Design research synthesis from 7 research agents

## Roadmap

**v1 (current):** Core pipeline — extraction, loading (full/incremental/append), silver/gold transforms, scheduling, DQ checks, schema drift detection, SMTP alerts, state management.

**v2:** `feather-connectors` — canonical silver transform library for SAP B1, SAP S4 HANA, and common Indian ERPs. Reuse silver mappings across all clients on the same source system.

**v3+:** LLM agent interface for client analysts — last-mile dashboard customisation guided by AI, working against the canonical silver layer.

## Status

**Pre-alpha** — Architecture complete, implementation starting. See [PRD](docs/prd.md) for the full feature roadmap (25 features across 5 phases).

## License

MIT
