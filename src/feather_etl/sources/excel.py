"""Excel source — reads .xlsx/.xls files from a directory using DuckDB read_xlsx()."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pyarrow as pa

from feather_etl.sources import StreamSchema
from feather_etl.sources.file_source import FileSource


class ExcelSource(FileSource):
    """Source that reads Excel files from a directory."""

    def __init__(self, path: Path) -> None:
        super().__init__(path)

    def _source_path_for_table(self, table: str) -> Path:
        """Excel: each table is a separate file in the directory."""
        return self.path / table

    def check(self) -> bool:
        return self.path.is_dir()

    def discover(self) -> list[StreamSchema]:
        xlsx_files = sorted(
            list(self.path.glob("*.xlsx")) + list(self.path.glob("*.xls"))
        )
        schemas: list[StreamSchema] = []
        con = duckdb.connect(":memory:")
        try:
            con.execute("INSTALL excel; LOAD excel;")
            for xlsx_file in xlsx_files:
                cols = con.execute(
                    "SELECT column_name, column_type "
                    "FROM (DESCRIBE SELECT * FROM read_xlsx(?))",
                    [str(xlsx_file)],
                ).fetchall()
                schemas.append(
                    StreamSchema(
                        name=xlsx_file.name,
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
            con.execute("INSTALL excel; LOAD excel;")
            col_sql = ", ".join(f'"{c}"' for c in columns) if columns else "*"
            where = self._build_where_clause(watermark_column, watermark_value, filter)
            query = f"SELECT {col_sql} FROM read_xlsx(?){where}"
            result = con.execute(query, [file_path]).arrow().read_all()
        finally:
            con.close()
        return result

    def get_schema(self, table: str) -> list[tuple[str, str]]:
        con = duckdb.connect(":memory:")
        file_path = str(self.path / table)
        try:
            con.execute("INSTALL excel; LOAD excel;")
            cols = con.execute(
                "SELECT column_name, column_type "
                "FROM (DESCRIBE SELECT * FROM read_xlsx(?))",
                [file_path],
            ).fetchall()
        finally:
            con.close()
        return [(c[0], c[1]) for c in cols]
