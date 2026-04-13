# Current State — Multi-Source Discover (Issue #8)

**As of commit:** `7b0bd57` on `main`
**Suite state:** 504 tests passing, 14 skipped, 0 failed. `bash scripts/hands_on_test.sh` 61/61.
**Branch:** `main` (all work done directly on main with explicit owner consent).

---

## TL;DR for the teammate picking this up

Phase 1 of the multi-source discover plan is **complete and green**. The `Source` Protocol, every source class, the registry, and `config.py` have all been refactored so each source self-describes via `from_yaml`. Config parsing is delegated; `SourceConfig` is deleted; the registry is lazy.

Phase 2 (YAML schema flip from `source:` → `sources:` list) is **not started**. The very next task would be Task 2.1, which is a large breaking change — see "How to resume" below.

---

## Design docs (read in this order)

1. **Spec:** [docs/superpowers/specs/2026-04-14-multi-source-discover-design.md](superpowers/specs/2026-04-14-multi-source-discover-design.md) — the approved design.
2. **Plan:** [docs/superpowers/plans/2026-04-14-multi-source-discover.md](superpowers/plans/2026-04-14-multi-source-discover.md) — the 5-phase, ~30-task execution plan. This is your work list.
3. **Issue on GitHub:** [#8](https://github.com/siraj-samsudeen/feather-etl/issues/8).

---

## What's done (Phase 1 — commits `c991df1` through `7b0bd57`)

Phase 1 goal: every `Source` subclass self-describes via `from_yaml(entry, config_dir)`, owns its own identifier rules via `validate_source_table`, and exposes `type: ClassVar[str]`. `config.py` becomes a thin YAML dispatcher that delegates to each source.

| # | Commit | Task | What changed |
|---|--------|------|--------------|
| 1 | `c991df1` | 1.1 | `Source` Protocol extended with `from_yaml`, `validate_source_table`, `name: str`, `type: ClassVar[str]`. `TestSourceDataclasses` rename in `tests/test_sources.py` to free the `TestSourceProtocol` name. |
| 2 | `0d6701a` | 1.2 | `SqlServerSource.from_yaml`, keyword-only `__init__`, `databases: list[str] \| None` param, `validate_source_table` (lenient). `_SQLSERVER_CONN_TEMPLATE` module constant. |
| 3 | `f033588` | 1.3 | `SqlServerSource.list_databases()` queries `sys.databases` excluding system DBs. |
| 4 | `af1a66b` | 1.3 fix | Strengthen `NOT IN` assertion in list_databases test + document `pyodbc.Error` contract. |
| 5 | `a0a004b` | 1.4 | `PostgresSource.from_yaml` — structural mirror of 1.2 (default port 5432, `host=... dbname=...` template). |
| 6 | `f052859` | 1.4 fix | Add missing `test_explicit_connection_string_overrides` + `validate_source_table` comment. |
| 7 | `7a278b4` | 1.5 | `PostgresSource.list_databases()` queries `pg_database` excluding templates + `postgres`. |
| 8 | `3c78120` | 1.5 fix | Add `test_propagates_psycopg2_error` + filter-direction asserts (`NOT IN`, `= false`). |
| 9 | `b5771f6` | 1.6 | All 5 file sources (csv, sqlite, duckdb, excel, json) get `type`, `from_yaml`, `validate_source_table`. Module-level helpers (`_SQL_IDENTIFIER_RE`, `_resolve_file_path`, `_reject_db_fields`) in `file_source.py`. **Task 1.1's `test_each_source_class_declares_type_attr` flips green here.** |
| 10 | `7d06e9b` | 1.6 fix | Clearer SQLite dotted-name error ("unqualified: use just '<table>'") + parametrized reject-db-fields test across all 5 file sources + helper docstring. |
| 11 | `cf7f7c4` | 1.7 | `registry.py` becomes lazy `type → dotted-path` map with `get_source_class()`. `create_source()` and `SOURCE_REGISTRY` removed. Closes issue #4 (lazy connector imports). |
| 12 | `c2bd17e` | 1.8 | `config.py` thins out. `FILE_SOURCE_TYPES`, `DB_CONNECTION_BUILDERS`, `SourceConfig` all deleted. `load_config` calls `get_source_class(type).from_yaml(...)`. Callers in `pipeline.py`, `commands/discover.py`, `commands/validate.py` read `cfg.source` directly. `_validate` delegates per-table `source_table` validation to the source class. |
| 13 | `7b0bd57` | 1.8 fix | Remove load-time `path.exists()` check from `_validate` (plan-violation fix). `test_missing_source_path_for_file_source` now asserts `cfg.source.check() is False` instead of load-time error — matches spec §5.2 (side-effect-free `from_yaml`). |

**Post-Phase-1 architecture invariants:**

- `Source` instances self-describe via `type: ClassVar[str]`.
- `FeatherConfig.source` is a live `Source` instance (still singular — Phase 2 flips to `sources: list[Source]`).
- `config.py:_validate()` does NOT do any source-structural validation. It only checks destination + defaults + table rules. Path/connection existence is runtime-checked by `source.check()`.
- Registry imports are lazy — `pyodbc` / `psycopg2` stay unloaded until a sqlserver/postgres source is instantiated.

---

## What's left — the roadmap

The plan is split into 5 phases. Phases 2–5 are all still pending. Each **phase** ends with a green suite; tasks within a phase may be intentionally broken and only re-greened at phase close.

### Phase 2 — YAML schema flip (`source:` → `sources:` list) — NOT STARTED

This is the next phase. It's the "expensive migration" (every test fixture, every doc). **Starting Phase 2 immediately breaks the suite until Task 2.2 migrates all inline test configs.** Plan has Tasks 2.1 → 2.6 designed as a tight unit; bundle them if you want.

- **2.1** — `config.py` parses `sources:` list; hard error on singular `source:`. Adds `TestSourcesList` (5 tests) and `TestSingularSourceMigrationError` (1 test) to `tests/test_config.py`.
- **2.2** — Mechanical migration of inline test configs across ~15 test files (every `"source": {...}` → `"sources": [{...}]`). Also update any assertion that reads `cfg.source.X` → `cfg.sources[0].X`. Run `grep -rn "cfg\.source\.\|config\.source\." tests/` to find them all.
- **2.3** — `pipeline.py` reads `cfg.sources[0]`.
- **2.4** — Non-discover commands (`run`, `validate`, `status`, `history`, `setup`) gain a multi-source guard: `if len(cfg.sources) > 1: exit(2)` with migration guidance. Test file: `tests/commands/test_multi_source_guard.py`.
- **2.5** — `init_wizard.py` template emits `sources:` list.
- **2.6** — Sync `README.md`, `docs/prd.md`, `docs/CONTRIBUTING.md` (the last adds the testing co-location principle as a project convention). Then a single large commit wrapping Phase 2.

⚠️ **A partial Task 2.1 dispatch was aborted mid-flight** (the subagent edited `config.py` and `tests/test_config.py` before being rejected). Those edits were reverted back to `7b0bd57`; the tree is clean. Do NOT look for Task 2.1 work in uncommitted files — it doesn't exist. Start fresh from the plan.

### Phase 3 — `discover` iterates + auto-enumerate — NOT STARTED

- **3.1** — `multi_source_yaml()` test helper in `tests/commands/conftest.py`.
- **3.2** — Rewrite `commands/discover.py` to loop over `cfg.sources`, write one `schema_<name>.json` per source. New file `tests/commands/test_discover_multi_source.py` with first 2 E2E tests.
- **3.3** — Auto-enumerate DB sources: when a sqlserver/postgres source has neither `database:` nor `databases:`, call `source.list_databases()` and produce child sources named `<parent>__<db>`. Uses `pg_ctl` fixture for integration tests.

### Phase 4 — State file + flags — NOT STARTED

- **4.1** — New module `src/feather_etl/discover_state.py` with `DiscoverState` class (load/save `feather_discover_state.json`, record ok/failed/removed/orphaned, `classify()` function). New `tests/test_discover_state.py`.
- **4.2** — Wire state into `discover.py`: cached = skip, failed = retry by default.
- **4.3** — Flags `--refresh`, `--retry-failed`, `--prune`.
- **4.4** — Permission-error path (E1): empty `list_databases()` → failed entry with remediation hint naming `VIEW ANY DATABASE` grant.

### Phase 5 — Rename detection — NOT STARTED

- **5.1** — Fingerprint computation + `detect_renames()` + `apply_renames()` in `discover_state.py`. Unit tests in `tests/test_discover_state.py`.
- **5.2** — Rename UX wired into `discover.py`: TTY prompt `[Y/n]`, non-TTY exit 3, `--yes` / `--no-renames` flags. Ambiguous fingerprint → error exit 2.

### Phase 6 — Final review + PR — NOT STARTED

- `ruff format .` (commit formatting separately per project convention).
- `ruff check .`.
- `gh pr create` — title "Multi-source discover (issue #8)", body per plan's Phase 6 template.

---

## How to resume

### Option A: Continue with subagent-driven execution (what I was doing)

Use the `superpowers:subagent-driven-development` skill. For each task:

1. Dispatch an implementer subagent with the FULL text of the task from the plan. Do not ask the subagent to read the plan file — paste the task body.
2. After implementer reports DONE, dispatch a spec-compliance reviewer (pass the commit SHA).
3. If spec-compliant, dispatch a `superpowers:code-reviewer` code quality reviewer.
4. If the reviewer flags Important issues, dispatch a fix subagent.
5. Mark the TodoWrite entry complete; repeat for the next task.

**Model routing I used:**
- **Sonnet** for Tasks 1.1, 1.2, 1.4, 1.6, and 1.7+1.8 (multi-file, integration work).
- **Haiku** for Tasks 1.3, 1.5 and small fix rounds (mechanical mirror-of-predecessor tasks).
- Spec review: **haiku** usually suffices; **sonnet** for the 1.7+1.8 close-out because of the plan-violation concern.

### Option B: Inline execution (fresh session)

Use `superpowers:executing-plans` — the whole plan is written with complete code snippets so you can execute tasks inline.

### Option C: Let a subagent do Phase 2 as one unit

Phase 2's tasks are tightly coupled (every intermediate commit between 2.1 and 2.2 is an import-broken state). Dispatch one subagent with the full Phase 2 text (tasks 2.1 through 2.6), let it commit task-by-task but run the suite only at the end of Phase 2. Review the whole phase as a unit.

---

## Verification commands

Before starting any work, confirm the baseline:

```bash
cd /Users/siraj/Desktop/NonDropBoxProjects/feather-etl
git log --oneline -1            # expect: 7b0bd57
uv run pytest -q                 # expect: 504 passed, 14 skipped, 0 failed
bash scripts/hands_on_test.sh   # expect: 61/61
```

After each phase closes, those commands must still be green. Between phases is fine for intermediate task commits (2.1 through 2.5) to be broken — just don't leave them broken in a pushed state.

---

## Review findings still open (not blocking, logged for Phase 2+)

From the code reviewer's Phase 1 close-out:

- **I-2 (1.7+1.8):** `validate.py` source label uses informal attribute reads (`getattr(cfg.source, "path", None)`, etc.). Consider adding a `Source.label()` method when Phase 2 multiplies the source count.
- **I-3 (1.7+1.8):** Informal Protocol attribute coupling (`path`, `host`, `database`, `_last_error`). Promote these to documented optional Protocol members before Phase 3 starts reading them heavily.
- **M-2 (1.7+1.8):** `resolved_source_name` still has `if cfg.type == "csv"` branching. Should become a per-class method (`basename_for_discover()` or similar) when Phase 3 revisits discover output naming.
- **M-1 (1.7+1.8):** `get_source_class` could benefit from `functools.lru_cache` to avoid re-importing on repeat lookups. Tiny perf win; do when touched.

None of these block progress.

---

## Owner preferences (important for teammate)

- **Small, reviewable chunks.** Each commit should change one logical thing; don't batch.
- **Plan docs before coding** — if Phase 2 uncovers something the plan didn't anticipate, write the adjustment to the plan doc first, commit it, then implement.
- **Challenge and push back** rather than blindly executing. If a task in the plan feels wrong, say so before doing it.
- **One question at a time** when clarifying scope with the owner.
- **`uv` is the package manager** — always `uv run pytest`, never bare `pytest`.
- **Format before push:** run `ruff format .` across the whole repo and commit as a separate style commit before opening a PR (per the auto-memory `feedback_format_all_before_push`).

---

## Contact

Work resumed on another machine: pull `main` and check `git log` for the latest commit. Then read this file top-to-bottom and jump to "How to resume."
