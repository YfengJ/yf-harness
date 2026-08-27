"""Static, workspace-local plugin discovery without automatic activation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import Field

from yfharness.core.models import DomainModel
from yfharness.tools.security import WorkspaceGuard

PluginCapabilityKind = Literal["rules", "skill", "command", "mcp", "hook"]
PluginPermission = Literal["read_workspace", "write_workspace", "execute", "network", "secrets"]


class PluginCapability(DomainModel):
    kind: PluginCapabilityKind
    path: str = Field(min_length=1, max_length=300)


class PluginManifest(DomainModel):
    schema_version: Literal[1] = 1
    id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=40)
    description: str = Field(default="", max_length=500)
    capabilities: list[PluginCapability] = Field(default_factory=list)
    requested_permissions: list[PluginPermission] = Field(default_factory=list)


class DiscoveredPlugin(DomainModel):
    manifest: PluginManifest
    manifest_path: str
    status: Literal["review_required"] = "review_required"
    warnings: list[str] = Field(default_factory=list)


def discover_plugins(workspace: Path, *, limit: int = 100) -> list[DiscoveredPlugin]:
    guard = WorkspaceGuard(workspace)
    root = guard.root / ".yfh" / "plugins"
    if not root.is_dir() or root.is_symlink():
        return []
    discovered: list[DiscoveredPlugin] = []
    for path in sorted(root.glob("*/plugin.json"))[:limit]:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 128_000:
            continue
        resolved = guard.resolve(path, must_exist=True)
        try:
            raw = json.loads(resolved.read_text(encoding="utf-8"))
            manifest = PluginManifest.model_validate(raw)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            continue
        warnings: list[str] = []
        if manifest.requested_permissions:
            warnings.append("需要用户审查权限；未自动激活")
        if any(item.kind in {"mcp", "hook"} for item in manifest.capabilities):
            warnings.append("MCP/Hook 声明不会自动执行")
        discovered.append(
            DiscoveredPlugin(
                manifest=manifest,
                manifest_path=guard.relative(resolved),
                warnings=warnings,
            )
        )
    return discovered
