from __future__ import annotations

from pathlib import Path

from feather_etl.commands.discover import _expand_db_sources
from feather_etl.sources.postgres import PostgresSource


def _make_postgres_source(
    *,
    explicit_name: bool,
    database: str | None = None,
    databases: list[str] | None = None,
) -> PostgresSource:
    entry: dict[str, object] = {
        "type": "postgres",
        "host": "localhost",
        "user": "tester",
        "password": "secret",
    }
    if explicit_name:
        entry["name"] = "warehouse"
    if database is not None:
        entry["database"] = database
    if databases is not None:
        entry["databases"] = databases
    return PostgresSource.from_yaml(entry, Path("."))


def test_expand_db_sources_children_inherit_explicit_true_from_parent() -> None:
    parent = _make_postgres_source(explicit_name=True, databases=["sales", "erp"])

    expanded = _expand_db_sources([parent])

    assert len(expanded) == 2
    assert all(child._explicit_name is True for child in expanded)


def test_expand_db_sources_children_inherit_explicit_false_from_parent() -> None:
    parent = _make_postgres_source(explicit_name=False)
    parent.list_databases = lambda: ["sales", "erp"]  # type: ignore[method-assign]

    expanded = _expand_db_sources([parent])

    assert len(expanded) == 2
    assert all(child._explicit_name is False for child in expanded)


def test_expand_db_sources_with_concrete_database_is_unchanged_and_preserves_flag() -> None:
    parent = _make_postgres_source(explicit_name=False, database="sales")

    expanded = _expand_db_sources([parent])

    assert expanded == [parent]
    assert expanded[0]._explicit_name is False
