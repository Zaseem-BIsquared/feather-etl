"""Source registry — lazy type→class map.

Each entry stores the dotted module path so importing the registry itself
does NOT import optional connector dependencies (pyodbc, psycopg2). The
target module is imported on first lookup. Closes issue #4.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from feather_etl.sources import Source


SOURCE_CLASSES: dict[str, str] = {
    "duckdb": "feather_etl.sources.duckdb_file.DuckDBFileSource",
    "csv": "feather_etl.sources.csv.CsvSource",
    "sqlite": "feather_etl.sources.sqlite.SqliteSource",
    "sqlserver": "feather_etl.sources.sqlserver.SqlServerSource",
    "postgres": "feather_etl.sources.postgres.PostgresSource",
    "mysql": "feather_etl.sources.mysql.MySQLSource",
    "excel": "feather_etl.sources.excel.ExcelSource",
    "json": "feather_etl.sources.json_source.JsonSource",
}


def get_source_class(type_name: str) -> type["Source"]:
    """Resolve the source class for a YAML `type:` value, importing lazily."""
    if type_name not in SOURCE_CLASSES:
        raise ValueError(
            f"Source type '{type_name}' is not implemented. "
            f"Registered: {sorted(SOURCE_CLASSES)}"
        )
    module_path, cls_name = SOURCE_CLASSES[type_name].rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, cls_name)
