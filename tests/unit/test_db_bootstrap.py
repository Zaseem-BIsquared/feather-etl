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
