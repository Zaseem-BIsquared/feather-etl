"""Real-DB integration tests for tests/db_bootstrap.py.

Uses a throwaway DB name so we never touch `feather_test`.
Each test: drop the DB → run bootstrap (pointed at the throwaway name)
→ assert the DB now exists → drop it again.
"""

from __future__ import annotations

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
        try:
            conn.autocommit = True
            cur = conn.cursor()
            try:
                cur.execute(f'DROP DATABASE IF EXISTS "{THROWAWAY_DB}"')
            finally:
                cur.close()
        finally:
            conn.close()

    def _exists(self) -> bool:
        import psycopg2

        conn = psycopg2.connect(POSTGRES_ADMIN_DSN)
        try:
            cur = conn.cursor()
            try:
                cur.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s",
                    (THROWAWAY_DB,),
                )
                return cur.fetchone() is not None
            finally:
                cur.close()
        finally:
            conn.close()

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
        try:
            cur = conn.cursor()
            try:
                cur.execute(f"DROP DATABASE IF EXISTS `{THROWAWAY_DB}`")
            finally:
                cur.close()
        finally:
            conn.close()

    def _exists(self) -> bool:
        import mysql.connector

        conn = mysql.connector.connect(**MYSQL_ADMIN_KWARGS)
        try:
            cur = conn.cursor()
            try:
                cur.execute(
                    "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA "
                    "WHERE SCHEMA_NAME = %s",
                    (THROWAWAY_DB,),
                )
                return cur.fetchone() is not None
            finally:
                cur.close()
        finally:
            conn.close()

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
