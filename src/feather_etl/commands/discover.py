"""`feather discover` command — iterates every source in feather.yaml."""

from __future__ import annotations

import json
import re
from pathlib import Path

import typer

from feather_etl.commands._common import _load_and_validate
from feather_etl.discover_state import DiscoverState, classify
from feather_etl.viewer_server import serve_and_open


def _sanitised_filename(name: str) -> str:
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
        # DB sources' from_yaml ignores config_dir (it's only used for file-path resolution)
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


def _fingerprint_for(source) -> str:
    """Composition per spec §6.7.

    DB sources: '<type>:<host>:<port>:<database>'. File sources: '<type>:<absolute_path>'.
    """
    if hasattr(source, "host") and source.host is not None:
        return (
            f"{source.type}:{source.host}:{source.port or ''}:"
            f"{source.database or ''}"
        )
    return f"{source.type}:{Path(source.path).resolve()}"


def discover(config: Path = typer.Option("feather.yaml", "--config")) -> None:
    """Save each source's schema to an auto-named schema JSON file, then serve/open the schema viewer."""
    cfg = _load_and_validate(config)
    target_dir = Path(".")
    state = DiscoverState.load(target_dir)

    sources = _expand_db_sources(cfg.sources)
    names = [s.name for s in sources]
    decisions = classify(state=state, current_names=names, flag=None)

    succeeded = 0
    failed_count = 0
    cached_count = 0
    total = len(sources)

    if state.last_run_at:
        typer.echo(
            f"Discovering from {config.name} (state file found, "
            f"last run {state.last_run_at})..."
        )
    else:
        typer.echo(f"Discovering from {config.name}...")

    for idx, source in enumerate(sources, start=1):
        prefix = f"  [{idx}/{total}] {source.name}"
        decision = decisions.get(source.name, "new")
        fingerprint = _fingerprint_for(source)

        if decision == "cached":
            entry = state.sources[source.name]
            cached_count += 1
            typer.echo(f"{prefix}  (cached, {entry.get('table_count', 0)} tables)")
            continue
        if decision == "skip":
            typer.echo(f"{prefix}  (skipped)")
            continue

        # "new", "retry", "rerun" — actually discover.
        if not source.check():
            err = getattr(source, "_last_error", "connection failed")
            failed_count += 1
            state.record_failed(
                name=source.name, type_=source.type, fingerprint=fingerprint,
                error=err, host=getattr(source, "host", None),
                database=getattr(source, "database", None),
            )
            typer.echo(f"{prefix}  → FAILED: {err}", err=True)
            continue
        try:
            out, count = _write_schema(source, target_dir)
        except Exception as e:
            failed_count += 1
            state.record_failed(
                name=source.name, type_=source.type, fingerprint=fingerprint,
                error=str(e), host=getattr(source, "host", None),
                database=getattr(source, "database", None),
            )
            typer.echo(f"{prefix}  → FAILED: {e}", err=True)
            continue
        succeeded += 1
        state.record_ok(
            name=source.name, type_=source.type, fingerprint=fingerprint,
            table_count=count, output_path=out,
            host=getattr(source, "host", None),
            database=getattr(source, "database", None),
        )
        label = "new" if decision == "new" else decision
        typer.echo(f"{prefix}  ({label})  → {count} tables → ./{out.name}")

    # Mark state-only entries as removed.
    for name, dec in decisions.items():
        if dec == "removed":
            state.record_removed(name)

    state.save()

    parts = [f"{succeeded + cached_count} succeeded"]
    if cached_count:
        parts.append(f"{cached_count} cached")
    if failed_count:
        parts.append(f"{failed_count} failed")
    typer.echo(f"\n{', '.join(parts)}.")

    serve_and_open(target_dir.resolve(), preferred_port=8000)
    if failed_count > 0:
        raise typer.Exit(code=2)


def register(app: typer.Typer) -> None:
    app.command(name="discover")(discover)
