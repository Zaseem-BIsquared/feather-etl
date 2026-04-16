"""Happy-path E2E for `feather discover` over multiple sources.

Per docs/CONTRIBUTING.md (testing co-location): edge cases for the
discover command live in tests/commands/test_discover.py. This file holds
end-to-end workflow tests — what a user actually does at the keyboard.
"""

from __future__ import annotations

import json
import shutil
import time

import pytest

from tests.commands.conftest import multi_source_yaml
from tests.conftest import FIXTURES_DIR


@pytest.mark.usefixtures("stub_viewer_serve")
class TestDiscoverHeterogeneousSources:
    def test_single_csv_source_writes_one_file(self, runner, tmp_path, monkeypatch):
        from feather_etl.cli import app

        csvs = tmp_path / "csv"
        shutil.copytree(FIXTURES_DIR / "csv_data", csvs)
        cfg = multi_source_yaml(
            tmp_path,
            [
                {"name": "sheets", "type": "csv", "path": str(csvs)},
            ],
        )
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

        cfg = multi_source_yaml(
            tmp_path,
            [
                {"name": "sheets", "type": "csv", "path": str(csvs)},
                {"name": "sqlite_db", "type": "sqlite", "path": str(sqlite)},
                {"name": "duck", "type": "duckdb", "path": str(duckdb_f)},
            ],
        )
        monkeypatch.chdir(tmp_path)

        r = runner.invoke(app, ["discover", "--config", str(cfg)])
        assert r.exit_code == 0, r.output
        names = {p.name for p in tmp_path.glob("schema_*.json")}
        assert names == {
            "schema_sheets.json",
            "schema_sqlite_db.json",
            "schema_duck.json",
        }


@pytest.mark.usefixtures("stub_viewer_serve")
class TestDiscoverResume:
    def test_second_run_skips_cached(self, runner, tmp_path, monkeypatch):
        from feather_etl.cli import app

        sqlite = tmp_path / "src.sqlite"
        shutil.copy2(FIXTURES_DIR / "sample_erp.sqlite", sqlite)
        cfg = multi_source_yaml(
            tmp_path,
            [
                {"name": "db", "type": "sqlite", "path": str(sqlite)},
            ],
        )
        monkeypatch.chdir(tmp_path)

        r1 = runner.invoke(app, ["discover", "--config", str(cfg)])
        assert r1.exit_code == 0
        first_mtime = (tmp_path / "schema_db.json").stat().st_mtime_ns

        # Touch the schema JSON so we can detect whether it was rewritten.
        time.sleep(0.05)

        r2 = runner.invoke(app, ["discover", "--config", str(cfg)])
        assert r2.exit_code == 0
        assert "cached" in r2.output
        # Cached run does NOT rewrite the schema file.
        assert (tmp_path / "schema_db.json").stat().st_mtime_ns == first_mtime

    def test_state_file_written(self, runner, tmp_path, monkeypatch):
        from feather_etl.cli import app

        sqlite = tmp_path / "src.sqlite"
        shutil.copy2(FIXTURES_DIR / "sample_erp.sqlite", sqlite)
        cfg = multi_source_yaml(
            tmp_path,
            [
                {"name": "db", "type": "sqlite", "path": str(sqlite)},
            ],
        )
        monkeypatch.chdir(tmp_path)

        r = runner.invoke(app, ["discover", "--config", str(cfg)])
        assert r.exit_code == 0
        state_path = tmp_path / "feather_discover_state.json"
        assert state_path.is_file()
        payload = json.loads(state_path.read_text())
        assert payload["schema_version"] == 1
        assert "db" in payload["sources"]
        assert payload["sources"]["db"]["status"] == "ok"


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
            cfg = multi_source_yaml(
                tmp_path,
                [
                    {
                        "name": "wh",
                        "type": "postgres",
                        "host": "localhost",
                        "user": "",
                        "password": "",
                        "databases": names,
                    },
                ],
            )
            monkeypatch.chdir(tmp_path)
            r = runner.invoke(app, ["discover", "--config", str(cfg)])
            assert r.exit_code == 0, r.output
            files = {p.name for p in tmp_path.glob("schema_*.json")}
            assert files == {"schema_wh__feather_a.json", "schema_wh__feather_b.json"}
        finally:
            self._drop_databases(names)

    def test_auto_enumerate(self, runner, tmp_path, monkeypatch):
        from feather_etl.cli import app

        names = ["feather_x", "feather_y"]
        self._create_databases(names)
        try:
            cfg = multi_source_yaml(
                tmp_path,
                [
                    {
                        "name": "wh",
                        "type": "postgres",
                        "host": "localhost",
                        "user": "",
                        "password": "",
                    },
                ],
            )
            monkeypatch.chdir(tmp_path)
            r = runner.invoke(app, ["discover", "--config", str(cfg)])
            assert r.exit_code == 0, r.output
            files = {p.name for p in tmp_path.glob("schema_*.json")}
            for n in names:
                assert f"schema_wh__{n}.json" in files
        finally:
            self._drop_databases(names)


@pytest.mark.usefixtures("stub_viewer_serve")
class TestDiscoverFlags:
    def test_refresh_rewrites_schema_files(self, runner, tmp_path, monkeypatch):
        from feather_etl.cli import app

        sqlite = tmp_path / "src.sqlite"
        shutil.copy2(FIXTURES_DIR / "sample_erp.sqlite", sqlite)
        cfg = multi_source_yaml(
            tmp_path,
            [
                {"name": "db", "type": "sqlite", "path": str(sqlite)},
            ],
        )
        monkeypatch.chdir(tmp_path)

        runner.invoke(app, ["discover", "--config", str(cfg)])
        first_mtime = (tmp_path / "schema_db.json").stat().st_mtime_ns

        time.sleep(0.05)
        r = runner.invoke(app, ["discover", "--config", str(cfg), "--refresh"])
        assert r.exit_code == 0
        assert (tmp_path / "schema_db.json").stat().st_mtime_ns > first_mtime

    def test_retry_failed_only_retries_failures(self, runner, tmp_path, monkeypatch):
        """Simulate a failed source then verify --retry-failed retries only it."""
        from feather_etl.cli import app

        sqlite = tmp_path / "src.sqlite"
        shutil.copy2(FIXTURES_DIR / "sample_erp.sqlite", sqlite)
        bogus = tmp_path / "missing.sqlite"  # doesn't exist → check() fails

        cfg = multi_source_yaml(
            tmp_path,
            [
                {"name": "ok", "type": "sqlite", "path": str(sqlite)},
                {"name": "bad", "type": "sqlite", "path": str(bogus)},
            ],
        )
        monkeypatch.chdir(tmp_path)

        r1 = runner.invoke(app, ["discover", "--config", str(cfg)])
        assert r1.exit_code == 2  # one failed
        ok_mtime = (tmp_path / "schema_ok.json").stat().st_mtime_ns

        # Make the bogus path valid.
        shutil.copy2(sqlite, bogus)

        time.sleep(0.05)
        r2 = runner.invoke(app, ["discover", "--config", str(cfg), "--retry-failed"])
        assert r2.exit_code == 0
        # ok was not re-discovered.
        assert (tmp_path / "schema_ok.json").stat().st_mtime_ns == ok_mtime
        # bad now has a schema file.
        assert (tmp_path / "schema_bad.json").is_file()

    def test_prune_removes_orphaned_state_and_file(self, runner, tmp_path, monkeypatch):
        from feather_etl.cli import app

        a = tmp_path / "a.sqlite"
        b = tmp_path / "b.sqlite"
        shutil.copy2(FIXTURES_DIR / "sample_erp.sqlite", a)
        shutil.copy2(FIXTURES_DIR / "sample_erp.sqlite", b)
        cfg = multi_source_yaml(
            tmp_path,
            [
                {"name": "a", "type": "sqlite", "path": str(a)},
                {"name": "b", "type": "sqlite", "path": str(b)},
            ],
        )
        monkeypatch.chdir(tmp_path)
        runner.invoke(app, ["discover", "--config", str(cfg)])
        assert (tmp_path / "schema_a.json").exists()
        assert (tmp_path / "schema_b.json").exists()

        # Remove 'b' from feather.yaml.
        cfg2 = multi_source_yaml(
            tmp_path,
            [
                {"name": "a", "type": "sqlite", "path": str(a)},
            ],
        )
        runner.invoke(app, ["discover", "--config", str(cfg2)])
        # 'b' marked removed in state, file still exists.
        assert (tmp_path / "schema_b.json").exists()

        r = runner.invoke(app, ["discover", "--config", str(cfg2), "--prune"])
        assert r.exit_code == 0
        assert not (tmp_path / "schema_b.json").exists()
        state = json.loads((tmp_path / "feather_discover_state.json").read_text())
        assert "b" not in state["sources"]


@pytest.mark.usefixtures("stub_viewer_serve")
class TestRenameNonTtyExit3:
    def test_rename_in_yaml_first_invocation_exits_3(
        self, runner, tmp_path, monkeypatch
    ):
        from feather_etl.cli import app

        sqlite = tmp_path / "src.sqlite"
        shutil.copy2(FIXTURES_DIR / "sample_erp.sqlite", sqlite)
        first_cfg = multi_source_yaml(
            tmp_path,
            [
                {"name": "erp", "type": "sqlite", "path": str(sqlite)},
            ],
        ).rename(tmp_path / "feather_erp.yaml")
        renamed_cfg = multi_source_yaml(
            tmp_path,
            [
                {"name": "erp_main", "type": "sqlite", "path": str(sqlite)},
            ],
        ).rename(tmp_path / "feather_erp_main.yaml")
        monkeypatch.chdir(tmp_path)

        first = runner.invoke(app, ["discover", "--config", str(first_cfg)])
        assert first.exit_code == 0, first.output

        second = runner.invoke(app, ["discover", "--config", str(renamed_cfg)])
        assert second.exit_code == 3, second.output
        output = second.output.lower()
        assert "rename" in output
        assert "--yes" in output
        assert "--no-renames" in output
        assert "erp" in second.output
        assert "erp_main" in second.output

    def test_yes_flag_migrates_state_and_files(self, runner, tmp_path, monkeypatch):
        from feather_etl.cli import app

        sqlite = tmp_path / "src.sqlite"
        shutil.copy2(FIXTURES_DIR / "sample_erp.sqlite", sqlite)
        first_cfg = multi_source_yaml(
            tmp_path,
            [
                {"name": "erp", "type": "sqlite", "path": str(sqlite)},
            ],
        ).rename(tmp_path / "feather_erp.yaml")
        renamed_cfg = multi_source_yaml(
            tmp_path,
            [
                {"name": "erp_main", "type": "sqlite", "path": str(sqlite)},
            ],
        ).rename(tmp_path / "feather_erp_main.yaml")
        monkeypatch.chdir(tmp_path)

        first = runner.invoke(app, ["discover", "--config", str(first_cfg)])
        assert first.exit_code == 0, first.output

        second = runner.invoke(app, ["discover", "--config", str(renamed_cfg), "--yes"])
        assert second.exit_code == 0, second.output
        assert (tmp_path / "schema_erp_main.json").is_file()
        assert not (tmp_path / "schema_erp.json").exists()

        state = json.loads((tmp_path / "feather_discover_state.json").read_text())
        assert "erp_main" in state["sources"]
        assert "erp" not in state["sources"]

    def test_no_renames_orphans_old_entry(self, runner, tmp_path, monkeypatch):
        from feather_etl.cli import app

        sqlite = tmp_path / "src.sqlite"
        shutil.copy2(FIXTURES_DIR / "sample_erp.sqlite", sqlite)
        first_cfg = multi_source_yaml(
            tmp_path,
            [
                {"name": "erp", "type": "sqlite", "path": str(sqlite)},
            ],
        ).rename(tmp_path / "feather_erp.yaml")
        renamed_cfg = multi_source_yaml(
            tmp_path,
            [
                {"name": "erp_main", "type": "sqlite", "path": str(sqlite)},
            ],
        ).rename(tmp_path / "feather_erp_main.yaml")
        monkeypatch.chdir(tmp_path)

        first = runner.invoke(app, ["discover", "--config", str(first_cfg)])
        assert first.exit_code == 0, first.output

        second = runner.invoke(
            app, ["discover", "--config", str(renamed_cfg), "--no-renames"]
        )
        assert second.exit_code == 0, second.output

        state = json.loads((tmp_path / "feather_discover_state.json").read_text())
        assert state["sources"]["erp"]["status"] == "orphaned"
        assert state["sources"]["erp_main"]["status"] == "ok"

    def test_refresh_flag_bypasses_rename_confirmation(
        self, runner, tmp_path, monkeypatch
    ):
        from feather_etl.cli import app

        sqlite = tmp_path / "src.sqlite"
        shutil.copy2(FIXTURES_DIR / "sample_erp.sqlite", sqlite)
        first_cfg = multi_source_yaml(
            tmp_path,
            [
                {"name": "erp", "type": "sqlite", "path": str(sqlite)},
            ],
        ).rename(tmp_path / "feather_erp.yaml")
        renamed_cfg = multi_source_yaml(
            tmp_path,
            [
                {"name": "erp_main", "type": "sqlite", "path": str(sqlite)},
            ],
        ).rename(tmp_path / "feather_erp_main.yaml")
        monkeypatch.chdir(tmp_path)

        first = runner.invoke(app, ["discover", "--config", str(first_cfg)])
        assert first.exit_code == 0, first.output

        refreshed = runner.invoke(
            app, ["discover", "--config", str(renamed_cfg), "--refresh"]
        )
        assert refreshed.exit_code == 0, refreshed.output
        assert "Rename confirmation required" not in refreshed.output
        assert (tmp_path / "schema_erp_main.json").is_file()

        state = json.loads((tmp_path / "feather_discover_state.json").read_text())
        assert state["sources"]["erp_main"]["status"] == "ok"
        assert state["sources"]["erp"]["status"] == "removed"

    def test_prune_flag_bypasses_rename_confirmation(
        self, runner, tmp_path, monkeypatch
    ):
        from feather_etl.cli import app

        sqlite = tmp_path / "src.sqlite"
        shutil.copy2(FIXTURES_DIR / "sample_erp.sqlite", sqlite)
        first_cfg = multi_source_yaml(
            tmp_path,
            [
                {"name": "erp", "type": "sqlite", "path": str(sqlite)},
            ],
        ).rename(tmp_path / "feather_erp.yaml")
        renamed_cfg = multi_source_yaml(
            tmp_path,
            [
                {"name": "erp_main", "type": "sqlite", "path": str(sqlite)},
            ],
        ).rename(tmp_path / "feather_erp_main.yaml")
        monkeypatch.chdir(tmp_path)

        first = runner.invoke(app, ["discover", "--config", str(first_cfg)])
        assert first.exit_code == 0, first.output
        assert (tmp_path / "schema_erp.json").is_file()

        pruned = runner.invoke(
            app, ["discover", "--config", str(renamed_cfg), "--prune"]
        )
        assert pruned.exit_code == 0, pruned.output
        assert "Rename confirmation required" not in pruned.output
        assert not (tmp_path / "schema_erp.json").exists()
        assert not (tmp_path / "schema_erp_main.json").exists()

        state = json.loads((tmp_path / "feather_discover_state.json").read_text())
        assert "erp" not in state["sources"]
