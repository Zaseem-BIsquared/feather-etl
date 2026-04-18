# MySQL Source — Design Spec

**Issue:** #25 — Support Extraction from MySQL DB
**Date:** 2026-04-18
**Status:** APPROVED

## Scope & Boundaries

**In:** A new `mysql` source type that extracts tables from MySQL databases into DuckDB, following the same pattern as Postgres/SQL Server. Includes YAML config parsing (`from_yaml`), connectivity check, table discovery, schema introspection, extraction with filtering/watermarks, change detection, multi-database listing, and registry integration. Unit tests + integration tests (gated behind `pytest.mark.mysql`).

**Out:** No MySQL-specific features beyond what Postgres already supports — no stored procedure extraction, no replication-based CDC, no SSL configuration beyond what `connection_string` allows. View discovery is tracked separately (#26).

## User-Facing Contract

New YAML config shape:

```yaml
sources:
  - name: my_erp
    type: mysql
    host: localhost
    port: 3306          # optional, default 3306
    user: root
    password: secret
    database: erp_db
```

Alternative: `connection_string:` for raw connection strings. `databases:` list for multi-DB discovery (XOR with `database:`). Table names are unqualified (`erp_sales`), database set at source level. All patterns identical to Postgres/SQL Server — no new concepts for users.

## Integration Surface

| File | Change | Risk |
|---|---|---|
| `src/feather_etl/sources/mysql.py` | **New file** — `MySQLSource` class | None (new code) |
| `src/feather_etl/sources/registry.py` | One line added to `SOURCE_CLASSES` dict | Minimal |
| `pyproject.toml` | One line added to `dependencies` | Minimal |
| `tests/test_mysql.py` | **New file** — unit + integration tests | None (new code) |

Only 2 existing files get single-line edits. Low blast radius.

## Task Breakdown

### Task 1: Add `mysql-connector-python` dependency

- **What:** Add `mysql-connector-python>=8.0` to `pyproject.toml` dependencies, run `uv sync`.
- **Why/Risk:** Required for MySQL connectivity. Risk: version conflicts — mitigated by `>=8.0` floor (widely compatible).
- **TDD test:** `import mysql.connector` succeeds.
- **Code:** One line in `pyproject.toml`.

### Task 2: Implement `MySQLSource` core — `from_yaml`, `check`, `validate_source_table`

- **What:** Create `mysql.py` with config parsing, connectivity check, and source_table validation.
- **Why/Risk:** Foundation for all other methods. Risk: `mysql-connector-python` uses keyword args (not DSN strings like psycopg2) — handled via `_connect_kwargs` dict and `_connect()` helper.
- **TDD test:** `from_yaml` builds correct connection params from host/port/user/password/database; enforces database/databases XOR; `check()` returns True/False with monkeypatched connector.
- **Code:** `MySQLSource` class extending `DatabaseSource`, `from_yaml` classmethod, `check()` method, `_connect()` helper.

### Task 3: Implement `discover`

- **What:** Query `INFORMATION_SCHEMA.TABLES` to list base tables in the connected database.
- **Why/Risk:** Enables `feather discover`. Risk: MySQL returns all databases in INFORMATION_SCHEMA — must filter with `TABLE_SCHEMA = database`.
- **TDD test:** Integration: `discover()` returns the 3 `erp_*` tables from `feather_test` with correct column info.
- **Code:** `discover()` method querying `INFORMATION_SCHEMA.TABLES` + `INFORMATION_SCHEMA.COLUMNS`.

### Task 4: Implement `get_schema`

- **What:** Query `INFORMATION_SCHEMA.COLUMNS` for a given table's column names and types.
- **Why/Risk:** Enables schema viewer. Risk: minimal — standard INFORMATION_SCHEMA query.
- **TDD test:** Integration: `get_schema("erp_sales")` returns expected columns (`id`, `customer_id`, `product`, `amount`, `modified_at`).
- **Code:** `get_schema()` method.

### Task 5: Implement `extract` with type mapping

- **What:** SELECT → chunked fetch → PyArrow Table, with column/filter/watermark support.
- **Why/Risk:** The core ETL operation. Risk: MySQL `cursor.description` type codes differ from Postgres — need `FieldType` constant → PyArrow mapping. `Decimal` values need float coercion.
- **TDD test:** Integration: `extract("erp_sales")` returns 10 rows with correct columns; `extract("erp_sales", filter="amount > 150")` returns filtered subset; watermark extract returns only newer rows.
- **Code:** `extract()` method + `_MYSQL_FIELD_TYPE_MAP` dict + `_MYSQL_INFO_SCHEMA_TYPE_MAP` dict.

### Task 6: Implement `detect_changes`

- **What:** Change detection to skip unchanged tables.
- **Why/Risk:** Enables skip-unchanged optimization. Risk: MySQL lacks Postgres's `row_to_json` — use `CHECKSUM TABLE` (MySQL built-in) instead.
- **TDD test:** Integration: first_run → changed; same state fed back → unchanged; incremental strategy → always changed.
- **Code:** `detect_changes()` method using `CHECKSUM TABLE`.

### Task 7: Implement `list_databases`

- **What:** List user databases on the server, excluding system DBs.
- **Why/Risk:** Enables multi-database discovery via `databases:` YAML key. Risk: minimal — `SHOW DATABASES` is standard MySQL.
- **TDD test:** Unit (mocked): returns user DBs, excludes `information_schema`, `mysql`, `performance_schema`, `sys`. Propagates connector errors.
- **Code:** `list_databases()` method using `SHOW DATABASES`.

### Task 8: Register in registry

- **What:** Add `"mysql"` entry to `SOURCE_CLASSES` in `registry.py`.
- **Why/Risk:** Makes `type: mysql` work in YAML. Risk: none — one-line addition, lazy import.
- **TDD test:** `get_source_class("mysql") is MySQLSource`.
- **Code:** One dict entry in `registry.py`.

## Dependency Chain

```
Task 1 (dependency) → Task 2 (core) → Task 3 (discover)
                                     → Task 4 (get_schema)
                                     → Task 5 (extract)
                                     → Task 6 (detect_changes)
                                     → Task 7 (list_databases)
                      Task 8 (registry) — anytime after Task 2
```

Tasks 3–7 are independent of each other, all depend on Task 2.

## Done Signal

```bash
uv run pytest tests/test_mysql.py -v   # all unit + integration tests pass
uv run pytest -q                        # full suite still green (582+ passed)
```

## Key MySQL vs Postgres Differences

| Concern | Postgres | MySQL |
|---|---|---|
| Default port | 5432 | 3306 |
| Default schema | `public` | n/a (database = schema) |
| System schemas to exclude in `discover()` | `pg_catalog`, `information_schema` | n/a (filter by `TABLE_SCHEMA = database`) |
| Change detection | `md5(string_agg(row_to_json(...)))` | `CHECKSUM TABLE` |
| Watermark formatting | ISO passthrough | ISO passthrough |
| Connection API | DSN string | Keyword args dict |
| `list_databases()` | `pg_database` catalog | `SHOW DATABASES` |
| Parameter placeholder | `%s` | `%s` (same) |
| Driver | psycopg2 | mysql-connector-python |
