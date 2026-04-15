"""`feather discover` command — iterates every source in feather.yaml."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from feather_etl.commands._common import _load_and_validate
from feather_etl.viewer_server import serve_and_open


def _sanitised_filename(name: str) -> str:
    import re
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)


def _write_schema(source, target_dir: Path) -> tuple[Path, int]:
    """Discover `source` and write JSON. Returns (path, table_count)."""
    schemas = source.discover()
    payload = [
        {
            "table_name": s.name,
            "columns": [{"name": c[0], "type": c[1]} for c in s.columns],
        }
        for s in schemas
    ]
    out = target_dir / f"schema_{_sanitised_filename(source.name)}.json"
    out.write_text(json.dumps(payload, indent=2))
    return out, len(schemas)


def _expand_db_sources(sources: list) -> list:
    """Expand sqlserver/postgres sources without explicit database into child sources.

    For each parent source:
      - If it has `database` set → keep as-is.
      - If it has `databases: [...]` set → produce one child per entry, named
        `<parent_name>__<db>`, with `database` set on the child.
      - Otherwise (DB source, neither set) → call list_databases() and
        produce one child per result.
      - File sources → keep as-is.
    """
    from feather_etl.sources.postgres import PostgresSource
    from feather_etl.sources.sqlserver import SqlServerSource

    expanded: list = []
    for src in sources:
        is_db = isinstance(src, (SqlServerSource, PostgresSource))
        if not is_db:
            expanded.append(src)
            continue
        if src.database is not None:
            expanded.append(src)
            continue
        databases = src.databases
        if databases is None:
            try:
                databases = src.list_databases()
            except Exception as e:
                src._last_error = (
                    f"Found 0 databases on host {src.host}. Either grant "
                    f"VIEW ANY DATABASE to this login, or specify "
                    f"`database:` / `databases: [...]` explicitly. ({e})"
                )
                expanded.append(src)
                continue
            if not databases:
                src._last_error = (
                    f"Found 0 databases on host {src.host}. Either grant "
                    f"VIEW ANY DATABASE to this login, or specify "
                    f"`database:` / `databases: [...]` explicitly."
                )
                expanded.append(src)
                continue
        for db in databases:
            child = type(src).from_yaml(
                {
                    "name": f"{src.name}__{db}",
                    "type": src.type,
                    "host": src.host,
                    "port": src.port,
                    "user": src.user,
                    "password": src.password,
                    "database": db,
                },
                Path("."),
            )
            expanded.append(child)
    return expanded


def discover(config: Path = typer.Option("feather.yaml", "--config")) -> None:
    """Save each source's schema to an auto-named schema JSON file, then serve/open the schema viewer."""
    cfg = _load_and_validate(config)
    target_dir = Path(".")

    sources = _expand_db_sources(cfg.sources)
    total = len(sources)

    succeeded = 0
    failed: list[tuple[str, str]] = []

    for idx, source in enumerate(sources, start=1):
        prefix = f"  [{idx}/{total}] {source.name}"
        if not source.check():
            err = getattr(source, "_last_error", "connection failed")
            failed.append((source.name, err))
            typer.echo(f"{prefix}  → FAILED: {err}", err=True)
            continue
        try:
            out, count = _write_schema(source, target_dir)
        except Exception as e:  # pragma: no cover — surfaces in tests
            failed.append((source.name, str(e)))
            typer.echo(f"{prefix}  → FAILED: {e}", err=True)
            continue
        succeeded += 1
        typer.echo(f"{prefix}  → {count} tables → ./{out.name}")

    typer.echo(f"\n{succeeded} succeeded, {len(failed)} failed.")
    serve_and_open(target_dir.resolve(), preferred_port=8000)
    if failed:
        raise typer.Exit(code=2)


def register(app: typer.Typer) -> None:
    app.command(name="discover")(discover)
