from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


DEFAULT_CONFIG: dict[str, Any] = {
    "data_directory": "",
}


def get_config_dir() -> Path:
    override = os.environ.get("PANOPTIX_CONFIG_DIR")
    if override:
        return Path(override)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "Panoptix"
    return Path.home() / ".panoptix"


def get_config_path() -> Path:
    return get_config_dir() / "config.json"


def load_config() -> dict[str, Any]:
    path = get_config_path()
    if not path.exists():
        return dict(DEFAULT_CONFIG)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dict(DEFAULT_CONFIG)
    if not isinstance(data, dict):
        return dict(DEFAULT_CONFIG)
    return {**DEFAULT_CONFIG, **data}


def save_config(changes: dict[str, Any]) -> dict[str, Any]:
    config = load_config()
    for key in DEFAULT_CONFIG:
        if key in changes:
            config[key] = str(changes[key] or "").strip()
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return config


def get_configured_data_directory() -> str:
    return str(load_config().get("data_directory", "")).strip()


def set_configured_data_directory(directory: str) -> dict[str, Any]:
    return save_config({"data_directory": directory})
