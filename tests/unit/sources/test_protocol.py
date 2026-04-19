"""Tests for the Source protocol / contract."""

from __future__ import annotations


class TestSourceProtocol:
    def test_protocol_has_from_yaml_and_validate_source_table(self):
        from feather_etl.sources import Source

        assert hasattr(Source, "from_yaml")
        assert hasattr(Source, "validate_source_table")

    def test_each_source_class_declares_type_attr(self):
        from feather_etl.sources.csv import CsvSource
        from feather_etl.sources.duckdb_file import DuckDBFileSource
        from feather_etl.sources.excel import ExcelSource
        from feather_etl.sources.json_source import JsonSource
        from feather_etl.sources.postgres import PostgresSource
        from feather_etl.sources.sqlite import SqliteSource
        from feather_etl.sources.sqlserver import SqlServerSource

        assert CsvSource.type == "csv"
        assert DuckDBFileSource.type == "duckdb"
        assert ExcelSource.type == "excel"
        assert JsonSource.type == "json"
        assert PostgresSource.type == "postgres"
        assert SqliteSource.type == "sqlite"
        assert SqlServerSource.type == "sqlserver"
