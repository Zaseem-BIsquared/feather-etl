"""JSON source — reads .json/.jsonl files from a directory using DuckDB read_json_auto()."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pyarrow as pa

from feather_etl.sources import StreamSchema
from feather_etl.sources.file_source import FileSource


class JsonSource(FileSource):
    """Source that reads JSON files from a directory."""

    def __init__(self, path: Path) -> None:
        super().__init__(path)

    def _source_path_for_table(self, table: str) -> Path:
        """JSON: each table is a separate file in the directory."""
        return self.path / table

    def check(self) -> bool:
        return self.path.is_dir()

    def discover(self) -> list[StreamSchema]:
        json_files = sorted(
            list(self.path.glob("*.json")) + list(self.path.glob("*.jsonl"))
        )
        schemas: list[StreamSchema] = []
        con = duckdb.connect(":memory:")
        try:
            for json_file in json_files:
                cols = con.execute(
                    "SELECT column_name, column_type "
                    "FROM (DESCRIBE SELECT * FROM read_json_auto(?))",
                    [str(json_file)],
                ).fetchall()
                schemas.append(
                    StreamSchema(
                        name=json_file.name,
                        columns=[(c[0], c[1]) for c in cols],
                        primary_key=None,
                        supports_incremental=False,
                    )
                )
        finally:
            con.close()
        return schemas

    def extract(
        self,
        table: str,
        columns: list[str] | None = None,
        filter: str | None = None,
        watermark_column: str | None = None,
        watermark_value: str | None = None,
    ) -> pa.Table:
        con = duckdb.connect(":memory:")
        file_path = str(self.path / table)
        try:
            col_sql = ", ".join(f'"{c}"' for c in columns) if columns else "*"
            where = self._build_where_clause(watermark_column, watermark_value, filter)
            query = f"SELECT {col_sql} FROM read_json_auto(?){where}"
            result = con.execute(query, [file_path]).arrow().read_all()
        finally:
            con.close()
        return result

    def get_schema(self, table: str) -> list[tuple[str, str]]:
        con = duckdb.connect(":memory:")
        file_path = str(self.path / table)
        try:
            cols = con.execute(
                "SELECT column_name, column_type "
                "FROM (DESCRIBE SELECT * FROM read_json_auto(?))",
                [file_path],
            ).fetchall()
        finally:
            con.close()
        return [(c[0], c[1]) for c in cols]
