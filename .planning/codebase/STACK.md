# Tech Stack

## Languages & Runtime

- **Python** — `.python-version` specifies **3.14**, `pyproject.toml` requires `>=3.10`
- **SQL** — Transform files in `transforms/silver/*.sql` and `transforms/gold/*.sql` (plain SELECT bodies, DuckDB SQL dialect)
- **Bash** — `scripts/hands_on_test.sh` integration test runner (72 checks)
- Total source: ~6,900 LOC across 24 Python files in `src/feather/`

## Frameworks & Libraries

### Core Framework
- **No web framework** — this is a CLI + library package, not a web app
- **Typer** (`>=0.9`) — CLI framework (`src/feather/cli.py`), provides `feather` command with subcommands: `init`, `validate`, `discover`, `setup`, `run`, `status`, `history`
- **DuckDB** (`>=1.0`) — Primary data engine for both source reading and destination storage
- **PyArrow** (`>=15.0`) — Zero-copy data interchange format between sources and DuckDB destination

### Key Libraries
- **PyYAML** (`>=6.0`) — Config parsing (`feather.yaml` files)
- **pyodbc** (`>=5.0`) — SQL Server / SAP B1 database connectivity (`src/feather/sources/sqlserver.py`)
- **psycopg2-binary** (`>=2.9`) — PostgreSQL connectivity (`src/feather/sources/postgres.py`)
- **APScheduler** (`>=3.10`) — Built-in job scheduling (declared dep, scheduling infra planned)
- **openpyxl** (`>=3.1`) — Excel `.xls` fallback reading (`.xlsx` handled natively by DuckDB excel extension)
- **pytz** — Timezone support (transitive dependency)

### Standard Library Usage (notable)
- `smtplib` + `email.mime.text` — SMTP alerting (`src/feather/alerts.py`)
- `graphlib.TopologicalSorter` — Transform dependency ordering (`src/feather/transforms.py`)
- `hashlib` — MD5 file hashing for change detection, SHA-256 for boundary dedup (`src/feather/sources/file_source.py`, `src/feather/pipeline.py`)
- `string.Template` — Variable substitution in transform SQL (`src/feather/transforms.py`)
- `logging` — JSONL file logging (`feather_log.jsonl`) via `src/feather/pipeline.py`
- `json` — NDJSON output mode, validation JSON, state serialization
- `dataclasses` — All data models (config, results, schemas, drift reports)

## Dependencies

### Production
| Package | Version | Purpose | Used in |
|---------|---------|---------|---------|
| `duckdb` | `>=1.0` | Local analytical DB, file readers (CSV/Excel/JSON/SQLite), destination | `src/feather/destinations/duckdb.py`, all file sources |
| `pyarrow` | `>=15.0` | Data interchange (all extract→load paths) | `src/feather/pipeline.py`, all source connectors |
| `pyyaml` | `>=6.0` | YAML config parsing | `src/feather/config.py`, `src/feather/init_wizard.py` |
| `typer` | `>=0.9` | CLI (depends on `click`) | `src/feather/cli.py` |
| `pyodbc` | `>=5.0` | SQL Server extraction | `src/feather/sources/sqlserver.py` |
| `psycopg2-binary` | `>=2.9` | PostgreSQL extraction | `src/feather/sources/postgres.py` |
| `apscheduler` | `>=3.10` | Job scheduling | Declared, scheduling feature planned |
| `openpyxl` | `>=3.1` | Excel `.xls` fallback | `src/feather/sources/excel.py` (DuckDB excel ext handles `.xlsx`) |
| `pytz` | any | Timezone support | Transitive |

### Development
| Package | Version | Purpose |
|---------|---------|---------|
| `pytest` | `>=8.0` | Test runner (341 tests across 28 test files) |
| `pytest-cov` | `>=5.0` | Code coverage |

## Build & Tooling

- **Package manager:** `uv` (lockfile: `uv.lock`)
- **Build backend:** `hatchling` (configured in `pyproject.toml` `[build-system]`)
- **Build target:** Wheel with `packages = ["src/feather"]`
- **Entry point:** `feather = "feather.cli:app"` (Typer app)
- **No linters/formatters configured** in `pyproject.toml` (no ruff/black/mypy sections)
- **Test runner:** `uv run pytest -q` (unit tests) + `bash scripts/hands_on_test.sh` (integration)
- **Fixture generators:** `scripts/create_*.py` — generate test DuckDB, SQLite, CSV, Excel fixtures

## Configuration

### Config Files
| File | Purpose |
|------|---------|
| `pyproject.toml` | Package metadata, deps, build config, dev deps |
| `uv.lock` | Locked dependency versions |
| `.python-version` | Python 3.14 |
| `feather.yaml` | Per-client pipeline config (source, destination, tables, alerts, schedules) |
| `tables/*.yaml` | Optional split table definitions (auto-merged by config loader) |
| `.env` / `.env.example` | Environment variables for secrets |
| `feather_validation.json` | Written at runtime by `feather validate` |

### Environment Variables
| Variable | Purpose | Used in |
|----------|---------|---------|
| `SQL_SERVER_CONNECTION_STRING` | SQL Server connection | `feather.yaml` via `${...}` |
| `MOTHERDUCK_TOKEN` | MotherDuck cloud auth (planned) | `feather.yaml` via `${...}` |
| `ALERT_EMAIL_USER` | SMTP credentials | `feather.yaml` via `${...}` |
| `ALERT_EMAIL_PASSWORD` | SMTP credentials | `feather.yaml` via `${...}` |
| `FEATHER_MODE` | Override mode (dev/prod/test) | `src/feather/config.py` |

### Mode System
- **`dev`** (default): target defaults to `bronze.*`, all transforms as VIEWs
- **`prod`**: target defaults to `silver.*`, column_map applied at extraction, gold materialized as TABLEs
- **`test`**: like dev but respects `row_limit` for faster test runs
- Resolution order: CLI `--mode` flag → `FEATHER_MODE` env var → YAML `mode:` → default `"dev"`

### Settings Pattern
- Config is parsed into `@dataclass` models in `src/feather/config.py`
- `${ENV_VAR}` substitution via `os.path.expandvars()` applied recursively to all YAML string values
- Paths resolved relative to config file directory, not CWD
- Validation writes `feather_validation.json` sidecar file
