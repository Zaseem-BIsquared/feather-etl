# Contributing conventions

This document describes the file conventions for plans, reviews, and fixes.
Every agent working on this repo should read it before starting.

---

## Document chain

Each piece of work follows this chain:

```
docs/plans/YYYY-MM-DD-<slice>-<topic>.md       ← implementation plan
docs/reviews/YYYY-MM-DD-<slice>-review.md      ← review of that implementation
docs/plans/YYYY-MM-DD-<slice>-fixes.md         ← plan to address review findings
docs/reviews/YYYY-MM-DD-<slice>-review-2.md    ← re-review after fixes
...
```

Links are two-way: every plan has a `Review:` field once reviewed; every review
has a `Plan:` field pointing to what was reviewed and (once it exists) a
`Fixes:` field pointing to the fix plan.

---

## Plan document header

```markdown
# <Title>

Created: YYYY-MM-DD
Status: DRAFT | APPROVED | IN PROGRESS | VERIFIED
Approved: Yes | No | Pending
Slice: N
Type: Feature | Fix | Refactor | Review-fixes
Review: <path to review doc, added after review>
```

## Review document header

```markdown
# <Slice> Review

Created: YYYY-MM-DD
Slice: N
Plan: <path to plan doc>
Commit: <short hash reviewed>
Status: OPEN | RESOLVED — see <fixes plan path>
Prior review: <path, if this is review-2+>
```

---

## Rules for the fixing agent

1. **Never edit findings in a review doc.**  The review is a permanent record.
   Editing it destroys the audit trail.

2. **Create a fixes plan** at `docs/plans/YYYY-MM-DD-<slice>-fixes.md`.
   Scope it to the findings you intend to address.  List any you are deferring
   and why.

3. **Graduate `TestKnownBugs` tests** as you fix each bug:
   - Read the test docstring — it states current wrong behaviour and correct
     post-fix behaviour.
   - Invert the assertion.
   - Remove the `BUG-N` prefix from the test name.
   - Move the test to the appropriate positive-behaviour test class.

4. **Update BUG-labelled tests** in the relevant layer (`tests/e2e/`,
   `tests/integration/`, or `tests/unit/`) to assert the corrected
   behaviour. Per `tests/README.md`, regression guards use `BUG-N` in the
   test docstring — invert the assertion, rename the function if it
   dropped the prefix, and move it out of any `TestKnownBugs` grouping
   if one existed.

5. **Run the test suite before opening for re-review:**
   ```bash
   uv run pytest -q   # must be all green
   ```

6. **Update the review doc Status line** (and only that line) to:
   `RESOLVED — see docs/plans/YYYY-MM-DD-<slice>-fixes.md`

7. **Do not request a re-review yourself.**  Tell the human what was fixed,
   what was deferred, and why.  The human decides when to ask for a re-review.

---

## Rules for the reviewing agent

1. Read `docs/reviews/` — find the most recent review for the slice.  Its
   `Status:` line tells you whether fixes have been applied.

2. Run both test suites first.  If any test fails before you read a line of
   code, note it immediately.

3. Create a new review file `docs/reviews/YYYY-MM-DD-<slice>-review-N.md`.
   Add `Prior review: <path>` to the header.

4. Cover:
   - Which findings from the prior review were fixed correctly.
   - Which were fixed incorrectly or partially.
   - Which are still open.
   - Any new issues introduced by the fixes.
   - New regression scenarios to add under the appropriate layer in
     `tests/` (e2e / integration / unit per `tests/README.md`).

5. Update artefacts:
   - Add new `BUG-N`-labelled regression tests for any new bugs found,
     in the appropriate `tests/` layer.
   - If new fixtures are needed, add a script in `scripts/` to regenerate them.

---

## Test suite conventions

See [`tests/README.md`](../tests/README.md) for the canonical contract:

- **Three-way decision rule** — where a given test belongs
  (`tests/e2e/` for CLI journeys; `tests/integration/` for multi-module
  Python-API slices; `tests/unit/` mirroring `src/feather_etl/` for
  single-module tests).
- **`ProjectFixture` / `cli` harness** — the fixtures every e2e test uses.
- **Workflow-stage file layout** for `tests/e2e/` (numbered 00–18).
- **Regression guard (`BUG-N`) pattern** — how to record an open bug as
  a failing test, and how to graduate it after the fix lands.

All tests use real DuckDB fixtures where possible; `unittest.mock` is
used only for module-isolation unit tests (e.g., SMTP, pyodbc).

### Fixtures

| File | Schema | Use for |
|---|---|---|
| `tests/fixtures/client.duckdb` | `icube.*`, 6 tables, ~14K rows | Real-world ERP data, messy schemas |
| `tests/fixtures/client_update.duckdb` | `icube.*`, 3 tables, ~12K rows | Future incremental/append tests |
| `tests/fixtures/sample_erp.duckdb` | `erp.*`, 3 tables, 12 rows | Fast tests, NULL handling, simple schema |
| `tests/fixtures/sample_erp.sqlite` | `erp.*`, 3 tables, 12 rows | SQLite source tests |
| `tests/fixtures/csv_data/` | 3 CSV files (orders, customers, products) | CSV source tests |

To regenerate fixtures:
```bash
python scripts/create_sample_erp_fixture.py        # DuckDB
python scripts/create_csv_sqlite_fixtures.py       # CSV + SQLite
```

---

## Testing co-location

Tests track with the **module of origin**, not with the feature that
motivated them. When you edit `SqlServerSource`, every constraint on your
change lives in `tests/test_sqlserver.py`. When you edit the discover
command, every flag combo lives in `tests/commands/test_discover.py`.

The one exception: happy-path E2E tests stand alone as "how does a user
actually use this end-to-end." They live in
`tests/commands/test_<workflow>.py`.

Do **not** create feature-named test files (e.g. `test_multi_source.py`) —
tests belong with the code they exercise.

---

## Local DB prerequisites

Two DB-gated test groups run against your local machine's brew-managed
servers:

- **PostgreSQL** — 5 integration tests in `tests/unit/sources/test_postgres.py`
  and `tests/e2e/test_03_discover.py`.
- **MySQL** — integration tests in `tests/unit/sources/test_mysql.py`.

Both expect a `feather_test` database to exist. The test suite creates
it automatically at session start if the servers are up:

```bash
brew services start postgresql@17 mysql
uv run pytest -q     # 0 DB-gated skips on a healthy setup
```

If a server is down, the suite prints a banner naming the exact
`brew services start …` command, the gated tests skip with a clear
reason, and the run still exits 0. Nothing else is needed — no manual
`createdb`, no `.env` secrets. Localhost auth uses brew defaults
(Postgres peer/trust, MySQL `root` without password).

---

## Current open reviews

| File | Slice | Status |
|---|---|---|
| [docs/reviews/2026-03-26-slice1-review.md](reviews/2026-03-26-slice1-review.md) | 1 | RESOLVED — see [fixes plan](plans/2026-03-26-slice1-fixes.md) |
