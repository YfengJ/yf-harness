from __future__ import annotations

from pathlib import Path

import pytest

from yfharness.core.models import ToolCall
from yfharness.tools.base import ToolContext
from yfharness.tools.registry import ToolExecutor, builtin_tools
from yfharness.tools.security import WorkspaceGuard
from yfharness.tools.shell import execute_command


@pytest.mark.asyncio
async def test_git_status_executes_real_git(tmp_path: Path) -> None:
    initialized = await execute_command(
        ["git", "init"],
        cwd=tmp_path,
        shell=False,
        timeout_seconds=10,
        output_limit=10_000,
        tool_call_id="setup",
    )
    assert initialized.success
    (tmp_path / "new.txt").write_text("new", encoding="utf-8")
    guard = WorkspaceGuard(tmp_path)
    executor = ToolExecutor(builtin_tools(), ToolContext(workspace=guard.root, guard=guard))

    status = await executor.execute(ToolCall(id="git", name="git_status", arguments={}))

    assert status.success
    assert "new.txt" in status.stdout


def test_builtin_registry_contains_required_first_release_tools() -> None:
    assert set(builtin_tools().names()) == {
        "apply_patch",
        "create_directory",
        "delete_path",
        "find_files",
        "get_file_info",
        "git_diff",
        "git_log",
        "git_status",
        "github_actions_list",
        "github_actions_rerun_failed",
        "github_branch_create",
        "github_comment",
        "github_issue_create",
        "github_issue_list",
        "github_pr_create",
        "github_pr_list",
        "github_repo_status",
        "github_sync",
        "list_directory",
        "move_path",
        "read_file",
        "run_command",
        "run_tests",
        "search_text",
        "write_file",
    }
