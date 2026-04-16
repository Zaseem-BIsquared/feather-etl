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


def detect_renames(*, state: DiscoverState,
                   current: list[tuple[str, str]]
                   ) -> tuple[list[tuple[str, str]], list[tuple[str, list[str]]]]:
    """Infer rename proposals from matching fingerprints."""
    current_names = {name for name, _ in current}
    state_only = [
        name for name, entry in state.sources.items()
        if name not in current_names
        and entry.get("status") in ("ok", "removed", "failed")
    ]

    proposals: list[tuple[str, str]] = []
    ambiguous: list[tuple[str, list[str]]] = []

    for new_name, fingerprint in current:
        if new_name in state.sources:
            continue
        candidates = [
            name for name in state_only
            if state.sources.get(name, {}).get("fingerprint") == fingerprint
        ]
        if len(candidates) == 1:
            proposals.append((candidates[0], new_name))
        elif len(candidates) > 1:
            ambiguous.append((new_name, candidates))

    return proposals, ambiguous


def _renamed_schema_path(path: str, old: str, new: str) -> str:
    current = Path(path)
    old_prefix = f"schema_{old}"
    if not current.name.startswith(old_prefix):
        return path
    new_name = current.name.replace(old_prefix, f"schema_{new}", 1)
    return str(current.with_name(new_name))


def apply_renames(*, state: DiscoverState, renames: list[tuple[str, str]],
                  config_dir: Path) -> None:
    """Move matched state entries and schema files to their new names."""
    for old, new in renames:
        if old not in state.sources:
            continue

        old_prefix = f"{old}__"
        new_prefix = f"{new}__"

        parent_entry = state.sources.pop(old)
        if "output_path" in parent_entry:
            parent_entry["output_path"] = _renamed_schema_path(
                parent_entry["output_path"], old, new
            )
        state.sources[new] = parent_entry

        if old in state.auto_enumeration:
            state.auto_enumeration[new] = state.auto_enumeration.pop(old)

        child_keys = [name for name in list(state.sources) if name.startswith(old_prefix)]
        for child_old in child_keys:
            child_new = new_prefix + child_old[len(old_prefix):]
            child_entry = state.sources.pop(child_old)
            if "output_path" in child_entry:
                child_entry["output_path"] = _renamed_schema_path(
                    child_entry["output_path"], old, new
                )
            state.sources[child_new] = child_entry

        for schema_file in sorted(config_dir.glob(f"schema_{old}*.json")):
            target_name = schema_file.name.replace(f"schema_{old}", f"schema_{new}", 1)
            schema_file.rename(config_dir / target_name)
