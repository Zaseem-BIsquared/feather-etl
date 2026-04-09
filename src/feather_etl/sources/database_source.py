"""DatabaseSource base class — shared behavior for database sources."""

from __future__ import annotations


class DatabaseSource:
    """Base for database sources (SQL Server, PostgreSQL, etc.).

    Provides:
    - __init__(connection_string): stores the connection string
    - _format_watermark(value): format watermark value for SQL (override per DB)
    - _build_where_clause(): constructs WHERE from filter + watermark

    Subclasses implement: check(), discover(), extract(), detect_changes(), get_schema().
    """

    def __init__(self, connection_string: str) -> None:
        self.connection_string = connection_string

    def _format_watermark(self, value: str) -> str:
        """Format a watermark value for use in a SQL WHERE clause.

        Default: pass through unchanged. Subclasses override for DB-specific formatting.
        """
        return value

    def _build_where_clause(
        self,
        filter: str | None = None,
        watermark_column: str | None = None,
        watermark_value: str | None = None,
    ) -> str:
        """Build a WHERE clause from optional filter and watermark."""
        parts: list[str] = []
        if filter:
            parts.append(f"({filter})")
        if watermark_column and watermark_value:
            wm_val = self._format_watermark(watermark_value)
            parts.append(f"{watermark_column} > '{wm_val}'")
        if not parts:
            return ""
        return " WHERE " + " AND ".join(parts)
