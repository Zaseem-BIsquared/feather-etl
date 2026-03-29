# Low-Effort Batch (V11, V14, V16, V18) Implementation Plan

Created: 2026-03-28
Status: VERIFIED
Approved: Yes
Iterations: 1
Worktree: Yes
Type: Feature

## Summary

**Goal:** Implement four low-effort PRD features: SMTP alerting (V11), retry with linear backoff (V14), boundary deduplication at watermark edges (V16), and `--json` CLI output with JSONL log file (V18).

**Architecture:** Each feature extends existing modules — `alerts.py` (new), `state.py` (retry + boundary), `pipeline.py` (retry flow + boundary filtering + alert wiring), `cli.py` (`--json` flag), `output.py` (new, JSON formatting helper). No new abstractions or middleware patterns.

**Tech Stack:** Python stdlib only for SMTP (`smtplib` + `email`), `hashlib` for PK hashing, `json` for NDJSON output. No new dependencies.

## Scope

### In Scope

- **V11:** `AlertsConfig` parsing, `send_alert()` via SMTP, pipeline failure trigger, hook points for future DQ/schema drift alerts
- **V14:** Retry count tracking, linear backoff computation (base 15min, cap 2hr), table skip during backoff window, reset on success, per-table isolation
- **V16:** PK hash computation at watermark boundary, storage in `boundary_hashes`, filtering on next incremental run
- **V18:** `--json` flag on all CLI commands (`run`, `status`, `history`, `validate`, `discover`, `setup`), NDJSON stdout, JSONL log file alongside state DB

### Out of Scope

- DQ check alert triggers (V9 not built yet — hook point only)
- Schema drift alert triggers (V10 not built yet — hook point only)
- Quarantine schema (better paired with V9 DQ checks)
- Log rotation/truncation (manual for now)
- Full-row hash for boundary dedup (PK-only per user decision)
- Configurable log path (uses config_dir default)

## Approach

**Chosen:** Modular additions — each feature gets its own module or natural extension point.

**Why:** Minimal coupling between features, easy to test independently, follows existing codebase patterns.

**Alternatives considered:** Pipeline middleware/hook pattern — rejected as over-engineering for 4 independent features that each touch ≤3 files.

## Context for Implementer

> Write for an implementer who has never seen the codebase.

- **Patterns to follow:**
  - Config parsing: `config.py:22-63` — dataclasses with fields matching YAML keys, parsed in `load_config()`
  - State methods: `state.py:128-316` — `_connect()` → try/finally → `con.close()` pattern
  - CLI commands: `cli.py:29-261` — each `@app.command()` loads config via `_load_and_validate()`, uses `typer.echo()` for output
  - Pipeline error handling: `pipeline.py:223-239` — catch Exception, record failure run, return `RunResult`

- **Conventions:**
  - All state DB connections use try/finally with `.close()`
  - Config dataclasses use `field(default_factory=...)` for mutable defaults
  - Tests use real DuckDB fixtures (no mocking), `tmp_path` for isolated state DBs
  - `from __future__ import annotations` at top of every module

- **Key files:**
  - `src/feather/config.py` (359 LOC) — YAML parsing, validation, `FeatherConfig` dataclass
  - `src/feather/state.py` (316 LOC) — `StateManager` with watermark/run methods
  - `src/feather/pipeline.py` (306 LOC) — `run_table()` and `run_all()` orchestration
  - `src/feather/cli.py` (260 LOC) — Typer CLI with 7 commands
  - `src/feather/destinations/duckdb.py` (144 LOC) — `load_full()`, `load_incremental()`, `load_append()`

- **Gotchas:**
  - `write_watermark()` uses a `_SENTINEL` pattern to distinguish "not provided" from `None` for `last_value`
  - The `_watermarks` table already has `retry_count`, `retry_after`, and `boundary_hashes` columns — they're created in `state.py:54-56` but never read/written
  - `pipeline.py:run_table()` catches all Exceptions at line 223 — retry state must be updated inside that handler
  - Current LOC is ~3000 total (above PRD's 1400 target but acceptable per prior decisions)

- **Domain context:**
  - Pipeline runs per-table: each table extracts → loads independently
  - Incremental extraction uses an overlap window (default 2 min) that re-fetches boundary rows to avoid gaps
  - This overlap is what creates duplicate boundary rows that V16 deduplicates
  - Linear backoff formula: `retry_after = now + min(retry_count × 15 min, 120 min)`

## Assumptions

- The `_watermarks.boundary_hashes` column (JSON type) can store a JSON array of hex digest strings — supported by `state.py:56`, Task 5 depends on this
- The `_watermarks.retry_count` and `retry_after` columns exist and default correctly — supported by `state.py:54-55`, Tasks 3-4 depend on this
- `smtplib.SMTP` with `starttls()` works for port 587 (standard SMTP relay) — supported by PRD FR12, Task 1 depends on this
- Typer supports adding a global `--json` option via callback — Tasks 7-8 depend on this
- `table.primary_key` is always set for incremental tables that need boundary dedup — if not set, boundary dedup is silently skipped, Task 5 depends on this
- **AC-FR7.b partial waiver:** PK-only hash (user decision) means updated boundary rows are skipped for one run cycle. This is accepted as a trade-off for simpler implementation. Task 5 depends on this decision.

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SMTP connection fails silently, masking alert config errors | Medium | Medium | Log SMTP errors clearly; `feather validate` checks `alerts` section syntax (not connectivity) |
| Boundary hash collision (two different PKs produce same hash) | Very Low | Low | Use SHA-256 — collision probability negligible for ETL row counts |
| `--json` breaks existing CLI output consumers (scripts) | Low | Medium | `--json` is opt-in flag, default output unchanged |
| Retry backoff delays all runs when source is persistently down | Medium | Medium | Cap at 120 minutes per PRD; operator sees `skipped` status in `feather status` |

## Goal Verification

### Truths

1. When `alerts` is configured in YAML and a pipeline table fails, an email is sent with `[CRITICAL]` subject prefix
2. When `alerts` is NOT configured, no SMTP connection is attempted on failure
3. After 2 consecutive failures, a table's `retry_after` is 30 minutes from now (2 × 15 min)
4. A table in backoff is skipped with status `skipped` and error referencing original failure
5. On successful run after failures, `retry_count` resets to 0 and `retry_after` clears
6. Boundary rows (at max watermark timestamp) from run N are skipped in run N+1 via PK hash match
7. `feather status --json` outputs NDJSON with `table_name`, `last_run_at`, `status`, `watermark`, `rows_loaded` fields
8. All CLI commands with `--json` produce only JSON on stdout (no human-readable text)
9. A `feather_log.jsonl` file is created alongside the state DB with structured log entries

### Artifacts

1. `src/feather/alerts.py` — `send_alert()` function + `AlertsConfig`
2. `src/feather/state.py` — retry and boundary hash methods
3. `src/feather/pipeline.py` — retry flow, boundary filtering, alert wiring
4. `src/feather/config.py` — `AlertsConfig` parsing
5. `src/feather/output.py` — JSON output helper for CLI
6. `src/feather/cli.py` — `--json` flag on all commands
7. `tests/test_alerts.py` — alerting tests
8. `tests/test_retry.py` — retry + backoff tests
9. `tests/test_boundary_dedup.py` — boundary deduplication tests
10. `tests/test_json_output.py` — `--json` CLI output tests

## Progress Tracking

- [x] Task 1: SMTP alerting module
- [x] Task 2: Alert config parsing
- [x] Task 3: Retry state management
- [x] Task 4: Retry pipeline integration
- [x] Task 5: Boundary deduplication
- [x] Task 6: JSONL structured logging
- [x] Task 7: --json CLI output helper
- [x] Task 8: --json flag on all CLI commands

**Total Tasks:** 8 | **Completed:** 8 | **Remaining:** 0

## Implementation Tasks

### Task 1: SMTP Alerting Module

**Objective:** Create `alerts.py` with `send_alert()` that sends emails via SMTP using stdlib. Include hook functions for future DQ and schema drift events.

**Dependencies:** None

**Files:**

- Create: `src/feather/alerts.py`
- Test: `tests/test_alerts.py`

**Key Decisions / Notes:**

- Use `smtplib.SMTP` with `starttls()` for port 587 (standard TLS relay)
- `send_alert(severity, table_name, message, config)` where severity is "CRITICAL", "WARNING", or "INFO"
- Subject format: `[{severity}] feather-etl: {message} — {table_name}` (per AC-FR12.b)
- If `config` is None (no alerts configured), return immediately (no-op)
- Add `alert_on_failure(table_name, error_message, config)`, `alert_on_dq_failure(table_name, check_details, config)`, `alert_on_schema_drift(table_name, drift_details, severity="INFO", config)` — last two are thin wrappers called by V9/V10. `alert_on_schema_drift` accepts a `severity` param (default "INFO") so V10 can pass "CRITICAL" for `type_changed` drift per FR12.6 without signature changes
- Catch `smtplib.SMTPException` and log errors — never let alerting crash the pipeline
- `alert_from` defaults to `smtp_user` if not provided (FR12.3)

**Definition of Done:**

- [ ] `send_alert()` sends email via SMTP with correct subject prefix per severity
- [ ] `alert_on_failure()` sends CRITICAL email with error details
- [ ] `alert_on_dq_failure()` and `alert_on_schema_drift(severity=...)` exist as callable hooks with severity parameter
- [ ] When config is None, all alert functions are no-ops
- [ ] SMTP errors are caught and logged, never crash pipeline
- [ ] All tests pass

**Verify:**

- `uv run pytest tests/test_alerts.py -q`

---

### Task 2: Alert Config Parsing

**Objective:** Parse `alerts` section from `feather.yaml` into `AlertsConfig` dataclass. Wire into `FeatherConfig`. The section is optional — missing means no alerting.

**Dependencies:** Task 1

**Files:**

- Modify: `src/feather/config.py`
- Test: `tests/test_config.py` (add tests)

**Key Decisions / Notes:**

- Add `AlertsConfig` dataclass: `smtp_host`, `smtp_port` (int), `smtp_user`, `smtp_password`, `alert_to`, `alert_from` (optional, defaults to `smtp_user`)
- Add `alerts: AlertsConfig | None = None` to `FeatherConfig`
- Parse in `load_config()` — if `alerts` key missing from YAML, set to None
- Validate: if `alerts` section exists, require `smtp_host`, `smtp_port`, `smtp_user`, `smtp_password`, `alert_to`
- Env var substitution already works recursively via `_resolve_yaml_env_vars()` — SMTP password will resolve `${ALERT_EMAIL_PASSWORD}` automatically

**Definition of Done:**

- [ ] `AlertsConfig` dataclass created with all fields per FR12.2
- [ ] `feather.yaml` with `alerts` section parses correctly
- [ ] `feather.yaml` without `alerts` section sets `config.alerts = None`
- [ ] Missing required alert fields produce validation error
- [ ] Env vars in alert config are resolved (e.g., `${ALERT_EMAIL_PASSWORD}`)
- [ ] All tests pass

**Verify:**

- `uv run pytest tests/test_config.py -q`

---

### Task 3: Retry State Management

**Objective:** Add methods to `StateManager` for retry count tracking and backoff computation. The `_watermarks` table already has `retry_count`, `retry_after`, and `boundary_hashes` columns.

**Dependencies:** None

**Files:**

- Modify: `src/feather/state.py`
- Test: `tests/test_retry.py`

**Key Decisions / Notes:**

- Add `increment_retry(table_name)`: reads current `retry_count`, increments, computes `retry_after = now + min(retry_count × 15 min, 120 min)`, updates `_watermarks`
- Add `reset_retry(table_name)`: sets `retry_count = 0`, `retry_after = NULL`
- Add `should_skip_retry(table_name) -> tuple[bool, str | None]`: returns `(True, original_error)` if `retry_after > now`, else `(False, None)`. The error message comes from the most recent failed `_runs` entry for this table.
- Add `get_last_failure_message(table_name) -> str | None`: queries `_runs` for the most recent failure error_message — called internally by `should_skip_retry()`
- The existing `write_watermark()` doesn't touch `retry_count`/`retry_after` — these are managed separately by the new methods
- Follow existing pattern: `_connect()` → try/finally → `con.close()`

**Definition of Done:**

- [ ] `increment_retry()` increments count and computes linear backoff
- [ ] Backoff formula: `now + min(retry_count × 15 min, 120 min)` — cap at 120 min
- [ ] After 2 failures: retry_after = now + 30 min (AC-FR13.a)
- [ ] After 10 failures: retry_after = now + 120 min, not 150 (AC-FR13.c)
- [ ] `reset_retry()` clears retry state
- [ ] `should_skip_retry()` returns correct skip decision based on current time
- [ ] `get_last_failure_message()` returns most recent failure error_message from `_runs`
- [ ] All connections closed in try/finally
- [ ] All tests pass

**Verify:**

- `uv run pytest tests/test_retry.py -q`

---

### Task 4: Retry Pipeline Integration

**Objective:** Wire retry logic into `run_table()`: check backoff before extraction, update retry state on failure/success, send alert on failure.

**Dependencies:** Task 1, Task 2, Task 3

**Files:**

- Modify: `src/feather/pipeline.py`
- Test: `tests/test_retry.py` (add integration tests)

**Key Decisions / Notes:**

- At start of `run_table()`, after state init: call `state.should_skip_retry(table.name)` — if True, record `skipped` run with error referencing original failure, return early
- In the `except Exception` block (pipeline.py:223): call `state.increment_retry(table.name)`, then `alert_on_failure(table.name, error_msg, config.alerts)` if alerts configured
- On success path (before returning): call `state.reset_retry(table.name)`
- Per-table isolation (FR13.5): one table's failure doesn't affect others — this is already true since `run_all()` loops independently

**Definition of Done:**

- [ ] Table in backoff window is skipped with status "skipped" and error referencing original failure (AC-FR13.b)
- [ ] On failure: retry_count incremented, retry_after computed, alert sent (if configured)
- [ ] On success after failures: retry_count reset to 0, retry_after cleared (FR13.4)
- [ ] Other tables continue running when one fails (FR13.5)
- [ ] Pipeline never crashes due to retry or alert errors
- [ ] All tests pass

**Verify:**

- `uv run pytest tests/test_retry.py -q`
- `uv run pytest tests/test_pipeline.py -q`

---

### Task 5: Boundary Deduplication

**Objective:** After incremental extraction with overlap, compute PK hashes of rows at the max watermark timestamp, store them in `boundary_hashes`. On next run, filter out rows whose PK hash matches stored hashes.

**Dependencies:** None

**Files:**

- Modify: `src/feather/pipeline.py`
- Modify: `src/feather/state.py` (add `write_boundary_hashes()`, `read_boundary_hashes()`)
- Create: `tests/test_boundary_dedup.py`

**Key Decisions / Notes:**

- **Hash computation:** For each row at max watermark timestamp, concatenate PK column values (as strings, pipe-delimited), SHA-256 hash, store hex digest in a JSON array
- **Storage:** `write_boundary_hashes(table_name, hashes: list[str])` updates `_watermarks.boundary_hashes` column (JSON)
- **Filtering:** In `run_table()` after extraction for incremental with overlap, read `boundary_hashes` from previous watermark. For each extracted row at the *old* max watermark value, compute PK hash and check against stored hashes. Filter out matches. This handles the overlap window re-fetch scenario.
- **When to compute new hashes:** After filtering, compute PK hashes of rows at the *new* max watermark timestamp and store them for the next run
- **Skip if no primary_key:** If `table.primary_key` is not set, skip boundary dedup entirely (no way to hash without PKs)
- **Use PyArrow filtering:** `data.filter(mask)` for efficient row removal
- Track `rows_skipped` count in the run record
- **AC-FR7.b limitation (user decision):** PK-only hash means a boundary row with updated non-PK columns (same timestamp, different payload) will be skipped for one run cycle. This is intentional — `load_incremental()` uses INSERT OR REPLACE, so once the watermark advances past that row, it's no longer at the boundary and flows through. The "lag-by-one-run" trade-off was accepted in exchange for simpler implementation (no full-row hash comparison)

**Definition of Done:**

- [ ] PK hashes computed at max watermark timestamp and stored in `boundary_hashes`
- [ ] On next incremental run with overlap, boundary rows with matching PK hash are skipped
- [ ] `rows_skipped` count reflects filtered boundary rows
- [ ] Skips boundary dedup gracefully when `primary_key` is not configured
- [ ] Works correctly with multi-column primary keys (pipe-delimited concatenation)
- [ ] All tests pass

**Verify:**

- `uv run pytest tests/test_boundary_dedup.py -q`

---

### Task 6: JSONL Structured Logging

**Objective:** Add structured JSONL logging to a file alongside the state DB. Each log entry is a JSON object with timestamp, level, event, and context fields.

**Dependencies:** None

**Files:**

- Modify: `src/feather/pipeline.py` (add JSONL log handler setup)
- Test: `tests/test_json_output.py`

**Key Decisions / Notes:**

- Create a `logging.FileHandler` that writes to `{config_dir}/feather_log.jsonl`
- Use a custom `logging.Formatter` subclass that formats each record as a JSON object: `{"timestamp": "...", "level": "INFO", "event": "...", "table": "...", ...}`
- Set up the handler in `run_all()` (the orchestration entry point) — add it to the root `feather` logger. **Guard against duplication:** before adding, check `if not any(isinstance(h, logging.FileHandler) and h.baseFilename == str(log_path) for h in logger.handlers)` — prevents duplicate handlers across multiple `run_all()` calls in the same process (common in tests)
- Include: extraction start/end, load start/end, skipped (unchanged), skipped (retry backoff), failure with error, transform results
- File appends — no rotation (out of scope)
- Human-readable console logging unchanged — JSONL is additional file output

**Definition of Done:**

- [ ] `feather_log.jsonl` created alongside state DB on first `feather run`
- [ ] Each line is valid JSON with `timestamp`, `level`, `event` fields
- [ ] Pipeline events logged: extract, load, skip, failure
- [ ] File is append-only (subsequent runs add lines, don't truncate)
- [ ] Console output unchanged (JSONL is file-only)
- [ ] All tests pass

**Verify:**

- `uv run pytest tests/test_json_output.py -q`

---

### Task 7: --json CLI Output Helper

**Objective:** Create `output.py` with helper functions that format data as NDJSON for `--json` mode, and human-readable tables for default mode.

**Dependencies:** None

**Files:**

- Create: `src/feather/output.py`
- Test: `tests/test_json_output.py` (add tests)

**Key Decisions / Notes:**

- `emit(data: dict | list[dict], json_mode: bool)`: if `json_mode`, print each dict as JSON line to stdout; else no-op (caller handles human output)
- `emit_line(data: dict, json_mode: bool)`: emit single dict
- Exit codes per FR11.15: 0 = success, 1 = validation/config error, 2 = runtime error
- Keep it simple — just JSON serialization with `default=str` for datetime handling
- No external dependencies

**Definition of Done:**

- [ ] `emit()` outputs NDJSON (one JSON object per line per dict)
- [ ] `emit_line()` outputs single JSON line
- [ ] Datetime values serialized as ISO strings
- [ ] Non-JSON mode is a no-op (caller handles formatting)
- [ ] All tests pass

**Verify:**

- `uv run pytest tests/test_json_output.py -q`

---

### Task 8: --json Flag on All CLI Commands

**Objective:** Add `--json` global option to the Typer CLI. When active, all commands output NDJSON instead of human-readable text.

**Dependencies:** Task 7

**Files:**

- Modify: `src/feather/cli.py`
- Test: `tests/test_json_output.py` (add CLI integration tests)

**Key Decisions / Notes:**

- **Typer callback pattern:** Add `@app.callback()` with `def main(ctx: typer.Context, json_mode: bool = typer.Option(False, "--json", help="Output as NDJSON"))` that stores `json_mode` in `ctx.ensure_object(dict)["json_mode"]`. Each subcommand takes `ctx: typer.Context` and reads `ctx.obj.get("json_mode", False)`. No existing `@app.callback()` in cli.py — confirmed. Do NOT use a global variable (breaks with Typer's eager callback ordering).
- Each command checks `json_mode` and branches output: JSON path uses `output.emit()`, human path keeps existing `typer.echo()` calls
- **JSON output shapes per command:**
  - `feather run --json`: `{"table_name": "...", "status": "success|failure|skipped", "rows_loaded": N, "error_message": "..."}`
  - `feather status --json`: `{"table_name": "...", "last_run_at": "...", "status": "...", "watermark": "...", "rows_loaded": N}` (per AC-FR11.d)
  - `feather history --json`: `{"run_id": "...", "table_name": "...", "started_at": "...", "ended_at": "...", "status": "...", "rows_loaded": N, "error_message": "..."}`
  - `feather validate --json`: `{"valid": true, "tables_count": N, "source_type": "...", "destination": "...", "mode": "..."}`
  - `feather discover --json`: `{"table_name": "...", "columns": [{"name": "...", "type": "..."}]}`
  - `feather setup --json`: `{"state_db": "...", "destination": "...", "schemas_created": true, "transforms_applied": N}`
- When `--json`, suppress all `typer.echo()` — only JSON on stdout
- Adjust exit codes: 0 = success, 1 = validation error, 2 = runtime error

**Definition of Done:**

- [ ] `--json` flag available on all CLI commands
- [ ] `feather status --json` outputs NDJSON per AC-FR11.d
- [ ] `feather run --json` outputs one JSON object per table result
- [ ] `feather history --json` outputs run history as NDJSON
- [ ] `feather validate --json` outputs validation result as JSON
- [ ] No human-readable text mixed into JSON output
- [ ] Default (no `--json`) output unchanged
- [ ] All tests pass

**Verify:**

- `uv run pytest tests/test_json_output.py -q`
- `uv run pytest tests/test_cli.py -q`

---

## Open Questions

None — all decisions resolved during planning.

### Deferred Ideas

- Log rotation for `feather_log.jsonl` — could add `--max-log-size` or integrate with `logrotate`
- SMTP connection validation in `feather validate` — test SMTP connectivity, not just config syntax
- Quarantine schema for rejected/failed rows — better paired with V9 (DQ checks)
