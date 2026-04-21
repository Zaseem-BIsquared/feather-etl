# DB Bootstrap for Tests — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

Created: 2026-04-21
Status: DRAFT
Spec: [docs/superpowers/specs/2026-04-21-db-bootstrap-for-tests-design.md](../specs/2026-04-21-db-bootstrap-for-tests-design.md)
Issue: [#48](https://github.com/siraj-samsudeen/feather-etl/issues/48)

**Goal:** Auto-create `feather_test` on local Postgres & MySQL at pytest session start so DB-gated tests stop silently skipping.

**Architecture:** New `tests/db_bootstrap.py` owns DSN constants, probes, per-flavor bootstrap, marker factories, and banner text. `tests/conftest.py` calls `ensure_bootstrap_databases()` from `pytest_sessionstart` (replacing the stale `pg_ctl` hook). The three test files that currently define local `_*_available()` probes import from the shared module instead.

**Tech Stack:** pytest, psycopg2-binary, mysql-connector-python (all already in `pyproject.toml`).

---

## File Structure

**Create**

- `tests/db_bootstrap.py` — DSN constants, `postgres_check()`, `mysql_check()`, `_ensure_postgres_database()`, `_ensure_mysql_database()`, `ensure_bootstrap_databases()`, `format_banner()`, `postgres_marker()`, `mysql_marker()`.
- `tests/unit/test_db_bootstrap.py` — unit tests (mocked drivers).
- `tests/integration/test_db_bootstrap.py` — real-DB integration tests (use throwaway DB name, not `feather_test`).

**Modify**

- `tests/conftest.py:13-22` — replace `pytest_configure`/`pytest_unconfigure` pg_ctl hooks with `pytest_sessionstart` bootstrap trigger.
- `tests/unit/sources/test_postgres.py:11-27` — delete local `CONN_STR` / `_postgres_available` / `postgres` marker; import from shared module.
- `tests/e2e/test_03_discover.py:28-46` — same migration (also uses `CONN_STR` in `TestDiscoverPostgresMultiDatabase` helpers — re-point those).
- `tests/unit/sources/test_mysql.py:161-175` — delete local `MYSQL_CONN_KWARGS` / `_mysql_available` / `mysql_db` marker; import from shared module.
- `docs/CONTRIBUTING.md` — insert "Local DB prerequisites" section before "Dev shortcuts" (~line 164).

**Outside scope**

- `src/feather_etl/**`, `pyproject.toml`, any CI config.

---

## Design notes carried from spec

- **Auth:** libpq default resolution (`PGUSER → USER`, no password) on Postgres; `user="root"`, no password on MySQL. Brew defaults on localhost make this work with no secret.
- **Admin DSN:** `dbname=postgres host=localhost` for Postgres; on MySQL, omit `database=` from connect kwargs.
- **Hook:** `pytest_sessionstart` (not `pytest_configure`) — bootstrapping a database is session lifecycle, not configuration.
- **Marker factories:** markers are built by *factory functions* (`postgres_marker()`, `mysql_marker()`) called from test files at their import time — which happens after `pytest_sessionstart` has run bootstrap. Returning a fresh `pytest.mark.skipif(...)` on each call keeps the reason string live.
- **`CREATE DATABASE` quirk:** Postgres requires `autocommit=True` on the admin connection.

---

## Task Breakdown

### Task 1: DSN constants + probes (TDD)

**Files:**
- Create: `tests/db_bootstrap.py`
- Test: `tests/unit/test_db_bootstrap.py`

- [ ] **Step 1: Write failing probe tests**

```python
# tests/unit/test_db_bootstrap.py
"""Unit tests for tests/db_bootstrap.py — drivers are always mocked here."""

from __future__ import annotations

import pytest


class TestPostgresCheck:
    def test_reachable_returns_true_none(self, monkeypatch):
        from tests import db_bootstrap as dbb

        class FakeConn:
            def close(self):
                pass

        monkeypatch.setattr(dbb.psycopg2, "connect", lambda *a, **k: FakeConn())
        ok, reason = dbb.postgres_check()
        assert ok is True
        assert reason is None

    def test_unreachable_returns_false_with_reason(self, monkeypatch):
        from tests import db_bootstrap as dbb

        def boom(*a, **k):
            raise dbb.psycopg2.OperationalError("connection refused")

        monkeypatch.setattr(dbb.psycopg2, "connect", boom)
        ok, reason = dbb.postgres_check()
        assert ok is False
        assert "connection refused" in reason


class TestMySQLCheck:
    def test_reachable_returns_true_none(self, monkeypatch):
        from tests import db_bootstrap as dbb

        class FakeConn:
            def close(self):
                pass

        monkeypatch.setattr(
            dbb.mysql.connector, "connect", lambda **k: FakeConn()
        )
        ok, reason = dbb.mysql_check()
        assert ok is True
        assert reason is None

    def test_unreachable_returns_false_with_reason(self, monkeypatch):
        from tests import db_bootstrap as dbb

        def boom(**k):
            raise dbb.mysql.connector.Error("access denied")

        monkeypatch.setattr(dbb.mysql.connector, "connect", boom)
        ok, reason = dbb.mysql_check()
        assert ok is False
        assert "access denied" in reason
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/test_db_bootstrap.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tests.db_bootstrap'`

- [ ] **Step 3: Create `tests/db_bootstrap.py` with constants + probes**

```python
# tests/db_bootstrap.py
"""Shared DB bootstrap for the test suite.

Owns the DSN constants, live-reachability probes, the per-flavor
`CREATE DATABASE IF NOT EXISTS` bootstrap, marker factories used by
test files, and the session-start banner shown when a server is down.

Everything here assumes brew-managed Postgres + MySQL on localhost with
default trust/peer auth. Not designed for credentialed production DBs.
"""

from __future__ import annotations

import mysql.connector
import psycopg2
import pytest

# ---------------------------------------------------------------------------
# Connection constants
# ---------------------------------------------------------------------------

TARGET_DB = "feather_test"

POSTGRES_DSN = f"dbname={TARGET_DB} host=localhost"
POSTGRES_ADMIN_DSN = "dbname=postgres host=localhost"

MYSQL_CONN_KWARGS = {"host": "localhost", "user": "root", "database": TARGET_DB}
MYSQL_ADMIN_KWARGS = {"host": "localhost", "user": "root"}


# ---------------------------------------------------------------------------
# Probes
# ---------------------------------------------------------------------------


def postgres_check() -> tuple[bool, str | None]:
    """Return (True, None) if `feather_test` is reachable on Postgres."""
    try:
        conn = psycopg2.connect(POSTGRES_DSN)
        conn.close()
        return (True, None)
    except Exception as exc:
        return (False, str(exc))


def mysql_check() -> tuple[bool, str | None]:
    """Return (True, None) if `feather_test` is reachable on MySQL."""
    try:
        conn = mysql.connector.connect(**MYSQL_CONN_KWARGS)
        conn.close()
        return (True, None)
    except Exception as exc:
        return (False, str(exc))
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/unit/test_db_bootstrap.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add tests/db_bootstrap.py tests/unit/test_db_bootstrap.py
git commit -m "test(db-bootstrap): add DSN constants and live-reachability probes"
```

---

### Task 2: Postgres bootstrap (TDD)

**Files:**
- Modify: `tests/db_bootstrap.py`
- Test: `tests/unit/test_db_bootstrap.py`

- [ ] **Step 1: Write failing Postgres-bootstrap tests**

Append to `tests/unit/test_db_bootstrap.py`:

```python
class TestEnsurePostgresDatabase:
    def _install_admin_connect(self, monkeypatch, exists: bool):
        """Patch psycopg2.connect for the admin DSN. Returns lists of SQL
        statements executed + whether a post-check probe was issued."""
        from tests import db_bootstrap as dbb

        executed: list[str] = []

        class FakeCursor:
            def execute(self, sql, *_):
                executed.append(sql)

            def fetchone(self):
                # Only called for the "does it exist?" SELECT
                return (1,) if exists else None

            def close(self):
                pass

        class FakeConn:
            autocommit = False

            def cursor(self):
                return FakeCursor()

            def close(self):
                pass

        def fake_connect(dsn, *a, **k):
            # Only admin DSN is exercised here; the post-check uses
            # postgres_check() which is monkeypatched separately.
            assert dsn == dbb.POSTGRES_ADMIN_DSN
            return FakeConn()

        monkeypatch.setattr(dbb.psycopg2, "connect", fake_connect)
        return executed

    def test_db_exists_no_create(self, monkeypatch):
        from tests import db_bootstrap as dbb

        executed = self._install_admin_connect(monkeypatch, exists=True)
        monkeypatch.setattr(dbb, "postgres_check", lambda: (True, None))

        ok, reason = dbb._ensure_postgres_database()

        assert ok is True
        assert reason is None
        # No CREATE should have been issued.
        assert not any("CREATE DATABASE" in s for s in executed)

    def test_db_missing_issues_create(self, monkeypatch):
        from tests import db_bootstrap as dbb

        executed = self._install_admin_connect(monkeypatch, exists=False)
        monkeypatch.setattr(dbb, "postgres_check", lambda: (True, None))

        ok, reason = dbb._ensure_postgres_database()

        assert ok is True
        assert reason is None
        assert any(
            "CREATE DATABASE" in s and dbb.TARGET_DB in s for s in executed
        )

    def test_driver_error_is_captured_not_raised(self, monkeypatch):
        from tests import db_bootstrap as dbb

        def boom(*a, **k):
            raise dbb.psycopg2.OperationalError("server down")

        monkeypatch.setattr(dbb.psycopg2, "connect", boom)

        ok, reason = dbb._ensure_postgres_database()

        assert ok is False
        assert "server down" in reason
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/unit/test_db_bootstrap.py::TestEnsurePostgresDatabase -v`
Expected: FAIL with `AttributeError: module 'tests.db_bootstrap' has no attribute '_ensure_postgres_database'`

- [ ] **Step 3: Add `_ensure_postgres_database` to `tests/db_bootstrap.py`**

Append to `tests/db_bootstrap.py`:

```python
# ---------------------------------------------------------------------------
# Per-flavor bootstrap
# ---------------------------------------------------------------------------


def _ensure_postgres_database() -> tuple[bool, str | None]:
    """Create `feather_test` on Postgres if it doesn't exist.

    CREATE DATABASE cannot run inside a transaction, hence autocommit=True.
    Any driver error is captured as the failure reason — never re-raised.
    """
    try:
        admin = psycopg2.connect(POSTGRES_ADMIN_DSN)
        admin.autocommit = True
        cur = admin.cursor()
        try:
            cur.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (TARGET_DB,)
            )
            if cur.fetchone() is None:
                # Identifier cannot be parameterized; TARGET_DB is a fixed const.
                cur.execute(f'CREATE DATABASE "{TARGET_DB}"')
        finally:
            cur.close()
            admin.close()
    except Exception as exc:
        return (False, str(exc))

    return postgres_check()
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/unit/test_db_bootstrap.py::TestEnsurePostgresDatabase -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add tests/db_bootstrap.py tests/unit/test_db_bootstrap.py
git commit -m "test(db-bootstrap): add Postgres CREATE DATABASE IF NOT EXISTS"
```

---

### Task 3: MySQL bootstrap (TDD)

**Files:**
- Modify: `tests/db_bootstrap.py`
- Test: `tests/unit/test_db_bootstrap.py`

- [ ] **Step 1: Write failing MySQL-bootstrap tests**

Append to `tests/unit/test_db_bootstrap.py`:

```python
class TestEnsureMySQLDatabase:
    def _install_admin_connect(self, monkeypatch, exists: bool):
        from tests import db_bootstrap as dbb

        executed: list[str] = []

        class FakeCursor:
            def execute(self, sql, *_):
                executed.append(sql)

            def fetchone(self):
                return (dbb.TARGET_DB,) if exists else None

            def close(self):
                pass

        class FakeConn:
            def cursor(self):
                return FakeCursor()

            def close(self):
                pass

        def fake_connect(**kwargs):
            assert "database" not in kwargs, (
                "admin connect must NOT specify a database"
            )
            return FakeConn()

        monkeypatch.setattr(dbb.mysql.connector, "connect", fake_connect)
        return executed

    def test_db_exists_no_create(self, monkeypatch):
        from tests import db_bootstrap as dbb

        executed = self._install_admin_connect(monkeypatch, exists=True)
        monkeypatch.setattr(dbb, "mysql_check", lambda: (True, None))

        ok, reason = dbb._ensure_mysql_database()

        assert ok is True
        assert reason is None
        assert not any("CREATE DATABASE" in s for s in executed)

    def test_db_missing_issues_create(self, monkeypatch):
        from tests import db_bootstrap as dbb

        executed = self._install_admin_connect(monkeypatch, exists=False)
        monkeypatch.setattr(dbb, "mysql_check", lambda: (True, None))

        ok, reason = dbb._ensure_mysql_database()

        assert ok is True
        assert reason is None
        assert any(
            "CREATE DATABASE" in s and dbb.TARGET_DB in s for s in executed
        )

    def test_driver_error_is_captured_not_raised(self, monkeypatch):
        from tests import db_bootstrap as dbb

        def boom(**k):
            raise dbb.mysql.connector.Error("connection refused")

        monkeypatch.setattr(dbb.mysql.connector, "connect", boom)

        ok, reason = dbb._ensure_mysql_database()

        assert ok is False
        assert "connection refused" in reason
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/unit/test_db_bootstrap.py::TestEnsureMySQLDatabase -v`
Expected: FAIL with `AttributeError: ... '_ensure_mysql_database'`

- [ ] **Step 3: Add `_ensure_mysql_database` to `tests/db_bootstrap.py`**

Append to `tests/db_bootstrap.py`:

```python
def _ensure_mysql_database() -> tuple[bool, str | None]:
    """Create `feather_test` on MySQL if it doesn't exist.

    Connects with no `database=` kwarg to avoid the chicken-and-egg of
    asking for a DB that may not yet exist. Any driver error is captured
    as the failure reason — never re-raised.
    """
    try:
        admin = mysql.connector.connect(**MYSQL_ADMIN_KWARGS)
        cur = admin.cursor()
        try:
            cur.execute(
                "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA "
                "WHERE SCHEMA_NAME = %s",
                (TARGET_DB,),
            )
            if cur.fetchone() is None:
                cur.execute(f"CREATE DATABASE `{TARGET_DB}`")
        finally:
            cur.close()
            admin.close()
    except Exception as exc:
        return (False, str(exc))

    return mysql_check()
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/unit/test_db_bootstrap.py::TestEnsureMySQLDatabase -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add tests/db_bootstrap.py tests/unit/test_db_bootstrap.py
git commit -m "test(db-bootstrap): add MySQL CREATE DATABASE IF NOT EXISTS"
```

---

### Task 4: Combined entry point + idempotency (TDD)

**Files:**
- Modify: `tests/db_bootstrap.py`
- Test: `tests/unit/test_db_bootstrap.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_db_bootstrap.py`:

```python
class TestEnsureBootstrapDatabases:
    def test_returns_dict_with_both_flavors(self, monkeypatch):
        from tests import db_bootstrap as dbb

        monkeypatch.setattr(dbb, "_ensure_postgres_database", lambda: (True, None))
        monkeypatch.setattr(dbb, "_ensure_mysql_database", lambda: (True, None))

        results = dbb.ensure_bootstrap_databases()

        assert set(results.keys()) == {"postgres", "mysql"}
        assert results["postgres"] == (True, None)
        assert results["mysql"] == (True, None)

    def test_failure_reasons_are_propagated(self, monkeypatch):
        from tests import db_bootstrap as dbb

        monkeypatch.setattr(
            dbb, "_ensure_postgres_database", lambda: (False, "pg down")
        )
        monkeypatch.setattr(
            dbb, "_ensure_mysql_database", lambda: (False, "my down")
        )

        results = dbb.ensure_bootstrap_databases()

        assert results["postgres"] == (False, "pg down")
        assert results["mysql"] == (False, "my down")

    def test_idempotent_second_call_issues_no_create(self, monkeypatch):
        """Two back-to-back calls on a DB that already exists → zero
        CREATE statements on the second call (the existence check
        short-circuits). This locks the spec's idempotency requirement."""
        from tests import db_bootstrap as dbb

        executed: list[str] = []

        class FakeCursor:
            def execute(self, sql, *_):
                executed.append(sql)

            def fetchone(self):
                return (1,)  # always "exists"

            def close(self):
                pass

        class FakeConn:
            autocommit = False

            def cursor(self):
                return FakeCursor()

            def close(self):
                pass

        monkeypatch.setattr(dbb.psycopg2, "connect", lambda *a, **k: FakeConn())
        monkeypatch.setattr(
            dbb.mysql.connector, "connect", lambda **k: FakeConn()
        )
        monkeypatch.setattr(dbb, "postgres_check", lambda: (True, None))
        monkeypatch.setattr(dbb, "mysql_check", lambda: (True, None))

        dbb.ensure_bootstrap_databases()
        dbb.ensure_bootstrap_databases()

        creates = [s for s in executed if "CREATE DATABASE" in s]
        assert creates == []
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/unit/test_db_bootstrap.py::TestEnsureBootstrapDatabases -v`
Expected: FAIL with `AttributeError: ... 'ensure_bootstrap_databases'`

- [ ] **Step 3: Add `ensure_bootstrap_databases`**

Append to `tests/db_bootstrap.py`:

```python
# ---------------------------------------------------------------------------
# Combined session-start entry point
# ---------------------------------------------------------------------------


def ensure_bootstrap_databases() -> dict[str, tuple[bool, str | None]]:
    """Run both flavor bootstraps. Returns per-flavor (ok, reason).

    Called once from `pytest_sessionstart`. Per-flavor logic is
    idempotent: exists → no CREATE; missing → one CREATE.
    """
    return {
        "postgres": _ensure_postgres_database(),
        "mysql": _ensure_mysql_database(),
    }
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/unit/test_db_bootstrap.py::TestEnsureBootstrapDatabases -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add tests/db_bootstrap.py tests/unit/test_db_bootstrap.py
git commit -m "test(db-bootstrap): add combined ensure_bootstrap_databases entry point"
```

---

### Task 5: Banner text helper (TDD)

**Files:**
- Modify: `tests/db_bootstrap.py`
- Test: `tests/unit/test_db_bootstrap.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_db_bootstrap.py`:

```python
class TestFormatBanner:
    def test_both_ok_returns_none(self):
        from tests.db_bootstrap import format_banner

        assert format_banner({
            "postgres": (True, None),
            "mysql": (True, None),
        }) is None

    def test_postgres_down_names_brew_command(self):
        from tests.db_bootstrap import format_banner

        out = format_banner({
            "postgres": (False, "could not connect"),
            "mysql": (True, None),
        })
        assert out is not None
        assert "brew services start postgresql@17" in out
        assert "could not connect" in out

    def test_mysql_down_names_brew_command(self):
        from tests.db_bootstrap import format_banner

        out = format_banner({
            "postgres": (True, None),
            "mysql": (False, "access denied"),
        })
        assert out is not None
        assert "brew services start mysql" in out
        assert "access denied" in out

    def test_both_down_names_both(self):
        from tests.db_bootstrap import format_banner

        out = format_banner({
            "postgres": (False, "pg"),
            "mysql": (False, "my"),
        })
        assert "brew services start postgresql@17" in out
        assert "brew services start mysql" in out
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/unit/test_db_bootstrap.py::TestFormatBanner -v`
Expected: FAIL with `ImportError: cannot import name 'format_banner'`

- [ ] **Step 3: Add `format_banner`**

Append to `tests/db_bootstrap.py`:

```python
# ---------------------------------------------------------------------------
# Banner shown at session start when a server is down
# ---------------------------------------------------------------------------


_BREW_COMMANDS = {
    "postgres": "brew services start postgresql@17",
    "mysql": "brew services start mysql",
}


def format_banner(results: dict[str, tuple[bool, str | None]]) -> str | None:
    """Return the session-start banner text, or None if both flavors are OK."""
    failed = [(flavor, reason) for flavor, (ok, reason) in results.items() if not ok]
    if not failed:
        return None

    lines = ["", "=" * 72, "feather-etl test suite: local DB unavailable"]
    for flavor, reason in failed:
        lines.append(f"  {flavor}: {reason}")
        lines.append(f"    fix:  {_BREW_COMMANDS[flavor]}")
    lines.append("DB-gated tests will skip. Suite will still exit 0.")
    lines.append("=" * 72)
    return "\n".join(lines)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/unit/test_db_bootstrap.py::TestFormatBanner -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add tests/db_bootstrap.py tests/unit/test_db_bootstrap.py
git commit -m "test(db-bootstrap): add session-start banner with brew-service hints"
```

---

### Task 6: Marker factories (TDD)

**Files:**
- Modify: `tests/db_bootstrap.py`
- Test: `tests/unit/test_db_bootstrap.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_db_bootstrap.py`:

```python
class TestMarkerFactories:
    """Markers are factories (not module-level constants) because conftest
    imports this module BEFORE pytest_sessionstart runs bootstrap — if
    the skipif boolean were evaluated at module load, it would see the
    pre-bootstrap state."""

    def test_postgres_marker_when_available(self, monkeypatch):
        from tests import db_bootstrap as dbb

        monkeypatch.setattr(dbb, "postgres_check", lambda: (True, None))
        marker = dbb.postgres_marker()

        # A non-skipping skipif has condition=False
        assert marker.kwargs.get("condition") is False or marker.args[0] is False

    def test_postgres_marker_when_unavailable_uses_reason(self, monkeypatch):
        from tests import db_bootstrap as dbb

        monkeypatch.setattr(dbb, "postgres_check", lambda: (False, "pg down"))
        marker = dbb.postgres_marker()

        # condition=True → skip; reason comes from probe
        cond = marker.kwargs.get("condition", marker.args[0] if marker.args else None)
        assert cond is True
        assert "pg down" in marker.kwargs["reason"]

    def test_mysql_marker_when_unavailable_uses_reason(self, monkeypatch):
        from tests import db_bootstrap as dbb

        monkeypatch.setattr(dbb, "mysql_check", lambda: (False, "my down"))
        marker = dbb.mysql_marker()

        cond = marker.kwargs.get("condition", marker.args[0] if marker.args else None)
        assert cond is True
        assert "my down" in marker.kwargs["reason"]
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/unit/test_db_bootstrap.py::TestMarkerFactories -v`
Expected: FAIL with `AttributeError: ... 'postgres_marker'`

- [ ] **Step 3: Add marker factories**

Append to `tests/db_bootstrap.py`:

```python
# ---------------------------------------------------------------------------
# Marker factories
# ---------------------------------------------------------------------------


def postgres_marker():
    """Build a fresh `pytest.mark.skipif` from a live probe.

    Called at test-file import time — which is *after* pytest_sessionstart
    has run bootstrap, so the probe sees the live DB.
    """
    ok, reason = postgres_check()
    return pytest.mark.skipif(
        not ok, reason=reason or "PostgreSQL not available"
    )


def mysql_marker():
    ok, reason = mysql_check()
    return pytest.mark.skipif(
        not ok, reason=reason or "MySQL not available"
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/unit/test_db_bootstrap.py::TestMarkerFactories -v`
Expected: 3 PASS

- [ ] **Step 5: Full module test run**

Run: `uv run pytest tests/unit/test_db_bootstrap.py -v`
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add tests/db_bootstrap.py tests/unit/test_db_bootstrap.py
git commit -m "test(db-bootstrap): add postgres_marker/mysql_marker factories"
```

---

### Task 7: Wire bootstrap into conftest via `pytest_sessionstart`

**Files:**
- Modify: `tests/conftest.py:1-23`

- [ ] **Step 1: Replace the stale pg_ctl hooks**

Replace lines 1-23 of `tests/conftest.py` with:

```python
"""Shared test fixtures for feather-etl."""

import shutil
import sys
from pathlib import Path

import pytest
import yaml

from tests.db_bootstrap import ensure_bootstrap_databases, format_banner
from tests.helpers import make_curation_entry, write_curation


def pytest_sessionstart(session):
    """Create `feather_test` on local Postgres & MySQL if missing.

    Runs before test collection, so `@postgres` / `@mysql_db` skipif
    probes in test modules see the live DBs.

    If a server is down, emit a banner naming the exact `brew services`
    command to fix it. Never fail the session — the gated tests skip
    with a clear reason and the suite still exits 0.
    """
    results = ensure_bootstrap_databases()
    banner = format_banner(results)
    if banner:
        # stderr keeps the banner out of captured stdout that tests assert on
        print(banner, file=sys.stderr)
```

- [ ] **Step 2: Run full suite, confirm fixtures still work**

Run: `uv run pytest -q`
Expected: suite runs. If both DBs are up, **0 skips** with reason "PostgreSQL not available" or "MySQL not available". If a DB is down, banner appears and gated tests skip cleanly.

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test(db-bootstrap): trigger ensure_bootstrap_databases at session start"
```

---

### Task 8: Migrate `tests/unit/sources/test_postgres.py`

**Files:**
- Modify: `tests/unit/sources/test_postgres.py:11-27`

- [ ] **Step 1: Delete the local probe + marker block (lines 11-27)**

Remove these lines from `tests/unit/sources/test_postgres.py`:

```python
CONN_STR = "dbname=feather_test host=localhost"


def _postgres_available() -> bool:
    try:
        import psycopg2

        conn = psycopg2.connect(CONN_STR)
        conn.close()
        return True
    except Exception:
        return False


postgres = pytest.mark.skipif(
    not _postgres_available(), reason="PostgreSQL not available"
)
```

Replace with:

```python
from tests.db_bootstrap import POSTGRES_DSN as CONN_STR, postgres_marker

postgres = postgres_marker()
```

(Keep `CONN_STR` as the local alias — the rest of the file uses it on many lines; aliasing avoids a churny rename.)

- [ ] **Step 2: Run the file**

Run: `uv run pytest tests/unit/sources/test_postgres.py -v`
Expected: all previously-passing tests still PASS. No skips (assuming Postgres is up).

- [ ] **Step 3: Commit**

```bash
git add tests/unit/sources/test_postgres.py
git commit -m "test(db-bootstrap): migrate test_postgres.py to shared probe/marker"
```

---

### Task 9: Migrate `tests/e2e/test_03_discover.py`

**Files:**
- Modify: `tests/e2e/test_03_discover.py:28-46`

- [ ] **Step 1: Replace the probe + marker block**

Remove lines 31-46 (`CONN_STR`, `_postgres_available`, `postgres` marker) and replace with:

```python
from tests.db_bootstrap import POSTGRES_DSN as CONN_STR, postgres_marker

postgres = postgres_marker()
```

The existing `from tests.conftest import FIXTURES_DIR` import at line 28 stays.

- [ ] **Step 2: Run the file**

Run: `uv run pytest tests/e2e/test_03_discover.py -v`
Expected: all previously-passing tests still PASS. `TestDiscoverPostgresMultiDatabase` runs (no skip) if Postgres is up.

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/test_03_discover.py
git commit -m "test(db-bootstrap): migrate test_03_discover.py to shared probe/marker"
```

---

### Task 10: Migrate `tests/unit/sources/test_mysql.py`

**Files:**
- Modify: `tests/unit/sources/test_mysql.py:161-175`

- [ ] **Step 1: Replace the probe + marker block**

Remove lines 161-175 (the `MYSQL_CONN_KWARGS` constant, `_mysql_available` function, and `mysql_db` marker) and replace with:

```python
from tests.db_bootstrap import MYSQL_CONN_KWARGS, mysql_marker

mysql_db = mysql_marker()
```

- [ ] **Step 2: Run the file**

Run: `uv run pytest tests/unit/sources/test_mysql.py -v`
Expected: all previously-passing tests still PASS. MySQL integration tests run (no skip) if MySQL is up.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/sources/test_mysql.py
git commit -m "test(db-bootstrap): migrate test_mysql.py to shared probe/marker"
```

---

### Task 11: Integration tests — real DB bootstrap

**Files:**
- Create: `tests/integration/test_db_bootstrap.py`

These tests prove the bootstrap actually creates a DB against real servers. They use a **throwaway DB name** (`feather_bootstrap_it`) so they don't interfere with the live `feather_test` the rest of the suite depends on.

- [ ] **Step 1: Write the integration tests**

```python
# tests/integration/test_db_bootstrap.py
"""Real-DB integration tests for tests/db_bootstrap.py.

Uses a throwaway DB name so we never touch `feather_test`.
Each test: drop the DB → run bootstrap (pointed at the throwaway name)
→ assert the DB now exists → drop it again.
"""

from __future__ import annotations

import pytest

from tests.db_bootstrap import (
    MYSQL_ADMIN_KWARGS,
    POSTGRES_ADMIN_DSN,
    mysql_marker,
    postgres_marker,
)

THROWAWAY_DB = "feather_bootstrap_it"


@postgres_marker()
class TestPostgresBootstrapIntegration:
    def _drop(self):
        import psycopg2

        conn = psycopg2.connect(POSTGRES_ADMIN_DSN)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(f'DROP DATABASE IF EXISTS "{THROWAWAY_DB}"')
        cur.close()
        conn.close()

    def _exists(self) -> bool:
        import psycopg2

        conn = psycopg2.connect(POSTGRES_ADMIN_DSN)
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (THROWAWAY_DB,)
        )
        found = cur.fetchone() is not None
        cur.close()
        conn.close()
        return found

    def test_bootstrap_creates_missing_database(self, monkeypatch):
        """Point the Postgres bootstrap at THROWAWAY_DB, drop it, run, assert."""
        from tests import db_bootstrap as dbb

        self._drop()
        assert not self._exists()

        monkeypatch.setattr(dbb, "TARGET_DB", THROWAWAY_DB)
        monkeypatch.setattr(
            dbb, "POSTGRES_DSN", f"dbname={THROWAWAY_DB} host=localhost"
        )
        try:
            ok, reason = dbb._ensure_postgres_database()
            assert ok, reason
            assert self._exists()
        finally:
            self._drop()


@mysql_marker()
class TestMySQLBootstrapIntegration:
    def _drop(self):
        import mysql.connector

        conn = mysql.connector.connect(**MYSQL_ADMIN_KWARGS)
        cur = conn.cursor()
        cur.execute(f"DROP DATABASE IF EXISTS `{THROWAWAY_DB}`")
        cur.close()
        conn.close()

    def _exists(self) -> bool:
        import mysql.connector

        conn = mysql.connector.connect(**MYSQL_ADMIN_KWARGS)
        cur = conn.cursor()
        cur.execute(
            "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA "
            "WHERE SCHEMA_NAME = %s",
            (THROWAWAY_DB,),
        )
        found = cur.fetchone() is not None
        cur.close()
        conn.close()
        return found

    def test_bootstrap_creates_missing_database(self, monkeypatch):
        from tests import db_bootstrap as dbb

        self._drop()
        assert not self._exists()

        monkeypatch.setattr(dbb, "TARGET_DB", THROWAWAY_DB)
        monkeypatch.setattr(
            dbb,
            "MYSQL_CONN_KWARGS",
            {"host": "localhost", "user": "root", "database": THROWAWAY_DB},
        )
        try:
            ok, reason = dbb._ensure_mysql_database()
            assert ok, reason
            assert self._exists()
        finally:
            self._drop()
```

- [ ] **Step 2: Run the file**

Run: `uv run pytest tests/integration/test_db_bootstrap.py -v`
Expected: 2 PASS (if both DBs up); otherwise the unavailable flavor skips cleanly.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_db_bootstrap.py
git commit -m "test(db-bootstrap): add real-DB integration tests via throwaway DB"
```

---

### Task 12: Docs — Local DB prerequisites

**Files:**
- Modify: `docs/CONTRIBUTING.md` (insert before `## Dev shortcuts` at ~line 164)

- [ ] **Step 1: Insert the section**

Insert this block immediately before the `## Dev shortcuts (\`poe\`)` heading:

```markdown
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
```

- [ ] **Step 2: Verify in an editor / markdown viewer**

Just read the section back to make sure it slots in cleanly between the preceding "Do not create feature-named test files" paragraph and the `## Dev shortcuts` heading.

- [ ] **Step 3: Commit**

```bash
git add docs/CONTRIBUTING.md
git commit -m "docs(contributing): add Local DB prerequisites section"
```

---

### Task 13: End-to-end verification (no commit)

This is the spec's acceptance-criteria exemplar (§3), run by hand.

- [ ] **Step 1: Baseline — both servers up**

Run:
```bash
brew services start postgresql@17 mysql
uv run pytest -q
```
Expected: suite completes, **zero** skips with reason "PostgreSQL not available" or "MySQL not available".

Quick check:
```bash
uv run pytest -q 2>&1 | grep -E "(PostgreSQL|MySQL) not available" | wc -l
```
Expected: `0`.

- [ ] **Step 2: Postgres down**

Run:
```bash
brew services stop postgresql@17
uv run pytest -q
```
Expected: banner on stderr naming `brew services start postgresql@17`, 5 postgres-gated tests skip, exit code 0.

- [ ] **Step 3: Restore**

Run:
```bash
brew services start postgresql@17
uv run pytest -q
```
Expected: back to zero DB-gated skips.

- [ ] **Step 4: Report**

If all three steps pass, the implementation meets the spec's acceptance criteria. No commit — this is verification only.

---

## Self-review

- **Spec coverage:** every spec §3 acceptance criterion maps to Task 13 steps. Spec §4 Scope items: auto-create DB (Tasks 2–4), banner (Task 5), probe consolidation (Tasks 8–10), stale `pg_ctl` removal (Task 7), CONTRIBUTING section (Task 12). Spec §8 Test design: probe tests (Task 1), exists/missing/driver-error for each flavor (Tasks 2–3), idempotency (Task 4), integration (Task 11).
- **Placeholders:** none — every code step shows the actual code.
- **Type consistency:** `postgres_check()`, `mysql_check()`, `_ensure_*_database()`, and `ensure_bootstrap_databases()` all return `(bool, str | None)` / `dict[str, tuple[bool, str | None]]` — consistent across tasks and callers.
