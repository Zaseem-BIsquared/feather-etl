"""Structural guard tests for the modular CLI layout."""

from __future__ import annotations

import inspect


def test_cli_has_no_inline_app_command_decorators() -> None:
    import feather_etl.cli

    assert "@app.command" not in inspect.getsource(feather_etl.cli)


def test_cli_registers_expected_commands_on_app() -> None:
    from feather_etl.cli import app

    registered_command_names = {
        command.name for command in app.registered_commands if command.name
    }

    assert registered_command_names == {
        "init",
        "validate",
        "discover",
        "view",
        "setup",
        "run",
        "history",
        "status",
    }


def test_command_modules_expose_register_functions() -> None:
    from feather_etl import commands

    module_names = [
        "init",
        "validate",
        "discover",
        "view",
        "setup",
        "run",
        "history",
        "status",
    ]

    for module_name in module_names:
        module = __import__(
            f"feather_etl.commands.{module_name}", fromlist=["register"]
        )
        assert callable(module.register)
