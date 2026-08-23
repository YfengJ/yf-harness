"""Deterministic config precedence and environment interpolation."""

from __future__ import annotations

import os
import re
import tomllib
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from yfharness.config.models import AppConfig
from yfharness.config.paths import config_file
from yfharness.core.exceptions import HarnessError

_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class ConfigError(HarnessError):
    """A configuration file or override cannot be validated safely."""


def load_config(
    *,
    workspace: Path | None = None,
    user_path: Path | None = None,
    project_path: Path | None = None,
    environ: Mapping[str, str] | None = None,
    cli_overrides: Mapping[str, Any] | None = None,
) -> AppConfig:
    """Load defaults < user < project < environment < CLI."""

    root = (workspace or Path.cwd()).resolve()
    env = environ if environ is not None else os.environ
    merged = AppConfig(workspace=root).model_dump(mode="python")
    default_user_path = user_path or config_file()
    default_project_path = project_path or root / ".yfh" / "config.toml"
    for path in (default_user_path, default_project_path):
        if path.is_file():
            merged = _deep_merge(merged, _read_toml(path))
    merged = _deep_merge(merged, _environment_overrides(env))
    merged = _deep_merge(merged, dict(cli_overrides or {}))
    merged["workspace"] = root
    try:
        expanded = _expand_environment(merged, env)
        return AppConfig.model_validate(expanded)
    except (ValidationError, KeyError) as exc:
        raise ConfigError(f"配置无效: {exc}") from exc


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"无法读取配置 {path}: {exc}") from exc


def _deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(base))
    for key, value in override.items():
        existing = result.get(key)
        if isinstance(existing, Mapping) and isinstance(value, Mapping):
            result[key] = _deep_merge(existing, value)
        else:
            result[key] = deepcopy(value)
    return result


def _environment_overrides(env: Mapping[str, str]) -> dict[str, Any]:
    mapping = {
        "YFH_DEFAULT_PROVIDER": "default_provider",
        "YFH_DEFAULT_MODEL": "default_model",
        "YFH_LANGUAGE": "language",
    }
    return {config_key: env[env_key] for env_key, config_key in mapping.items() if env_key in env}


def _expand_environment(value: Any, env: Mapping[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _expand_environment(item, env) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_environment(item, env) for item in value]
    if isinstance(value, str):

        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in env:
                raise KeyError(f"缺少环境变量 {name}")
            return env[name]

        return _ENV_PATTERN.sub(replace, value)
    return value
