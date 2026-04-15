# Discover Auto-Open + View Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship issue #17 so `feather discover` always serves and opens the schema viewer, plus add `feather view [PATH] [--port]` with shared viewer runtime behavior.

**Architecture:** Add a shared `viewer_server` module that owns viewer file sync, smart port selection, and HTTP serving/browser launch. Both `discover` and `view` call this shared module so UX behavior stays consistent and future discover rewrites only need one integration point. Keep commands thin and fully test behavior through command tests and focused unit tests for the shared module.

**Tech Stack:** Python 3.10+, Typer, pytest, `importlib.resources`, `http.server`, `socketserver`, `webbrowser`, Hatch (`pyproject.toml` wheel resource include).

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `src/feather_etl/resources/__init__.py` | Package marker for bundled assets | Create |
| `src/feather_etl/resources/schema_viewer.html` | Bundled viewer HTML served by CLI | Create (copy from `scripts/schema_viewer.html`) |
| `src/feather_etl/viewer_server.py` | Shared runtime: sync viewer file, pick port, serve, open browser | Create |
| `src/feather_etl/commands/view.py` | New `feather view` command | Create |
| `src/feather_etl/commands/discover.py` | Integrate post-discover viewer sync + serving | Modify |
| `src/feather_etl/cli.py` | Register new `view` command | Modify |
| `pyproject.toml` | Include bundled resource files in wheel | Modify |
| `tests/test_viewer_server.py` | Unit tests for shared viewer runtime | Create |
| `tests/commands/test_view.py` | Command tests for `feather view` | Create |
| `tests/commands/test_discover.py` | Verify discover delegates to shared viewer runtime and messaging | Modify |
| `tests/test_cli_structure.py` | CLI command registry contract includes `view` | Modify |
| `README.md` | Command docs and schema browsing flow | Modify |

---

### Task 1: Bundle Viewer Resource + Viewer Sync Core

**Files:**
- Create: `src/feather_etl/resources/__init__.py`
- Create: `src/feather_etl/resources/schema_viewer.html`
- Create: `src/feather_etl/viewer_server.py`
- Create: `tests/test_viewer_server.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Write failing unit tests for viewer sync behavior**

Create `tests/test_viewer_server.py` with:

```python
from __future__ import annotations

from pathlib import Path


class TestSyncViewerHtml:
    def test_creates_viewer_when_missing(self, tmp_path, monkeypatch):
        from feather_etl import viewer_server as vs

        monkeypatch.setattr(vs, "_packaged_viewer_bytes", lambda: b"<html>v1</html>")

        result = vs.sync_viewer_html(tmp_path)

        assert result.status == "created"
        assert result.path == tmp_path / "schema_viewer.html"
        assert result.path.read_bytes() == b"<html>v1</html>"

    def test_unchanged_file_is_not_rewritten(self, tmp_path, monkeypatch):
        from feather_etl import viewer_server as vs

        target = tmp_path / "schema_viewer.html"
        target.write_bytes(b"<html>same</html>")
        before = target.stat().st_mtime_ns

        monkeypatch.setattr(vs, "_packaged_viewer_bytes", lambda: b"<html>same</html>")

        result = vs.sync_viewer_html(tmp_path)

        assert result.status == "unchanged"
        assert target.stat().st_mtime_ns == before

    def test_different_file_is_updated(self, tmp_path, monkeypatch):
        from feather_etl import viewer_server as vs

        target = tmp_path / "schema_viewer.html"
        target.write_bytes(b"<html>old</html>")

        monkeypatch.setattr(vs, "_packaged_viewer_bytes", lambda: b"<html>new</html>")

        result = vs.sync_viewer_html(tmp_path)

        assert result.status == "updated"
        assert target.read_bytes() == b"<html>new</html>"


class TestSyncStatusMessage:
    def test_created_and_updated_have_message(self):
        from feather_etl.viewer_server import sync_status_message

        assert sync_status_message("created") is not None
        assert sync_status_message("updated") is not None

    def test_unchanged_has_no_message(self):
        from feather_etl.viewer_server import sync_status_message

        assert sync_status_message("unchanged") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_viewer_server.py::TestSyncViewerHtml tests/test_viewer_server.py::TestSyncStatusMessage -v
```

Expected: FAIL with import/module errors because `viewer_server.py` does not exist yet.

- [ ] **Step 3: Add resource package and sync-only implementation**

Create `src/feather_etl/resources/__init__.py`:

```python
"""Bundled non-Python resources for feather_etl."""
```

Copy the viewer file:

```bash
cp scripts/schema_viewer.html src/feather_etl/resources/schema_viewer.html
```

Create `src/feather_etl/viewer_server.py` with:

```python
"""Shared schema-viewer runtime helpers for discover/view commands."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Literal

VIEWER_FILENAME = "schema_viewer.html"

SyncStatus = Literal["created", "updated", "unchanged"]


@dataclass(frozen=True)
class ViewerSyncResult:
    path: Path
    status: SyncStatus


def _packaged_viewer_bytes() -> bytes:
    return (files("feather_etl.resources") / VIEWER_FILENAME).read_bytes()


def sync_viewer_html(target_dir: Path) -> ViewerSyncResult:
    """Ensure target dir has the latest bundled schema_viewer.html."""
    target = target_dir / VIEWER_FILENAME
    bundled = _packaged_viewer_bytes()

    if not target.exists():
        target.write_bytes(bundled)
        return ViewerSyncResult(path=target, status="created")

    current = target.read_bytes()
    if current != bundled:
        target.write_bytes(bundled)
        return ViewerSyncResult(path=target, status="updated")

    return ViewerSyncResult(path=target, status="unchanged")


def sync_status_message(status: SyncStatus) -> str | None:
    if status == "created":
        return "Created schema_viewer.html from bundled viewer."
    if status == "updated":
        return "Updated schema_viewer.html to latest bundled version."
    return None
```

Update `pyproject.toml` wheel target block to include resources:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/feather_etl"]
include = ["src/feather_etl/resources/**"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/test_viewer_server.py::TestSyncViewerHtml tests/test_viewer_server.py::TestSyncStatusMessage -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add pyproject.toml \
        src/feather_etl/resources/__init__.py \
        src/feather_etl/resources/schema_viewer.html \
        src/feather_etl/viewer_server.py \
        tests/test_viewer_server.py
git commit -m "feat(viewer): bundle schema viewer and sync local copy"
```

---

### Task 2: Port Selection + Serve/Open Runtime

**Files:**
- Modify: `src/feather_etl/viewer_server.py`
- Modify: `tests/test_viewer_server.py`

- [ ] **Step 1: Add failing tests for port fallback and URL output contract**

Append to `tests/test_viewer_server.py`:

```python
class TestChoosePort:
    def test_returns_preferred_when_available(self, monkeypatch):
        from feather_etl import viewer_server as vs

        monkeypatch.setattr(vs, "_can_bind", lambda host, port: True)

        assert vs.choose_port(preferred_port=8000) == 8000

    def test_falls_back_when_preferred_is_busy(self, monkeypatch):
        from feather_etl import viewer_server as vs

        monkeypatch.setattr(vs, "_can_bind", lambda host, port: False)
        monkeypatch.setattr(vs, "_free_port", lambda host: 9123)

        assert vs.choose_port(preferred_port=8000) == 9123


class TestServeAndOpen:
    def test_prints_url_once_and_manual_hint_on_browser_failure(
        self, tmp_path, monkeypatch, capsys
    ):
        from feather_etl import viewer_server as vs

        class DummyServer:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def serve_forever(self):
                return None

        monkeypatch.setattr(vs, "choose_port", lambda preferred_port=8000: 8123)
        monkeypatch.setattr(vs.socketserver, "TCPServer", lambda addr, handler: DummyServer())
        monkeypatch.setattr(vs.webbrowser, "open", lambda url: False)

        vs.serve_and_open(tmp_path)
        out = capsys.readouterr().out

        assert out.count("http://localhost:8123/schema_viewer.html") == 1
        assert "Browser launch failed. Open the URL above manually." in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_viewer_server.py::TestChoosePort tests/test_viewer_server.py::TestServeAndOpen -v
```

Expected: FAIL because `choose_port` and `serve_and_open` are not implemented.

- [ ] **Step 3: Implement port + serving runtime in `viewer_server.py`**

Update `src/feather_etl/viewer_server.py` to:

```python
"""Shared schema-viewer runtime helpers for discover/view commands."""

from __future__ import annotations

import functools
import http.server
import socket
import socketserver
import webbrowser
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Literal

import typer

VIEWER_FILENAME = "schema_viewer.html"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000

SyncStatus = Literal["created", "updated", "unchanged"]


@dataclass(frozen=True)
class ViewerSyncResult:
    path: Path
    status: SyncStatus


def _packaged_viewer_bytes() -> bytes:
    return (files("feather_etl.resources") / VIEWER_FILENAME).read_bytes()


def sync_viewer_html(target_dir: Path) -> ViewerSyncResult:
    """Ensure target dir has the latest bundled schema_viewer.html."""
    target = target_dir / VIEWER_FILENAME
    bundled = _packaged_viewer_bytes()

    if not target.exists():
        target.write_bytes(bundled)
        return ViewerSyncResult(path=target, status="created")

    current = target.read_bytes()
    if current != bundled:
        target.write_bytes(bundled)
        return ViewerSyncResult(path=target, status="updated")

    return ViewerSyncResult(path=target, status="unchanged")


def sync_status_message(status: SyncStatus) -> str | None:
    if status == "created":
        return "Created schema_viewer.html from bundled viewer."
    if status == "updated":
        return "Updated schema_viewer.html to latest bundled version."
    return None


def _can_bind(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _free_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def choose_port(preferred_port: int = DEFAULT_PORT) -> int:
    if _can_bind(DEFAULT_HOST, preferred_port):
        return preferred_port
    return _free_port(DEFAULT_HOST)


def _viewer_url(port: int) -> str:
    return f"http://localhost:{port}/{VIEWER_FILENAME}"


def serve_and_open(target_dir: Path, preferred_port: int = DEFAULT_PORT) -> None:
    """Serve target_dir and open schema_viewer.html in browser."""
    port = choose_port(preferred_port=preferred_port)
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler,
        directory=str(target_dir),
    )

    with socketserver.TCPServer((DEFAULT_HOST, port), handler) as server:
        url = _viewer_url(port)
        typer.echo(f"Serving {target_dir} at {url}")
        opened = webbrowser.open(url)
        if not opened:
            typer.echo("Browser launch failed. Open the URL above manually.")
        typer.echo("Press Ctrl+C to stop.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            typer.echo("Stopped.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/test_viewer_server.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add src/feather_etl/viewer_server.py tests/test_viewer_server.py
git commit -m "feat(viewer): serve schema viewer with smart port fallback"
```

---

### Task 3: Add `feather view` Command + CLI Registration

**Files:**
- Create: `src/feather_etl/commands/view.py`
- Modify: `src/feather_etl/cli.py`
- Create: `tests/commands/test_view.py`
- Modify: `tests/test_cli_structure.py`

- [ ] **Step 1: Write failing command and CLI-structure tests**

Create `tests/commands/test_view.py`:

```python
"""Tests for the `feather view` command."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def viewer_calls(monkeypatch):
    from feather_etl.commands import view as view_mod
    from feather_etl.viewer_server import ViewerSyncResult

    calls: dict[str, object] = {}

    def fake_sync(target_dir: Path) -> ViewerSyncResult:
        calls["sync_target"] = target_dir
        return ViewerSyncResult(path=target_dir / "schema_viewer.html", status="unchanged")

    def fake_serve(target_dir: Path, preferred_port: int = 8000) -> None:
        calls["serve_target"] = target_dir
        calls["serve_port"] = preferred_port

    monkeypatch.setattr(view_mod, "sync_viewer_html", fake_sync)
    monkeypatch.setattr(view_mod, "serve_and_open", fake_serve)
    return calls


class TestView:
    def test_view_defaults_to_current_directory(self, runner, tmp_path, monkeypatch, viewer_calls):
        from feather_etl.cli import app

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["view"])

        assert result.exit_code == 0
        assert viewer_calls["sync_target"] == tmp_path.resolve()
        assert viewer_calls["serve_target"] == tmp_path.resolve()
        assert viewer_calls["serve_port"] == 8000

    def test_view_accepts_path_and_port(self, runner, tmp_path, viewer_calls):
        from feather_etl.cli import app

        target = tmp_path / "schemas"
        target.mkdir()

        result = runner.invoke(app, ["view", str(target), "--port", "8765"])

        assert result.exit_code == 0
        assert viewer_calls["serve_target"] == target.resolve()
        assert viewer_calls["serve_port"] == 8765

    def test_invalid_path_fails(self, runner, tmp_path):
        from feather_etl.cli import app

        missing = tmp_path / "missing"
        result = runner.invoke(app, ["view", str(missing)])

        assert result.exit_code != 0
        assert "does not exist" in result.output.lower()

    def test_prints_update_message_only_for_updated(self, runner, tmp_path, monkeypatch):
        from feather_etl.cli import app
        from feather_etl.commands import view as view_mod
        from feather_etl.viewer_server import ViewerSyncResult

        target = tmp_path / "schemas"
        target.mkdir()

        monkeypatch.setattr(
            view_mod,
            "sync_viewer_html",
            lambda d: ViewerSyncResult(path=d / "schema_viewer.html", status="updated"),
        )
        monkeypatch.setattr(view_mod, "serve_and_open", lambda d, preferred_port=8000: None)

        result = runner.invoke(app, ["view", str(target)])

        assert result.exit_code == 0
        assert "Updated schema_viewer.html to latest bundled version." in result.output
```

Update `tests/test_cli_structure.py` expectations:

```python
assert registered_command_names == {
    "init",
    "validate",
    "discover",
    "view",
    "setup",
    "run",
    "history",
    "status",
}
```

```python
module_names = [
    "init",
    "validate",
    "discover",
    "view",
    "setup",
    "run",
    "history",
    "status",
]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/commands/test_view.py tests/test_cli_structure.py -v
```

Expected: FAIL because `feather view` and command registration do not exist.

- [ ] **Step 3: Implement `view` command and register it**

Create `src/feather_etl/commands/view.py`:

```python
"""`feather view` command."""

from __future__ import annotations

from pathlib import Path

import typer

from feather_etl.viewer_server import (
    sync_status_message,
    sync_viewer_html,
    serve_and_open,
)


def view(
    path: Path = typer.Argument(
        Path("."),
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    port: int = typer.Option(8000, "--port", min=1, max=65535),
) -> None:
    """Serve schema viewer for an existing folder."""
    target_dir = path.resolve()
    sync_result = sync_viewer_html(target_dir)
    msg = sync_status_message(sync_result.status)
    if msg:
        typer.echo(msg)
    serve_and_open(target_dir, preferred_port=port)


def register(app: typer.Typer) -> None:
    app.command(name="view")(view)
```

Update `src/feather_etl/cli.py`:

```python
from feather_etl.commands.view import register as register_view
```

Add registration with the other commands:

```python
register_discover(app)
register_view(app)
register_setup(app)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/commands/test_view.py tests/test_cli_structure.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

```bash
git add src/feather_etl/commands/view.py \
        src/feather_etl/cli.py \
        tests/commands/test_view.py \
        tests/test_cli_structure.py
git commit -m "feat(cli): add feather view command"
```

---

### Task 4: Integrate Viewer Runtime into `discover`

**Files:**
- Modify: `src/feather_etl/commands/discover.py`
- Modify: `tests/commands/test_discover.py`

- [ ] **Step 1: Add failing tests for discover integration hooks**

In `tests/commands/test_discover.py`, add imports and an autouse fixture near top:

```python
import pytest
from feather_etl.viewer_server import ViewerSyncResult


@pytest.fixture
def viewer_calls(monkeypatch):
    from feather_etl.commands import discover as discover_mod

    calls: dict[str, object] = {}

    def fake_sync(target_dir: Path) -> ViewerSyncResult:
        calls["sync_target"] = target_dir
        return ViewerSyncResult(path=target_dir / "schema_viewer.html", status="unchanged")

    def fake_serve(target_dir: Path, preferred_port: int = 8000) -> None:
        calls["serve_target"] = target_dir
        calls["serve_port"] = preferred_port

    monkeypatch.setattr(discover_mod, "sync_viewer_html", fake_sync)
    monkeypatch.setattr(discover_mod, "serve_and_open", fake_serve)
    return calls
```

Add tests inside `class TestDiscover`:

```python
def test_invokes_viewer_runtime(self, runner, tmp_path: Path, monkeypatch, viewer_calls):
    from feather_etl.cli import app

    config_path = _write_sqlite_config(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["discover", "--config", str(config_path)])

    assert result.exit_code == 0
    assert viewer_calls["sync_target"] == tmp_path.resolve()
    assert viewer_calls["serve_target"] == tmp_path.resolve()
    assert viewer_calls["serve_port"] == 8000


def test_prints_sync_message_when_viewer_updated(self, runner, tmp_path: Path, monkeypatch):
    from feather_etl.cli import app
    from feather_etl.commands import discover as discover_mod

    config_path = _write_sqlite_config(tmp_path)
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(
        discover_mod,
        "sync_viewer_html",
        lambda d: ViewerSyncResult(path=d / "schema_viewer.html", status="updated"),
    )
    monkeypatch.setattr(discover_mod, "serve_and_open", lambda d, preferred_port=8000: None)

    result = runner.invoke(app, ["discover", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "Updated schema_viewer.html to latest bundled version." in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/commands/test_discover.py::TestDiscover::test_invokes_viewer_runtime tests/commands/test_discover.py::TestDiscover::test_prints_sync_message_when_viewer_updated -v
```

Expected: FAIL because discover command does not call viewer runtime yet.

- [ ] **Step 3: Wire discover command to shared viewer runtime**

Update `src/feather_etl/commands/discover.py` imports:

```python
from feather_etl.viewer_server import (
    serve_and_open,
    sync_status_message,
    sync_viewer_html,
)
```

After schema JSON write + existing summary line, add:

```python
    target_dir = out_path.parent.resolve()
    sync_result = sync_viewer_html(target_dir)
    msg = sync_status_message(sync_result.status)
    if msg:
        typer.echo(msg)

    serve_and_open(target_dir, preferred_port=8000)
```

Keep existing behavior before this block unchanged:

```python
    typer.echo(f"Wrote {len(schemas)} table(s) to ./{out_path}")
```

- [ ] **Step 4: Run discover tests**

Run:

```bash
uv run pytest tests/commands/test_discover.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 4**

```bash
git add src/feather_etl/commands/discover.py tests/commands/test_discover.py
git commit -m "feat(discover): auto-open bundled schema viewer after discover"
```

---

### Task 5: README Update + Final Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update command list and schema browsing docs**

In `README.md`, update command list to include `view`:

```markdown
feather discover                       # discover schema, then serve + open viewer
feather view [PATH]                    # serve/open schema viewer for existing folder
feather view --port 8765               # prefer port 8765, fallback if busy
```

Replace the old manual 4-step schema browsing section with:

```markdown
### Browsing a source schema

`feather discover` now writes schema JSON and immediately serves `schema_viewer.html` on localhost, then opens your browser.

Use `feather view` when you already have schema JSON files and want to browse them without running discover again:

Port behavior: tries your preferred port first (default 8000), then falls back to a free port if occupied.
```

Use these command examples under that section:

```bash
feather discover
# Serving /path/to/project at http://localhost:8000/schema_viewer.html
# Press Ctrl+C to stop.

feather view
feather view path/to/schemas
feather view path/to/schemas --port 8765
```

Keep a short optional manual-hosting note below this section:

```markdown
If you prefer manual hosting, you can still serve the folder with any static web server.
```

- [ ] **Step 2: Run targeted regression tests**

Run:

```bash
uv run pytest tests/test_viewer_server.py tests/commands/test_view.py tests/commands/test_discover.py tests/test_cli_structure.py -v
```

Expected: PASS.

- [ ] **Step 3: Run full suite**

Run:

```bash
uv run pytest -q
```

Expected: PASS (or existing known skips only).

- [ ] **Step 4: Commit Task 5**

```bash
git add README.md
git commit -m "docs(readme): document discover auto-open and new view command"
```

---

## Final PR Checklist

- [ ] Run format/lint if needed by branch standards.

```bash
uv run ruff format .
uv run ruff check .
```

- [ ] Confirm command UX manually in a temp project:

```bash
uv run feather discover --config /path/to/feather.yaml
uv run feather view /path/to/schema/folder
uv run feather view /path/to/schema/folder --port 8765
```

- [ ] Open PR for issue #17 with summary:
  - bundled viewer resource
  - shared viewer runtime module
  - new `feather view` command
  - discover auto-open integration
  - updated CLI structure tests + docs

---

## Self-Review Notes

### 1. Spec coverage

- `discover` auto-open default behavior: Task 4
- `view` command with `--port`: Task 3
- shared behavior for sync/serve/open: Tasks 1 + 2
- port policy (8000 then fallback): Task 2 + Task 3 tests
- single URL line + browser-failure hint: Task 2 tests
- packaged resource + wheel inclusion: Task 1
- `test_cli_structure.py` update: Task 3
- README replacement of manual flow: Task 5

### 2. Placeholder scan

- No `TODO`, `TBD`, “implement later”, or undefined “appropriate” steps.
- Every code-changing step includes concrete code snippets or explicit copy commands.

### 3. Type/signature consistency

- Shared runtime API used consistently across tasks:
  - `sync_viewer_html(target_dir: Path) -> ViewerSyncResult`
  - `sync_status_message(status: SyncStatus) -> str | None`
  - `serve_and_open(target_dir: Path, preferred_port: int = 8000) -> None`
- Command usage signatures match tests and implementation snippets.
