import os
from pathlib import Path
from typing import Any, Dict

try:
    import tomllib
except ImportError:
    import tomli as tomllib


DEFAULT_CONFIG_PATHS = [
    "configs/aurora.toml",
    os.path.expanduser("~/.aurora/config.toml"),
]


def load_toml_config(path: str | None = None) -> Dict[str, Any]:
    if path is None:
        for candidate in DEFAULT_CONFIG_PATHS:
            if Path(candidate).exists():
                path = candidate
                break

    if path is None or not Path(path).exists():
        return {}

    with open(path, "rb") as f:
        return tomllib.load(f)
