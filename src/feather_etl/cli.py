"""feather CLI — thin wrapper over config, pipeline, state, and sources."""

from __future__ import annotations

from pathlib import Path

import typer

from feather_etl.output import emit, emit_line

app = typer.Typer(name="feather", help="feather-etl: config-driven ETL")


@app.callback()
def main(
    ctx: typer.Context,
    json: bool = typer.Option(False, "--json", help="Output as NDJSON"),
) -> None:
    """feather-etl: config-driven ETL."""
    ctx.ensure_object(dict)["json_mode"] = json


def _is_json(ctx: typer.Context) -> bool:
    """Read --json flag from Typer context."""
    return ctx.ensure_object(dict).get("json_mode", False)


def _load_and_validate(config_path: Path, mode_override: str | None = None):
    """Load config, validate, write validation JSON. Raises on failure."""
    from feather_etl.config import load_config, write_validation_json

    try:
        cfg = load_config(config_path, mode_override=mode_override)
        write_validation_json(config_path, cfg)
        return cfg
    except (ValueError, FileNotFoundError) as e:
        if isinstance(e, FileNotFoundError):
            typer.echo(f"Config file not found: {config_path}", err=True)
        else:
            write_validation_json(config_path, None, errors=[str(e)])
            typer.echo(f"Validation failed: {e}", err=True)
        raise typer.Exit(code=1)


@app.command()
def init(
    ctx: typer.Context,
    project_name: str | None = typer.Argument(None, help="Project directory name."),
) -> None:
    """Scaffold a new client project with template files."""
    if project_name is None:
        project_name = typer.prompt("Project name")

    project_path = Path(project_name).resolve()
    if project_path.exists():
        non_hidden = [f for f in project_path.iterdir() if not f.name.startswith(".")]
        if non_hidden:
            typer.echo(
                f"Directory '{project_name}' already exists and is not empty.",
                err=True,
            )
            raise typer.Exit(code=1)

    from feather_etl.init_wizard import scaffold_project

    files_created = scaffold_project(project_path)
    if _is_json(ctx):
        emit_line({"project": str(project_path), "files_created": files_created}, json_mode=True)
    else:
        typer.echo(f"Project scaffolded at {project_path}")


@app.command()
def validate(ctx: typer.Context, config: Path = typer.Option("feather.yaml", "--config")) -> None:
    """Validate config, test source connection, and write feather_validation.json."""
    from feather_etl.sources.registry import create_source

    cfg = _load_and_validate(config)

    # Test source connection
    source = create_source(cfg.source)
    source_ok = source.check()

    if _is_json(ctx):
        emit_line(
            {
                "valid": True,
                "tables_count": len(cfg.tables),
                "source_type": cfg.source.type,
                "destination": str(cfg.destination.path),
                "mode": cfg.mode,
                "source_connected": source_ok,
            },
            json_mode=True,
        )
    else:
        typer.echo(f"Config valid: {len(cfg.tables)} table(s)")
        source_label = cfg.source.path or cfg.source.host or "configured"
        conn_status = "connected" if source_ok else "FAILED"
        typer.echo(f"  Source: {cfg.source.type} ({source_label}) — {conn_status}")
        typer.echo(f"  Destination: {cfg.destination.path}")
        typer.echo(f"  State: {cfg.config_dir / 'feather_state.duckdb'}")
        for t in cfg.tables:
            typer.echo(f"  Table: {t.name} → {t.target_table} ({t.strategy})")

    if not source_ok:
        typer.echo("Source connection failed.", err=True)
        raise typer.Exit(code=2)


@app.command()
def discover(ctx: typer.Context, config: Path = typer.Option("feather.yaml", "--config")) -> None:
    """List tables and columns available in the configured source."""
    from feather_etl.sources.registry import create_source

    cfg = _load_and_validate(config)
    source = create_source(cfg.source)

    if not source.check():
        typer.echo("Source connection failed.", err=True)
        raise typer.Exit(code=2)

    schemas = source.discover()
    if _is_json(ctx):
        emit(
            [
                {
                    "table_name": s.name,
                    "columns": [{"name": c[0], "type": c[1]} for c in s.columns],
                }
                for s in schemas
            ],
            json_mode=True,
        )
    else:
        typer.echo(f"Found {len(schemas)} table(s):\n")
        for s in schemas:
            typer.echo(f"  {s.name}")
            for col_name, col_type in s.columns:
                typer.echo(f"    {col_name}: {col_type}")
            typer.echo()


@app.command()
def setup(
    ctx: typer.Context,
    config: Path = typer.Option("feather.yaml", "--config"),
    mode: str | None = typer.Option(None, "--mode"),
) -> None:
    """Preview and initialize state DB and schemas. Optional — feather run creates them automatically."""
    from feather_etl.destinations.duckdb import DuckDBDestination
    from feather_etl.state import StateManager

    cfg = _load_and_validate(config, mode_override=mode)
    if not _is_json(ctx):
        typer.echo(f"Mode: {cfg.mode}")

    state_path = cfg.config_dir / "feather_state.duckdb"
    sm = StateManager(state_path)
    sm.init_state()
    if not _is_json(ctx):
        typer.echo(f"State DB initialized: {state_path}")

    dest = DuckDBDestination(path=cfg.destination.path)
    dest.setup_schemas()
    if not _is_json(ctx):
        typer.echo(f"Schemas created in: {cfg.destination.path}")

    # Execute transforms (silver views, gold views/tables) if any exist
    from feather_etl.transforms import (
        build_execution_order,
        discover_transforms,
        execute_transforms,
    )

    transforms_applied = 0
    transforms = discover_transforms(cfg.config_dir)
    if transforms:
        ordered = build_execution_order(transforms)
        con = dest._connect()
        try:
            if cfg.mode == "prod":
                gold_only = [t for t in ordered if t.schema == "gold"]
                results = execute_transforms(con, gold_only)
            else:
                results = execute_transforms(con, ordered, force_views=True)
        finally:
            con.close()

        transforms_applied = sum(1 for r in results if r.status == "success")

        if not _is_json(ctx):
            silver_views = sum(
                1 for r in results if r.schema == "silver" and r.status == "success"
            )
            gold_views = sum(
                1
                for r in results
                if r.schema == "gold" and r.type == "view" and r.status == "success"
            )
            gold_tables = sum(
                1
                for r in results
                if r.schema == "gold" and r.type == "table" and r.status == "success"
            )
            parts = []
            if silver_views:
                parts.append(f"{silver_views} silver view(s)")
            if gold_views:
                parts.append(f"{gold_views} gold view(s)")
            if gold_tables:
                parts.append(f"{gold_tables} gold table(s)")
            typer.echo(f"Transforms applied: {', '.join(parts)}")

            errors = [r for r in results if r.status == "error"]
            for r in errors:
                typer.echo(
                    f"  Transform error: {r.schema}.{r.name} — {r.error}", err=True
                )

    if _is_json(ctx):
        emit_line(
            {
                "state_db": str(state_path),
                "destination": str(cfg.destination.path),
                "schemas_created": True,
                "transforms_applied": transforms_applied,
            },
            json_mode=True,
        )


@app.command()
def run(
    ctx: typer.Context,
    config: Path = typer.Option("feather.yaml", "--config"),
    mode: str | None = typer.Option(None, "--mode"),
    table: str | None = typer.Option(None, "--table", help="Extract only this table."),
) -> None:
    """Extract all configured tables (or a single table with --table)."""
    from feather_etl.pipeline import run_all

    cfg = _load_and_validate(config, mode_override=mode)
    if not _is_json(ctx):
        typer.echo(f"Mode: {cfg.mode}")
    try:
        results = run_all(cfg, config, table_filter=table)
    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1)

    if _is_json(ctx):
        emit(
            [
                {
                    "table_name": r.table_name,
                    "status": r.status,
                    "rows_loaded": r.rows_loaded,
                    "error_message": r.error_message,
                }
                for r in results
            ],
            json_mode=True,
        )
    else:
        for r in results:
            if r.status == "success":
                typer.echo(f"  {r.table_name}: {r.status} ({r.rows_loaded} rows)")
            elif r.status == "skipped":
                typer.echo(f"  {r.table_name}: skipped (unchanged)")
            else:
                typer.echo(f"  {r.table_name}: {r.status} — {r.error_message}")

        successes = sum(1 for r in results if r.status == "success")
        skipped = sum(1 for r in results if r.status == "skipped")

        parts = [f"{successes}/{len(results)} tables extracted"]
        if skipped:
            parts.append(f"{skipped} skipped")
        typer.echo(f"\n{', '.join(parts)}.")

    failures = sum(
        1 for r in results
        if r.status == "failure" or (r.status == "skipped" and r.error_message)
    )
    if failures > 0:
        raise typer.Exit(code=1)


@app.command()
def history(
    ctx: typer.Context,
    config: Path = typer.Option("feather.yaml", "--config"),
    table: str | None = typer.Option(None, "--table", help="Filter by table name."),
    limit: int = typer.Option(20, "--limit", help="Maximum number of runs to show."),
) -> None:
    """Show recent run history."""
    from feather_etl.state import StateManager

    cfg = _load_and_validate(config)
    state_path = cfg.config_dir / "feather_state.duckdb"

    if not state_path.exists():
        typer.echo("No state DB found. Run 'feather run' first.", err=True)
        raise typer.Exit(code=1)

    sm = StateManager(state_path)
    rows = sm.get_history(table_name=table, limit=limit)

    if not rows:
        if not _is_json(ctx):
            typer.echo("No runs recorded yet.")
        return

    if _is_json(ctx):
        emit(
            [
                {
                    "run_id": row["run_id"],
                    "table_name": row["table_name"],
                    "started_at": str(row.get("started_at", "")),
                    "ended_at": str(row.get("ended_at", "")),
                    "status": row["status"],
                    "rows_loaded": row.get("rows_loaded"),
                    "error_message": row.get("error_message"),
                }
                for row in rows
            ],
            json_mode=True,
        )
    else:
        typer.echo(f"{'Table':<30} {'Status':<12} {'Rows':<10} {'Started':<28} {'Run ID'}")
        typer.echo("-" * 100)
        for row in rows:
            typer.echo(
                f"{row['table_name']:<30} {row['status']:<12} "
                f"{row.get('rows_loaded', '-') or '-'!s:<10} "
                f"{str(row.get('started_at', '-')):<28} {row.get('run_id', '-')}"
            )
            if row.get("error_message"):
                error = str(row["error_message"])
                if len(error) > 80:
                    error = error[:77] + "..."
                typer.echo(f"  Error: {error}")


@app.command()
def status(ctx: typer.Context, config: Path = typer.Option("feather.yaml", "--config")) -> None:
    """Show last run status for all tables."""
    from feather_etl.state import StateManager

    cfg = _load_and_validate(config)
    state_path = cfg.config_dir / "feather_state.duckdb"

    if not state_path.exists():
        typer.echo("No state DB found. Run 'feather setup' first.", err=True)
        raise typer.Exit(code=1)

    sm = StateManager(state_path)
    rows = sm.get_status()

    if not rows:
        if _is_json(ctx):
            return
        typer.echo("No runs recorded yet.")
        return

    if _is_json(ctx):
        emit(
            [
                {
                    "table_name": row["table_name"],
                    "last_run_at": str(row.get("ended_at", "")),
                    "status": row["status"],
                    "watermark": row.get("watermark"),
                    "rows_loaded": row.get("rows_loaded"),
                }
                for row in rows
            ],
            json_mode=True,
        )
    else:
        typer.echo(f"{'Table':<30} {'Status':<12} {'Rows':<10} {'Last Run'}")
        typer.echo("-" * 75)
        for row in rows:
            typer.echo(
                f"{row['table_name']:<30} {row['status']:<12} "
                f"{row.get('rows_loaded', '-'):<10} {row.get('ended_at', '-')}"
            )
            if row["status"] == "failure" and row.get("error_message"):
                error = str(row["error_message"])
                if len(error) > 80:
                    error = error[:77] + "..."
                typer.echo(f"  Error: {error}")
