"""
Create CSV and SQLite test fixtures from sample_erp.duckdb.

Generates:
  tests/fixtures/csv_data/orders.csv      — 5 rows
  tests/fixtures/csv_data/customers.csv   — 4 rows
  tests/fixtures/csv_data/products.csv    — 3 rows (row 3 has NULL stock_qty)
  tests/fixtures/sample_erp.sqlite        — 3 tables, same data

Run from the repo root:

    python scripts/create_csv_sqlite_fixtures.py

The script is idempotent — re-running recreates all files from scratch.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import duckdb

FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures"
SOURCE_DB = FIXTURES_DIR / "sample_erp.duckdb"
CSV_DIR = FIXTURES_DIR / "csv_data"
SQLITE_PATH = FIXTURES_DIR / "sample_erp.sqlite"

TABLES = [
    ("erp", "orders"),
    ("erp", "customers"),
    ("erp", "products"),
]


def create_csv_fixtures() -> None:
    CSV_DIR.mkdir(exist_ok=True)

    con = duckdb.connect(str(SOURCE_DB), read_only=True)
    for schema, table in TABLES:
        csv_path = CSV_DIR / f"{table}.csv"
        con.execute(f"COPY {schema}.{table} TO '{csv_path}' (FORMAT CSV, HEADER)")
        rows = con.execute(f"SELECT COUNT(*) FROM {schema}.{table}").fetchone()[0]
        print(f"  CSV: {csv_path.name:<20} {rows} rows")
    con.close()


def create_sqlite_fixture() -> None:
    if SQLITE_PATH.exists():
        SQLITE_PATH.unlink()

    # Read data from DuckDB source
    ddb = duckdb.connect(str(SOURCE_DB), read_only=True)

    scon = sqlite3.connect(str(SQLITE_PATH))

    # --- orders ---
    scon.execute("""
        CREATE TABLE orders (
            order_id     INTEGER PRIMARY KEY,
            customer_id  INTEGER,
            order_date   TEXT,
            total_amount REAL,
            status       TEXT,
            created_at   TEXT
        )
    """)
    rows = ddb.execute("SELECT * FROM erp.orders").fetchall()
    scon.executemany(
        "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?)",
        [(r[0], r[1], str(r[2]), float(r[3]), r[4], str(r[5])) for r in rows],
    )
    print(f"  SQLite: orders              {len(rows)} rows")

    # --- customers ---
    scon.execute("""
        CREATE TABLE customers (
            customer_id  INTEGER PRIMARY KEY,
            name         TEXT,
            email        TEXT,
            city         TEXT,
            credit_limit REAL,
            created_at   TEXT
        )
    """)
    rows = ddb.execute("SELECT * FROM erp.customers").fetchall()
    scon.executemany(
        "INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?)",
        [(r[0], r[1], r[2], r[3], float(r[4]), str(r[5])) for r in rows],
    )
    print(f"  SQLite: customers            {len(rows)} rows")

    # --- products (NULL in stock_qty) ---
    scon.execute("""
        CREATE TABLE products (
            product_id   INTEGER PRIMARY KEY,
            product_name TEXT,
            category     TEXT,
            unit_price   REAL,
            stock_qty    INTEGER
        )
    """)
    rows = ddb.execute("SELECT * FROM erp.products").fetchall()
    scon.executemany(
        "INSERT INTO products VALUES (?, ?, ?, ?, ?)",
        [(r[0], r[1], r[2], float(r[3]), r[4]) for r in rows],
    )
    print(f"  SQLite: products             {len(rows)} rows (row 3 has NULL stock_qty)")

    scon.commit()
    scon.close()
    ddb.close()


if __name__ == "__main__":
    print("Creating CSV fixtures...")
    create_csv_fixtures()
    print("\nCreating SQLite fixture...")
    create_sqlite_fixture()
    print(f"\nDone. Files at {FIXTURES_DIR}")
