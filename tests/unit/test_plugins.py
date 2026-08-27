from __future__ import annotations

import json
from pathlib import Path

from yfharness.core.plugins import discover_plugins


def test_plugin_discovery_is_static_and_marks_permissions_for_review(tmp_path: Path) -> None:
    plugin = tmp_path / ".yfh" / "plugins" / "reviewer"
    plugin.mkdir(parents=True)
    (plugin / "plugin.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "reviewer",
                "name": "Reviewer",
                "version": "1.0.0",
                "capabilities": [
                    {"kind": "rules", "path": "rules/review.md"},
                    {"kind": "mcp", "path": "mcp.json"},
                ],
                "requested_permissions": ["read_workspace", "network"],
            }
        ),
        encoding="utf-8",
    )

    discovered = discover_plugins(tmp_path)

    assert len(discovered) == 1
    assert discovered[0].status == "review_required"
    assert discovered[0].manifest.id == "reviewer"
    assert any("MCP/Hook" in warning for warning in discovered[0].warnings)


def test_plugin_discovery_skips_invalid_or_unknown_schema(tmp_path: Path) -> None:
    plugin = tmp_path / ".yfh" / "plugins" / "invalid"
    plugin.mkdir(parents=True)
    (plugin / "plugin.json").write_text(
        '{"schema_version": 2, "id": "invalid", "name": "Invalid", "version": "1"}',
        encoding="utf-8",
    )

    assert discover_plugins(tmp_path) == []
