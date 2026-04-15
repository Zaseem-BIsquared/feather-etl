"""Happy-path E2E for `feather discover` over multiple sources.

Per docs/CONTRIBUTING.md (testing co-location): edge cases for the
discover command live in tests/commands/test_discover.py. This file holds
end-to-end workflow tests — what a user actually does at the keyboard.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tests.commands.conftest import multi_source_yaml
from tests.conftest import FIXTURES_DIR


@pytest.mark.usefixtures("stub_viewer_serve")
class TestDiscoverHeterogeneousSources:
    def test_single_csv_source_writes_one_file(self, runner, tmp_path, monkeypatch):
        from feather_etl.cli import app

        csvs = tmp_path / "csv"
        shutil.copytree(FIXTURES_DIR / "csv_data", csvs)
        cfg = multi_source_yaml(tmp_path, [
            {"name": "sheets", "type": "csv", "path": str(csvs)},
        ])
        monkeypatch.chdir(tmp_path)

        r = runner.invoke(app, ["discover", "--config", str(cfg)])
        assert r.exit_code == 0, r.output
        files = sorted(tmp_path.glob("schema_*.json"))
        assert [f.name for f in files] == ["schema_sheets.json"]
        payload = json.loads(files[0].read_text())
        assert isinstance(payload, list)
        assert len(payload) == 3  # csv_data has 3 files

    def test_heterogeneous_sources_write_one_file_per_source(
        self, runner, tmp_path, monkeypatch
    ):
        from feather_etl.cli import app

        csvs = tmp_path / "csv"
        shutil.copytree(FIXTURES_DIR / "csv_data", csvs)
        sqlite = tmp_path / "src.sqlite"
        shutil.copy2(FIXTURES_DIR / "sample_erp.sqlite", sqlite)
        duckdb_f = tmp_path / "src.duckdb"
        shutil.copy2(FIXTURES_DIR / "sample_erp.duckdb", duckdb_f)

        cfg = multi_source_yaml(tmp_path, [
            {"name": "sheets", "type": "csv", "path": str(csvs)},
            {"name": "sqlite_db", "type": "sqlite", "path": str(sqlite)},
            {"name": "duck", "type": "duckdb", "path": str(duckdb_f)},
        ])
        monkeypatch.chdir(tmp_path)

        r = runner.invoke(app, ["discover", "--config", str(cfg)])
        assert r.exit_code == 0, r.output
        names = {p.name for p in tmp_path.glob("schema_*.json")}
        assert names == {"schema_sheets.json", "schema_sqlite_db.json",
                         "schema_duck.json"}


CONN_STR = "dbname=feather_test host=localhost"


def _postgres_available() -> bool:
    try:
        import psycopg2
        psycopg2.connect(CONN_STR).close()
        return True
    except Exception:
        return False


postgres = pytest.mark.skipif(
    not _postgres_available(), reason="PostgreSQL not available"
)


@postgres
@pytest.mark.usefixtures("stub_viewer_serve")
class TestDiscoverPostgresMultiDatabase:
    def _create_databases(self, names):
        import psycopg2
        conn = psycopg2.connect(CONN_STR)
        conn.autocommit = True
        cur = conn.cursor()
        for n in names:
            cur.execute(f"DROP DATABASE IF EXISTS {n}")
            cur.execute(f"CREATE DATABASE {n}")
        cur.close()
        conn.close()

    def _drop_databases(self, names):
        import psycopg2
        conn = psycopg2.connect(CONN_STR)
        conn.autocommit = True
        cur = conn.cursor()
        for n in names:
            cur.execute(f"DROP DATABASE IF EXISTS {n}")
        cur.close()
        conn.close()

    def test_explicit_databases(self, runner, tmp_path, monkeypatch):
        from feather_etl.cli import app

        names = ["feather_a", "feather_b"]
        self._create_databases(names)
        try:
            cfg = multi_source_yaml(tmp_path, [
                {"name": "wh", "type": "postgres", "host": "localhost",
                 "user": "", "password": "", "databases": names},
            ])
            monkeypatch.chdir(tmp_path)
            r = runner.invoke(app, ["discover", "--config", str(cfg)])
            assert r.exit_code == 0, r.output
            files = {p.name for p in tmp_path.glob("schema_*.json")}
            assert files == {"schema_wh__feather_a.json",
                             "schema_wh__feather_b.json"}
        finally:
            self._drop_databases(names)

    def test_auto_enumerate(self, runner, tmp_path, monkeypatch):
        from feather_etl.cli import app

        names = ["feather_x", "feather_y"]
        self._create_databases(names)
        try:
            cfg = multi_source_yaml(tmp_path, [
                {"name": "wh", "type": "postgres", "host": "localhost",
                 "user": "", "password": ""},
            ])
            monkeypatch.chdir(tmp_path)
            r = runner.invoke(app, ["discover", "--config", str(cfg)])
            assert r.exit_code == 0, r.output
            files = {p.name for p in tmp_path.glob("schema_*.json")}
            for n in names:
                assert f"schema_wh__{n}.json" in files
        finally:
            self._drop_databases(names)
