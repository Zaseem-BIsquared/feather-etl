"""Tests for feather.config module."""

import json
import os
from pathlib import Path

import pytest
import yaml

from tests.helpers import write_config


def _minimal_config(tmp_path: Path, source_path: str | None = None) -> dict:
    """Return a valid minimal config dict."""
    if source_path is None:
        db = tmp_path / "source.duckdb"
        db.touch()
        source_path = str(db)
    return {
        "source": {"type": "duckdb", "path": source_path},
        "destination": {"path": str(tmp_path / "feather_data.duckdb")},
        "tables": [
            {
                "name": "test_table",
                "source_table": "main.test",
                "target_table": "bronze.test_table",
                "strategy": "full",
            }
        ],
    }


class TestConfigParsing:
    def test_valid_config_parses(self, tmp_path: Path):
        from feather_etl.config import load_config

        cfg = _minimal_config(tmp_path)
        config_file = write_config(tmp_path, cfg)
        result = load_config(config_file, validate=False)
        assert result.source.type == "duckdb"
        assert len(result.tables) == 1
        assert result.tables[0].name == "test_table"

    def test_env_var_substitution(self, tmp_path: Path):
        from feather_etl.config import load_config

        os.environ["FEATHER_TEST_PATH"] = str(tmp_path / "source.duckdb")
        try:
            cfg = _minimal_config(tmp_path)
            cfg["source"]["path"] = "${FEATHER_TEST_PATH}"
            config_file = write_config(tmp_path, cfg)
            result = load_config(config_file, validate=False)
            assert "${" not in str(result.source.path)
            assert "source.duckdb" in str(result.source.path)
        finally:
            del os.environ["FEATHER_TEST_PATH"]

    def test_path_resolution_relative_to_config(self, tmp_path: Path):
        from feather_etl.config import load_config

        subdir = tmp_path / "project"
        subdir.mkdir()
        cfg = _minimal_config(tmp_path)
        cfg["source"]["path"] = "./source.duckdb"
        cfg["destination"]["path"] = "./data.duckdb"
        config_file = write_config(tmp_path, cfg, directory=subdir)
        result = load_config(config_file, validate=False)
        assert result.source.path == subdir / "source.duckdb"
        assert result.destination.path == subdir / "data.duckdb"

    def test_target_table_defaults_to_silver(self, tmp_path: Path):
        from feather_etl.config import load_config

        cfg = _minimal_config(tmp_path)
        del cfg["tables"][0]["target_table"]
        config_file = write_config(tmp_path, cfg)
        result = load_config(config_file, validate=False)
        assert result.tables[0].target_table == ""  # mode-derived at runtime

    def test_tables_directory_merge(self, tmp_path: Path):
        from feather_etl.config import load_config

        db = tmp_path / "source.duckdb"
        cfg = {
            "source": {"type": "duckdb", "path": str(db)},
            "destination": {"path": str(tmp_path / "data.duckdb")},
            "tables": [
                {
                    "name": "inline_table",
                    "source_table": "main.inline",
                    "target_table": "bronze.inline_table",
                    "strategy": "full",
                }
            ],
        }
        config_file = write_config(tmp_path, cfg)

        tables_dir = tmp_path / "tables"
        tables_dir.mkdir()
        extra = {
            "tables": [
                {
                    "name": "dir_table",
                    "source_table": "main.dir",
                    "target_table": "bronze.dir_table",
                    "strategy": "full",
                }
            ]
        }
        (tables_dir / "extra.yaml").write_text(yaml.dump(extra))

        result = load_config(config_file, validate=False)
        names = {t.name for t in result.tables}
        assert names == {"inline_table", "dir_table"}

    def test_no_primary_key_does_not_error(self, tmp_path: Path):
        """primary_key validation deferred to Slice 3."""
        from feather_etl.config import load_config

        cfg = _minimal_config(tmp_path)
        # No primary_key field at all
        config_file = write_config(tmp_path, cfg)
        result = load_config(config_file, validate=False)
        assert result.tables[0].primary_key is None


class TestConfigValidation:
    def test_bad_source_type(self, tmp_path: Path):
        from feather_etl.config import load_config

        cfg = _minimal_config(tmp_path)
        cfg["source"]["type"] = "mongodb"
        config_file = write_config(tmp_path, cfg)
        with pytest.raises(ValueError, match="Unsupported source type"):
            load_config(config_file)

    def test_missing_source_path_for_file_source(self, tmp_path: Path):
        from feather_etl.config import load_config

        cfg = _minimal_config(tmp_path)
        cfg["source"]["path"] = str(tmp_path / "nonexistent.duckdb")
        config_file = write_config(tmp_path, cfg)
        with pytest.raises(ValueError, match="does not exist"):
            load_config(config_file)

    def test_bad_strategy(self, tmp_path: Path):
        from feather_etl.config import load_config

        cfg = _minimal_config(tmp_path)
        cfg["tables"][0]["strategy"] = "upsert"
        config_file = write_config(tmp_path, cfg)
        with pytest.raises(ValueError, match="strategy"):
            load_config(config_file)

    def test_bad_target_schema_prefix(self, tmp_path: Path):
        from feather_etl.config import load_config

        cfg = _minimal_config(tmp_path)
        cfg["tables"][0]["target_table"] = "staging.test_table"
        config_file = write_config(tmp_path, cfg)
        with pytest.raises(ValueError, match="schema"):
            load_config(config_file)


class TestValidationJson:
    def test_writes_on_success(self, tmp_path: Path):
        from feather_etl.config import load_config, write_validation_json

        cfg = _minimal_config(tmp_path)
        config_file = write_config(tmp_path, cfg)
        result = load_config(config_file)
        write_validation_json(config_file, result)
        vj = json.loads((tmp_path / "feather_validation.json").read_text())
        assert vj["valid"] is True
        assert vj["errors"] == []
        assert vj["tables_count"] == 1

    def test_writes_on_failure(self, tmp_path: Path):
        from feather_etl.config import write_validation_json

        write_validation_json(
            tmp_path / "feather.yaml", None, errors=["bad source type"]
        )
        vj = json.loads((tmp_path / "feather_validation.json").read_text())
        assert vj["valid"] is False
        assert "bad source type" in vj["errors"]


class TestEnvVarEdgeCases:
    def test_numeric_values_pass_through(self, tmp_path: Path):
        """config.py line 73: non-string values returned as-is."""
        from feather_etl.config import load_config

        cfg = _minimal_config(tmp_path)
        cfg["defaults"] = {"overlap_window_minutes": 5, "batch_size": 50000}
        config_file = write_config(tmp_path, cfg)
        result = load_config(config_file, validate=False)
        assert result.defaults.overlap_window_minutes == 5
        assert result.defaults.batch_size == 50000

    def test_dotenv_auto_loaded_from_config_dir(
        self, tmp_path: Path, monkeypatch
    ):
        """Regression for siraj-samsudeen/feather-etl#1.

        A `.env` file next to `feather.yaml` should be loaded automatically,
        so users don't have to manually `export` variables before running
        `feather validate`, `feather run`, etc. Without this, `${VAR}`
        references in feather.yaml fall back to `os.environ` only.
        """
        from feather_etl.config import load_config

        # Ensure the var is NOT already in the environment
        monkeypatch.delenv("FEATHER_TEST_DOTENV_VAR", raising=False)
        assert "FEATHER_TEST_DOTENV_VAR" not in os.environ  # must come from .env, not shell

        # Write .env alongside the config — this is what should get auto-loaded
        (tmp_path / ".env").write_text("FEATHER_TEST_DOTENV_VAR=bronze\n")

        cfg = _minimal_config(tmp_path)
        cfg["tables"][0]["target_table"] = "${FEATHER_TEST_DOTENV_VAR}.t"
        config_file = write_config(tmp_path, cfg)

        result = load_config(config_file, validate=False)
        # If .env was loaded, ${FEATHER_TEST_DOTENV_VAR} resolved to "bronze"
        assert result.tables[0].target_table == "bronze.t"

    def test_dotenv_does_not_override_existing_env(
        self, tmp_path: Path, monkeypatch
    ):
        """Existing shell/CI env vars must win over .env (override=False).

        Important for CI/CD: secrets come from the environment, not a
        committed .env file. A stray committed .env must not silently
        clobber what the pipeline passes in.
        """
        from feather_etl.config import load_config

        # Simulate CI env variable setup
        monkeypatch.setenv("FEATHER_TEST_OVERRIDE_VAR", "gold")

        (tmp_path / ".env").write_text("FEATHER_TEST_OVERRIDE_VAR=bronze\n")

        cfg = _minimal_config(tmp_path)
        cfg["tables"][0]["target_table"] = "${FEATHER_TEST_OVERRIDE_VAR}.t"
        config_file = write_config(tmp_path, cfg)

        result = load_config(config_file, validate=False)
        assert result.tables[0].target_table == "gold.t"

    def test_unresolved_env_var_gives_clear_error(self, tmp_path: Path):
        """UX-4: Unset env vars should show which variable is missing."""
        from feather_etl.config import load_config

        cfg = _minimal_config(tmp_path)
        cfg["destination"]["path"] = "${MISSING_DEST_PATH}"
        config_file = write_config(tmp_path, cfg)
        with pytest.raises(ValueError, match="MISSING_DEST_PATH"):
            load_config(config_file, validate=False)


class TestConfigValidationExtended:
    def test_unregistered_source_type_rejected(self, tmp_path: Path):
        """Source types not in SOURCE_REGISTRY should be rejected at validate."""
        from feather_etl.config import load_config

        cfg = {
            "source": {"type": "ftp", "connection_string": "ftp://example.com"},
            "destination": {"path": str(tmp_path / "data.duckdb")},
            "tables": [
                {
                    "name": "t",
                    "source_table": "main.t",
                    "target_table": "bronze.t",
                    "strategy": "full",
                },
            ],
        }
        config_file = write_config(tmp_path, cfg)
        with pytest.raises(ValueError, match="Unsupported source type"):
            load_config(config_file)

    def test_missing_table_field_gives_friendly_error(self, tmp_path: Path):
        """BUG-4: Missing required table fields should raise ValueError, not KeyError."""
        from feather_etl.config import load_config

        db = tmp_path / "source.duckdb"
        db.touch()
        cfg = {
            "source": {"type": "duckdb", "path": str(db)},
            "destination": {"path": str(tmp_path / "data.duckdb")},
            "tables": [
                {
                    "name": "t",
                    "source_table": "main.t",
                    "target_table": "bronze.t",
                },  # strategy missing
            ],
        }
        config_file = write_config(tmp_path, cfg)
        with pytest.raises(ValueError, match="missing required field"):
            load_config(config_file)

    def test_missing_source_section_gives_friendly_error(self, tmp_path: Path):
        """Missing 'source' section should raise ValueError, not KeyError."""
        from feather_etl.config import load_config

        cfg = {
            "destination": {"path": str(tmp_path / "data.duckdb")},
            "tables": [],
        }
        config_file = write_config(tmp_path, cfg)
        with pytest.raises(ValueError, match="Missing required config section"):
            load_config(config_file)

    def test_destination_parent_must_exist(self, tmp_path: Path):
        """BUG-6: Non-existent destination parent should fail at validate."""
        from feather_etl.config import load_config

        db = tmp_path / "source.duckdb"
        db.touch()
        cfg = {
            "source": {"type": "duckdb", "path": str(db)},
            "destination": {
                "path": str(tmp_path / "nonexistent" / "sub" / "data.duckdb")
            },
            "tables": [
                {
                    "name": "t",
                    "source_table": "main.t",
                    "target_table": "bronze.t",
                    "strategy": "full",
                },
            ],
        }
        config_file = write_config(tmp_path, cfg)
        with pytest.raises(ValueError, match="Destination directory does not exist"):
            load_config(config_file)

    def test_hyphenated_target_table_rejected(self, tmp_path: Path):
        """BUG-7: Hyphens in target table names should be caught at validate."""
        from feather_etl.config import load_config

        db = tmp_path / "source.duckdb"
        db.touch()
        cfg = _minimal_config(tmp_path)
        cfg["tables"][0]["target_table"] = "bronze.my-hyphenated-table"
        config_file = write_config(tmp_path, cfg)
        with pytest.raises(ValueError, match="invalid characters"):
            load_config(config_file)

    def test_target_table_requires_schema_prefix(self, tmp_path: Path):
        """BUG-7: target_table without schema prefix should be rejected."""
        from feather_etl.config import load_config

        cfg = _minimal_config(tmp_path)
        cfg["tables"][0]["target_table"] = "no_schema_table"
        config_file = write_config(tmp_path, cfg)
        with pytest.raises(ValueError, match="must include a schema prefix"):
            load_config(config_file)

    def test_incremental_requires_timestamp_column(self, tmp_path: Path):
        """UX-8: incremental strategy without timestamp_column should be rejected."""
        from feather_etl.config import load_config

        cfg = _minimal_config(tmp_path)
        cfg["tables"][0]["strategy"] = "incremental"
        # No timestamp_column
        config_file = write_config(tmp_path, cfg)
        with pytest.raises(ValueError, match="timestamp_column"):
            load_config(config_file)

    def test_incremental_with_timestamp_column_passes(self, tmp_path: Path):
        """incremental + timestamp_column should be accepted."""
        from feather_etl.config import load_config

        cfg = _minimal_config(tmp_path)
        cfg["tables"][0]["strategy"] = "incremental"
        cfg["tables"][0]["timestamp_column"] = "modified_date"
        config_file = write_config(tmp_path, cfg)
        result = load_config(config_file)
        assert result.tables[0].strategy == "incremental"

    def test_negative_overlap_window_rejected(self, tmp_path: Path):
        """H-2: negative overlap_window_minutes must be rejected."""
        from feather_etl.config import load_config

        cfg = _minimal_config(tmp_path)
        cfg["defaults"] = {"overlap_window_minutes": -5}
        config_file = write_config(tmp_path, cfg)
        with pytest.raises(ValueError, match="overlap_window_minutes"):
            load_config(config_file)

    def test_zero_overlap_window_accepted(self, tmp_path: Path):
        """H-2: overlap_window_minutes = 0 is valid."""
        from feather_etl.config import load_config

        cfg = _minimal_config(tmp_path)
        cfg["defaults"] = {"overlap_window_minutes": 0}
        config_file = write_config(tmp_path, cfg)
        result = load_config(config_file)
        assert result.defaults.overlap_window_minutes == 0

    def test_source_table_with_semicolon_rejected(self, tmp_path: Path):
        """M-1: source_table containing semicolons must be rejected."""
        from feather_etl.config import load_config

        cfg = _minimal_config(tmp_path)
        cfg["tables"][0]["source_table"] = "main.test; DROP TABLE foo"
        config_file = write_config(tmp_path, cfg)
        with pytest.raises(ValueError, match="source_table.*invalid"):
            load_config(config_file)

    def test_source_table_with_comment_rejected(self, tmp_path: Path):
        """M-1: source_table containing SQL comments must be rejected."""
        from feather_etl.config import load_config

        cfg = _minimal_config(tmp_path)
        cfg["tables"][0]["source_table"] = "main.test--comment"
        config_file = write_config(tmp_path, cfg)
        with pytest.raises(ValueError, match="source_table.*invalid"):
            load_config(config_file)

    def test_valid_source_table_formats_accepted(self, tmp_path: Path):
        """M-1: legitimate source_table formats should pass validation."""
        from feather_etl.config import load_config

        # schema.table format (DuckDB)
        cfg = _minimal_config(tmp_path)
        cfg["tables"][0]["source_table"] = "erp.SalesInvoice"
        config_file = write_config(tmp_path, cfg)
        result = load_config(config_file)
        assert result.tables[0].source_table == "erp.SalesInvoice"

    def test_csv_source_table_filename_accepted(self, tmp_path: Path):
        """M-1: CSV source_table (filename) should pass validation."""
        from feather_etl.config import load_config

        csv_dir = tmp_path / "csv_data"
        csv_dir.mkdir()
        cfg = _minimal_config(tmp_path)
        cfg["source"] = {"type": "csv", "path": str(csv_dir)}
        cfg["tables"][0]["source_table"] = "orders.csv"
        config_file = write_config(tmp_path, cfg)
        result = load_config(config_file)
        assert result.tables[0].source_table == "orders.csv"

    def test_duckdb_source_table_without_schema_rejected(self, tmp_path: Path):
        """R-1: DuckDB source_table must be schema.table format."""
        from feather_etl.config import load_config

        cfg = _minimal_config(tmp_path)
        cfg["tables"][0]["source_table"] = "just_a_table"
        config_file = write_config(tmp_path, cfg)
        with pytest.raises(ValueError, match="source_table.*schema\\.table"):
            load_config(config_file)

    def test_duckdb_source_table_with_spaces_rejected(self, tmp_path: Path):
        """R-1: DuckDB source_table with spaces in identifiers must be rejected."""
        from feather_etl.config import load_config

        cfg = _minimal_config(tmp_path)
        cfg["tables"][0]["source_table"] = "erp.Sales Invoice"
        config_file = write_config(tmp_path, cfg)
        with pytest.raises(ValueError, match="source_table.*invalid"):
            load_config(config_file)

    def test_duckdb_source_table_with_parens_rejected(self, tmp_path: Path):
        """R-1: DuckDB source_table with parentheses must be rejected."""
        from feather_etl.config import load_config

        cfg = _minimal_config(tmp_path)
        cfg["tables"][0]["source_table"] = "erp.test()"
        config_file = write_config(tmp_path, cfg)
        with pytest.raises(ValueError, match="source_table.*invalid"):
            load_config(config_file)


class TestAlertsConfig:
    def test_no_alerts_section_sets_none(self, tmp_path: Path):
        from feather_etl.config import load_config

        cfg = _minimal_config(tmp_path)
        config_file = write_config(tmp_path, cfg)
        result = load_config(config_file, validate=False)
        assert result.alerts is None

    def test_valid_alerts_section_parses(self, tmp_path: Path):
        from feather_etl.config import load_config

        cfg = _minimal_config(tmp_path)
        cfg["alerts"] = {
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_user": "user@example.com",
            "smtp_password": "secret",
            "alert_to": "ops@example.com",
        }
        config_file = write_config(tmp_path, cfg)
        result = load_config(config_file, validate=False)
        assert result.alerts is not None
        assert result.alerts.smtp_host == "smtp.example.com"
        assert result.alerts.smtp_port == 587
        assert result.alerts.smtp_user == "user@example.com"
        assert result.alerts.alert_to == "ops@example.com"

    def test_alert_from_defaults_to_smtp_user(self, tmp_path: Path):
        from feather_etl.config import load_config

        cfg = _minimal_config(tmp_path)
        cfg["alerts"] = {
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_user": "user@example.com",
            "smtp_password": "secret",
            "alert_to": "ops@example.com",
        }
        config_file = write_config(tmp_path, cfg)
        result = load_config(config_file, validate=False)
        assert result.alerts.alert_from == "user@example.com"

    def test_explicit_alert_from(self, tmp_path: Path):
        from feather_etl.config import load_config

        cfg = _minimal_config(tmp_path)
        cfg["alerts"] = {
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_user": "user@example.com",
            "smtp_password": "secret",
            "alert_to": "ops@example.com",
            "alert_from": "noreply@example.com",
        }
        config_file = write_config(tmp_path, cfg)
        result = load_config(config_file, validate=False)
        assert result.alerts.alert_from == "noreply@example.com"

    def test_missing_required_alert_field_raises(self, tmp_path: Path):
        from feather_etl.config import load_config

        cfg = _minimal_config(tmp_path)
        cfg["alerts"] = {
            "smtp_host": "smtp.example.com",
            # missing smtp_port, smtp_user, smtp_password, alert_to
        }
        config_file = write_config(tmp_path, cfg)
        with pytest.raises(ValueError, match="alerts.*missing"):
            load_config(config_file, validate=False)

    def test_alerts_env_var_resolved(self, tmp_path: Path, monkeypatch):
        from feather_etl.config import load_config

        monkeypatch.setenv("TEST_SMTP_PASS", "env_secret")
        cfg = _minimal_config(tmp_path)
        cfg["alerts"] = {
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_user": "user@example.com",
            "smtp_password": "${TEST_SMTP_PASS}",
            "alert_to": "ops@example.com",
        }
        config_file = write_config(tmp_path, cfg)
        result = load_config(config_file, validate=False)
        assert result.alerts.smtp_password == "env_secret"


class TestSourceName:
    def test_source_name_is_optional(self, tmp_path: Path):
        from feather_etl.config import load_config

        cfg_dict = _minimal_config(tmp_path)
        config_file = write_config(tmp_path, cfg_dict)
        result = load_config(config_file, validate=False)
        assert result.source.name is None

    def test_source_name_is_accepted(self, tmp_path: Path):
        from feather_etl.config import load_config

        cfg_dict = _minimal_config(tmp_path)
        cfg_dict["source"]["name"] = "prod-erp"
        config_file = write_config(tmp_path, cfg_dict)
        result = load_config(config_file, validate=False)
        assert result.source.name == "prod-erp"
