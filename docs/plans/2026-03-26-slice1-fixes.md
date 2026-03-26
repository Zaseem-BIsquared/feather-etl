# Slice 1 Review Fixes

Created: 2026-03-26
Status: VERIFIED
Approved: Yes
Slice: 1
Type: Review-fixes
Review: [docs/reviews/2026-03-26-slice1-review.md](../reviews/2026-03-26-slice1-review.md)

---

## Scope

Fix all 8 BUG-N findings and all 9 UX-N findings from the hands-on review.
Static review findings (C-1 through C-4, H-1 through H-8, M-5 through M-10,
L-*, NIT-*) are **deferred** — they require architectural changes (connection
leak cleanup, SQL injection quoting, strategy dispatch, per-table loop
restructuring) that belong in a separate plan.

### Deferred (with rationale)

| ID | Issue | Why deferred |
|---|---|---|
| C-1 | SQL injection via unquoted identifiers | BUG-7 fix adds input validation as a defense layer; full quoting is Slice 2 scope |
| C-3, H-2, H-4 | Connection leaks | Systematic `try/finally` or context manager refactor — separate PR |
| C-4 | State/dest re-created per table in loop | Requires `run_all` restructuring — separate PR |
| H-1 | TOCTOU race in chmod | Low practical risk on single-user pipelines |
| H-3 | extract() ignores params | Incremental/append not implemented yet (Slice 2) |
| H-5 | run_id contains `:` and `+` | Safe for DuckDB VARCHAR; revisit if used as filename |
| H-6 | Duplicate-timestamp race in get_status | Extremely unlikely with per-table sequential execution |
| H-7 | Staging table zombie on ROLLBACK failure | Edge case; DuckDB rollback rarely fails |
| M-5 | Non-atomic write_watermark | No concurrent writers in Slice 1 |
| M-6 | Strategy not dispatched (incremental silently full-loads) | Slice 2 scope |
| M-7 | write_validation_json called twice | Minor; no user impact |
| M-10 | Duplicate table names silently loaded | Rare edge case; Slice 2 validation |
| L-*, NIT-* | Style and naming nits | Low priority |

---

## Findings addressed

### Production code changes

| File | Findings | Change |
|---|---|---|
| `config.py` | BUG-2, BUG-4, BUG-6, BUG-7, UX-4, UX-8 | Validate against `SOURCE_REGISTRY` (not `VALID_SOURCE_TYPES`); catch `KeyError` in `_parse_tables`; check destination parent exists; validate SQL identifiers in `target_table`; detect unresolved `${VAR}`; require `timestamp_column` for incremental; require schema prefix in `target_table`; validate missing top-level sections |
| `cli.py` | BUG-3, BUG-5, UX-2, UX-3, UX-5, UX-7, UX-9 | Catch `FileNotFoundError`; exit 1 on any failure; resolve `.` to CWD name; ignore hidden dirs in init emptiness check; show error message in status; update setup help text; show state path in validate |
| `pipeline.py` | BUG-1/UX-6 | Remove `logger.error()` — CLI handles display; remove unused `logging` import |
| `state.py` | UX-5 | Add `error_message` to `get_status()` query; update docstring documenting all-time history (BUG-8 decision) |
| `README.md` | UX-1 | Replace non-existent CLI features with actual CLI |

### Test changes

| File | Change |
|---|---|
| `test_cli.py` | Update exit code assertion for bad table run (BUG-5); add tests for: missing config file (BUG-3), .git-allowed init (UX-3), init-dot name (UX-2), validate state path (UX-9), status error message (UX-5), all-time history (BUG-8), run-without-setup (UX-7) |
| `test_config.py` | Add tests for: csv source rejected (BUG-2), missing table field (BUG-4), missing section (BUG-3), destination parent (BUG-6), hyphenated name (BUG-7), schema prefix required (BUG-7), unresolved env var (UX-4), incremental requires timestamp (UX-8) |
| `test_integration.py` | Graduate TestKnownBugs tests: BUG-2/3/5/7 → TestValidationGuards/TestErrorIsolation; keep M-6 (strategy dispatch) as sole remaining known bug |
| `hands_on_test.sh` | Invert BUG-labelled checks in S1/S3/S6/S13/S14/S15/S16 |

### Design decisions (autonomous)

1. **BUG-8 (status shows all-time history):** Kept as intentional behavior. History should not be lost when config changes. Documented in `get_status()` docstring. Added test confirming the behavior.

2. **UX-7 (run auto-creates DBs):** Kept as intentional behavior. `setup` is documented as optional in its help text. Added test confirming auto-creation works.

3. **BUG-2 approach:** Lazy import of `SOURCE_REGISTRY` inside `_validate()` to avoid circular import (`config.py` ← `registry.py` ← `config.py`). Removed `VALID_SOURCE_TYPES` constant entirely.

4. **BUG-7 identifier validation:** Added regex `^[a-zA-Z_][a-zA-Z0-9_]*$` for target table name part. Also requires schema prefix (schema.table format) — bare table names like `my_table` are rejected with a helpful suggestion.

5. **UX-4 env var detection:** Check runs after `_resolve_yaml_env_vars()` but before config construction, so unresolved vars are caught before they cause confusing path errors downstream.
