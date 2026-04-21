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
