# feather-etl — Independent Test Plan

You are testing **feather-etl**, a Python ETL tool that extracts data from source databases/files into a local DuckDB warehouse. Your job is to verify every feature works correctly by running the tool and checking the results.

Read the README.md to understand how the tool works. Test fixtures are in `tests/fixtures/`. The CLI entry point is `feather` (run via `uv run feather`).

DO NOT READ source code to understand the functionality. if something is not clear, you should report it back and skip the test so that the docs can be improved. Or show what test you tried writing and what error you got. 
---

## 1. Source Types

Test that feather-etl can extract data from each supported file-based source type:

- **DuckDB file** — Use the `sample_erp.duckdb` fixture. Extract all 4 tables. Verify row counts match the source.
- **CSV** — Use the CSV files in `csv_data/`. Extract all 3 files. Verify data loads correctly.
- **SQLite** — Use the `sample_erp.sqlite` fixture. Extract at least 2 tables. Verify data matches.
- **Large dataset** — Use the `client.duckdb` fixture (real-world ERP data, 11K+ rows). Extract the largest table. Verify the full row count comes through without truncation or error.

**Note:** All loaded tables include two metadata columns (`_etl_loaded_at`, `_etl_run_id`) appended by the destination layer. These are PRD-mandated audit columns present on every row regardless of source type or target schema. Account for them when checking column counts.

## 2. Load Strategies

- **Full strategy** — Extract a table with `strategy: full`. Run it twice. The second run should replace the data completely (not append duplicates).
- **Incremental strategy** — Extract a table that has a timestamp column using `strategy: incremental`. Verify that only new/modified rows are captured on subsequent runs. The `erp.sales` table in `sample_erp.duckdb` has a `modified_at` column suitable for this.

## 3. Change Detection

- **Unchanged source** — Run extraction, then immediately run again without changing anything. The second run should skip all tables (detected as unchanged).
- **Modified source** — Run extraction, modify the source file (add a row), run again. The tool should detect the change and re-extract.

## 4. CLI Commands

Test every CLI command and verify it produces sensible output:

- `feather init` — Scaffold a new client project. Verify the expected directory structure and files are created.
- `feather validate` — Validate a config file. Verify it reports table count, source info, and destination. Also test with an intentionally broken config and verify it produces a clear error.
- `feather discover` — List tables and columns from a source. Verify it shows all available tables with their column names and types.
- `feather setup` — Initialize state DB and schemas. Verify it creates the expected infrastructure without extracting data.
- `feather run` — Extract all configured tables. Verify data lands in the right place with correct row counts.
- `feather status` — Show run history. Verify it shows each table's last status, row count, and timestamp.

## 5. Pipeline Modes

The tool has three modes: `dev`, `prod`, and `test`. Mode is set via `mode:` in the YAML config.

- **Dev mode** (default) — Data should land in the `bronze` schema. All source columns should be extracted. Verify no data appears in `silver`.
- **Prod mode** — Data should land in the `silver` schema. Verify no data appears in `bronze`.
- **Prod mode with column_map** — When a table has a `column_map` defined, prod mode should extract only the mapped columns and rename them. Verify the output table has the renamed columns plus `_etl_loaded_at` and `_etl_run_id` metadata columns, and none of the unmapped source columns.
- **Test mode with row_limit** — When `mode: test` and `defaults.row_limit` is set, each table should extract at most that many rows. Verify the row counts are capped.
- **Dev mode ignores column_map and row_limit** — Even if `column_map` and `row_limit` are configured, dev mode should extract all columns and all rows.

## 6. Mode Override Precedence

The mode can be set in three places. Test that the priority order works:

1. `--mode` CLI flag should override everything
2. `FEATHER_MODE` environment variable should override the YAML value
3. `mode:` in YAML is the baseline default

Test each override by setting a lower-priority source to one mode and a higher-priority source to a different mode, then verify the higher-priority one wins.

## 7. Invalid Mode Handling

- Set an invalid mode value (like `staging`) in the YAML config. Verify the tool rejects it with a clear error message that tells the user where the bad value came from (YAML, env var, or CLI flag).

## 8. SQL Transforms

The tool supports SQL transform files in `transforms/silver/` and `transforms/gold/` directories.

- **Silver transforms** — Create a `.sql` file that selects/renames columns from a bronze table. Verify it creates a queryable view in the silver schema.
- **Gold transforms** — Create a `.sql` file marked `-- materialized: true` that aggregates data from silver. Verify the result is queryable.
- **Dependency ordering** — Gold transforms depend on silver transforms. Verify that the tool executes them in the right order (silver first, then gold).
- **Dev mode** — All transforms (including materialized gold) should be created as views.
- **Prod mode** — Materialized gold transforms should be created as real tables, not views. Verify by checking the table type in `information_schema.tables`.

## 9. Setup Command and Mode

- `feather setup` in dev mode should create both silver and gold transforms as views.
- `feather setup --mode prod` should skip silver transforms entirely (silver is populated by extraction in prod) and create only gold transforms as materialized tables.

## 10. Explicit Target Override

When a table has an explicit `target_table` set in the config, it should always be used regardless of mode. For example, a table with `target_table: bronze.audit` should land in `bronze.audit` even when running in prod mode (which would normally send it to silver).

## 11. Config Validation

- Missing required sections (`source`, `destination`) should produce clear errors.
- Invalid strategy values should be rejected.
- Unresolved environment variables (`${SOME_VAR}` where SOME_VAR is not set) should be caught and reported.

## 12. PostgreSQL Source

Test extraction from a real PostgreSQL database. Requires PostgreSQL running locally (via mise or similar).

**Setup:** Run `uv run python scripts/create_postgres_test_fixture.py` to create the `feather_test` database with `erp` schema (sales: 10 rows, customers: 4 rows, products: 5 rows). Connection string: `dbname=feather_test host=localhost`.

- **Full extraction** — Configure `type: postgres` with `connection_string`. Extract all 3 tables. Verify row counts match source (10, 4, 5).
- **Incremental extraction** — Use `erp.sales` with `strategy: incremental` and `timestamp_column: modified_at`. Run once, insert a new row into PostgreSQL, run again. Verify only the new row appears in the incremental batch.
- **Change detection** — Run extraction twice without modifying source. The second run should skip all tables (detected as unchanged via checksum).
- **Discover** — Run `feather discover`. Verify it lists all tables with column names and types.
- **Column types** — Verify integer, text, float, and timestamp columns map correctly to the DuckDB destination.

**Note:** All loaded tables include `_etl_loaded_at` and `_etl_run_id` metadata columns.

## 13. Excel Source

Test extraction from Excel (.xlsx) files.

- **Full extraction** — Configure `type: excel` with path pointing to `tests/fixtures/excel_data/`. Extract all 3 files (orders.xlsx, customers.xlsx, products.xlsx). Verify row counts (5, 4, 3).
- **Column types** — Verify numeric, text, and boolean columns load correctly.
- **Discover** — Run `feather discover`. Verify it lists all .xlsx files with their column schemas.
- **Change detection** — Run twice without modifying files. Second run should skip (file mtime + MD5 unchanged).
- **Source table naming** — The `source_table` in config must include the `.xlsx` extension (e.g., `orders.xlsx`).

## 14. JSON Source

Test extraction from JSON files.

- **Full extraction** — Configure `type: json` with path pointing to `tests/fixtures/json_data/`. Extract all 3 files (orders.json, customers.json, products.json). Verify row counts (5, 4, 3).
- **Column types** — Verify that numeric, string, and boolean JSON values map to correct DuckDB types.
- **Discover** — Run `feather discover`. Verify it lists all .json files with their column schemas.
- **Change detection** — Works via FileSource base (mtime + MD5), same as CSV.
- **Source table naming** — The `source_table` must include `.json` extension.

## 15. Single-Table Extraction

Test the `--table` flag for `feather run`.

- **Filter to one table** — Configure multiple tables. Run `feather run --table <name>`. Verify only that table is extracted, others are skipped.
- **Unknown table** — Run `feather run --table nonexistent`. Verify clear error message listing available table names and exit code 1.
- **No flag** — Run `feather run` without `--table`. Verify all tables are extracted (existing behavior preserved).

## 16. Run History

Test the `feather history` command.

- **After runs** — Extract some tables, then run `feather history`. Verify it shows a formatted table with run_id, table name, status, rows loaded, and timestamps.
- **Filter by table** — Run `feather history --table <name>`. Verify only runs for that table are shown.
- **Limit** — Run `feather history --limit 5`. Verify at most 5 runs are shown.
- **Empty state** — Run `feather history` before any extraction. Verify it shows "No runs recorded yet."

## 17. Append Strategy

Test the append (insert-only) load strategy.

- **First append** — Configure a table with `strategy: append`. Run extraction. Verify data lands in the target table with `_etl_loaded_at` and `_etl_run_id` metadata columns.
- **Second append with changed source** — Modify the source (add rows), run again. Verify BOTH the original AND new rows exist in the target (not replaced).
- **Unchanged source skip** — Run again without modifying source. Verify the run is skipped (change detection prevents duplicate append).
- **Row accumulation** — After multiple successful appends, verify the total row count equals the sum of all appended batches.

---

## How to Report Results

For each section above, report:
- **PASS** — what you tested and what you observed
- **FAIL** — what you expected vs what actually happened, with the exact error or wrong output
- **SKIP** — if a test couldn't be run, explain why
