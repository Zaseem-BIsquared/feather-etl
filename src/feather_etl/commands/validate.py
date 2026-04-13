"""`feather validate` command."""

from __future__ import annotations

from pathlib import Path

import typer

from feather_etl.commands._common import _is_json, _load_and_validate
from feather_etl.output import emit_line


def validate(
    ctx: typer.Context, config: Path = typer.Option("feather.yaml", "--config")
) -> None:
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
        err = getattr(source, "_last_error", None)
        if err:
            typer.echo(f"  Details: {err}", err=True)
        raise typer.Exit(code=2)


def register(app: typer.Typer) -> None:
    app.command(name="validate")(validate)

