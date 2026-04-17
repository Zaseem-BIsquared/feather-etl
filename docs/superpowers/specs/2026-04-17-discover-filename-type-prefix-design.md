# Discover filename: include source type prefix

**Date:** 2026-04-17
**Issue:** [#21](https://github.com/siraj-samsudeen/feather-etl/issues/21)
**Status:** design approved, pending implementation plan

## Problem

`feather discover` writes one JSON schema per source. The current filenames are:

- `schema_<source_name>.json` for file sources
- `schema_<source_name>_<db_name>.json` for DB sources (via the `_expand_db_sources` mechanism stitching `__<db>` into the child `name`)

When a project has multiple sources of different types, the filenames don't reveal the source type. Users cannot tell at a glance which JSON belongs to a postgres source vs a CSV vs an Excel file. They must open each file or cross-reference `feather.yaml` to navigate.

## Goal

Surface the source type in the discover JSON filename whenever the user explicitly named the source in `feather.yaml`. Leave auto-derived filenames untouched — they already carry the type via the auto-derivation format (`<type>-<basename|host>`).

## Naming rule

The filename is prefixed with `<type>_` **if and only if the user provided an explicit `name:` in `feather.yaml`**. Auto-derived names are left alone.

| yaml | Old | New |
|---|---|---|
| `name: prod`, postgres, `database: sales` | `schema_prod.json` | `schema_postgres_prod.json` |
| `name: prod`, postgres, `databases: [sales, hr]` | `schema_prod__sales.json`, `schema_prod__hr.json` | `schema_postgres_prod__sales.json`, `schema_postgres_prod__hr.json` |
| `name: prod`, postgres, no `database`/`databases` (auto-listed) | `schema_prod__<db>.json` per DB | `schema_postgres_prod__<db>.json` per DB |
| `name: orders`, csv | `schema_orders.json` | `schema_csv_orders.json` |
| No `name:`, csv `path: ./orders.csv` | `schema_csv-orders.csv.json` | unchanged |
| No `name:`, sqlserver `host: localhost` | `schema_sqlserver-localhost.json` | unchanged |

The rule is uniform across all registered source types (`csv`, `duckdb`, `sqlite`, `excel`, `json`, `postgres`, `sqlserver`). There are no per-type special cases.

## Why we need an explicit-name flag

`config.py:337-338` backfills `src.name` with the auto-derived value when a single-source yaml omits `name:`. After that point, `cfg.name` is always truthy — so `if cfg.name:` cannot distinguish user-provided names from backfilled ones.

To keep the rule honest, each `Source` instance carries a boolean `_explicit_name` attribute that records whether the yaml entry contained a `name:` field. The filename helper reads this flag; truthiness of `cfg.name` is no longer a reliable signal.

## Architecture

### Single source of truth

`schema_output_path(cfg: Source) -> Path` in `config.py` is the only place that builds a discover JSON filename. Every caller routes through it. Its current body is replaced.

### Components

- **Source classes' `from_yaml`** — set `self._explicit_name = bool(entry.get("name"))` when constructing the instance. Applies to every source module under `src/feather_etl/sources/`.
- **`config.py` loader** — when it backfills `src.name` for single-source configs, it does NOT touch `_explicit_name` (which stays `False`, as set by `from_yaml`).
- **`_expand_db_sources`** (in `commands/discover.py`) — when building child sources for `databases` expansion, copy the parent's `_explicit_name` onto the child rather than re-inferring it from the synthesized `"name"` string in the entry dict.
- **`schema_output_path`** — reads `getattr(cfg, "_explicit_name", False)` to decide whether to prepend `<type>_`. It does NOT append `_<database>` — DB expansion already embeds the db name into `cfg.name` via `__<db>`.
- **Call sites** — two places construct discover filenames today: `commands/discover.py:_write_schema` (inline f-string) and `discover_state.py:_renamed_schema_path` + `_rename_schema_file` (string replacement). Both are refactored to call `schema_output_path`.

### Data flow

```
feather.yaml → FeatherConfig.load_yaml
                    │
                    ├── Source.from_yaml(entry) sets _explicit_name = bool(entry.get("name"))
                    └── loader backfills cfg.name if single-source + missing; _explicit_name untouched

feather discover → _expand_db_sources(sources)
                    │
                    └── for each DB child: child._explicit_name = parent._explicit_name

_write_schema(source) → schema_output_path(source) → Path
_renamed_schema_path(..., cfg)  → schema_output_path(cfg) → Path
```

## Implementation sketch

```python
# src/feather_etl/config.py
def schema_output_path(cfg: "Source") -> Path:
    """Filename for `feather discover` JSON output.

    If the user explicitly named the source in yaml, prepend the type:
      schema_<type>_<name>.json
    Otherwise keep the auto-derived form (which already carries the type):
      schema_<auto-name>.json
    """
    stem = resolved_source_name(cfg)
    if getattr(cfg, "_explicit_name", False):
        stem = f"{cfg.type}_{stem}"
    return Path(f"schema_{stem}.json")
```

```python
# every src/feather_etl/sources/*.py `from_yaml` classmethod
@classmethod
def from_yaml(cls, entry: dict, config_dir: Path) -> "Self":
    ...
    src = cls(...)
    src._explicit_name = bool(entry.get("name"))
    return src
```

```python
# src/feather_etl/commands/discover.py, inside _expand_db_sources
child = type(src).from_yaml({...}, Path("."))
child._explicit_name = src._explicit_name  # inherit, don't infer
expanded.append(child)
```

```python
# src/feather_etl/commands/discover.py, inside _write_schema
from feather_etl.config import schema_output_path
out = target_dir / schema_output_path(source)
```

## Testing

### Unit tests — `tests/test_discover_io.py`

Update the 5 existing `schema_output_path` assertions at lines 127-179 to match the new rule. Construct sources through the real loader (or manually set `_explicit_name`) so tests exercise the explicitness signal rather than bypassing it.

New cases:

- `test_schema_output_path_explicit_name_prepends_type` — one case per registered type.
- `test_schema_output_path_auto_name_unchanged` — single-source yaml with no `name:` produces the unprefixed filename.
- `test_expand_db_sources_propagates_explicit_flag` — children inherit parent's `_explicit_name` in both directions: explicit parent → explicit children (prefixed filenames); auto parent → auto children (unprefixed). The auto-parent case is the one that catches a dropped inheritance line; without it the happy-path tests still pass.

### CLI integration — `scripts/hands_on_test.sh`

Grep for hard-coded `schema_*.json` assertions and update expected filenames to match the new rule. Adjust any fixture yaml used by the script if needed.

## Migration

**None.** The typed-filename feature has not shipped yet. Pre-release testers are told once, in the implementation plan's rollout note: delete any existing `schema_*.json` and `feather_discover_state.json` before the next discover run after this change lands. No auto-rename, no side-by-side output, no flag.

## Edge cases

- **`_explicit_name` missing on older in-memory instances** — `schema_output_path` uses `getattr(cfg, "_explicit_name", False)` so missing attribute = auto-derived behavior, never crashes.
- **Child source with no parent flag** — can't happen: `_expand_db_sources` always sets the flag on children it builds.
- **User picks a name that looks auto-derived** (e.g. `name: postgres-localhost`) — still gets the prefix. The rule is "did yaml have `name:`?", not "does the string look auto-format." Matches user expectation.
- **Duplicate-name detection** at `config.py:339-342` — still uses `src.name`, unaffected.
- **Rename inference** in `discover_state.py` — routes through `schema_output_path`, so renaming a source in yaml produces the correct new-format filename regardless of whether the user flipped explicit-on-auto or the other way around.

## What we are NOT doing

- No `--typed-names` flag. Unconditional.
- No side-by-side writing of old + new filenames.
- No auto-migration of existing files or state entries.
- No change to auto-derivation format (`<type>-<basename|host>`).
- No change to `_expand_db_sources` child-naming (`<parent_name>__<db>`).
- No deprecation of `schema_output_path` — its body is replaced in place; signature stays `(cfg: "Source") -> Path`.
- No changes to commands other than `discover`.
