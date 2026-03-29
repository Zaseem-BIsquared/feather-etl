"""Pipeline orchestrator for feather-etl."""

from __future__ import annotations

import hashlib
import json as json_mod
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc

from feather.alerts import alert_on_failure
from feather.config import FeatherConfig, TableConfig
from feather.destinations.duckdb import DuckDBDestination
from feather.sources.registry import create_source
from feather.state import StateManager

logger = logging.getLogger(__name__)


class _JsonlFormatter(logging.Formatter):
    """Format log records as JSON lines."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        # Include extra fields if present
        for key in ("table", "status", "rows_loaded", "error"):
            if hasattr(record, key):
                entry[key] = getattr(record, key)
        return json_mod.dumps(entry, default=str)


def _setup_jsonl_logging(config_dir: Path) -> None:
    """Add a JSONL FileHandler to the feather logger (idempotent)."""
    log_path = config_dir / "feather_log.jsonl"
    feather_logger = logging.getLogger("feather")

    # Guard against duplicate handlers across multiple run_all() calls
    for h in feather_logger.handlers:
        if isinstance(h, logging.FileHandler) and h.baseFilename == str(log_path.resolve()):
            return

    handler = logging.FileHandler(str(log_path), mode="a")
    handler.setFormatter(_JsonlFormatter())
    handler.setLevel(logging.INFO)
    feather_logger.addHandler(handler)
    feather_logger.setLevel(logging.INFO)


def _resolve_target(table: TableConfig, mode: str) -> str:
    """Derive effective target from mode unless explicitly set."""
    if table.target_table:
        return table.target_table
    if mode == "prod":
        return f"silver.{table.name}"
    return f"bronze.{table.name}"


def _apply_column_map(data: pa.Table, column_map: dict[str, str]) -> pa.Table:
    """Select and rename columns per column_map. Returns new table with only mapped columns."""
    source_cols = list(column_map.keys())
    # Select only the mapped columns
    data = data.select(source_cols)
    # Rename: build new names in order
    new_names = [column_map[c] for c in data.column_names]
    return data.rename_columns(new_names)


def _compute_pk_hashes(
    data: pa.Table,
    primary_key: list[str],
    ts_column: str,
    watermark_value: str,
) -> list[str]:
    """Compute SHA-256 hashes of PK values for rows at the given watermark timestamp."""
    ts_vals = data.column(ts_column).to_pylist()
    pk_cols = {pk: data.column(pk).to_pylist() for pk in primary_key}
    hashes = []
    for i in range(data.num_rows):
        if str(ts_vals[i]) == watermark_value:
            key = "|".join(str(pk_cols[pk][i]) for pk in primary_key)
            hashes.append(hashlib.sha256(key.encode()).hexdigest())
    return hashes


def _filter_boundary_rows(
    data: pa.Table,
    primary_key: list[str] | None,
    ts_column: str,
    old_watermark: str,
    prev_hashes: list[str],
) -> tuple[pa.Table, int]:
    """Filter out boundary rows whose PK hash matches stored hashes.

    Returns (filtered_data, rows_skipped).
    """
    if not primary_key or not prev_hashes:
        return data, 0

    prev_set = set(prev_hashes)
    ts_vals = data.column(ts_column).to_pylist()
    pk_cols = {pk: data.column(pk).to_pylist() for pk in primary_key}
    mask = []
    skipped = 0
    for i in range(data.num_rows):
        if str(ts_vals[i]) == old_watermark:
            key = "|".join(str(pk_cols[pk][i]) for pk in primary_key)
            h = hashlib.sha256(key.encode()).hexdigest()
            if h in prev_set:
                mask.append(False)
                skipped += 1
                continue
        mask.append(True)
    return data.filter(mask), skipped


@dataclass
class RunResult:
    table_name: str
    run_id: str
    status: str  # "success", "failure", "skipped"
    rows_loaded: int = 0
    error_message: str | None = None


def run_table(
    config: FeatherConfig,
    table: TableConfig,
    working_dir: Path,
) -> RunResult:
    """Run a single table through the pipeline: extract → load → update state."""
    logger.info("Starting extraction", extra={"table": table.name})
    now = datetime.now(timezone.utc)
    run_id = f"{table.name}_{now.isoformat()}"

    state_path = working_dir / "feather_state.duckdb"
    state = StateManager(state_path)
    state.init_state()

    # Retry backoff check: skip if table is in backoff window
    skip, skip_error = state.should_skip_retry(table.name)
    if skip:
        ended_at = datetime.now(timezone.utc)
        error_msg = f"In backoff (previous failure: {skip_error})"
        logger.info("Skipped (retry backoff)", extra={"table": table.name, "status": "skipped"})
        state.record_run(
            run_id=run_id,
            table_name=table.name,
            started_at=now,
            ended_at=ended_at,
            status="skipped",
            error_message=error_msg,
        )
        return RunResult(
            table_name=table.name,
            run_id=run_id,
            status="skipped",
            error_message=error_msg,
        )

    dest = DuckDBDestination(path=config.destination.path)
    dest.setup_schemas()

    source = create_source(config.source)
    effective_target = _resolve_target(table, config.mode)

    # Prod mode with column_map: extract only mapped columns
    prod_columns = (
        list(table.column_map.keys())
        if config.mode == "prod" and table.column_map
        else None
    )

    # Change detection: check if source file changed since last run
    wm = state.read_watermark(table.name)
    change = source.detect_changes(table.source_table, last_state=wm)

    started_at = datetime.now(timezone.utc)

    if not change.changed:
        ended_at = datetime.now(timezone.utc)
        state.record_run(
            run_id=run_id,
            table_name=table.name,
            started_at=started_at,
            ended_at=ended_at,
            status="skipped",
        )
        # Touch scenario: mtime changed but hash identical — update watermark
        # so next run skips re-hashing
        if change.metadata:
            state.write_watermark(
                table.name,
                strategy=table.strategy,
                last_run_at=ended_at,
                last_file_mtime=change.metadata.get("file_mtime"),
                last_file_hash=change.metadata.get("file_hash"),
                last_checksum=change.metadata.get("checksum"),
                last_row_count=change.metadata.get("row_count"),
            )
        return RunResult(
            table_name=table.name,
            run_id=run_id,
            status="skipped",
        )

    try:
        is_incremental = table.strategy == "incremental"
        wm_last_value = wm.get("last_value") if wm else None
        watermark_before = str(wm_last_value) if wm_last_value else None

        if is_incremental and wm_last_value is not None:
            # Subsequent incremental run: apply overlap window
            overlap = config.defaults.overlap_window_minutes
            wm_dt = datetime.fromisoformat(str(wm_last_value))
            effective_wm = wm_dt - timedelta(minutes=overlap)
            effective_wm_str = effective_wm.isoformat()

            data = source.extract(
                table.source_table,
                columns=prod_columns,
                filter=table.filter,
                watermark_column=table.timestamp_column,
                watermark_value=effective_wm_str,
            )
            if config.mode == "test" and config.defaults.row_limit:
                data = data.slice(0, config.defaults.row_limit)
            if config.mode == "prod" and table.column_map:
                data = _apply_column_map(data, table.column_map)

            # Boundary dedup: filter out rows already loaded in previous run
            prev_hashes = state.read_boundary_hashes(table.name)
            data, rows_skipped_boundary = _filter_boundary_rows(
                data, table.primary_key, table.timestamp_column,
                str(wm_last_value), prev_hashes,
            )

            if data.num_rows == 0:
                ended_at = datetime.now(timezone.utc)
                state.record_run(
                    run_id=run_id,
                    table_name=table.name,
                    started_at=started_at,
                    ended_at=ended_at,
                    status="success",
                    rows_extracted=0,
                    rows_loaded=0,
                    watermark_before=watermark_before,
                    watermark_after=watermark_before,
                )
                # Update file mtime/hash but keep last_value unchanged
                state.write_watermark(
                    table.name,
                    strategy=table.strategy,
                    last_run_at=ended_at,
                    last_file_mtime=change.metadata.get("file_mtime"),
                    last_file_hash=change.metadata.get("file_hash"),
                    last_value=str(wm_last_value),
                )
                state.reset_retry(table.name)
                return RunResult(
                    table_name=table.name,
                    run_id=run_id,
                    status="success",
                    rows_loaded=0,
                )

            rows_loaded = dest.load_incremental(
                effective_target, data, run_id, table.timestamp_column
            )
        elif table.strategy == "append":
            # Append strategy: extract full source, insert without deleting existing rows
            data = source.extract(table.source_table, columns=prod_columns, filter=table.filter)
            if config.mode == "test" and config.defaults.row_limit:
                data = data.slice(0, config.defaults.row_limit)
            if config.mode == "prod" and table.column_map:
                data = _apply_column_map(data, table.column_map)
            rows_loaded = dest.load_append(effective_target, data, run_id)
        else:
            # Full strategy, or first incremental run (no watermark yet)
            if is_incremental and table.filter:
                data = source.extract(table.source_table, columns=prod_columns, filter=table.filter)
            else:
                data = source.extract(table.source_table, columns=prod_columns)
            if config.mode == "test" and config.defaults.row_limit:
                data = data.slice(0, config.defaults.row_limit)
            if config.mode == "prod" and table.column_map:
                data = _apply_column_map(data, table.column_map)
            rows_loaded = dest.load_full(effective_target, data, run_id)

        # Compute new watermark value for incremental tables
        new_last_value = None
        if is_incremental and data.num_rows > 0:
            max_ts = pc.max(data.column(table.timestamp_column)).as_py()
            new_last_value = max_ts.isoformat() if max_ts else None
        elif is_incremental and wm_last_value is not None:
            new_last_value = str(wm_last_value)

        watermark_after = new_last_value

        # Store boundary hashes for next run's dedup
        if is_incremental and new_last_value and table.primary_key and data.num_rows > 0:
            new_hashes = _compute_pk_hashes(
                data, table.primary_key, table.timestamp_column, new_last_value,
            )
            state.write_boundary_hashes(table.name, new_hashes)

        ended_at = datetime.now(timezone.utc)
        state.write_watermark(
            table.name,
            strategy=table.strategy,
            last_run_at=ended_at,
            last_file_mtime=change.metadata.get("file_mtime"),
            last_file_hash=change.metadata.get("file_hash"),
            last_value=new_last_value,
            last_checksum=change.metadata.get("checksum"),
            last_row_count=change.metadata.get("row_count"),
        )
        state.record_run(
            run_id=run_id,
            table_name=table.name,
            started_at=started_at,
            ended_at=ended_at,
            status="success",
            rows_extracted=rows_loaded,
            rows_loaded=rows_loaded,
            watermark_before=watermark_before,
            watermark_after=watermark_after,
        )
        state.reset_retry(table.name)
        logger.info(
            "Loaded %d rows", rows_loaded,
            extra={"table": table.name, "status": "success", "rows_loaded": rows_loaded},
        )
        return RunResult(
            table_name=table.name,
            run_id=run_id,
            status="success",
            rows_loaded=rows_loaded,
        )
    except Exception as e:
        ended_at = datetime.now(timezone.utc)
        error_msg = str(e)
        logger.error(
            "Failed: %s", error_msg,
            extra={"table": table.name, "status": "failure", "error": error_msg},
        )
        state.record_run(
            run_id=run_id,
            table_name=table.name,
            started_at=started_at,
            ended_at=ended_at,
            status="failure",
            error_message=error_msg,
        )
        state.increment_retry(table.name)
        alert_on_failure(table.name, error_msg, config=config.alerts)
        return RunResult(
            table_name=table.name,
            run_id=run_id,
            status="failure",
            error_message=error_msg,
        )


def run_all(
    config: FeatherConfig,
    config_path: Path,
    table_filter: str | None = None,
) -> list[RunResult]:
    """Run all configured tables (or a single table if table_filter is set).

    After extraction, rebuilds materialized gold transforms if any tables
    succeeded and transform SQL files exist.

    Raises ValueError if table_filter names a table not in config.
    """
    working_dir = config.config_dir
    _setup_jsonl_logging(working_dir)

    tables = config.tables
    if table_filter is not None:
        tables = [t for t in config.tables if t.name == table_filter]
        if not tables:
            available = ", ".join(t.name for t in config.tables)
            raise ValueError(
                f"Table '{table_filter}' not found in config. "
                f"Available tables: {available}"
            )

    results: list[RunResult] = []
    for table in tables:
        result = run_table(config, table, working_dir)
        results.append(result)

    # Post-extraction transforms (mode-dependent)
    # Include skipped tables: transforms must run even when extraction is
    # skipped (e.g. mode switch dev→prod needs to rematerialise gold).
    any_ok = any(r.status in ("success", "skipped") for r in results)
    if any_ok:
        try:
            from feather.transforms import (
                build_execution_order,
                discover_transforms,
                execute_transforms,
                rebuild_materialized_gold,
            )

            transforms = discover_transforms(config.config_dir)
            if transforms:
                ordered = build_execution_order(transforms)
                dest = DuckDBDestination(path=config.destination.path)
                con = dest._connect()
                try:
                    if config.mode == "prod":
                        # Prod: create all as views first (gold needs silver),
                        # then rebuild gold as materialized tables
                        execute_transforms(con, ordered)
                        rebuild_results = rebuild_materialized_gold(con, ordered)
                        count = sum(1 for r in rebuild_results if r.status == "success")
                        if count:
                            logger.info("Rebuilt %d materialized gold table(s)", count)
                    else:
                        # Dev/test: create everything as views (force_views)
                        execute_transforms(con, ordered, force_views=True)
                finally:
                    con.close()
        except Exception as e:
            logger.error("Transform rebuild failed: %s", e)

    return results
