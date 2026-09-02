"""One place for all user-level storage paths."""

from __future__ import annotations

import os
from pathlib import Path

from platformdirs import user_config_path, user_data_path, user_log_path

APP_NAME = "YF-Harness"
APP_AUTHOR = "YF-Harness"


def config_dir() -> Path:
    if override := os.environ.get("YFH_CONFIG_DIR"):
        return Path(override).expanduser()
    return Path(user_config_path(APP_NAME, APP_AUTHOR))


def config_file() -> Path:
    return config_dir() / "config.toml"


def managed_config_file() -> Path:
    """App-owned non-secret integration settings kept separate from hand-written TOML."""

    return config_dir() / "managed-integrations.json"


def data_dir() -> Path:
    if override := os.environ.get("YFH_DATA_DIR"):
        return Path(override).expanduser()
    return Path(user_data_path(APP_NAME, APP_AUTHOR))


def log_dir() -> Path:
    if override := os.environ.get("YFH_LOG_DIR"):
        return Path(override).expanduser()
    return Path(user_log_path(APP_NAME, APP_AUTHOR))


def database_file() -> Path:
    return data_dir() / "yfharness.sqlite3"
