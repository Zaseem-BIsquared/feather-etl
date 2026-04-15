# Discover Auto-Open + `view` Command — design

**Issue:** [#17 feather discover --open + feather view: one-command schema browser](https://github.com/siraj-samsudeen/feather-etl/issues/17)
**Status:** Design approved, ready for implementation planning
**Date:** 2026-04-14

---

## 1. Problem

Current schema viewing requires multiple manual steps: generate JSON, copy viewer HTML, start a server, and open a browser. This causes repeated friction and breaks workflow continuity.

Issue #17 goal: make schema browsing a first-class CLI flow while preserving the ability to manually host files if users want to.

---

## 2. Scope

### In scope

1. `feather discover` writes schema JSON and then always serves + opens schema viewer.
2. Add standalone `feather view [PATH]` command for serving an existing folder without re-discovery.
3. Package `schema_viewer.html` as an installable resource.
4. Share viewer-serving logic between `discover` and `view`.
5. Update tests and README accordingly.

### Out of scope

1. Daemon/background process management (`--stop`, PID files, detached servers).
2. Host binding customization (`--host` flag).
3. Browser-disable flag for `discover`.
4. Multi-source integration concerns from issue #8 (handled separately in that branch/plan).

---

## 3. Final Decisions

| Area | Decision |
|---|---|
| Overall scope | Full issue #17 in one pass: `discover` integration + new `view` command |
| `discover` behavior | Default behavior is always: discover -> serve -> open browser (no disable flag) |
| Server lifecycle | Blocking; command stays active until `Ctrl+C` |
| Bind address | `127.0.0.1` only |
| Host flag | Not added |
| Default port strategy | Try `8000`; if occupied, fallback to free ephemeral port |
| `view --port` behavior | Try requested port first; if occupied, fallback to free ephemeral port |
| URL output | Print URL exactly once always |
| Browser launch failure output | Print one hint line: browser launch failed, open URL above manually (without repeating URL) |
| Viewer file sync policy | For both commands: create if missing; compare content; update only when content differs |
| Viewer update messaging | Print update message only when replacing an outdated/different local viewer file |
| Reuse strategy | Shared internal module used by both commands |
| CLI structure tests | Add `view` coverage to `tests/test_cli_structure.py` |

---

## 4. CLI UX Contract

## 4.1 `feather discover`

1. Load/validate config.
2. Discover tables and write schema JSON output.
3. Ensure viewer HTML is synced in serving folder.
4. Start local HTTP server on `127.0.0.1`.
5. Print the serving URL once.
6. Try to open browser.
7. If browser launch fails, print one non-duplicative manual-open hint.
8. Block until `Ctrl+C`.

This intentionally changes current command ergonomics: `discover` becomes an interactive viewer-first command.

## 4.2 `feather view [PATH] [--port <int>]`

1. Resolve target folder (default `.` when PATH omitted).
2. Validate folder exists.
3. Ensure viewer HTML is synced.
4. Start server + open browser using same shared logic and output style as `discover`.
5. Block until `Ctrl+C`.

---

## 5. Architecture

## 5.1 New package resource

1. Add `src/feather_etl/resources/schema_viewer.html`.
2. Add `src/feather_etl/resources/__init__.py`.
3. Load resource with `importlib.resources`.
4. Include resources in wheel build config.

## 5.2 New internal module

Create `src/feather_etl/viewer_server.py` as the single owner of viewer runtime behavior.

Suggested responsibilities:

1. `sync_viewer_html(target_dir: Path) -> SyncResult`
   - Ensure local `schema_viewer.html` exists and matches packaged content.
   - Return status (`created`, `updated`, `unchanged`) for user messaging.

2. `pick_port(preferred: int = 8000) -> int`
   - Try preferred port first.
   - Fallback to free port if unavailable.

3. `serve_and_open(target_dir: Path, preferred_port: int = 8000) -> None`
   - Bind `127.0.0.1`.
   - Start `http.server` with `SimpleHTTPRequestHandler(directory=...)`.
   - Print URL once.
   - Attempt browser launch.
   - Print failure hint only when launch fails.
   - Block with clean `Ctrl+C` shutdown.

## 5.3 Command integration

1. Update `src/feather_etl/commands/discover.py` to call shared viewer module after writing schema JSON.
2. Add new `src/feather_etl/commands/view.py` command module with `register(app)`.
3. Register `view` in `src/feather_etl/cli.py`.

---

## 6. Data Flow

## 6.1 `discover` path

1. Discover command runs and writes schema output file(s).
2. Target serving folder determined from output location.
3. Viewer sync runs:
   - missing file -> copy
   - different content -> overwrite + emit update message
   - identical -> no rewrite, no update message
4. Port selection:
   - try `8000`
   - fallback to free port on conflict
5. URL emitted once.
6. Browser open attempted.
7. Hint emitted only on launch failure.
8. Process serves until interrupted.

## 6.2 `view` path

1. Validate path.
2. Run same viewer sync behavior.
3. Port selection:
   - if `--port` provided, try it first, then fallback to free port
   - if omitted, use default preferred `8000`, then fallback
4. Same serve/open/message lifecycle as discover.

---

## 7. Error Handling

1. Invalid view path: clear validation error + non-zero exit.
2. Resource load failure: clear packaged-resource error + non-zero exit.
3. Server bind failure on preferred port: fallback to free port.
4. Browser launch failure: server continues; one manual-open hint shown.
5. Ctrl+C shutdown: graceful exit without noisy traceback.

---

## 8. Testing Strategy

## 8.1 New tests

1. `tests/test_viewer_server.py`
   - viewer sync create/update/unchanged behavior
   - preferred-port then fallback behavior
   - URL-printing contract
   - browser-launch failure hint behavior

2. `tests/commands/test_view.py`
   - `view` default directory
   - `view <PATH>` behavior
   - `view --port` tries preferred then falls back
   - invalid path failure

## 8.2 Existing tests to update

1. `tests/commands/test_discover.py`
   - discover now includes serving/open flow
   - expected output includes URL and serving lifecycle messaging

2. `tests/test_cli_structure.py`
   - expected command registration includes `view`
   - module export/register check includes `commands.view`

## 8.3 Behavior assertions to keep explicit

1. URL line appears exactly once.
2. Browser failure message does not repeat URL.
3. Viewer update message appears only when file was created/updated.
4. No rewrite when local viewer matches packaged version.

---

## 9. Documentation Updates

1. Update README “Browsing a source schema” section:
   - `discover` now opens viewer by default
   - include `view [PATH]` and `--port`
   - remove old 4-step manual sequence as primary path
2. Keep manual serving as an optional advanced path note.

---

## 10. Acceptance Criteria

1. `schema_viewer.html` is packaged and available from installed wheel.
2. `feather discover` writes schema JSON and then serves + opens viewer by default.
3. `feather view [PATH]` serves folder without running discovery.
4. Server binds to `127.0.0.1`.
5. Port behavior: preferred 8000 first, fallback automatically if occupied.
6. `view --port` tries requested port first and also falls back when occupied.
7. URL printed once in both success and browser-failure paths.
8. Browser-failure message does not duplicate URL.
9. Viewer file sync policy is identical for both commands and rewrites only on content change.
10. `tests/test_cli_structure.py` includes `view` command registration expectations.

---

## 11. Notes for Issue #8 Compatibility

This design is intentionally isolated in a separate branch/worktree from issue #8. The only expected future conflict zone is `commands/discover.py` (and discover command tests), which is acceptable and will be reconciled when #8 is rebased after #17 merges.
