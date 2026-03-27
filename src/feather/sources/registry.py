"""Source registry — maps type names to source classes."""

from __future__ import annotations

from typing import Any

from feather.config import SourceConfig
from feather.sources import Source
from feather.sources.csv import CsvSource
from feather.sources.duckdb_file import DuckDBFileSource
from feather.sources.sqlite import SqliteSource

SOURCE_REGISTRY: dict[str, type[Any]] = {
    "duckdb": DuckDBFileSource,
    "csv": CsvSource,
    "sqlite": SqliteSource,
}


def create_source(config: SourceConfig) -> Source:
    """Factory: resolve source type -> instantiate."""
    if config.type not in SOURCE_REGISTRY:
        raise ValueError(
            f'Source type "{config.type}" is not implemented. '
            f"Registered: {list(SOURCE_REGISTRY)}"
        )
    cls = SOURCE_REGISTRY[config.type]
    return cls(path=config.path)
