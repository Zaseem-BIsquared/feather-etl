"""Unit tests for tests/db_bootstrap.py — drivers are always mocked here."""

from __future__ import annotations


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

        monkeypatch.setattr(dbb.mysql.connector, "connect", lambda **k: FakeConn())
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


class TestEnsurePostgresDatabase:
    def _install_admin_connect(self, monkeypatch, exists: bool):
        """Patch psycopg2.connect for the admin DSN. Returns the list of
        SQL statements the fake cursor observed."""
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
        assert any("CREATE DATABASE" in s and dbb.TARGET_DB in s for s in executed)

    def test_driver_error_is_captured_not_raised(self, monkeypatch):
        from tests import db_bootstrap as dbb

        def boom(*a, **k):
            raise dbb.psycopg2.OperationalError("server down")

        monkeypatch.setattr(dbb.psycopg2, "connect", boom)

        ok, reason = dbb._ensure_postgres_database()

        assert ok is False
        assert "server down" in reason


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
            assert "database" not in kwargs, "admin connect must NOT specify a database"
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
        assert any("CREATE DATABASE" in s and dbb.TARGET_DB in s for s in executed)

    def test_driver_error_is_captured_not_raised(self, monkeypatch):
        from tests import db_bootstrap as dbb

        def boom(**k):
            raise dbb.mysql.connector.Error("connection refused")

        monkeypatch.setattr(dbb.mysql.connector, "connect", boom)

        ok, reason = dbb._ensure_mysql_database()

        assert ok is False
        assert "connection refused" in reason


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
