from __future__ import annotations

import sys
from pathlib import Path

import pytest

from yfharness.config.models import AppConfig, MCPServerSettings, MCPToolPolicy
from yfharness.core.exceptions import PolicyDeniedError, ToolExecutionError
from yfharness.core.models import ApprovalDecision, ToolCall, ToolRiskLevel
from yfharness.core.policies import ApprovalPolicy
from yfharness.integrations.mcp import register_mcp_tools
from yfharness.tools.base import ToolContext
from yfharness.tools.registry import ToolExecutor, ToolRegistry
from yfharness.tools.security import WorkspaceGuard

_SERVER = Path(__file__).parents[1] / "fixtures" / "mcp_stdio_server.py"


def config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        workspace=tmp_path,
        mcp_servers={
            "fixture": MCPServerSettings(
                command=[sys.executable, str(_SERVER)],
                enabled=True,
                enabled_tools=["echo", "hidden"],
                disabled_tools=["hidden"],
                env_keys=["MCP_ALLOWED"],
            )
        },
    )


@pytest.mark.asyncio
async def test_mcp_discovery_filters_names_and_ignores_trust_annotations(tmp_path: Path) -> None:
    registry = ToolRegistry()

    names = await register_mcp_tools(registry, config(tmp_path), tmp_path)

    assert names == ["mcp__fixture__echo"]
    definition = registry.definitions()[0]
    assert definition.risk_level is ToolRiskLevel.HIGH
    assert definition.read_only is False


@pytest.mark.asyncio
async def test_mcp_tool_uses_existing_approval_and_env_allowlist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCP_ALLOWED", "yes")
    monkeypatch.setenv("MCP_SECRET", "must-not-pass")
    registry = ToolRegistry()
    await register_mcp_tools(registry, config(tmp_path), tmp_path)
    context = ToolContext(workspace=tmp_path, guard=WorkspaceGuard(tmp_path), run_id="run")
    denied = ToolExecutor(registry, context, policy=ApprovalPolicy.SAFE_AUTO)
    call = ToolCall(id="call", name="mcp__fixture__echo", arguments={"value": "hello"})

    with pytest.raises(PolicyDeniedError, match="需要审批"):
        await denied.execute(call)

    async def approve(_: object) -> ApprovalDecision:
        return ApprovalDecision.ALLOW_ONCE

    allowed = ToolExecutor(
        registry,
        context,
        policy=ApprovalPolicy.SAFE_AUTO,
        approval_handler=approve,
    )
    result = await allowed.execute(call)
    assert result.success is True
    assert result.structured_data == {"echo": "hello"}
    assert "allowed=yes" in result.stdout
    assert "must-not-pass" not in result.stdout


@pytest.mark.asyncio
async def test_mcp_schema_is_checked_before_approval(tmp_path: Path) -> None:
    registry = ToolRegistry()
    await register_mcp_tools(registry, config(tmp_path), tmp_path)
    context = ToolContext(workspace=tmp_path, guard=WorkspaceGuard(tmp_path))
    executor = ToolExecutor(registry, context, policy=ApprovalPolicy.ALWAYS_ASK)

    with pytest.raises(ToolExecutionError, match="missing required"):
        await executor.execute(ToolCall(id="bad", name="mcp__fixture__echo", arguments={}))


@pytest.mark.asyncio
async def test_local_override_can_expose_known_mcp_search_as_read_only(tmp_path: Path) -> None:
    app_config = config(tmp_path)
    settings = app_config.mcp_servers["fixture"]
    settings.tool_overrides["echo"] = MCPToolPolicy(
        read_only=True,
        risk_level=ToolRiskLevel.MEDIUM,
        always_approval=False,
        network=True,
    )
    registry = ToolRegistry()
    await register_mcp_tools(registry, app_config, tmp_path)

    definition = registry.definitions()[0]
    assert definition.read_only is True
    assert definition.risk_level is ToolRiskLevel.MEDIUM
