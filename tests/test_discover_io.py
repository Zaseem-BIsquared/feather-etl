"""Unit tests for discover I/O helpers in feather_etl.config."""


class TestSanitize:
    def test_keeps_safe_chars(self):
        from feather_etl.config import _sanitize

        assert _sanitize("prod-erp.db_01") == "prod-erp.db_01"

    def test_replaces_unsafe_chars(self):
        from feather_etl.config import _sanitize

        assert _sanitize("prod/erp") == "prod_erp"
        assert _sanitize("192.168.2.62:1433") == "192.168.2.62_1433"
        assert _sanitize("a b c") == "a_b_c"

    def test_preserves_dots_and_hyphens(self):
        from feather_etl.config import _sanitize

        assert _sanitize("db.internal-prod") == "db.internal-prod"


class TestResolvedSourceName:
    def _cfg(self, **kwargs):
        from feather_etl.config import SourceConfig

        return SourceConfig(**kwargs)

    def test_user_name_wins_over_auto(self):
        from feather_etl.config import resolved_source_name

        cfg = self._cfg(type="sqlserver", name="prod-erp", host="db.internal")
        assert resolved_source_name(cfg) == "prod-erp"

    def test_user_name_is_sanitized(self):
        from feather_etl.config import resolved_source_name

        cfg = self._cfg(type="sqlserver", name="prod/erp", host="db.internal")
        assert resolved_source_name(cfg) == "prod_erp"

    def test_sqlserver_auto_uses_type_and_host(self):
        from feather_etl.config import resolved_source_name

        cfg = self._cfg(type="sqlserver", host="192.168.2.62")
        assert resolved_source_name(cfg) == "sqlserver-192.168.2.62"

    def test_sqlserver_auto_sanitizes_host(self):
        from feather_etl.config import resolved_source_name

        cfg = self._cfg(type="sqlserver", host="192.168.2.62:1433")
        assert resolved_source_name(cfg) == "sqlserver-192.168.2.62_1433"

    def test_postgres_auto_uses_type_and_host(self):
        from feather_etl.config import resolved_source_name

        cfg = self._cfg(type="postgres", host="db.internal")
        assert resolved_source_name(cfg) == "postgres-db.internal"

    def test_csv_auto_uses_directory_basename(self, tmp_path):
        from feather_etl.config import resolved_source_name

        csv_dir = tmp_path / "csv_data"
        csv_dir.mkdir()
        cfg = self._cfg(type="csv", path=csv_dir)
        assert resolved_source_name(cfg) == "csv-csv_data"

    def test_sqlite_auto_uses_file_basename_without_ext(self, tmp_path):
        from feather_etl.config import resolved_source_name

        sqlite_file = tmp_path / "source.sqlite"
        sqlite_file.touch()
        cfg = self._cfg(type="sqlite", path=sqlite_file)
        assert resolved_source_name(cfg) == "sqlite-source"

    def test_duckdb_auto_uses_file_basename_without_ext(self, tmp_path):
        from feather_etl.config import resolved_source_name

        duck_file = tmp_path / "my_data.duckdb"
        duck_file.touch()
        cfg = self._cfg(type="duckdb", path=duck_file)
        assert resolved_source_name(cfg) == "duckdb-my_data"

    def test_excel_auto_uses_file_basename_without_ext(self, tmp_path):
        from feather_etl.config import resolved_source_name

        xl = tmp_path / "sheet.xlsx"
        xl.touch()
        cfg = self._cfg(type="excel", path=xl)
        assert resolved_source_name(cfg) == "excel-sheet"

    def test_json_auto_uses_file_basename_without_ext(self, tmp_path):
        from feather_etl.config import resolved_source_name

        js = tmp_path / "events.json"
        js.touch()
        cfg = self._cfg(type="json", path=js)
        assert resolved_source_name(cfg) == "json-events"

    def test_db_source_without_host_falls_back_to_unknown(self):
        from feather_etl.config import resolved_source_name

        cfg = self._cfg(type="sqlserver", host=None)
        assert resolved_source_name(cfg) == "sqlserver-unknown"

    def test_file_source_without_path_falls_back_to_unknown(self):
        from feather_etl.config import resolved_source_name

        cfg = self._cfg(type="csv", path=None)
        assert resolved_source_name(cfg) == "csv-unknown"


class TestSchemaOutputPath:
    def _cfg(self, **kwargs):
        from feather_etl.config import SourceConfig

        return SourceConfig(**kwargs)

    def test_db_source_includes_database_suffix(self):
        from pathlib import Path

        from feather_etl.config import schema_output_path

        cfg = self._cfg(type="sqlserver", host="192.168.2.62", database="ZAKYA")
        assert schema_output_path(cfg) == Path("schema_sqlserver-192.168.2.62_ZAKYA.json")

    def test_db_source_sanitizes_database(self):
        from pathlib import Path

        from feather_etl.config import schema_output_path

        cfg = self._cfg(type="sqlserver", host="db.internal", database="My DB")
        assert schema_output_path(cfg) == Path("schema_sqlserver-db.internal_My_DB.json")

    def test_db_source_without_database(self):
        from pathlib import Path

        from feather_etl.config import schema_output_path

        cfg = self._cfg(type="sqlserver", host="db.internal")
        assert schema_output_path(cfg) == Path("schema_sqlserver-db.internal.json")

    def test_file_source_has_no_database_suffix(self, tmp_path):
        from pathlib import Path

        from feather_etl.config import schema_output_path

        sqlite_file = tmp_path / "source.sqlite"
        sqlite_file.touch()
        cfg = self._cfg(type="sqlite", path=sqlite_file)
        assert schema_output_path(cfg) == Path("schema_sqlite-source.json")

    def test_user_name_used_in_path(self):
        from pathlib import Path

        from feather_etl.config import schema_output_path

        cfg = self._cfg(type="sqlserver", name="prod-erp", host="db", database="ZAKYA")
        assert schema_output_path(cfg) == Path("schema_prod-erp_ZAKYA.json")
