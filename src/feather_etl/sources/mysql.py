"""MySQL source — reads from MySQL via mysql-connector-python."""

from __future__ import annotations

import decimal
from pathlib import Path
from typing import ClassVar

import mysql.connector
import pyarrow as pa

from feather_etl.sources import ChangeResult, StreamSchema
from feather_etl.sources.database_source import DatabaseSource

# mysql.connector FieldType constants → PyArrow type
_MYSQL_FIELD_TYPE_MAP: dict[int, pa.DataType] = {
    0: pa.float64(),  # DECIMAL
    1: pa.int8(),  # TINY
    2: pa.int16(),  # SHORT
    3: pa.int64(),  # LONG
    4: pa.float32(),  # FLOAT
    5: pa.float64(),  # DOUBLE
    7: pa.timestamp("us"),  # TIMESTAMP
    8: pa.int64(),  # LONGLONG
    9: pa.int64(),  # INT24
    10: pa.date32(),  # DATE
    11: pa.time64("us"),  # TIME
    12: pa.timestamp("us"),  # DATETIME
    13: pa.int16(),  # YEAR
    15: pa.string(),  # VARCHAR
    16: pa.bool_(),  # BIT
    246: pa.float64(),  # NEWDECIMAL
    249: pa.binary(),  # TINY_BLOB
    250: pa.binary(),  # MEDIUM_BLOB
    251: pa.binary(),  # LONG_BLOB
    252: pa.binary(),  # BLOB
    253: pa.string(),  # VAR_STRING
    254: pa.string(),  # STRING
}

# INFORMATION_SCHEMA DATA_TYPE string → PyArrow type
_MYSQL_INFO_SCHEMA_TYPE_MAP: dict[str, pa.DataType] = {
    "int": pa.int64(),
    "bigint": pa.int64(),
    "smallint": pa.int16(),
    "tinyint": pa.int8(),
    "mediumint": pa.int64(),
    "float": pa.float32(),
    "double": pa.float64(),
    "decimal": pa.float64(),
    "numeric": pa.float64(),
    "bit": pa.bool_(),
    "boolean": pa.bool_(),
    "char": pa.string(),
    "varchar": pa.string(),
    "text": pa.string(),
    "tinytext": pa.string(),
    "mediumtext": pa.string(),
    "longtext": pa.string(),
    "enum": pa.string(),
    "set": pa.string(),
    "date": pa.date32(),
    "time": pa.time64("us"),
    "datetime": pa.timestamp("us"),
    "timestamp": pa.timestamp("us"),
    "year": pa.int16(),
    "binary": pa.binary(),
    "varbinary": pa.binary(),
    "blob": pa.binary(),
    "tinyblob": pa.binary(),
    "mediumblob": pa.binary(),
    "longblob": pa.binary(),
    "json": pa.string(),
}


def _mysql_field_type_to_arrow(type_code: int) -> pa.DataType:
    """Map a mysql.connector FieldType code to a PyArrow type."""
    return _MYSQL_FIELD_TYPE_MAP.get(type_code, pa.string())


class MySQLSource(DatabaseSource):
    """Source that reads tables from MySQL via mysql-connector-python."""

    type: ClassVar[str] = "mysql"

    def __init__(
        self,
        connection_string: str,
        *,
        name: str = "",
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str | None = None,
        databases: list[str] | None = None,
        batch_size: int = 120_000,
    ) -> None:
        super().__init__(connection_string)
        self.name = name
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.databases = databases
        self.batch_size = batch_size
        self._last_error: str | None = None
        self._connect_kwargs: dict = {}

    def _connect(self):
        """Return a MySQL connection using stored kwargs."""
        return mysql.connector.connect(**self._connect_kwargs)

    @classmethod
    def from_yaml(cls, entry: dict, config_dir: Path) -> "MySQLSource":
        name = entry.get("name", "")
        explicit_conn = entry.get("connection_string")
        host = entry.get("host")
        port = entry.get("port", 3306)
        user = entry.get("user")
        password = entry.get("password")
        database = entry.get("database")
        databases = entry.get("databases")

        if database is not None and databases is not None:
            raise ValueError("database and databases are mutually exclusive; use one.")
        if databases is not None and not databases:
            raise ValueError("databases list must be non-empty.")

        if explicit_conn:
            conn_str = explicit_conn
            connect_kwargs: dict = {}
        elif host:
            connect_kwargs = {"host": host, "port": port}
            if database:
                connect_kwargs["database"] = database
            if user:
                connect_kwargs["user"] = user
            if password:
                connect_kwargs["password"] = password
            conn_str = (
                f"host={host};port={port};database={database or ''}"
                f";user={user or ''}"
            )
        else:
            raise ValueError(
                "mysql source requires either 'connection_string' or 'host'."
            )

        source = cls(
            connection_string=conn_str,
            name=name,
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            databases=databases,
        )
        source._connect_kwargs = connect_kwargs
        source._explicit_name = bool(entry.get("name"))
        return source

    def validate_source_table(self, source_table: str) -> list[str]:
        return []

    def check(self) -> bool:
        self._last_error = None
        try:
            conn = self._connect()
            conn.close()
            return True
        except mysql.connector.Error as e:
            self._last_error = str(e)
            return False

    def discover(self) -> list[StreamSchema]:
        raise NotImplementedError("discover not yet implemented")

    def get_schema(self, table: str) -> list[tuple[str, str]]:
        raise NotImplementedError("get_schema not yet implemented")

    def extract(
        self,
        table: str,
        columns: list[str] | None = None,
        filter: str | None = None,
        watermark_column: str | None = None,
        watermark_value: str | None = None,
    ) -> pa.Table:
        raise NotImplementedError("extract not yet implemented")

    def detect_changes(
        self, table: str, last_state: dict[str, object] | None = None
    ) -> ChangeResult:
        raise NotImplementedError("detect_changes not yet implemented")

    def list_databases(self) -> list[str]:
        raise NotImplementedError("list_databases not yet implemented")
