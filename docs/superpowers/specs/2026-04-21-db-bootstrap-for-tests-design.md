# Local-DB bootstrap for the test suite

Created: 2026-04-21
Status: DRAFT
Issue: [#48](https://github.com/siraj-samsudeen/feather-etl/issues/48)

---

# Part I — Requirements

## 1. Problem

Five Postgres-gated tests and the MySQL-gated tests in this repo skip themselves silently when the local DB server does not have a database named `feather_test`. The skip reason — `"PostgreSQL not available"` or `"MySQL not available"` — conflates three distinct failure modes:

- The server is not running.
- The server is running but `feather_test` does not exist.
- The server is running and `feather_test` exists, but the connection auth fails.

The most common failure today is the middle one: the developer has `postgresql@17` and `mysql` running via `brew services`, but nothing has ever created the `feather_test` database on those servers, so the probe fails and the tests silently skip.

A related issue: `tests/conftest.py` already tries to paper over this by calling `pg_ctl start` at session start. The hook is a no-op on brew installs (because `pg_ctl` is keg-only and not on `PATH`), so it neither helps nor warns.

The result: a quiet coverage gap that grows over time. Issue #26 (view discovery for database sources) will add more Postgres tests that will also silently skip on the same machines.

## 2. Goal

A developer with `postgresql@17` and `mysql` running via `brew services` should see **zero DB-gated skips** on `uv run pytest -q`, with no manual setup beyond `brew services start`. The bootstrap should be idempotent, cost near-zero on every run after the first, and fail loudly when the server is actually down — not silently.

## 3. Acceptance criteria

- Both DBs reachable: `uv run pytest -q` completes with **zero** DB-gated skips.
- Postgres unreachable: a session-start banner names `brew services start postgresql@17`, the 5 Postgres-gated tests skip with a clear reason, and the suite exits 0.
- MySQL unreachable: a session-start banner names `brew services start mysql`, the MySQL-gated tests skip with a clear reason, and the suite exits 0.
- `feather_test` persists across runs on both servers and holds no test-authored data between sessions.

### End-to-end verification

A concrete exemplar of the acceptance criteria, run by hand once the implementation lands:

```
brew services start postgresql@17 mysql
uv run pytest -q                           # 0 DB-gated skips
brew services stop postgresql@17
uv run pytest -q                           # banner + 5 skips + exit 0
brew services start postgresql@17
```

---

# Part II — Design

## 4. Scope

Work lives entirely inside `tests/` and `docs/CONTRIBUTING.md`. No product code, CI config, or test-body changes.

**In**

- Missing `feather_test` is created automatically on first test-suite run — on both Postgres and MySQL. Persistent across runs. Idempotent.
- A loud banner at session start when a server is unreachable, naming the exact `brew services start …` command.
- The three duplicated `_*_available()` probe definitions get consolidated into one place.
- The stale `pg_ctl` attempt in `conftest.py` is replaced with a working bootstrap.
- A one-paragraph "Local DB prerequisites" section in `docs/CONTRIBUTING.md`.

**Out**

- Docker, docker-compose, testcontainers. The brew-managed DBs already running on the developer's machine are the source of truth.
- CI pipeline changes. Explicitly not a concern for this work.
- SQL Server tests. They use mocked connections — no skip problem.
- Auto-starting `brew services`. If a server is down, the banner tells the developer; the tests skip cleanly.
- Non-Mac developer support without `brew services`. A Linux addendum is a future issue.
- Production-like credential-rich Postgres or MySQL connections. The whole design assumes brew-default trust/peer auth on localhost.

## 5. Key decisions

Only the internal forks a reviewer would not have noticed from Scope alone.

### Auth

**Chose:** Default libpq user resolution (`PGUSER` → `USER`), no password.

**Why not an explicit user/password in test config?** It would introduce a new secret to manage and break on fresh clones. Brew-default `pg_hba.conf` and MySQL's localhost `root` trust make auth-free localhost connections the correct default.

### Admin DB for `CREATE DATABASE`

**Chose:** `dbname=postgres` on Postgres; no-DB connection on MySQL.

**Why not connect to `feather_test` itself?** Circular — the bootstrap runs precisely when `feather_test` may not exist yet. Both servers expose a pre-existing admin namespace the bootstrap can open without needing the target DB.

### Hook choice

**Chose:** `pytest_sessionstart` over `pytest_configure`.

**Why not `pytest_configure`?** Both hooks fire before test collection (where `skipif` probes run), so either works timing-wise — the old broken bootstrap used `pytest_configure`. The real distinction is semantic: `pytest_configure` is pytest's hook for *configuration* (plugin registration, option parsing); `pytest_sessionstart` is for *session lifecycle* work like resource setup. Bootstrapping a database is lifecycle, not configuration. Using the conventional hook keeps future maintainers from wondering "why is a DB bootstrap in `pytest_configure`?"

## 6. How it works

The bootstrap runs once at session start, before any test collects. Everything else is downstream of that.

```
 pytest start
   │
   ├─ pytest_sessionstart ─▶ ensure_bootstrap_databases()
   │                            │
   │                            ├─ Postgres: connect → check → CREATE → ok | fail → stash reason
   │                            └─ MySQL:    connect → check → CREATE → ok | fail → stash reason
   │
   ├─ any flavor failed? ─▶ emit banner with brew-services command
   │
   ├─ test collection begins — @postgres / @mysql_db skipif probes see live DB
   │
   ├─ tests run (or skip with the stashed reason)
   │
   └─ session end — feather_test persists
```

Postgres requires `autocommit=True` because `CREATE DATABASE` cannot run inside a transaction.

## 7. Integration surface

Where the outcomes from §4 live in the codebase. Describes the terrain; per-file edit procedure lives in the implementation plan.

**New**

- `tests/db_bootstrap.py` — home of the shared probes, DSN constants, bootstrap entry point, and banner helper.

**Modified**

- `tests/conftest.py` — currently holds the stale `pg_ctl` hook; becomes the home of the `pytest_sessionstart` bootstrap trigger. Blast radius: every test session.
- `tests/e2e/test_03_discover.py` — currently defines a local `_postgres_available` probe, `CONN_STR`, and `postgres` marker; migrates to the shared module.
- `tests/unit/sources/test_postgres.py` — same local-probe situation; same migration.
- `tests/unit/sources/test_mysql.py` — same for MySQL.
- `docs/CONTRIBUTING.md` — gains a "Local DB prerequisites" section.

**Outside this scope**

- `src/feather_etl/**` — not a product change.
- `pyproject.toml` — both DB drivers are already dependencies.
- Any CI config.

## 8. Test design

Unit tests for `db_bootstrap.py` (mocked drivers):

- Probe: reachable → `(True, None)`; unreachable → `(False, reason_string)`.
- Bootstrap: DB exists → no `CREATE` issued; DB missing → `CREATE` issued, post-check succeeds.
- Driver error: exception caught, reason stashed, never re-raised.
- Idempotency: two calls in a row produce one `CREATE`.

Integration tests (gated by the shared `@postgres` / `@mysql_db` markers):

- Per flavor: `feather_test` absent → bootstrap → DB exists.
