"""FileSource base class — shared behavior for file-based sources."""

from __future__ import annotations

from pathlib import Path

from feather.sources import ChangeResult


class FileSource:
    """Base for file-based sources (DuckDB, CSV, SQLite, etc.).

    Provides:
    - __init__(path): stores the source path
    - check(): verifies the path exists
    - detect_changes(): Slice 1 stub — always returns changed=True

    Subclasses implement: discover(), extract(), get_schema().
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    def check(self) -> bool:
        return self.path.exists()

    def detect_changes(
        self, table: str, last_state: dict[str, object] | None = None
    ) -> ChangeResult:
        # Slice 1: no change detection — always extract
        return ChangeResult(changed=True, reason="first_run")
