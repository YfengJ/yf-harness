"""Atomic persistence for app-owned, non-secret integration settings."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from yfharness.config.models import MCPServerSettings
from yfharness.config.paths import managed_config_file


def read_managed_config(path: Path | None = None) -> dict[str, Any]:
    target = path or managed_config_file()
    if not target.is_file():
        return {}
    value = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("托管集成配置必须是 JSON 对象")
    return value


def save_mcp_server(
    name: str,
    settings: MCPServerSettings | None,
    *,
    path: Path | None = None,
) -> None:
    target = path or managed_config_file()
    payload = read_managed_config(target)
    servers = payload.setdefault("mcp_servers", {})
    if not isinstance(servers, dict):
        raise ValueError("托管配置中的 mcp_servers 必须是对象")
    if settings is None:
        servers.pop(name, None)
    else:
        servers[name] = settings.model_dump(mode="json")
    _atomic_json(target, payload)


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        Path(temporary_name).replace(path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise
