# Current State — Multi-Source Discover (Issue #8)

**As of commit:** `0a4c436` on `phase-2-yaml-schema-flip` (post-rebase onto upstream/main at `89ff463` — issue #17)
**Suite state:** 535 tests passing, 14 skipped, 0 failed. `bash scripts/hands_on_test.sh` 61/61.
**Branch:** `phase-2-yaml-schema-flip` — Phase 2 work done on a feature branch, rebased onto upstream/main (which now includes issue #17's `feather view` + auto-open viewer). NOT yet pushed and NOT yet merged to `main`. Awaiting owner direction on `ruff format .` + push + PR.
**Safety backup:** branch `phase-2-backup-pre-rebase` holds the pre-rebase state at `79dc954` (9 Phase 2 commits on top of `d2d15eb`). Keep it until Phase 3 is fully verified.

---

## TL;DR for the teammate picking this up

Phases 1 AND 2 of the multi-source discover plan are **complete and green**. Phase 1 made every source self-describe via `from_yaml`. Phase 2 flipped the YAML schema from singular `source: {...}` to plural `sources: [...]` everywhere (config parser, fixtures, pipeline, all commands, init wizard, hands_on_test.sh, README, prd, CONTRIBUTING).

Phase 3 (`discover` iterates over sources + auto-enumerates DB sources) is **not started**. The very next task would be Task 3.1 — see "How to resume" below.

**Pending close-out before Phase 3 starts:** the `phase-2-yaml-schema-flip` branch needs `ruff format .` as a separate style commit, then push + PR creation. Owner explicitly said "don't push, I'll tell you what to do" — this is the open hand-off point.

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
- `config.py:_validate()` does NOT do any source-structural validation. It only checks destination + defaults + table rules. Path/connection existence is runtime-checked by `source.check()`.
- Registry imports are lazy — `pyodbc` / `psycopg2` stay unloaded until a sqlserver/postgres source is instantiated.

---

## What's done (Phase 2 — commits `3300a33` through `21025c3`, + rebase cleanup `0a4c436`)

Phase 2 goal: flip the YAML schema from singular `source: {...}` to plural `sources: [...]` across the entire codebase, with a migration error for old configs and a multi-source guard for non-discover commands. **8 commits on the rebased branch + 1 post-rebase cleanup commit, fully green.**

> **SHAs changed after rebase.** Phase 2 was rebased onto upstream/main on 2026-04-15 to pick up issue #17 (`89ff463` — auto-open schema viewer + `feather view` command). All 8 Phase 2 commits were replayed with new SHAs; the pre-rebase SHAs (`bcadfda..79dc954`) live only on the `phase-2-backup-pre-rebase` safety branch. The table below shows post-rebase SHAs.

| # | Commit | Task | What changed |
|---|--------|------|--------------|
| 1 | `3300a33` | 2.1 | `config.py` parses `sources:` list; hard `ValueError` on singular `source:` with migration hint. `FeatherConfig.sources: list[Source]` replaces `source`. New `TestSourcesList` (5 tests) + `TestSingularSourceMigrationError` (1 test) in `tests/test_config.py`. |
| 2 | `866a7e2` | 2.1 fix | Friendly `ValueError` when a `sources[]` entry is not a mapping (catches `sources: [null]` / `sources: ["str"]`). Regression test `test_sources_entry_must_be_mapping`. |
| 3 | `3d8185d` | 2.2+2.3+2.4 | **Bundled** mechanical migration: every inline test fixture flipped `"source": {...}` → `"sources": [{...}]`; every `cfg.source.X` → `cfg.sources[0].X`; `pipeline.py` reads `config.sources[0]`; new helper `_enforce_single_source(cfg, command_name)` in `commands/_common.py` invoked by `run/validate/status/history/setup` (exit code 2 with migration guidance). New `tests/commands/test_multi_source_guard.py` with 5 tests. `discover.py` got a minimal 2-line `cfg.source` → `cfg.sources[0]` fix (necessary deviation from prompt — discover tests would have crashed otherwise). |
| 4 | `c849141` | 2.2 fix | Restore meaningful coverage in `test_source_name_is_optional` — the mechanical rewrite had degraded it to a tautology (`assert sources[0] is not None`). Now hardcodes `assert sources[0].name == "duckdb-source"` to actually verify auto-derivation. |
| 5 | `5a4967c` | polish | Address 3 code-review nits on the multi-source guard (clearer error text, consistent wording across 5 tests). |
| 6 | `4a663d4` | 2.5 | `init_wizard.py` template emits `sources:` list. New `TestInitTemplateUsesSourcesList` (2 tests) verifies scaffold YAML loads cleanly. |
| 7 | `b956ec9` | 2.6 | Sync `README.md` (1 SQL Server example), `docs/prd.md` (4 examples), `docs/CONTRIBUTING.md` (new `## Testing co-location` section). 20 YAML blocks in `scripts/hands_on_test.sh` migrated. |
| 8 | `21025c3` | 2.6 fix | `prd.md` source-alternatives block had been rewritten as 3 list entries with `# OR` comments — valid YAML but **misleading** (would fail Task 2.1's name-required rule). Replaced with single active entry + commented-out complete `sources:` blocks for each alternative. Caught by reading the actual diff after the implementer flagged the section as a "judgment call." |
| 9 | `0a4c436` | rebase cleanup | **Post-rebase on #17.** Migrated #17's new discover test (`test_invokes_shared_viewer_runtime_after_writing_json`) from inline singular `source:` to `sources:` list — git rebase was clean but the test was a **semantic landmine** only visible at test time. Added "Post-#17 Compatibility Baseline" section to the plan doc enumerating 6 behavior contracts Phase 3 must preserve. |

**Post-Phase-2 architecture invariants:**

- `FeatherConfig.sources: list[Source]` — always a list, always non-empty (parser enforces).
- Singular `source:` in YAML is a **hard error** with a migration hint pointing at the new shape.
- `_enforce_single_source(cfg, command_name)` in `commands/_common.py` is the single chokepoint for non-discover commands. Calling it after config load + before any work is the contract every non-discover command follows.
- `discover.py` still reads `cfg.sources[0]` (single-source). Phase 3 rewrites it to loop.
- `init_wizard.py` scaffolds `sources:` list — one source by default.

**Post-rebase invariants (from issue #17):**

- `discover.py` calls `serve_and_open(viewer_target_dir, preferred_port=8000)` as its last side-effect. `serve_and_open` is imported at **module level** (not inside the function) so tests can `monkeypatch.setattr(discover_cmd, "serve_and_open", ...)`. Phase 3 must preserve both the call and the module-level import.
- `feather view` command exists in `src/feather_etl/commands/view.py` with `--port 1-65535` (default 8000) and a PATH argument. Phase 3 does NOT touch `view`.
- Viewer runtime lives in `src/feather_etl/viewer_server.py` with port-fallback logic. Phase 3 must not reach into this file.
- Full Phase 3 compatibility contract lives in the **Post-#17 Compatibility Baseline** section at the bottom of `docs/superpowers/plans/2026-04-14-multi-source-discover.md` — read it before starting Task 3.1.

---

## What's left — the roadmap

The plan is split into 5 phases. Phases 1 and 2 are DONE. Phases 3–5 are still pending. Each **phase** ends with a green suite; tasks within a phase may be intentionally broken and only re-greened at phase close.

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

**Model routing I used (across Phase 1 + Phase 2):**

- **Sonnet** for multi-file integration work: Tasks 1.1, 1.2, 1.4, 1.6, 1.7+1.8, and Phase 2 Task 2.1 + bundled 2.2+2.3+2.4 + Task 2.6 docs sync. Also for the final whole-branch review.
- **Haiku** for mechanical / mirror-of-predecessor tasks: 1.3, 1.5, small fix rounds, polish nits, init wizard template.
- Spec review: **haiku** usually suffices; bump to **sonnet** when the change touches plan-sensitive areas (e.g. 1.7+1.8 plan-violation concern).

### Option B: Inline execution (fresh session)

Use `superpowers:executing-plans` — the whole plan is written with complete code snippets so you can execute tasks inline.

---

## Lesson from Phase 2 (read this before Phase 3)

When dispatching mechanical-migration subagents, **read the actual diff** on any block the implementer flags as a "judgment call" in self-review. Two real semantic regressions slipped past spec review this phase and were only caught by reading the diff:

1. `test_source_name_is_optional` got rewritten to `assert sources[0] is not None` — vacuously true (the line above would have raised). Lost coverage of auto-derivation.
2. `prd.md` source-alternatives block got rewritten as 3 list entries with `# OR (choose one)` — valid YAML meaning the wrong thing (would fail the very rule Task 2.1 introduced).

Both passed spec compliance review (the spec only said "use sources: list"). Both were caught at the diff-reading step. Build the habit: `git show <sha> -- <file>` on any "judgment call" file the implementer mentions.

---

## Verification commands

Before starting any work, confirm the baseline:

```bash
cd /Users/jaseem/Desktop/NonDropBoxProjects/feather-etl  # path differs across machines
git log --oneline -1            # expect: 0a4c436 on phase-2-yaml-schema-flip
uv run pytest -q                 # expect: 535 passed, 14 skipped, 0 failed
bash scripts/hands_on_test.sh   # expect: 61/61
uv run feather discover --help   # must mention: "schema JSON" + "serve/open the schema viewer"
uv run feather view --help       # must show: --port 1-65535, default 8000
```

After each phase closes, those commands must still be green. Between phases is fine for intermediate task commits to be broken — just don't leave them broken in a pushed state.

---

## Review findings still open (not blocking, logged for Phase 6 close-out)

**From Phase 1 code review** (still open):

- **I-2 (1.7+1.8):** `validate.py` source label uses informal attribute reads (`getattr(cfg.source, "path", None)`, etc.). Consider adding a `Source.label()` method when Phase 3 multiplies the source count.
- **I-3 (1.7+1.8):** Informal Protocol attribute coupling (`path`, `host`, `database`, `_last_error`). Promote these to documented optional Protocol members before Phase 3 starts reading them heavily.
- **M-2 (1.7+1.8):** `resolved_source_name` still has `if cfg.type == "csv"` branching. Should become a per-class method (`basename_for_discover()` or similar) when Phase 3 revisits discover output naming.
- **M-1 (1.7+1.8):** `get_source_class` could benefit from `functools.lru_cache` to avoid re-importing on repeat lookups. Tiny perf win; do when touched.

**From Phase 2 final whole-branch code review** (3 deferred nits, all flagged for Phase 6):

- **Nit 1:** Stale `resolved_paths["source"]` JSON key in `discover.py` schema output — still uses singular noun even though the config is now plural. Phase 3 rewrites discover output anyway, so defer.
- **Nit 2:** `test_multi_source_guard.py` couples on stderr substrings (`"single-source" in r.output`). Fragile if the error message ever gets reworded — consider asserting on the exit code alone, or extracting the message into a module constant.
- **Nit 3:** The new `## Testing co-location` section in `CONTRIBUTING.md` includes an exception clause whose example path doesn't match an actual file in the repo. Update or remove the example before final PR.

None of these block Phase 3.

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

Work resumed on another machine: `git fetch && git checkout phase-2-yaml-schema-flip` (the branch is **not yet pushed** as of `0a4c436` — if the branch isn't on the remote, the work is still local on the previous machine). There is also a safety branch `phase-2-backup-pre-rebase` pointing at the pre-rebase tip `79dc954` — keep it around until Phase 3 is verified, delete when no longer needed. Then read this file top-to-bottom and jump to "How to resume."
