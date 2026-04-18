"""Tests for MySQL source.

Real-database tests are marked with a skip decorator and are skipped when
the local MySQL instance is not reachable.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# MySQLSource.from_yaml — unit tests (no DB needed)
# ---------------------------------------------------------------------------


class TestMySQLFromYaml:
    def test_minimal_entry_builds_connect_kwargs(self):
        from feather_etl.sources.mysql import MySQLSource

        entry = {
            "name": "wh",
            "type": "mysql",
            "host": "db.example.com",
            "user": "u",
            "password": "p",
            "database": "warehouse",
        }
        src = MySQLSource.from_yaml(entry, Path("."))
        assert src.name == "wh"
        assert src.host == "db.example.com"
        assert src.port == 3306
        assert src.database == "warehouse"
        assert src._connect_kwargs["host"] == "db.example.com"
        assert src._connect_kwargs["port"] == 3306
        assert src._connect_kwargs["database"] == "warehouse"
        assert src._connect_kwargs["user"] == "u"
        assert src._connect_kwargs["password"] == "p"

    def test_explicit_port(self):
        from feather_etl.sources.mysql import MySQLSource

        entry = {
            "name": "wh",
            "type": "mysql",
            "host": "h",
            "port": 3307,
            "user": "u",
            "password": "p",
            "database": "X",
        }
        src = MySQLSource.from_yaml(entry, Path("."))
        assert src.port == 3307
        assert src._connect_kwargs["port"] == 3307

    def test_explicit_connection_string(self):
        from feather_etl.sources.mysql import MySQLSource

        entry = {
            "name": "wh",
            "type": "mysql",
            "connection_string": "host=raw;database=verbatim",
        }
        src = MySQLSource.from_yaml(entry, Path("."))
        assert src.connection_string == "host=raw;database=verbatim"

    def test_databases_list_and_xor_rules(self):
        from feather_etl.sources.mysql import MySQLSource

        ok = {
            "name": "wh",
            "type": "mysql",
            "host": "h",
            "user": "u",
            "password": "p",
            "databases": ["A", "B"],
        }
        src = MySQLSource.from_yaml(ok, Path("."))
        assert src.databases == ["A", "B"]

        with pytest.raises(ValueError, match="mutually exclusive"):
            MySQLSource.from_yaml({**ok, "database": "C"}, Path("."))

        with pytest.raises(ValueError, match="non-empty"):
            MySQLSource.from_yaml({**ok, "databases": []}, Path("."))

    def test_missing_host_and_connection_string_raises(self):
        from feather_etl.sources.mysql import MySQLSource

        with pytest.raises(ValueError, match="requires either"):
            MySQLSource.from_yaml({"name": "x", "type": "mysql"}, Path("."))


# ---------------------------------------------------------------------------
# MySQLSource — unit tests (no DB needed)
# ---------------------------------------------------------------------------


class TestMySQLSourceUnit:
    def test_source_type_is_mysql(self):
        from feather_etl.sources.mysql import MySQLSource

        assert MySQLSource.type == "mysql"

    def test_watermark_passthrough(self):
        """MySQLSource uses the default _format_watermark (ISO unchanged)."""
        from feather_etl.sources.mysql import MySQLSource

        src = MySQLSource(connection_string="dummy")
        assert src._format_watermark("2026-01-01T10:00:00") == "2026-01-01T10:00:00"

    def test_build_where_filter_only(self):
        from feather_etl.sources.mysql import MySQLSource

        src = MySQLSource(connection_string="dummy")
        result = src._build_where_clause(filter="active = 1")
        assert result == " WHERE (active = 1)"

    def test_build_where_watermark_only(self):
        from feather_etl.sources.mysql import MySQLSource

        src = MySQLSource(connection_string="dummy")
        result = src._build_where_clause(
            watermark_column="modified_at", watermark_value="2026-01-01"
        )
        assert result == " WHERE modified_at > '2026-01-01'"

    def test_build_where_both(self):
        from feather_etl.sources.mysql import MySQLSource

        src = MySQLSource(connection_string="dummy")
        result = src._build_where_clause(
            filter="active = 1",
            watermark_column="modified_at",
            watermark_value="2026-01-01",
        )
        assert result == " WHERE (active = 1) AND modified_at > '2026-01-01'"


class TestMySQLValidateSourceTable:
    def test_plain_table_ok(self):
        from feather_etl.sources.mysql import MySQLSource

        src = MySQLSource(connection_string="dummy", name="x")
        assert src.validate_source_table("orders") == []

    def test_qualified_table_ok(self):
        from feather_etl.sources.mysql import MySQLSource

        src = MySQLSource(connection_string="dummy", name="x")
        assert src.validate_source_table("mydb.orders") == []


# ---------------------------------------------------------------------------
# MySQLSource.check() — unit tests (mocked connector)
# ---------------------------------------------------------------------------


class TestMySQLCheckLastError:
    def test_check_failure_populates_last_error(self, monkeypatch):
        from feather_etl.sources import mysql as mysql_mod
        from feather_etl.sources.mysql import MySQLSource

        def boom(**kwargs):
            raise mysql_mod.mysql.connector.Error("Access denied for user 'root'")

        monkeypatch.setattr(mysql_mod.mysql.connector, "connect", boom)

        src = MySQLSource(connection_string="dummy")
        src._connect_kwargs = {"host": "nope"}
        assert src.check() is False
        assert src._last_error is not None
        assert "Access denied" in src._last_error

    def test_check_success_clears_last_error(self, monkeypatch):
        from feather_etl.sources import mysql as mysql_mod
        from feather_etl.sources.mysql import MySQLSource

        src = MySQLSource(connection_string="dummy")
        src._connect_kwargs = {"host": "localhost"}
        src._last_error = "stale error from a prior call"

        class FakeConn:
            def close(self):
                pass

        monkeypatch.setattr(
            mysql_mod.mysql.connector, "connect", lambda **k: FakeConn()
        )
        assert src.check() is True
        assert src._last_error is None
