"""`feather validate` command."""

from __future__ import annotations

from pathlib import Path

import typer

from feather_etl.commands._common import (
    _is_json,
    _load_and_validate,
)
from feather_etl.output import emit_line


def validate(
    ctx: typer.Context, config: Path = typer.Option("feather.yaml", "--config")
) -> None:
    """Validate config, test source connection, and write feather_validation.json."""
    cfg = _load_and_validate(config)

    # Test source connections
    all_ok = True
    for source in cfg.sources:
        source_ok = source.check()
        if not source_ok:
            all_ok = False
        if not _is_json(ctx):
            source_label = (
                getattr(source, "path", None)
                or getattr(source, "host", None)
                or "configured"
            )
            conn_status = "connected" if source_ok else "FAILED"
            typer.echo(f"  Source: {source.type} ({source_label}) — {conn_status}")
            if not source_ok:
                err = getattr(source, "_last_error", None)
                if err:
                    typer.echo(f"    Details: {err}", err=True)

    if _is_json(ctx):
        emit_line(
            {
                "valid": True,
                "tables_count": len(cfg.tables),
                "source_type": cfg.sources[0].type,
                "destination": str(cfg.destination.path),
                "mode": cfg.mode,
                "source_connected": all_ok,
            },
            json_mode=True,
        )
    else:
        typer.echo(f"Config valid: {len(cfg.tables)} table(s)")
        typer.echo(f"  Destination: {cfg.destination.path}")
        typer.echo(f"  State: {cfg.config_dir / 'feather_state.duckdb'}")
        for t in cfg.tables:
            typer.echo(f"  Table: {t.name} → {t.target_table} ({t.strategy})")

    if not all_ok:
        typer.echo("Source connection failed.", err=True)
        raise typer.Exit(code=2)


def register(app: typer.Typer) -> None:
    app.command(name="validate")(validate)
