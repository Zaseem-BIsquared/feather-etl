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


MYSQL_CONN_KWARGS = {"host": "localhost", "user": "root", "database": "feather_test"}


def _mysql_available() -> bool:
    try:
        import mysql.connector

        conn = mysql.connector.connect(**MYSQL_CONN_KWARGS)
        conn.close()
        return True
    except Exception:
        return False


mysql_db = pytest.mark.skipif(not _mysql_available(), reason="MySQL not available")


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


# ---------------------------------------------------------------------------
# MySQLSource.discover() — integration tests (real MySQL)
# ---------------------------------------------------------------------------


@mysql_db
class TestMySQLDiscoverIntegration:
    @pytest.fixture
    def source(self):
        from feather_etl.sources.mysql import MySQLSource

        src = MySQLSource(connection_string="")
        src._connect_kwargs = MYSQL_CONN_KWARGS
        src.database = "feather_test"
        return src

    def test_discover_returns_erp_tables(self, source):
        schemas = source.discover()
        names = {s.name for s in schemas}
        assert "erp_customers" in names
        assert "erp_products" in names
        assert "erp_sales" in names

    def test_discover_schema_fields(self, source):
        schemas = source.discover()
        sales = next(s for s in schemas if s.name == "erp_sales")
        assert sales.supports_incremental is True
        assert sales.primary_key is None
        col_names = [c[0] for c in sales.columns]
        assert "id" in col_names
        assert "amount" in col_names

    def test_discover_column_types(self, source):
        schemas = source.discover()
        sales = next(s for s in schemas if s.name == "erp_sales")
        col_types = {c[0]: c[1] for c in sales.columns}
        assert col_types["id"] == "int"
        assert col_types["product"] == "varchar"
        assert col_types["amount"] == "decimal"


# ---------------------------------------------------------------------------
# MySQLSource.get_schema() — integration tests (real MySQL)
# ---------------------------------------------------------------------------


@mysql_db
class TestMySQLGetSchemaIntegration:
    @pytest.fixture
    def source(self):
        from feather_etl.sources.mysql import MySQLSource

        src = MySQLSource(connection_string="")
        src._connect_kwargs = MYSQL_CONN_KWARGS
        src.database = "feather_test"
        return src

    def test_get_schema_returns_columns(self, source):
        cols = source.get_schema("erp_sales")
        col_names = [c[0] for c in cols]
        assert "id" in col_names
        assert "customer_id" in col_names
        assert "product" in col_names
        assert "amount" in col_names
        assert "modified_at" in col_names

    def test_get_schema_returns_types(self, source):
        cols = source.get_schema("erp_sales")
        col_types = {c[0]: c[1] for c in cols}
        assert col_types["id"] == "int"
        assert col_types["amount"] == "decimal"
        assert col_types["modified_at"] == "timestamp"
