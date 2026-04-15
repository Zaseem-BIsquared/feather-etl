"""`feather discover` command."""

from __future__ import annotations

from pathlib import Path

import typer

from feather_etl.commands._common import _load_and_validate
from feather_etl.viewer_server import serve_and_open


def discover(config: Path = typer.Option("feather.yaml", "--config")) -> None:
    """Save source schema to an auto-named JSON file, then serve/open the schema viewer."""
    import json

    from feather_etl.config import schema_output_path

    cfg = _load_and_validate(config)
    source = cfg.source

    if not source.check():
        typer.echo("Source connection failed.", err=True)
        raise typer.Exit(code=2)

    schemas = source.discover()
    payload = [
        {
            "table_name": s.name,
            "columns": [{"name": c[0], "type": c[1]} for c in s.columns],
        }
        for s in schemas
    ]
    out_path = schema_output_path(cfg.source)
    out_path.write_text(json.dumps(payload, indent=2))
    typer.echo(f"Wrote {len(schemas)} table(s) to ./{out_path}")

    viewer_target_dir = out_path.parent.resolve()
    serve_and_open(viewer_target_dir, preferred_port=8000)


def register(app: typer.Typer) -> None:
    app.command(name="discover")(discover)
