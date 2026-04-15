"""Shared helpers for feather_etl command modules."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from feather_etl.config import FeatherConfig


def _is_json(ctx: typer.Context) -> bool:
    """Read --json flag from Typer context."""
    return ctx.ensure_object(dict).get("json_mode", False)


def _enforce_single_source(cfg: FeatherConfig, command_name: str) -> None:
    """Exit 2 if cfg has multiple sources. Used by every non-discover command."""
    if len(cfg.sources) > 1:
        typer.echo(
            f"Command '{command_name}' is single-source for now (multi-source support is tracked in issue #8). "
            f"Use `feather discover` to enumerate multi-source schemas, or "
            f"split into one feather.yaml per source for non-discover operations.",
            err=True,
        )
        raise typer.Exit(code=2)


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
