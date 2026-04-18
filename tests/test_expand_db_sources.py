"""Tests for the shared expand_db_sources utility."""

from __future__ import annotations

from unittest.mock import MagicMock


class TestExpandDbSources:
    def test_file_sources_pass_through(self):
        """File sources are returned unchanged."""
        from feather_etl.sources.expand import expand_db_sources

        mock_src = MagicMock()
        mock_src.database = None
        mock_src.databases = None
        # Not a DatabaseSource subclass — simulate a FileSource
        result = expand_db_sources([mock_src])
        assert result == [mock_src]

    def test_db_source_with_single_database_passes_through(self):
        """DB source with database set is returned unchanged."""
        from feather_etl.sources.expand import expand_db_sources
        from feather_etl.sources.database_source import DatabaseSource

        mock_src = MagicMock(spec=DatabaseSource)
        mock_src.database = "mydb"
        mock_src.databases = None
        result = expand_db_sources([mock_src])
        assert result == [mock_src]

    def test_db_source_with_databases_list_expands(self):
        """DB source with databases: [a, b] produces one child per db."""
        from feather_etl.sources.expand import expand_db_sources
        from feather_etl.sources.database_source import DatabaseSource

        mock_src = MagicMock(spec=DatabaseSource)
        mock_src.database = None
        mock_src.databases = ["db_a", "db_b"]
        mock_src.name = "test_server"
        mock_src.type = "sqlserver"
        mock_src.host = "localhost"
        mock_src.port = 1433
        mock_src.user = "sa"
        mock_src.password = "pass"
        mock_src._explicit_name = False

        child_a = MagicMock(spec=DatabaseSource)
        child_b = MagicMock(spec=DatabaseSource)
        type(mock_src).from_yaml = MagicMock(side_effect=[child_a, child_b])

        result = expand_db_sources([mock_src])
        assert len(result) == 2
        calls = type(mock_src).from_yaml.call_args_list
        assert calls[0][0][0]["database"] == "db_a"
        assert calls[0][0][0]["name"] == "test_server__db_a"
        assert calls[1][0][0]["database"] == "db_b"
        assert calls[1][0][0]["name"] == "test_server__db_b"
