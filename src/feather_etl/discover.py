"""`feather discover` core — orchestration without Typer.

Three pure top-level functions:

* ``detect_renames_for_sources(state, sources) -> RenameDetection``
  Pure detection. Returns proposals + ambiguous list. No I/O.

* ``apply_rename_decision(state, accepted, rejected, sources, config_dir) -> None``
  Applies a pre-resolved decision. The CLI wrapper resolves the decision
  interactively (Typer confirm prompt + --yes / --no-renames) and calls this.

* ``run_discover(cfg, config_dir, *, refresh, retry_failed, prune) -> DiscoverReport``
  Per-source discovery loop. Assumes renames already resolved.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from feather_etl.config import FeatherConfig, schema_output_path
from feather_etl.discover_state import (
    DiscoverState,
    apply_renames,
    classify,
    detect_renames,
)


@dataclass
class RenameDetection:
    """Output of ``detect_renames_for_sources``."""

    proposals: list[tuple[str, str]] = field(default_factory=list)
    ambiguous: list[tuple[str, list[str]]] = field(default_factory=list)


@dataclass
class SourceDiscoveryResult:
    """One source's outcome from ``run_discover``."""

    name: str
    decision: str  # "new" | "retry" | "rerun" | "cached" | "skip" | "removed"
    status: str  # "succeeded" | "failed" | "cached" | "skipped" | "pruned"
    table_count: int = 0
    output_path: Path | None = None
    error: str | None = None


@dataclass
class DiscoverReport:
    """Aggregate result of ``run_discover``."""

    results: list[SourceDiscoveryResult] = field(default_factory=list)
    succeeded_count: int = 0
    failed_count: int = 0
    cached_count: int = 0
    pruned_count: int = 0
    state_last_run_at: str | None = None


def _write_schema(source, target_dir: Path) -> tuple[Path, int]:
    """Discover ``source`` and write its schema JSON. Returns (path, table_count)."""
    schemas = source.discover()
    payload = [
        {
            "table_name": s.name,
            "columns": [{"name": c[0], "type": c[1]} for c in s.columns],
        }
        for s in schemas
    ]
    out = target_dir / schema_output_path(source)
    out.write_text(json.dumps(payload, indent=2))
    return out, len(schemas)


def _fingerprint_for(source) -> str:
    """Composition per spec §6.7.

    DB sources: '<type>:<host>:<port>:<database>'. File sources: '<type>:<absolute_path>'.
    """
    if hasattr(source, "host") and source.host is not None:
        return (
            f"{source.type}:{source.host}:{source.port or ''}:{source.database or ''}"
        )
    return f"{source.type}:{Path(source.path).resolve()}"


def detect_renames_for_sources(
    state: DiscoverState,
    sources: list,
) -> RenameDetection:
    """Pure detection. Returns proposals + ambiguous list. No I/O, no prompts."""
    current_pairs = [(source.name, _fingerprint_for(source)) for source in sources]
    proposals, ambiguous = detect_renames(state=state, current=current_pairs)
    return RenameDetection(proposals=list(proposals), ambiguous=list(ambiguous))


def apply_rename_decision(
    state: DiscoverState,
    accepted: list[tuple[str, str]],
    rejected: list[tuple[str, str]],
    sources: list,
    config_dir: Path,
) -> None:
    """Apply a pre-resolved rename decision.

    ``accepted`` proposals are applied via ``apply_renames`` (state + files
    are renamed). ``rejected`` proposals are recorded as orphaned (the new
    name is treated as a fresh source on the next discovery pass).
    """
    if accepted:
        apply_renames(
            state=state,
            renames=accepted,
            config_dir=config_dir,
            sources=sources,
        )
    for old_name, new_name in rejected:
        state.record_orphaned(
            old_name,
            note=f"rename rejected; new source discovered as {new_name}",
        )


def run_discover(
    cfg: FeatherConfig,
    config_dir: Path,
    *,
    refresh: bool,
    retry_failed: bool,
    prune: bool,
) -> DiscoverReport:
    """Per-source discovery loop. Assumes renames already resolved.

    The CLI wrapper is responsible for:
      * resolving rename proposals (interactive or via --yes / --no-renames)
        and calling ``apply_rename_decision`` before invoking this function;
      * exiting with code 2 on ambiguous renames (using ``RenameDetection``);
      * calling ``serve_and_open`` after this function returns.
    """
    from feather_etl.sources.expand import expand_db_sources

    state = DiscoverState.load(config_dir)
    sources = expand_db_sources(cfg.sources)

    flag: str | None = None
    if refresh:
        flag = "refresh"
    elif retry_failed:
        flag = "retry-failed"
    elif prune:
        flag = "prune"

    names = [s.name for s in sources]
    decisions = classify(state=state, current_names=names, flag=flag)

    report = DiscoverReport(state_last_run_at=state.last_run_at)

    if flag == "prune":
        for name, dec in list(decisions.items()):
            entry = state.sources.get(name)
            if dec == "removed" or (
                entry and entry.get("status") in ("orphaned", "removed")
            ):
                output_path: Path | None = None
                if entry and entry.get("output_path"):
                    target = config_dir / Path(entry["output_path"]).name
                    if target.is_file():
                        output_path = target
                        target.unlink()
                state.sources.pop(name, None)
                report.pruned_count += 1
                report.results.append(
                    SourceDiscoveryResult(
                        name=name,
                        decision=dec,
                        status="pruned",
                        output_path=output_path,
                    )
                )
        state.save()
        return report

    for source in sources:
        decision = decisions.get(source.name, "new")
        fingerprint = _fingerprint_for(source)

        if decision == "cached":
            entry = state.sources[source.name]
            report.cached_count += 1
            report.results.append(
                SourceDiscoveryResult(
                    name=source.name,
                    decision=decision,
                    status="cached",
                    table_count=entry.get("table_count", 0),
                )
            )
            continue
        if decision == "skip":
            report.results.append(
                SourceDiscoveryResult(
                    name=source.name, decision=decision, status="skipped"
                )
            )
            continue

        # Source came from expand_db_sources with a pre-set error.
        if hasattr(source, "_last_error") and source._last_error:
            report.failed_count += 1
            state.record_failed(
                name=source.name,
                type_=source.type,
                fingerprint=fingerprint,
                error=source._last_error,
                host=getattr(source, "host", None),
                database=getattr(source, "database", None),
            )
            report.results.append(
                SourceDiscoveryResult(
                    name=source.name,
                    decision=decision,
                    status="failed",
                    error=source._last_error,
                )
            )
            continue

        if not source.check():
            err = getattr(source, "_last_error", "connection failed")
            report.failed_count += 1
            state.record_failed(
                name=source.name,
                type_=source.type,
                fingerprint=fingerprint,
                error=err,
                host=getattr(source, "host", None),
                database=getattr(source, "database", None),
            )
            report.results.append(
                SourceDiscoveryResult(
                    name=source.name, decision=decision, status="failed", error=err
                )
            )
            continue

        try:
            out, count = _write_schema(source, config_dir)
        except Exception as e:  # noqa: BLE001 — preserve existing broad-catch behavior
            report.failed_count += 1
            state.record_failed(
                name=source.name,
                type_=source.type,
                fingerprint=fingerprint,
                error=str(e),
                host=getattr(source, "host", None),
                database=getattr(source, "database", None),
            )
            report.results.append(
                SourceDiscoveryResult(
                    name=source.name,
                    decision=decision,
                    status="failed",
                    error=str(e),
                )
            )
            continue

        report.succeeded_count += 1
        state.record_ok(
            name=source.name,
            type_=source.type,
            fingerprint=fingerprint,
            table_count=count,
            output_path=out,
            host=getattr(source, "host", None),
            database=getattr(source, "database", None),
        )
        report.results.append(
            SourceDiscoveryResult(
                name=source.name,
                decision=decision,
                status="succeeded",
                table_count=count,
                output_path=out,
            )
        )

    # Mark state-only entries as removed (preserves prior CLI behavior).
    for name, dec in decisions.items():
        if dec == "removed" and state.sources.get(name, {}).get("status") != "orphaned":
            state.record_removed(name)

    state.save()
    return report
