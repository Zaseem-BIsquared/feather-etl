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
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TARGET_DB,))
            if cur.fetchone() is None:
                # Identifier cannot be parameterized; TARGET_DB is a fixed const.
                cur.execute(f'CREATE DATABASE "{TARGET_DB}"')
        finally:
            cur.close()
            admin.close()
    except Exception as exc:
        return (False, str(exc))

    return postgres_check()


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
