"""Create PostgreSQL test fixture database matching sample_erp schema.

Requires: PostgreSQL running locally, psycopg2-binary installed.
Usage: uv run python scripts/create_postgres_test_fixture.py
"""

from __future__ import annotations

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


DB_NAME = "feather_test"
SCHEMA = "erp"

# Connection string for tests
CONN_STRING = f"dbname={DB_NAME} host=localhost"


def main() -> None:
    # Connect to default database to create test DB
    conn = psycopg2.connect("dbname=postgres host=localhost")
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()

    # Drop and recreate test database
    cur.execute(f"DROP DATABASE IF EXISTS {DB_NAME}")
    cur.execute(f"CREATE DATABASE {DB_NAME}")
    cur.close()
    conn.close()

    # Connect to test database and create schema + tables
    conn = psycopg2.connect(CONN_STRING)
    cur = conn.cursor()

    cur.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    # Sales table — matches sample_erp.duckdb erp.sales
    cur.execute(f"""
        CREATE TABLE {SCHEMA}.sales (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            product TEXT,
            amount DOUBLE PRECISION,
            modified_at TIMESTAMP
        )
    """)
    cur.execute(f"""
        INSERT INTO {SCHEMA}.sales (id, customer_id, product, amount, modified_at) VALUES
        (1, 101, 'Widget A', 100.0, '2026-01-01 10:00:00'),
        (2, 102, 'Widget B', 200.0, '2026-01-02 11:00:00'),
        (3, 101, 'Widget C', 150.0, '2026-01-03 12:00:00'),
        (4, 103, 'Widget A', 100.0, '2026-01-04 13:00:00'),
        (5, 102, 'Widget D', 300.0, '2026-01-05 14:00:00'),
        (6, 101, 'Widget B', 250.0, '2026-01-06 15:00:00'),
        (7, 104, 'Widget C', 175.0, '2026-01-07 16:00:00'),
        (8, 103, 'Widget A', 125.0, '2026-01-08 17:00:00'),
        (9, 102, 'Widget E', 400.0, '2026-01-09 18:00:00'),
        (10, 101, 'Widget D', 350.0, '2026-01-10 19:00:00')
    """)

    # Customers table — matches sample_erp.duckdb erp.customers
    cur.execute(f"""
        CREATE TABLE {SCHEMA}.customers (
            id INTEGER PRIMARY KEY,
            name TEXT,
            city TEXT,
            created_at TIMESTAMP
        )
    """)
    cur.execute(f"""
        INSERT INTO {SCHEMA}.customers (id, name, city, created_at) VALUES
        (101, 'Acme Corp', 'Mumbai', '2025-01-01 00:00:00'),
        (102, 'Beta Ltd', 'Delhi', '2025-02-01 00:00:00'),
        (103, 'Gamma Inc', 'Chennai', '2025-03-01 00:00:00'),
        (104, 'Delta Co', 'Bangalore', '2025-04-01 00:00:00')
    """)

    # Products table — matches sample_erp.duckdb erp.products
    cur.execute(f"""
        CREATE TABLE {SCHEMA}.products (
            id INTEGER PRIMARY KEY,
            name TEXT,
            category TEXT,
            price DOUBLE PRECISION
        )
    """)
    cur.execute(f"""
        INSERT INTO {SCHEMA}.products (id, name, category, price) VALUES
        (1, 'Widget A', 'Standard', 100.0),
        (2, 'Widget B', 'Standard', 200.0),
        (3, 'Widget C', 'Premium', 150.0),
        (4, 'Widget D', 'Premium', 300.0),
        (5, 'Widget E', 'Deluxe', 400.0)
    """)

    conn.commit()
    cur.close()
    conn.close()

    print(f"Created database '{DB_NAME}' with schema '{SCHEMA}'")
    print("  erp.sales: 10 rows")
    print("  erp.customers: 4 rows")
    print("  erp.products: 5 rows")
    print(f"  Connection string: {CONN_STRING}")


if __name__ == "__main__":
    main()
