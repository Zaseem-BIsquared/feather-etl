"""Unit tests for feather_etl.commands.cache private helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class _FakeSource:
    name: str
    database: str | None = None
    databases: list[str] | None = None


@dataclass
class _FakeCfg:
    sources: list


class TestLookupSourceName:
    """``_lookup_source_name`` falls back to the raw ``source_db`` when
    ``resolve_source`` raises ValueError (commands/cache.py:149-150)."""

    def test_returns_match_when_resolvable(self):
        from feather_etl.commands.cache import _lookup_source_name

        cfg = _FakeCfg(sources=[_FakeSource(name="erp", database="erp")])
        assert _lookup_source_name(cfg, "erp") == "erp"

    def test_falls_back_to_raw_source_db_on_mismatch(self):
        """When source_db points at nothing configured, the helper returns
        the input string so the CLI has something to print."""
        from feather_etl.commands.cache import _lookup_source_name

        cfg = _FakeCfg(sources=[_FakeSource(name="erp", database="erp")])
        assert _lookup_source_name(cfg, "nonexistent_db") == "nonexistent_db"
