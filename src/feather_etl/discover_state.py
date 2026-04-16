"""Persistent state for `feather discover` — feather_discover_state.json."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
STATE_FILENAME = "feather_discover_state.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DiscoverState:
    config_dir: Path
    sources: dict[str, dict] = field(default_factory=dict)
    auto_enumeration: dict[str, dict] = field(default_factory=dict)
    last_run_at: str | None = None

    @classmethod
    def load(cls, config_dir: Path) -> "DiscoverState":
        path = config_dir / STATE_FILENAME
        if not path.is_file():
            return cls(config_dir=config_dir)
        raw = json.loads(path.read_text())
        return cls(
            config_dir=config_dir,
            sources=raw.get("sources", {}),
            auto_enumeration=raw.get("auto_enumeration", {}),
            last_run_at=raw.get("last_run_at"),
        )

    def save(self) -> None:
        self.last_run_at = _now_iso()
        payload = {
            "schema_version": SCHEMA_VERSION,
            "last_run_at": self.last_run_at,
            "sources": self.sources,
            "auto_enumeration": self.auto_enumeration,
        }
        (self.config_dir / STATE_FILENAME).write_text(
            json.dumps(payload, indent=2)
        )

    def record_ok(self, *, name: str, type_: str, fingerprint: str,
                  table_count: int, output_path: Path,
                  host: str | None = None,
                  database: str | None = None) -> None:
        self.sources[name] = {
            "type": type_,
            "host": host,
            "database": database,
            "fingerprint": fingerprint,
            "status": "ok",
            "discovered_at": _now_iso(),
            "table_count": table_count,
            "output_path": str(output_path),
        }

    def record_failed(self, *, name: str, type_: str, fingerprint: str,
                      error: str, host: str | None = None,
                      database: str | None = None) -> None:
        prev = self.sources.get(name, {})
        attempts = int(prev.get("attempt_count", 0)) + 1
        self.sources[name] = {
            "type": type_,
            "host": host,
            "database": database,
            "fingerprint": fingerprint,
            "status": "failed",
            "attempted_at": _now_iso(),
            "error": error,
            "attempt_count": attempts,
        }

    def record_removed(self, name: str) -> None:
        if name in self.sources:
            self.sources[name]["status"] = "removed"
            self.sources[name]["removed_detected_at"] = _now_iso()

    def record_orphaned(self, name: str, note: str = "") -> None:
        if name in self.sources:
            self.sources[name]["status"] = "orphaned"
            self.sources[name]["orphaned_detected_at"] = _now_iso()
            if note:
                self.sources[name]["note"] = note

    def record_auto_enum(self, *, parent_name: str, type_: str,
                         host: str | None, databases_seen: list[str]) -> None:
        self.auto_enumeration[parent_name] = {
            "type": type_,
            "host": host,
            "last_enumerated_at": _now_iso(),
            "databases_seen": list(databases_seen),
        }


# --- classification ---------------------------------------------------------

def classify(*, state: DiscoverState, current_names: list[str],
             flag: str | None) -> dict[str, str]:
    """Return per-name decision for this run.

    flag: None, "refresh", "retry-failed", "prune".
    """
    decisions: dict[str, str] = {}
    state_names = set(state.sources)
    current = list(current_names)

    for name in current:
        entry = state.sources.get(name)
        if entry is None:
            decisions[name] = "new"
            continue
        status = entry.get("status", "ok")
        if flag == "refresh":
            decisions[name] = "rerun"
        elif flag == "retry-failed":
            decisions[name] = "retry" if status == "failed" else "skip"
        elif flag == "prune":
            decisions[name] = "skip"
        else:
            if status == "ok":
                decisions[name] = "cached"
            elif status == "failed":
                decisions[name] = "retry"
            else:  # removed/orphaned coming back into config
                decisions[name] = "rerun"

    for name in state_names - set(current):
        decisions[name] = "removed"
    return decisions
