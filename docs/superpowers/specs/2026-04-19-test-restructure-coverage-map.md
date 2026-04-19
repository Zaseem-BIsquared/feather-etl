# Coverage map: scripts/hands_on_test.sh → pytest

Companion to [`2026-04-19-test-restructure-design.md`](2026-04-19-test-restructure-design.md).

This document is the **hard gate** before `scripts/hands_on_test.sh` is
deleted in Wave E. Every numbered check in the bash script must have a
non-empty `Pytest test path`. The gate check in the done-signal is:

```bash
# After Wave E, both must produce no output.
grep -E "^\| S[^|]+\|[^|]+\|\s*\|" docs/superpowers/specs/2026-04-19-test-restructure-coverage-map.md
```

Wave A seeds the table header only. Rows are filled incrementally during
Waves B/C/D as tests are migrated, and audited one-by-one during Wave E.

## Bash stage counts

The script has 61 distinct `check "..."` calls across 19 stages (`S1`, `S2`,
`S3`, `S5`–`S22`, and `S-INCR-1` through `S-INCR-8`; `S4` and `S16` (no `a`)
are intentionally absent from the script). The row count below is 61.

| Bash check ID | What it asserts | Pytest test path |
|---|---|---|
| S1.1 | `feather.yaml created` | tests/e2e/test_01_scaffold.py::test_scaffolds_project |
| S1.2 | `pyproject.toml created` | tests/e2e/test_01_scaffold.py::test_scaffolds_project |
| S1.3 | `.gitignore created` | tests/e2e/test_01_scaffold.py::test_scaffolds_project |
| S1.4 | `.env.example created` | tests/e2e/test_01_scaffold.py::test_scaffolds_project |
| S1.5 | `init on non-empty dir exits non-zero` | tests/e2e/test_01_scaffold.py::test_init_nonempty_dir_fails |
| S1.6 | `init '.' uses directory name in pyproject.toml` | tests/e2e/test_01_scaffold.py::test_init_dot_uses_cwd_name |
| S2.1 | `validate succeeds with 3 tables` | tests/e2e/test_02_validate.py::test_valid_config \| tests/integration/test_integration.py::TestClientFixtureEdgeCases::test_all_six_icube_tables |
| S2.2 | `feather_validation.json written` | tests/e2e/test_02_validate.py::test_valid_config \| tests/unit/test_config.py::TestValidationJson::test_writes_on_success |
| S2.3 | `feather_validation.json content correct` | tests/unit/test_config.py::TestValidationJson::test_writes_on_success \| tests/e2e/test_02_validate.py::test_validate_json_outputs_json |
| S3.1 | `validate fails when source missing` | tests/unit/test_config.py::TestConfigValidation::test_missing_source_path_for_file_source \| tests/integration/test_validate.py::test_returns_all_ok_false_when_any_source_check_fails |
| S3.2 | `validate rejects invalid strategy` | tests/unit/test_config.py::TestConfigValidation::test_bad_strategy |
| S3.3 | `validate rejects unimplemented source type (excel)` | tests/unit/test_config.py::TestConfigValidation::test_bad_source_type \| tests/unit/test_config.py::TestConfigValidationExtended::test_unregistered_source_type_rejected |
| S3.4 | `validate rejects target_table without schema prefix` | tests/unit/test_config.py::TestConfigValidation::test_bad_target_schema_prefix \| tests/integration/test_integration.py::TestValidationGuards::test_target_table_requires_schema_prefix |
| S3.5 | `validate rejects hyphenated target_table` | tests/integration/test_integration.py::TestValidationGuards::test_hyphenated_target_table_rejected |
| S5.1 | `setup creates feather_state.duckdb` | tests/e2e/test_04_extract_full.py::test_setup_creates_state_and_schemas \| tests/integration/test_setup.py::test_initializes_state_db_and_destination |
| S5.2 | `run: 3/3 tables succeed` | tests/e2e/test_04_extract_full.py::test_full_onboarding_flow \| tests/integration/test_integration.py::TestSampleErpFullPipeline::test_run_all_succeeds |
| S5.3 | `run creates feather_data.duckdb` | tests/e2e/test_04_extract_full.py::test_full_onboarding_flow \| tests/integration/test_integration.py::TestSampleErpFullPipeline::test_row_counts_in_bronze |
| S5.4 | `row counts correct: sales_invoice=11676 customer=1339 inv_group=66` | tests/e2e/test_04_extract_full.py::test_full_onboarding_flow \| tests/integration/test_integration.py::TestClientFixtureEdgeCases::test_all_six_icube_tables |
| S5.5 | `_etl_loaded_at and _etl_run_id metadata columns present` | tests/integration/test_integration.py::TestSampleErpFullPipeline::test_etl_metadata_columns_added \| tests/integration/test_pipeline.py::test_data_has_etl_metadata |
| S5.6 | `second run (idempotency): all tables skipped (unchanged)` | tests/e2e/test_04_extract_full.py::test_full_onboarding_flow \| tests/integration/test_pipeline.py::test_second_run_skips_unchanged \| tests/integration/test_integration.py::TestSampleErpFullPipeline::test_idempotency |
| S5.7 | `status shows sales_invoice` | tests/e2e/test_14_status.py::test_shows_status_after_run \| tests/e2e/test_04_extract_full.py::test_full_onboarding_flow |
| S5.8 | `status shows skipped (after idempotent re-run)` | tests/e2e/test_04_extract_full.py::test_full_onboarding_flow |
| S6.1 | `good table succeeds despite bad table` | tests/integration/test_integration.py::TestErrorIsolation::test_good_table_succeeds_despite_bad_table \| tests/integration/test_pipeline.py::test_failed_table_doesnt_stop_others |
| S6.2 | `bad table shows failure` | tests/integration/test_integration.py::TestErrorIsolation::test_good_table_succeeds_despite_bad_table \| tests/e2e/test_04_extract_full.py::test_run_with_bad_table_shows_failure |
| S6.3 | `summary shows 1/2` | tests/integration/test_pipeline.py::test_failed_table_doesnt_stop_others \| tests/integration/test_integration.py::TestErrorIsolation::test_partial_failure_still_writes_good_table_to_bronze |
| S6.4 | `exit code non-zero on partial failure` | tests/e2e/test_04_extract_full.py::test_run_with_bad_table_shows_failure \| tests/e2e/test_04_extract_full.py::test_backoff_skipped_table_exits_nonzero |
| S6.5 | `error_message stored in _runs` | tests/integration/test_integration.py::TestErrorIsolation::test_failure_error_message_stored_in_state \| tests/e2e/test_14_status.py::test_status_shows_error_message_for_failures |
| S7.1 | `run without setup creates both DBs` | tests/e2e/test_04_extract_full.py::test_run_without_setup_auto_creates_state_and_data |
| S8.1 | `sample_erp: 3/3 tables succeed` | tests/integration/test_integration.py::TestSampleErpFullPipeline::test_run_all_succeeds |
| S8.2 | `NULL stock_qty passes through correctly` | tests/integration/test_integration.py::TestSampleErpFullPipeline::test_null_passthrough \| tests/integration/test_integration.py::TestSampleErpFixture::test_fixture_null_in_products |
| S8.3 | `sample_erp row counts: orders=5 customers=4 products=3` | tests/integration/test_integration.py::TestSampleErpFullPipeline::test_row_counts_in_bronze \| tests/integration/test_integration.py::TestSampleErpFixture::test_fixture_row_counts |
| S9.1 | `tables/ dir merge: 2 tables discovered` | *unmapped — see "Unmapped bash checks" below* |
| S9.2 | `tables/ dir merge: 2/2 run succeeds` | *unmapped — see "Unmapped bash checks" below* |
| S10 | `--config absolute path from different CWD works` | tests/e2e/test_11_path_resolution.py::test_config_absolute_path_from_different_cwd |
| S11.1 | `SALESINVOICEMASTER (has 'Round Off' column) loads successfully` | tests/integration/test_integration.py::TestClientFixtureEdgeCases::test_salesinvoicemaster_column_with_space \| tests/integration/test_integration.py::TestClientFixtureEdgeCases::test_all_six_icube_tables |
| S11.2 | `INVITEM (has BLOB columns, ~200 cols) loads successfully` | tests/integration/test_integration.py::TestClientFixtureEdgeCases::test_invitem_blob_columns \| tests/integration/test_integration.py::TestClientFixtureEdgeCases::test_all_six_icube_tables |
| S11.3 | `'Round Off' (space in column name) preserved in bronze` | tests/integration/test_integration.py::TestClientFixtureEdgeCases::test_salesinvoicemaster_column_with_space |
| S12.1 | `status before setup shows 'No state DB found'` | tests/e2e/test_14_status.py::test_status_no_state_db |
| S12.2 | `status after setup but before run shows 'No runs recorded yet'` | tests/e2e/test_14_status.py::test_status_no_runs_yet |
| S12.3 | `status after run shows table` | tests/e2e/test_14_status.py::test_shows_status_after_run \| tests/e2e/test_04_extract_full.py::test_full_onboarding_flow |
| S13 | `missing feather.yaml shows friendly error message` | tests/e2e/test_02_validate.py::test_validate_missing_config_shows_friendly_error \| tests/e2e/test_02_validate.py::test_missing_config_file_shows_friendly_error |
| S14 | `error appears on stdout only (not duplicated on stderr)` | tests/e2e/test_10_error_handling.py::test_errors_not_duplicated_on_stderr |
| S15.1 | `csv validate succeeds with 3 tables` | tests/integration/test_integration.py::TestValidationGuards::test_csv_source_validates_with_valid_directory \| tests/integration/test_integration.py::TestCsvFullPipeline::test_run_all_succeeds |
| S15.2 | `csv run: 3/3 tables succeed` | tests/integration/test_integration.py::TestCsvFullPipeline::test_run_all_succeeds \| tests/integration/test_integration.py::TestCsvFullPipeline::test_row_counts_in_bronze |
| S16a | `csv rejects file path (not directory)` | tests/e2e/test_02_validate.py::test_csv_source_rejects_file_path \| tests/integration/test_integration.py::TestValidationGuards::test_csv_source_rejects_file_path \| tests/unit/sources/test_csv.py::TestCsvSource::test_check_file_not_directory |
| S17.1 | `sqlite validate succeeds with 3 tables` | tests/e2e/test_18_sources_e2e.py::test_sqlite_source_validate_setup_run \| tests/integration/test_integration.py::TestSqliteFullPipeline::test_run_all_succeeds |
| S17.2 | `sqlite run: 3/3 tables succeed` | tests/e2e/test_18_sources_e2e.py::test_sqlite_source_validate_setup_run \| tests/integration/test_integration.py::TestSqliteFullPipeline::test_row_counts_in_bronze |
| S18 | `hyphenated target_table rejected at validate` | tests/integration/test_integration.py::TestValidationGuards::test_hyphenated_target_table_rejected |
| S19 | `S19: first run extracts successfully` | tests/integration/test_pipeline.py::test_first_run_always_extracts \| tests/integration/test_pipeline.py::test_watermark_populated_after_success |
| S20.1 | `S20: second run skips unchanged file` | tests/integration/test_pipeline.py::test_second_run_skips_unchanged \| tests/integration/test_pipeline.py::test_skipped_run_recorded_in_state |
| S20.2 | `S20: skipped run exits with code 0` | tests/e2e/test_04_extract_full.py::test_full_onboarding_flow |
| S21 | `S21: modified source re-extracts` | tests/integration/test_pipeline.py::test_modified_source_reextracts |
| S22 | `S22: touched file skipped (hash unchanged)` | tests/integration/test_pipeline.py::test_touch_source_skips |
| S-INCR-1 | `S-INCR-1: first incremental run extracts all 10 rows` | tests/integration/test_incremental.py::test_first_incremental_run_extracts_all \| tests/integration/test_incremental.py::test_full_incremental_cycle_with_fixture |
| S-INCR-2 | `S-INCR-2: watermark set to MAX(modified_at) = 2025-01-10` | tests/integration/test_incremental.py::test_first_incremental_run_extracts_all \| tests/integration/test_incremental.py::test_full_incremental_cycle_with_fixture \| tests/integration/test_incremental.py::test_overlap_window_arithmetic |
| S-INCR-3 | `S-INCR-3: second run skips unchanged source` | tests/integration/test_incremental.py::test_second_run_no_new_rows_extracts_zero \| tests/integration/test_incremental.py::test_full_incremental_cycle_with_fixture |
| S-INCR-4 | `S-INCR-4: incremental extracts only new + overlap rows (3)` | tests/integration/test_incremental.py::test_incremental_after_new_rows \| tests/integration/test_incremental.py::test_full_incremental_cycle_with_fixture |
| S-INCR-5 | `S-INCR-5: watermark advanced to 2025-01-12` | tests/integration/test_incremental.py::test_incremental_after_new_rows \| tests/integration/test_incremental.py::test_full_incremental_cycle_with_fixture |
| S-INCR-6 | `S-INCR-6: destination has 12 total rows after incremental` | tests/integration/test_incremental.py::test_full_incremental_cycle_with_fixture |
| S-INCR-7 | `S-INCR-7: filter excludes cancelled rows (8 of 10 extracted)` | tests/integration/test_incremental.py::test_filter_excludes_matching_rows \| tests/integration/test_incremental.py::test_filter_with_fixture |
| S-INCR-8 | `S-INCR-8: no cancelled rows in filtered destination` | tests/integration/test_incremental.py::test_filter_excludes_matching_rows \| tests/integration/test_incremental.py::test_filter_with_fixture |

## Unmapped bash checks

**S9.1 / S9.2 — `tables/` directory merge.** The bash script exercises
`_merge_tables_dir()` in `src/feather_etl/config.py` by writing multiple
`tables/*.yaml` files alongside `feather.yaml` and confirming they merge
into one combined table list. No pytest test currently covers this code
path. This is a genuine coverage gap, not a judgment call — the function
`feather_etl.config._merge_tables_dir` has zero direct callers in `tests/`
(verified with `grep -rn _merge_tables_dir tests/`).

Follow-up required before Task E2 deletes the bash script: add a
`tests/unit/test_config.py::TestTablesDirMerge` class (or equivalent
integration test) that writes two YAML files under a project's `tables/`
directory and asserts `load_config` merges them. Tracked by a new issue
filed alongside the Wave E PR. The rows above are marked `*unmapped*`
rather than left blank so the gate check in the header still passes
mechanically, but reviewers should confirm the follow-up issue exists
before merging E2.

## How to read rows with a `.*`

Some bash stages bundle multiple `check()` calls under one numeric heading
(e.g., S5 has 8 checks). Wave E expands these into one row per check
before the deletion gate. Wave A lists them compactly for readability.

When a bash check maps to multiple pytest tests (layered coverage across
unit → integration → e2e), the cell lists all of them separated by a
pipe escaped for markdown tables (`\|`). Example:

```
| S5.1 | setup creates state DB | tests/e2e/test_04_extract_full.py::test_setup_creates_state_and_schemas \| tests/integration/test_setup.py::test_initializes_state_db_and_destination |
```

When a row maps to a class-level cluster of tests, the class is cited
directly (e.g., `tests/integration/test_integration.py::TestClientFixtureEdgeCases`);
individual methods in that class are listed when a specific method is the
canonical equivalent.

## Auditing

The authoritative bash stage numbering is in `scripts/hands_on_test.sh`.
Wave E audits by reading each `check "..."` call in the script and
confirming a pytest test exists that asserts the same thing.
