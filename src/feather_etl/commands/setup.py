"""`feather setup` command."""

from __future__ import annotations

from pathlib import Path

import typer

from feather_etl.commands._common import _enforce_single_source, _is_json, _load_and_validate
from feather_etl.output import emit_line


def setup(
    ctx: typer.Context,
    config: Path = typer.Option("feather.yaml", "--config"),
    mode: str | None = typer.Option(None, "--mode"),
) -> None:
    """Preview and initialize state DB and schemas. Optional — feather run creates them automatically."""
    from feather_etl.destinations.duckdb import DuckDBDestination
    from feather_etl.state import StateManager

    cfg = _load_and_validate(config, mode_override=mode)
    _enforce_single_source(cfg, "setup")
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


def register(app: typer.Typer) -> None:
    app.command(name="setup")(setup)

