"""Shared test utility functions."""

from pathlib import Path

import yaml


def write_config(tmp_path: Path, config: dict, directory: Path | None = None) -> Path:
    config_file = (directory or tmp_path) / "feather.yaml"
    config_file.write_text(yaml.dump(config, default_flow_style=False))
    return config_file
