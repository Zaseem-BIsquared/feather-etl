# `feather discover` — auto-save JSON by default (design)

- **Issue:** [#16](https://github.com/siraj-samsudeen/feather-etl/issues/16)
- **Date:** 2026-04-13
- **Status:** Design approved, ready for implementation plan
- **Touched files:** `src/feather_etl/config.py`, `src/feather_etl/cli.py`, `tests/`, `scripts/hands_on_test.sh`

## Motivation

Today, `feather discover` prints tables and columns to stdout. For databases with hundreds of tables this is unusable as a quick overview, and piping `--json` to a file loses the connection identity (multiple dumps collide or overwrite). The workflow we're enabling is: run `discover`, open the resulting file in an HTML schema viewer. The CLI should produce a predictable, self-describing artifact without shell redirection.

## User-facing behavior

```
$ feather discover
Wrote 29 table(s) to ./schema_sqlserver-192.168.2.62_ZAKYA.json
```

One command, one action, one line of output. The filename identifies the source connection. No flags, no modes, no alternative outputs.

## Config schema change

Add an optional `name` field to `source` in `feather.yaml`:

```yaml
source:
  type: sqlserver
  name: prod-erp          # optional; auto-derived from type+host/path if absent
  host: ${SQLSERVER_HOST}
  database: ${SQLSERVER_DATABASE}
```

`source.name` is **not** written back to `feather.yaml` by `discover` — it is computed fresh each invocation. Persisting the auto-derived name (so the user can see it and edit it) is valuable, but belongs to a separate command like `feather validate --fix` or a dedicated config handler, not to `discover`. See Follow-ups below.

### Auto-derivation recipe

| Source type | Derived name |
|---|---|
| `sqlserver`, `postgres` | `<type>-<host>` |
| `csv` | `csv-<dirname>` (basename of source directory) |
| `sqlite`, `duckdb_file`, `excel`, `json` | `<type>-<basename-without-ext>` |

### Filename format

- DB sources: `./schema_<name>_<database>.json`
- File sources: `./schema_<name>.json`

### Sanitization

Every segment (`name`, `host`, `database`) is sanitized via the same rule: characters outside `[A-Za-z0-9._-]` are replaced with `_`. Applies uniformly to user-supplied and auto-derived values — typos or copy-pastes (e.g. `prod/erp`) are silently cleaned. Dots are preserved so IPs remain readable.

## Implementation sketch

### `src/feather_etl/config.py`

- Add `name: str | None = None` to `SourceConfig`.
- Add helper `resolved_source_name(cfg: SourceConfig) -> str` — returns sanitized `cfg.name` if set, otherwise computes from the recipe table.
- Add helper `schema_output_path(cfg: SourceConfig) -> Path` — builds `./schema_<name>[_<database>].json`, sanitizing the database segment.

### `src/feather_etl/cli.py`

Rewrite `discover()` ([lines 115-144](../../../src/feather_etl/cli.py#L115-L144)):

- Remove the `_is_json(ctx)` branch and the per-table stdout listing.
- Build JSON payload `[{"table_name": str, "columns": [{"name": str, "type": str}, ...]}, ...]`.
- Write to `schema_output_path(cfg.source)` with `json.dumps(..., indent=2)`.
- Print exactly one line: `Wrote <N> table(s) to <path>`.

Silent overwrite on re-run — same source produces same filename; no `--force` check, no prompt.

### Tests — `tests/`

All coverage lives in pytest. New file `test_discover.py`, subprocess-based (invokes the CLI as a real process, parses the written file):

- Per source type (sqlserver, postgres, csv, sqlite, duckdb_file, excel, json): auto-derived name, file exists at predicted path, JSON parses with expected shape.
- User override via `source.name` wins over auto-derivation.
- User-supplied `source.name` with unsafe chars is silently sanitized in the filename.
- Silent overwrite on second run: second invocation replaces first file without error.
- Zero-table source: writes `[]`, prints `Wrote 0 table(s) to ...`.

Extend `test_config.py`: `source.name` field is accepted as optional.

### `scripts/hands_on_test.sh` — DELETE-ONLY

Per project policy, `hands_on_test.sh` is deprecated — do not add new checks. Remove entries that relate to the current discover behavior:

- S4 assertions (lines 218-227): grep "Found 6 table", "icube.SALESINVOICE", "ModifiedDate".
- S15 assertion (lines 633-636): grep "orders.csv".
- S17 assertion (lines 701-704): grep "orders".

Do not add replacements. Coverage moves entirely to `test_discover.py`.

## Edge cases

- **Unsafe chars in host/database/name.** Sanitized silently.
- **Host with port** (`192.168.2.62:1433`). `:` replaced with `_` → `192.168.2.62_1433`.
- **Zero tables discovered.** File still written (content `[]`), normal message printed.
- **Two databases on same host.** Filename includes database suffix, so they coexist.
- **CSV source with trailing slash in path.** Normalized via `Path(...).resolve().name`.
- **Absolute vs relative paths in file sources.** Both work; derivation uses the basename only.
- **CWD not writable.** Raises `PermissionError` naming the target path. No fallback directory.

## Non-goals

Decisions already locked during design — do not re-propose during review or planning:

- No `--out PATH` flag.
- No `--print` / `--stdout` / `--json` stdout override.
- No `--force` flag; overwrite is always silent.
- No timestamp suffixes or history retention.
- No non-JSON output formats (YAML, CSV, HTML).
- No prompt before overwrite.
- Building the HTML schema viewer is a separate effort, not part of this change.
- Full removal of `hands_on_test.sh` is out of scope — only the three discover entries are removed.

## Follow-ups (separate issues, not this spec)

- **Write auto-derived `source.name` back to `feather.yaml`.** Valuable for discoverability — user sees what the name resolved to and can edit it. Belongs in `feather validate --fix` or a dedicated config handler, not in `discover`, because (a) `discover` should stay a pure read operation, (b) config mutation wants its own dry-run / confirm / backup semantics, and (c) it benefits every command that reads `source.name`, not just `discover`. File a separate issue.
- **HTML schema viewer** that reads the JSON file. Downstream consumer of this work.
- **Full removal of `hands_on_test.sh`.** Gradual migration as commands are touched; separate sweep when remaining entries are small.

## Rationale notes

- **`source.name` as a separate field, always present.** File sources have no `host`; DB sources may want a business label (`prod-erp`) rather than an IP. One unified field covers every source type with zero per-type config surface.
- **Compute-on-read, don't persist.** Auto-deriving the name fresh each run avoids a stale-override footgun when `host` changes.
- **Silent sanitization over validation.** User typos and copy-pastes are common; rejecting a run because a colon snuck into a name is hostile. Dots are preserved so the output remains recognizable.
- **Deprecate `hands_on_test.sh` entries as we touch them.** Shell-grep tests of stdout are dead weight once the CLI contract changes; subprocess-based pytest tests with structured assertions replace them cleanly.
- **Pre-release means minimal surface.** No backward-compat flags, no `--json` stdout mode — this command has no real-world callers yet, so we're designing the cleanest default and can reintroduce flags later if a concrete user need emerges.
