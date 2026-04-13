"""Source connectors for feather-etl."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, Protocol

import pyarrow as pa


@dataclass
class StreamSchema:
    """Describes a discoverable table/stream."""

    name: str
    columns: list[tuple[str, str]]
    primary_key: list[str] | None
    supports_incremental: bool


@dataclass
class ChangeResult:
    """Result of change detection check."""

    changed: bool
    reason: str  # "first_run", "hash_changed", "unchanged"
    metadata: dict[str, object] = field(default_factory=dict)


class Source(Protocol):
    """Any class with these methods is a valid feather-etl source."""

    name: str
    type: ClassVar[str]

    @classmethod
    def from_yaml(cls, entry: dict, config_dir: Path) -> "Source":
        """Parse one `sources:` list entry and return a configured instance.

        All per-type rules live here: port defaults, connection-string template,
        path resolution, database/databases XOR validation. Side-effect free —
        does not open connections.
        """
        ...

    def validate_source_table(self, source_table: str) -> list[str]:
        """Return error messages for this source_table string. Empty list = valid."""
        ...

    def check(self) -> bool: ...

    def discover(self) -> list[StreamSchema]: ...

    def extract(
        self,
        table: str,
        columns: list[str] | None = None,
        filter: str | None = None,
        watermark_column: str | None = None,
        watermark_value: str | None = None,
    ) -> pa.Table: ...

    def detect_changes(
        self, table: str, last_state: dict[str, object] | None = None
    ) -> ChangeResult: ...

    def get_schema(self, table: str) -> list[tuple[str, str]]: ...
