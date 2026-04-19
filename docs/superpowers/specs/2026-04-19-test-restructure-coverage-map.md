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

| Bash check ID | What it asserts | Pytest test path |
|---|---|---|
| S1.1 | `feather init` creates `feather.yaml` | |
| S1.2 | `feather init` creates `pyproject.toml` | |
| S1.3 | `feather init` creates `.gitignore` | |
| S1.4 | `feather init` creates `.env.example` | |
| S1.5 | `feather init` creates `README.md` | |
| S1.6 | `feather init` creates `discovery/` directory | |
| S2.* | `feather validate` — client fixture (8 checks) | |
| S3.* | `feather validate` — failure cases (8 checks) | |
| S5.* | `feather setup` + `run` + `status` — client fixture (9 checks) | |
| S6.* | Partial failure / error isolation (5 checks) | |
| S7 | `feather run` without prior setup auto-creates state and data DBs | |
| S8.* | sample_erp fixture (3 checks) | |
| S9.* | `tables/` directory merge (2 checks) | |
| S10 | `--config` absolute path from different CWD | tests/e2e/test_11_path_resolution.py::test_config_absolute_path_from_different_cwd |
| S11.* | BLOB columns / spaces in column names (3 checks) | |
| S12.* | `feather status` edge cases (3 checks) | |
| S13 | Missing `feather.yaml` shows friendly error | tests/e2e/test_02_validate.py::test_validate_missing_config_shows_friendly_error |
| S14 | Error output not duplicated on stderr | tests/e2e/test_10_error_handling.py::test_errors_not_duplicated_on_stderr |
| S15.* | CSV source validate + run (2 checks) | |
| S16a | CSV rejects file path (not directory) | tests/e2e/test_02_validate.py::test_csv_source_rejects_file_path |
| S17.* | SQLite source validate + run (2 checks) | tests/e2e/test_18_sources_e2e.py::test_sqlite_source_validate_setup_run |
| S18 | Hyphenated `target_table` rejected at validate | |
| S19 | Change detection: first run succeeds | |
| S20 | Change detection: second run (unchanged) skipped | |
| S21 | Change detection: modify source → re-extracts | |
| S22 | Change detection: touch (mtime changes, content identical) → skipped | |
| S-INCR-1 | Incremental: first run extracts all rows | |
| S-INCR-2 | Incremental: watermark is set | |
| S-INCR-3 | Incremental: second run, file unchanged → skipped | |
| S-INCR-4 | Incremental: new rows → only new rows + overlap extracted | |
| S-INCR-5 | Incremental: watermark advanced to new MAX | |
| S-INCR-6 | Incremental: destination has correct total row count | |
| S-INCR-7 | Incremental: filter excludes matching rows | |
| S-INCR-8 | Incremental: no filtered rows in destination | |

## How to read rows with a `.*`

Some bash stages bundle multiple `check()` calls under one numeric heading
(e.g., S5 has 9 checks). Wave E expands these into one row per check
before the deletion gate. Wave A lists them compactly for readability.

## Auditing

The authoritative bash stage numbering is in `scripts/hands_on_test.sh`.
Wave E audits by reading each `check "..."` call in the script and
confirming a pytest test exists that asserts the same thing.
