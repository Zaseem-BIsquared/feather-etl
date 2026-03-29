# Parallel Slices Verification — Sonnet Agent

**Date:** 2026-03-28
**Agent:** claude-sonnet-4-6
**Worktree:** agent-ada1cab7

---

## Test Suite Results

### pytest

```
341 passed, 19 warnings in 14.80s
```

All 341 tests pass. The 19 warnings are `PytestUnknownMarkWarning` for `@pytest.mark.unit` in `tests/test_sqlserver.py` — cosmetic, not failures.

### hands_on_test.sh

```
Results: 70 passed, 0 failed
All checks passed.
```

Both baselines are green before feature verification.

---

## Feature Verification

### Feature 1: PostgreSQL Source

**Status:** PARTIAL — discover PASS, run FAIL

**Evidence — discover (PASS):**
```
$ uv run feather discover --config /tmp/feather-pg/feather.yaml

Found 3 table(s):

  erp.customers
    id: integer
    name: text
    city: text
    created_at: timestamp without time zone

  erp.products
    id: integer
    name: text
    category: text
    price: double precision

  erp.sales
    id: integer
    customer_id: integer
    product: text
    amount: double precision
    modified_at: timestamp without time zone
```

`feather discover` correctly lists all 3 tables with their schemas.

**Evidence — run (FAIL):**
```
$ uv run feather run --config /tmp/feather-pg/feather.yaml

Mode: dev
  sales: failure — Conversion Error: Could not convert string '6667be9b7b7332f487fda8f1b45bda02' to INT32
  customers: failure — Conversion Error: Could not convert string '3414f7764ddd17907b77408bbf2fa8bb' to INT32
  products: failure — Conversion Error: Could not convert string '35bc3211baa257e680549166bf951343' to INT32

0/3 tables extracted.
```

**Root Cause:** `state.py` line 49 declares `last_checksum INTEGER` in the `_watermarks` table schema. PostgreSQL's `detect_changes()` uses `md5(string_agg(...))` which returns a 32-character hex string (e.g. `6667be9b...`). When `write_watermark()` passes this hex string as `last_checksum`, DuckDB raises `Conversion Error: Could not convert string '...' to INT32`.

**Fix required:** Change `last_checksum INTEGER` to `last_checksum VARCHAR` in `src/feather/state.py` line 49. (File-based sources store `None` for `last_checksum` so they are unaffected; SQL Server source uses the same MD5 approach and would have the same bug.)

**Config used:**
```yaml
source:
  type: postgres
  connection_string: "dbname=feather_test host=localhost"
destination:
  path: output.duckdb
tables:
  - name: sales
    source_table: erp.sales
    strategy: full
  - name: customers
    source_table: erp.customers
    strategy: full
  - name: products
    source_table: erp.products
    strategy: full
```

---

### Feature 2: Excel Source

**Status:** PASS

**Evidence:**
```
$ uv run feather run --config /tmp/feather-excel/feather.yaml

Mode: dev
  orders: success (5 rows)
  customers: success (4 rows)
  products: success (3 rows)

3/3 tables extracted.
```

Row counts confirmed in output DuckDB:
```
bronze.orders:    5 rows  ✓
bronze.customers: 4 rows  ✓
bronze.products:  3 rows  ✓
```

**Config used:**
```yaml
source:
  type: excel
  path: /Users/siraj/Desktop/NonDropBoxProjects/feather-etl/tests/fixtures/excel_data
destination:
  path: output.duckdb
tables:
  - name: orders
    source_table: orders.xlsx
    strategy: full
  - name: customers
    source_table: customers.xlsx
    strategy: full
  - name: products
    source_table: products.xlsx
    strategy: full
```

---

### Feature 3: JSON Source

**Status:** PASS

**Evidence:**
```
$ uv run feather run --config /tmp/feather-json/feather.yaml

Mode: dev
  orders: success (5 rows)
  customers: success (4 rows)
  products: success (3 rows)

3/3 tables extracted.
```

Row counts confirmed in output DuckDB:
```
bronze.orders:    5 rows  ✓
bronze.customers: 4 rows  ✓
bronze.products:  3 rows  ✓
```

**Config used:**
```yaml
source:
  type: json
  path: /Users/siraj/Desktop/NonDropBoxProjects/feather-etl/tests/fixtures/json_data
destination:
  path: output.duckdb
tables:
  - name: orders
    source_table: orders.json
    strategy: full
  - name: customers
    source_table: customers.json
    strategy: full
  - name: products
    source_table: products.json
    strategy: full
```

---

### Feature 4: --table Filter

**Status:** PASS

**Evidence — single table extraction:**
```
$ uv run feather run --config /tmp/feather-filter/feather.yaml --table customers

Mode: dev
  customers: success (4 rows)

1/1 tables extracted.
```

Confirmed only `bronze.customers` exists in output — `bronze.orders` and `bronze.products` were not created.

**Evidence — nonexistent table error:**
```
$ uv run feather run --config /tmp/feather-filter/feather.yaml --table nonexistent
(exit code 1)

Mode: dev
Table 'nonexistent' not found in config. Available tables: orders, customers, products
```

Error is correctly surfaced with available table names listed.

**Config used:** 3-table CSV config (orders, customers, products from csv_data fixtures).

---

### Feature 5: feather history

**Status:** PASS

**Evidence — full history:**
```
$ uv run feather history --config /tmp/feather-json/feather.yaml

Table                          Status       Rows       Started                      Run ID
----------------------------------------------------------------------------------------------------
products                       success      3          2026-03-28 20:15:28.167758   products_2026-03-28T14:45:28.151338+00:00
customers                      success      4          2026-03-28 20:15:28.122742   customers_2026-03-28T14:45:28.105592+00:00
orders                         success      5          2026-03-28 20:15:28.060015   orders_2026-03-28T14:45:28.039018+00:00
```

**Evidence — --table filter:**
```
$ uv run feather history --config /tmp/feather-json/feather.yaml --table orders

Table                          Status       Rows       Started                      Run ID
----------------------------------------------------------------------------------------------------
orders                         success      5          2026-03-28 20:15:28.060015   orders_2026-03-28T14:45:28.039018+00:00
```

**Evidence — --limit flag:**
```
$ uv run feather history --config /tmp/feather-json/feather.yaml --limit 1

Table                          Status       Rows       Started                      Run ID
----------------------------------------------------------------------------------------------------
products                       success      3          2026-03-28 20:15:28.167758   products_2026-03-28T14:45:28.151338+00:00
```

All three flags (`--table`, `--limit`, default full) work correctly.

---

### Feature 6: Append Strategy

**Status:** PASS

**Evidence:**

Run 1 — source has 5 rows:
```
$ uv run feather run --config /tmp/feather-append/feather.yaml

Mode: dev
  orders: success (5 rows)
```

Source modified — 2 rows appended (7 rows total in CSV).

Run 2 — source has 7 rows:
```
$ uv run feather run --config /tmp/feather-append/feather.yaml

Mode: dev
  orders: success (7 rows)
```

Row count after both runs:
```
Total rows in bronze.orders after 2 append runs: 12
Order IDs: [1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 7]
```

Run 1 inserted rows 1-5. Run 2 inserted all 7 rows from updated source (rows 1-5 again + new rows 6-7). Total = 12, confirming no truncation between runs.

**Config used:**
```yaml
source:
  type: csv
  path: /tmp/feather-append
destination:
  path: output.duckdb
tables:
  - name: orders
    source_table: orders.csv
    strategy: append
```

---

## Summary

| Feature | Status | Notes |
|---------|--------|-------|
| PostgreSQL Source | PARTIAL | `discover` works; `run` fails — `last_checksum` column type is `INTEGER` but PostgreSQL MD5 checksum is a VARCHAR hex string |
| Excel Source | PASS | Correct row counts (5/4/3) |
| JSON Source | PASS | Correct row counts (5/4/3) |
| --table Filter | PASS | Single-table isolation confirmed; nonexistent table gives clear error |
| feather history | PASS | Default, `--table`, and `--limit` all work |
| Append Strategy | PASS | Two runs accumulated 5+7=12 rows; no replacement |

**One bug found:** `src/feather/state.py` line 49: `last_checksum INTEGER` must be `last_checksum VARCHAR` to store the MD5 hex strings returned by `PostgresSource.detect_changes()` (and `SqlServerSource.detect_changes()` uses the same pattern and would fail identically).
