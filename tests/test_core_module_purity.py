"""Purity test: pure-core modules must not import Typer.

The split between `commands/<name>.py` (Typer-aware CLI wrapper) and
`<name>.py` (pure orchestration) is a load-bearing architectural
constraint enforced here. If you find yourself wanting to add `typer`
to a module in this list, the split is wrong — push the Typer concern
back into the corresponding `commands/<name>.py` wrapper instead.
"""

from __future__ import annotations

import importlib
import inspect

import pytest

CORE_MODULES = [
    "feather_etl.pipeline",
    "feather_etl.cache",
    "feather_etl.viewer_server",
    "feather_etl.init_wizard",
    "feather_etl.exceptions",
    "feather_etl.history",
    "feather_etl.status",
]


@pytest.mark.parametrize("module_name", CORE_MODULES)
def test_core_module_does_not_import_typer(module_name: str) -> None:
    module = importlib.import_module(module_name)
    source = inspect.getsource(module)
    assert "import typer" not in source, (
        f"{module_name} must not import typer — push the Typer concern "
        f"into the corresponding commands/<name>.py wrapper."
    )
    assert "from typer" not in source, (
        f"{module_name} must not import from typer — push the Typer concern "
        f"into the corresponding commands/<name>.py wrapper."
    )
