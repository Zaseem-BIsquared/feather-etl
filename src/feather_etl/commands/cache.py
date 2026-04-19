"""`feather cache` command — dev-only local bronze pull."""

from __future__ import annotations

from pathlib import Path

import typer

from feather_etl.commands._common import _load_and_validate


def cache(
    config: Path = typer.Option("feather.yaml", "--config"),
    table: str | None = typer.Option(
        None,
        "--table",
        help="Comma-separated bronze table names to cache. "
        "Default: all curated tables.",
    ),
    source: str | None = typer.Option(
        None,
        "--source",
        help="Comma-separated source_db values to cache. "
        "Default: all sources in curation.",
    ),
    refresh: bool = typer.Option(
        False,
        "--refresh",
        help="Force re-pull even if source is unchanged.",
    ),
) -> None:
    """Pull curated source tables into bronze (dev-only)."""
    from feather_etl.cache import run_cache

    curation_path = Path(config).resolve().parent / "discovery" / "curation.json"
    if not curation_path.exists():
        typer.echo(
            f"discovery/curation.json not found in {curation_path.parent.parent}. "
            f"Run 'feather discover' and curate tables first.",
            err=True,
        )
        raise typer.Exit(code=2)

    cfg = _load_and_validate(config)

    if cfg.mode == "prod":
        typer.echo(
            "feather cache is a dev-only tool. "
            "Remove 'mode: prod' or unset FEATHER_MODE=prod to use it.",
            err=True,
        )
        raise typer.Exit(code=2)

    tables = cfg.tables
    results = run_cache(cfg, tables, cfg.config_dir, refresh=refresh)

    # Grouped-by-source_db output
    from collections import defaultdict
    groups: dict[str, list] = defaultdict(list)
    for r in results:
        groups[r.source_db].append(r)

    typer.echo("Mode: dev (cache)")
    total_success = 0
    total_cached = 0
    total_failed = 0
    for source_db, rs in groups.items():
        succ = sum(1 for r in rs if r.status == "success")
        cach = sum(1 for r in rs if r.status == "cached")
        fail = sum(1 for r in rs if r.status == "failure")
        total_success += succ
        total_cached += cach
        total_failed += fail

        parts = []
        if succ:
            parts.append(f"{succ} extracted")
        if cach:
            parts.append(f"{cach} cached")
        if fail:
            parts.append(f"{fail} failed")
        # Look up the source 'name' for the parenthetical. For file sources,
        # source_db == source.name, so fall back to source_db.
        src_name = _lookup_source_name(cfg, source_db)
        line = f"  {source_db:<12} ({src_name}): {', '.join(parts) or '0 tables'}"
        typer.echo(line)
        for r in rs:
            if r.status == "failure":
                err = (r.error_message or "").splitlines()[0][:120]
                typer.echo(f"    ✗ {r.table_name} — {err}")

    total = len(results)
    summary_parts = []
    if total_success:
        summary_parts.append(f"{total_success} extracted")
    if total_cached:
        summary_parts.append(f"{total_cached} cached")
    if total_failed:
        summary_parts.append(f"{total_failed} failed")
    typer.echo(f"\n{total} tables: {', '.join(summary_parts) or '0 tables'}.")

    if total_failed:
        raise typer.Exit(code=1)


def _lookup_source_name(cfg, source_db: str) -> str:
    """Find the YAML source 'name' corresponding to a source_db."""
    from feather_etl.curation import resolve_source
    try:
        src = resolve_source(source_db, cfg.sources)
        return src.name
    except ValueError:
        return source_db


def register(app: typer.Typer) -> None:
    app.command(name="cache")(cache)
