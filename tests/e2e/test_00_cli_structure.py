"""Workflow stage 00: CLI surface — commands registered, --help renders.

Structural guards that pin the Typer app's registered commands and the
minimum viable `feather <cmd> --help` behaviour. These are e2e by the
"exercises the CLI" criterion even when they don't use CliRunner — a
broken CLI surface breaks every subsequent e2e test.
"""

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
        "cache",
    }


def test_command_modules_expose_register_functions() -> None:
    module_names = [
        "init",
        "validate",
        "discover",
        "view",
        "setup",
        "run",
        "history",
        "status",
        "cache",
    ]

    for module_name in module_names:
        module = __import__(
            f"feather_etl.commands.{module_name}", fromlist=["register"]
        )
        assert callable(module.register)


def test_feather_help_lists_cache(project, cli):
    result = cli("--help", config=False)
    assert result.exit_code == 0
    assert "cache" in result.output


def test_feather_cache_help_renders(project, cli):
    import re

    result = cli("cache", "--help")
    assert result.exit_code == 0
    # Strip ANSI escape sequences added by Rich so flag names aren't
    # split across styling boundaries (e.g. "-\x1b[0m\x1b[36m-table").
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    assert "--table" in plain
    assert "--source" in plain
    assert "--refresh" in plain
    assert "--config" in plain
