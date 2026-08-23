from __future__ import annotations

from pathlib import Path

import pytest

from yfharness.core.exceptions import PolicyDeniedError
from yfharness.core.models import ApprovalDecision, ApprovalRequest, ToolCall
from yfharness.core.policies import AgentMode, ApprovalPolicy
from yfharness.tools.base import ToolContext
from yfharness.tools.registry import ToolExecutor, builtin_tools
from yfharness.tools.security import WorkspaceGuard


def context(workspace: Path) -> ToolContext:
    guard = WorkspaceGuard(workspace)
    return ToolContext(workspace=guard.root, guard=guard)


def test_guard_blocks_parent_and_absolute_escape(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    guard = WorkspaceGuard(workspace)

    with pytest.raises(PolicyDeniedError):
        guard.resolve("../outside.txt", must_exist=True)
    with pytest.raises(PolicyDeniedError):
        guard.resolve(outside, must_exist=True)


def test_guard_blocks_symlink_escape_for_read_and_write(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("secret", encoding="utf-8")
    (workspace / "link").symlink_to(outside, target_is_directory=True)
    guard = WorkspaceGuard(workspace)

    with pytest.raises(PolicyDeniedError):
        guard.resolve("link/secret.txt", must_exist=True)
    with pytest.raises(PolicyDeniedError):
        guard.resolve("link/new.txt")


@pytest.mark.asyncio
async def test_search_does_not_follow_symlink_files(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("unique-secret-text", encoding="utf-8")
    (workspace / "linked.txt").symlink_to(outside)
    executor = ToolExecutor(builtin_tools(), context(workspace))

    result = await executor.execute(
        ToolCall(id="search", name="search_text", arguments={"query": "unique-secret-text"})
    )
    assert result.structured_data["matches"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", [AgentMode.CHAT, AgentMode.PLAN, AgentMode.REVIEW])
async def test_read_only_modes_cannot_write(tmp_path: Path, mode: AgentMode) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    executor = ToolExecutor(
        builtin_tools(),
        context(workspace),
        mode=mode,
        policy=ApprovalPolicy.FULL_AUTO,
        full_auto_enabled=True,
    )

    with pytest.raises(PolicyDeniedError):
        await executor.execute(
            ToolCall(id="write-1", name="write_file", arguments={"path": "x.txt", "content": "x"})
        )
    assert not (workspace / "x.txt").exists()


@pytest.mark.asyncio
async def test_rejected_tool_never_executes(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    async def deny(_: ApprovalRequest) -> ApprovalDecision:
        return ApprovalDecision.DENY

    executor = ToolExecutor(builtin_tools(), context(workspace), approval_handler=deny)
    with pytest.raises(PolicyDeniedError, match="用户拒绝"):
        await executor.execute(
            ToolCall(id="write-1", name="write_file", arguments={"path": "x.txt", "content": "x"})
        )
    assert not (workspace / "x.txt").exists()


@pytest.mark.asyncio
async def test_delete_always_requires_approval_even_full_auto(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "keep.txt"
    target.write_text("keep", encoding="utf-8")

    async def deny(_: ApprovalRequest) -> ApprovalDecision:
        return ApprovalDecision.DENY

    executor = ToolExecutor(
        builtin_tools(),
        context(workspace),
        policy=ApprovalPolicy.FULL_AUTO,
        full_auto_enabled=True,
        approval_handler=deny,
    )
    with pytest.raises(PolicyDeniedError):
        await executor.execute(
            ToolCall(id="delete-1", name="delete_path", arguments={"path": "keep.txt"})
        )
    assert target.exists()


@pytest.mark.asyncio
async def test_full_auto_is_disabled_by_default(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    executor = ToolExecutor(builtin_tools(), context(workspace), policy=ApprovalPolicy.FULL_AUTO)

    with pytest.raises(PolicyDeniedError):
        await executor.execute(
            ToolCall(id="write-1", name="write_file", arguments={"path": "x", "content": "x"})
        )
