from __future__ import annotations

from pathlib import Path

import pytest

from yfharness.core.exceptions import PolicyDeniedError
from yfharness.core.models import ApprovalDecision, ApprovalRequest, ToolCall
from yfharness.core.policies import AgentMode
from yfharness.integrations.github import (
    GitHubError,
    GitHubService,
    _repository_from_remote,
    _validate_branch,
)
from yfharness.tools.base import ToolContext
from yfharness.tools.registry import ToolExecutor, builtin_tools
from yfharness.tools.security import WorkspaceGuard, github_cli_environment


@pytest.mark.parametrize(
    ("remote", "expected"),
    [
        ("https://github.com/owner/repo.git", "owner/repo"),
        ("git@github.com:owner/repo.git", "owner/repo"),
        ("ssh://git@github.com/owner/repo", "owner/repo"),
        ("http://github.com/owner/repo.git", None),
        ("https://gitlab.com/owner/repo.git", None),
    ],
)
def test_repository_scope_only_accepts_github_origin(remote: str, expected: str | None) -> None:
    assert _repository_from_remote(remote) == expected


@pytest.mark.parametrize("branch", ["../escape", "bad name", "-force", "main..other"])
def test_branch_validation_rejects_unsafe_names(branch: str) -> None:
    with pytest.raises(ValueError):
        _validate_branch(branch)


@pytest.mark.parametrize(
    "destination",
    [
        "https://example.test/leak.git",
        "git@github.com:other/repo.git",
        "git@github.com:owner/repo.git\ngit@github.com:other/repo.git",
    ],
)
def test_push_rejects_different_or_additional_destination(tmp_path: Path, destination: str) -> None:
    calls: list[list[str]] = []

    class ScopedGitHub(GitHubService):
        def _git(self, arguments: list[str], *, timeout: float = 30) -> str:
            calls.append(arguments)
            if "--push" in arguments:
                return destination
            return "git@github.com:owner/repo.git"

    service = ScopedGitHub(tmp_path)
    with pytest.raises(GitHubError, match="推送目标"):
        service.push()
    assert not any(call[0] == "push" for call in calls)


def test_github_environment_uses_user_state_not_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    environment = github_cli_environment({"PATH": "/usr/bin"})

    assert environment["HOME"] == str(Path.home())
    assert not (tmp_path / ".local").exists()


@pytest.mark.asyncio
async def test_github_read_uses_approval_and_marks_external_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    guard = WorkspaceGuard(tmp_path)
    approvals: list[ApprovalRequest] = []

    async def approve(request: ApprovalRequest) -> ApprovalDecision:
        approvals.append(request)
        return ApprovalDecision.ALLOW_ONCE

    class FakeGitHub:
        def __init__(self, workspace: Path) -> None:
            assert workspace == tmp_path

        def snapshot(self) -> dict[str, object]:
            return {"repository": "owner/repo", "private": True}

    monkeypatch.setattr("yfharness.tools.github.GitHubService", FakeGitHub)
    executor = ToolExecutor(
        builtin_tools(),
        ToolContext(workspace=tmp_path, guard=guard),
        mode=AgentMode.PLAN,
        approval_handler=approve,
    )

    result = await executor.execute(
        ToolCall(id="github-read", name="github_repo_status", arguments={})
    )

    assert approvals[0].network is True
    assert result.structured_data["trust"] == "external_untrusted"
    assert result.structured_data["private"] is True


@pytest.mark.asyncio
async def test_plan_mode_denies_github_remote_write_before_execution(tmp_path: Path) -> None:
    guard = WorkspaceGuard(tmp_path)
    executor = ToolExecutor(
        builtin_tools(), ToolContext(workspace=tmp_path, guard=guard), mode=AgentMode.PLAN
    )

    with pytest.raises(PolicyDeniedError, match="禁止工具"):
        await executor.execute(
            ToolCall(id="github-write", name="github_sync", arguments={"action": "push"})
        )
