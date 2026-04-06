# Integrations

## Databases

### DuckDB (Destination — Primary)
- **Engine:** DuckDB `>=1.0` (embedded analytical database)
- **Connection pattern:** `duckdb.connect(str(path))` — file-based, no server
- **Two separate DuckDB files per client:**
  - `feather_data.duckdb` — extracted data (bronze/silver/gold schemas)
  - `feather_state.duckdb` — run history, watermarks, DQ results, schema snapshots
- **Schema layout:** `bronze`, `silver`, `gold`, `_quarantine` (created by `DuckDBDestination.setup_schemas()`)
- **Load strategies:** full (atomic swap), incremental (partition overwrite), append (insert-only)
- **ETL metadata columns:** `_etl_loaded_at` (TIMESTAMP), `_etl_run_id` (VARCHAR) added to all loaded tables
- **Connection in:** `src/feather/destinations/duckdb.py`, `src/feather/state.py`
- **Security:** File permissions set to `0o600` on creation (non-Windows)

### DuckDB (Source — File-based)
- **Pattern:** ATTACH source `.duckdb` file as `source_db` in read-only mode
- **Connection in:** `src/feather/sources/duckdb_file.py`
- **Read method:** `ATTACH '{path}' AS source_db (READ_ONLY)` then `SELECT FROM source_db.schema.table`

### SQLite (Source)
- **Access via:** DuckDB `sqlite_scanner` extension (`INSTALL sqlite_scanner; LOAD sqlite_scanner`)
- **Read method:** `sqlite_scan('{path}', '{table}')` — no direct SQLite driver
- **Connection in:** `src/feather/sources/sqlite.py`

### SQL Server (Source)
- **Driver:** `pyodbc` (`>=5.0`)
- **Connection:** `pyodbc.connect(connection_string, timeout=10)`
- **Data path:** `pyodbc cursor → fetchmany(batch_size) → column-oriented dict → PyArrow RecordBatch`
- **Batch size:** 120,000 rows (configurable via `defaults.batch_size`)
- **Change detection:** `CHECKSUM_AGG(BINARY_CHECKSUM(*))` + `COUNT(*)`
- **Type coercion:** `decimal.Decimal` → `float`, `uuid.UUID` → `str` (at extraction time)
- **Connection in:** `src/feather/sources/sqlserver.py`

### PostgreSQL (Source)
- **Driver:** `psycopg2-binary` (`>=2.9`)
- **Connection:** `psycopg2.connect(connection_string, connect_timeout=10)`
- **Data path:** Same as SQL Server: cursor → fetchmany → dict → PyArrow
- **Change detection:** `md5(string_agg(row_to_json(t)::text, '' ORDER BY {pk}))` + `COUNT(*)`
- **PK discovery:** `pg_index` + `pg_attribute` system catalogs
- **Connection in:** `src/feather/sources/postgres.py`

### MotherDuck (Planned — Not Yet Implemented)
- **Planned for V13 (Slice 13)**
- **Mechanism:** DuckDB `ATTACH 'md:{database}?motherduck_token={token}'`
- **Scope:** Gold tables only synced to cloud
- **Config:** `sync.type: motherduck`, `sync.token: "${MOTHERDUCK_TOKEN}"`
- **Referenced in:** `README.md`, `docs/prd.md`, `docs/research.md`

## External APIs

### SMTP Email (Alerting)
- **Library:** Python stdlib `smtplib` + `email.mime.text.MIMEText`
- **Protocol:** SMTP with STARTTLS
- **Config section:** `alerts:` in `feather.yaml` (smtp_host, smtp_port, smtp_user, smtp_password, alert_to, alert_from)
- **No-op pattern:** All alert functions are no-ops if `config is None` (alerts section omitted)
- **Alert severities:**
  - `[CRITICAL]` — pipeline failure, type-changed schema drift (`src/feather/alerts.py:alert_on_failure`)
  - `[WARNING]` — DQ check failure (`src/feather/alerts.py:alert_on_dq_failure`)
  - `[INFO]` — schema drift (added/removed columns) (`src/feather/alerts.py:alert_on_schema_drift`)
- **Connection in:** `src/feather/alerts.py`

### No other external API integrations
- No REST APIs, no webhook calls, no cloud SDKs (beyond planned MotherDuck)
- No Slack, PagerDuty, or third-party notification services

## File I/O

### Files Read (Sources)
| Format | Reader | File in |
|--------|--------|---------|
| CSV (`.csv`) | DuckDB `read_csv()` | `src/feather/sources/csv.py` |
| Excel (`.xlsx`) | DuckDB `read_xlsx()` via excel extension | `src/feather/sources/excel.py` |
| Excel (`.xls`) | DuckDB `read_xlsx()` + openpyxl fallback | `src/feather/sources/excel.py` |
| JSON (`.json`, `.jsonl`) | DuckDB `read_json_auto()` | `src/feather/sources/json_source.py` |
| DuckDB (`.duckdb`) | DuckDB `ATTACH` | `src/feather/sources/duckdb_file.py` |
| SQLite (`.sqlite`) | DuckDB `sqlite_scan()` | `src/feather/sources/sqlite.py` |
| YAML (`.yaml`) | PyYAML `yaml.safe_load()` | `src/feather/config.py` |
| SQL (`.sql`) | `Path.read_text()` | `src/feather/transforms.py` |

### Files Written (Runtime)
| File | Format | Purpose | Written by |
|------|--------|---------|------------|
| `feather_data.duckdb` | DuckDB | Extracted + transformed data | `src/feather/destinations/duckdb.py` |
| `feather_state.duckdb` | DuckDB | Watermarks, run history, DQ results, schema snapshots | `src/feather/state.py` |
| `feather_validation.json` | JSON | Config validation result | `src/feather/config.py:write_validation_json()` |
| `feather_log.jsonl` | NDJSON | Structured pipeline log (append mode) | `src/feather/pipeline.py:_setup_jsonl_logging()` |

### Files Generated (Init Wizard)
| File | Purpose | Generated by |
|------|---------|------------|
| `feather.yaml` | Client config template | `src/feather/init_wizard.py` |
| `pyproject.toml` | Client project dependencies | `src/feather/init_wizard.py` |
| `.gitignore` | Excludes DuckDB files, .env | `src/feather/init_wizard.py` |
| `.env.example` | Credential placeholders | `src/feather/init_wizard.py` |
| `transforms/silver/`, `transforms/gold/` | Transform directories | `src/feather/init_wizard.py` |
| `tables/`, `extracts/` | Optional split config + custom queries | `src/feather/init_wizard.py` |

### CSV Glob Pattern Support
- `source_table` accepts glob patterns (e.g., `sales_*.csv`) for multi-file tables
- Per-file change detection with individual mtime/hash tracking stored as JSON in `_watermarks.last_file_hash`
- Implementation: `src/feather/sources/csv.py:CsvSource`

## Authentication & Security

### Credential Management
- **Pattern:** `${ENV_VAR}` substitution in `feather.yaml` — resolved via `os.path.expandvars()` at config load time
- **Validation:** Unresolved `${VAR}` patterns after expansion raise `ValueError` (prevents running with missing secrets)
- **Env var resolution:** Recursive across all YAML string values (`src/feather/config.py:_resolve_yaml_env_vars()`)
- **No secrets store integration** — relies on environment variables (`.env` files for local dev)

### File Permissions
- DuckDB files (`feather_data.duckdb`, `feather_state.duckdb`) created with `0o600` permissions on Unix
- Implementation: `src/feather/destinations/duckdb.py:DuckDBDestination._connect()`, `src/feather/state.py:StateManager._connect()`

### Database Connections
- SQL Server: connection string passed directly to `pyodbc.connect()` with 10s timeout
- PostgreSQL: connection string passed directly to `psycopg2.connect()` with 10s timeout
- No connection pooling — connections opened/closed per operation
- No TLS configuration beyond what the connection string provides

## Other Integrations

### DuckDB Extensions (Auto-installed at Runtime)
- **`excel`** — `INSTALL excel; LOAD excel;` for `.xlsx`/`.xls` reading (`src/feather/sources/excel.py`)
- **`sqlite_scanner`** — `INSTALL sqlite_scanner; LOAD sqlite_scanner;` for SQLite sources (`src/feather/sources/sqlite.py`)

### CLI Output Modes
- **Human-readable** (default): Typer `echo()` formatted text
- **NDJSON** (`--json` flag): Machine-readable output for automation/scripting (`src/feather/output.py`)

### Logging
- **JSONL file logging:** `feather_log.jsonl` — structured JSON lines with timestamp, level, event, table, status, rows_loaded
- **Python logging module:** `logging.getLogger("feather")` with `FileHandler`
- **Idempotent handler setup:** Guards against duplicate handlers across multiple `run_all()` calls

### State Tables (in `feather_state.duckdb`)
| Table | Purpose |
|-------|---------|
| `_state_meta` | Schema version tracking, feather version |
| `_watermarks` | Per-table watermark values, file hashes, retry state, boundary hashes |
| `_runs` | Full run history with timing, row counts, errors, schema changes |
| `_run_steps` | Granular step-level tracking within runs |
| `_dq_results` | Data quality check results per run |
| `_schema_snapshots` | Column-level schema snapshots for drift detection |

### Retry/Backoff System
- Linear backoff: 15 min × retry_count, capped at 120 min
- Stored in `_watermarks.retry_count` and `_watermarks.retry_after`
- Implementation: `src/feather/state.py:StateManager.increment_retry()`, `should_skip_retry()`

### No Message Queues, Webhooks, or Event Systems
- Pipeline is synchronous, single-process, sequential table extraction
- APScheduler declared as dependency but scheduling feature not yet fully integrated in source
