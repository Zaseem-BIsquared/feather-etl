"""feather init — project scaffolding + interactive wizard (V17)."""

from __future__ import annotations

from pathlib import Path

import yaml

FEATHER_YAML_TEMPLATE = """\
# feather-etl configuration
# Docs: https://github.com/your-org/feather-etl

source:
  type: duckdb                        # duckdb, sqlite, csv, excel, json, sqlserver
  path: ./source.duckdb               # path to source file (file-based sources)
  # connection_string: "${SQL_SERVER_CONNECTION_STRING}"  # for sqlserver

destination:
  path: ./feather_data.duckdb         # local DuckDB for extracted data

# state:
#   path: ./feather_state.duckdb      # defaults to feather_state.duckdb

# defaults:
#   overlap_window_minutes: 2
#   batch_size: 120000

# schedule_tiers:
#   hot: "twice daily"
#   cold: weekly

tables:
  - name: example_table
    source_table: schema.table_name   # e.g., icube.SALESINVOICE
    target_table: bronze.example_table
    strategy: full                    # full, incremental, append
    # primary_key: [id]
    # timestamp_column: modified_date  # required for incremental/append
"""

PYPROJECT_TEMPLATE = """\
[project]
name = "{name}"
version = "0.1.0"
description = "feather-etl client project"
requires-python = ">=3.10"
dependencies = ["feather-etl>=0.1.0"]
"""

GITIGNORE_TEMPLATE = """\
*.duckdb
*.duckdb.wal
feather_validation.json
.env
__pycache__/
.venv/
"""

ENV_EXAMPLE_TEMPLATE = """\
# Environment variables for feather-etl
# Copy to .env and fill in values

# SQL_SERVER_CONNECTION_STRING=
# MOTHERDUCK_TOKEN=
# ALERT_EMAIL_USER=
# ALERT_EMAIL_PASSWORD=
"""

FILE_SOURCE_TYPES = {"duckdb", "sqlite", "csv", "excel", "json"}


def scaffold_project(project_path: Path) -> list[str]:
    """Create a new client project directory with template files."""
    project_path.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    name = project_path.name

    files: dict[str, str] = {
        "feather.yaml": FEATHER_YAML_TEMPLATE,
        "pyproject.toml": PYPROJECT_TEMPLATE.format(name=name),
        ".gitignore": GITIGNORE_TEMPLATE,
        ".env.example": ENV_EXAMPLE_TEMPLATE,
    }
    for rel_path, content in files.items():
        fp = project_path / rel_path
        fp.write_text(content)
        created.append(rel_path)

    return created


def _table_name_from_source(source_table: str) -> str:
    """Derive clean table name (e.g., 'erp.customers' → 'customers')."""
    return source_table.split(".")[-1].lower()


def _infer_strategy(columns: list[tuple[str, str]]) -> str:
    """Infer extraction strategy from column names."""
    ts_names = {"modified_date", "modifieddate", "timestamp", "updated_at", "last_modified"}
    col_names = {c[0].lower() for c in columns}
    return "incremental" if col_names & ts_names else "full"


def _infer_timestamp_column(columns: list[tuple[str, str]]) -> str | None:
    """Find the best timestamp column candidate."""
    candidates = ["modified_date", "modifieddate", "timestamp", "updated_at", "last_modified"]
    col_map = {c[0].lower(): c[0] for c in columns}
    for name in candidates:
        if name in col_map:
            return col_map[name]
    return None


def _generate_config_yaml(
    source_type: str,
    source_path: str | None,
    connection_string: str | None,
    tables: list[dict],
) -> str:
    """Generate feather.yaml content."""
    config: dict = {
        "source": {"type": source_type},
        "destination": {"path": "./feather_data.duckdb"},
        "tables": tables,
    }
    if source_path:
        config["source"]["path"] = source_path
    if connection_string:
        config["source"]["connection_string"] = connection_string
    return yaml.dump(config, default_flow_style=False, sort_keys=False)


def _build_table_configs(schemas: list) -> list[dict]:
    """Convert discovered schemas to table config dicts."""
    table_configs = []
    for schema in schemas:
        name = _table_name_from_source(schema.name)
        strategy = _infer_strategy(schema.columns)
        entry: dict = {
            "name": name,
            "source_table": schema.name,
            "target_table": f"bronze.{name}",
            "strategy": strategy,
        }
        ts_col = _infer_timestamp_column(schema.columns)
        if ts_col and strategy == "incremental":
            entry["timestamp_column"] = ts_col
        table_configs.append(entry)
    return table_configs


def _write_project_files(
    project_path: Path,
    source_type: str,
    source_path: str | None,
    connection_string: str | None,
    table_configs: list[dict],
) -> dict:
    """Write feather.yaml and silver stubs. Return summary dict."""
    yaml_content = _generate_config_yaml(
        source_type, source_path, connection_string, table_configs,
    )
    (project_path / "feather.yaml").write_text(yaml_content)

    return {
        "project": str(project_path),
        "tables_configured": len(table_configs),
        "tables": [t["name"] for t in table_configs],
        "files_created": ["feather.yaml", "pyproject.toml", ".gitignore", ".env.example"],
    }


def run_non_interactive(
    project_path: Path,
    source_type: str,
    source_path: str | None = None,
    connection_string: str | None = None,
    tables_filter: str | None = None,
) -> dict:
    """Non-interactive wizard: discover tables, generate config."""
    from feather_etl.config import SourceConfig
    from feather_etl.sources.registry import create_source

    scaffold_project(project_path)

    src_config = SourceConfig(
        type=source_type,
        path=Path(source_path) if source_path else None,
        connection_string=connection_string,
    )
    source = create_source(src_config)
    if not source.check():
        raise RuntimeError(f"Cannot connect to source: {source_type}")

    discovered = source.discover()
    if tables_filter:
        filter_names = [t.strip() for t in tables_filter.split(",")]
        discovered = [s for s in discovered if s.name in filter_names]

    table_configs = _build_table_configs(discovered)
    return _write_project_files(
        project_path, source_type, source_path, connection_string, table_configs,
    )


def run_interactive(project_path: Path) -> dict:
    """Interactive wizard: prompt for source, discover, select tables."""
    import typer

    from feather_etl.config import SourceConfig
    from feather_etl.sources.registry import create_source

    scaffold_project(project_path)

    valid_types = sorted(FILE_SOURCE_TYPES | {"sqlserver", "postgres"})
    source_type = typer.prompt(f"Source type ({', '.join(valid_types)})")
    if source_type not in valid_types:
        typer.echo(f"Invalid source type: {source_type}", err=True)
        raise typer.Exit(code=1)

    source_path = None
    connection_string = None
    if source_type in FILE_SOURCE_TYPES:
        source_path = typer.prompt("Source path")
    else:
        connection_string = typer.prompt("Connection string")

    src_config = SourceConfig(
        type=source_type,
        path=Path(source_path) if source_path else None,
        connection_string=connection_string,
    )
    source = create_source(src_config)
    if not source.check():
        typer.echo("Source connection failed.", err=True)
        raise typer.Exit(code=1)

    discovered = source.discover()
    if not discovered:
        typer.echo("No tables found in source.", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"\nFound {len(discovered)} table(s):")
    for i, schema in enumerate(discovered, 1):
        typer.echo(f"  {i}. {schema.name} ({len(schema.columns)} columns)")

    selection = typer.prompt("\nSelect tables (numbers separated by spaces, or 'all')")
    if selection.strip().lower() == "all":
        selected = discovered
    else:
        indices = [int(x) - 1 for x in selection.split() if x.isdigit()]
        selected = [discovered[i] for i in indices if 0 <= i < len(discovered)]

    if not selected:
        typer.echo("No tables selected.", err=True)
        raise typer.Exit(code=1)

    table_configs = _build_table_configs(selected)
    result = _write_project_files(
        project_path, source_type, source_path, connection_string, table_configs,
    )

    typer.echo(f"\nProject configured with {len(table_configs)} table(s).")
    typer.echo("Next steps:")
    typer.echo("  1. Review feather.yaml")
    typer.echo("  2. Edit transforms/silver/*.sql for column mappings")
    typer.echo("  3. Run: feather setup && feather run")

    return result
