from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from yfharness.core.exceptions import PolicyDeniedError, ToolExecutionError
from yfharness.core.models import ApprovalDecision, ApprovalRequest, ToolCall, ToolRiskLevel
from yfharness.tools.base import ToolContext
from yfharness.tools.changes import ChangeJournal
from yfharness.tools.patch import create_patch
from yfharness.tools.registry import ToolExecutor, builtin_tools
from yfharness.tools.security import WorkspaceGuard, sanitized_environment


def make_context(workspace: Path, *, output_limit: int = 100_000) -> ToolContext:
    guard = WorkspaceGuard(workspace)
    return ToolContext(
        workspace=guard.root,
        guard=guard,
        changes=ChangeJournal(guard),
        output_limit=output_limit,
    )


async def allow(_: ApprovalRequest) -> ApprovalDecision:
    return ApprovalDecision.ALLOW_ONCE


@pytest.mark.asyncio
async def test_read_search_find_and_file_info(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_bytes(b"alpha\nbeta\n")
    executor = ToolExecutor(builtin_tools(), make_context(tmp_path))

    read = await executor.execute(
        ToolCall(id="1", name="read_file", arguments={"path": "src/a.py"})
    )
    search = await executor.execute(
        ToolCall(id="2", name="search_text", arguments={"query": "BETA", "path": "src"})
    )
    found = await executor.execute(
        ToolCall(id="3", name="find_files", arguments={"pattern": "*.py"})
    )
    info = await executor.execute(
        ToolCall(id="4", name="get_file_info", arguments={"path": "src/a.py"})
    )

    assert read.stdout == "alpha\nbeta\n"
    assert search.structured_data["matches"][0]["line"] == 2  # type: ignore[index]
    assert found.structured_data["paths"] == ["src/a.py"]
    assert info.structured_data["is_file"] is True


@pytest.mark.asyncio
async def test_write_preview_and_undo(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    target.write_text("old\n", encoding="utf-8")
    requests: list[ApprovalRequest] = []
    context = make_context(tmp_path)

    async def approve(request: ApprovalRequest) -> ApprovalDecision:
        requests.append(request)
        return ApprovalDecision.ALLOW_ONCE

    executor = ToolExecutor(builtin_tools(), context, approval_handler=approve)
    result = await executor.execute(
        ToolCall(
            id="write",
            name="write_file",
            arguments={"path": "file.txt", "content": "new\n"},
        )
    )

    assert result.success and target.read_text(encoding="utf-8") == "new\n"
    assert "-old" in (requests[0].diff_preview or "")
    assert context.changes is not None
    context.changes.undo_last()
    assert target.read_text(encoding="utf-8") == "old\n"


@pytest.mark.asyncio
async def test_move_overwrite_can_restore_both_files(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    destination = tmp_path / "destination.txt"
    source.write_text("source", encoding="utf-8")
    destination.write_text("destination", encoding="utf-8")
    context = make_context(tmp_path)
    executor = ToolExecutor(builtin_tools(), context, approval_handler=allow)

    result = await executor.execute(
        ToolCall(
            id="move",
            name="move_path",
            arguments={
                "source": "source.txt",
                "destination": "destination.txt",
                "overwrite": True,
            },
        )
    )
    assert result.success and destination.read_text(encoding="utf-8") == "source"
    assert context.changes is not None
    context.changes.undo_last()
    assert source.read_text(encoding="utf-8") == "source"
    assert destination.read_text(encoding="utf-8") == "destination"


@pytest.mark.asyncio
async def test_apply_patch_is_real_and_rejects_stale_context(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    old = "one\ntwo\nthree\n"
    new = "one\nTWO\nthree\n"
    target.write_text(old, encoding="utf-8")
    executor = ToolExecutor(builtin_tools(), make_context(tmp_path), approval_handler=allow)

    result = await executor.execute(
        ToolCall(
            id="patch",
            name="apply_patch",
            arguments={"path": "file.txt", "patch": create_patch("file.txt", old, new)},
        )
    )
    assert result.success and target.read_text(encoding="utf-8") == new

    with pytest.raises(ToolExecutionError, match="上下文不匹配"):
        await executor.execute(
            ToolCall(
                id="stale",
                name="apply_patch",
                arguments={"path": "file.txt", "patch": create_patch("file.txt", old, "changed\n")},
            )
        )


@pytest.mark.asyncio
async def test_apply_patch_preserves_crlf_line_endings(tmp_path: Path) -> None:
    target = tmp_path / "windows.txt"
    old = "one\ntwo\nthree\n"
    new = "one\nTWO\nthree\n"
    target.write_bytes(old.replace("\n", "\r\n").encode())
    executor = ToolExecutor(builtin_tools(), make_context(tmp_path), approval_handler=allow)

    result = await executor.execute(
        ToolCall(
            id="patch-crlf",
            name="apply_patch",
            arguments={"path": "windows.txt", "patch": create_patch("windows.txt", old, new)},
        )
    )

    assert result.success
    assert target.read_bytes() == new.replace("\n", "\r\n").encode()


@pytest.mark.asyncio
async def test_shell_output_limit_and_secret_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VERY_SECRET_API_KEY", "must-not-leak")
    executor = ToolExecutor(
        builtin_tools(), make_context(tmp_path, output_limit=20), approval_handler=allow
    )
    code = "import os; print(os.getenv('VERY_SECRET_API_KEY', '')); print('x' * 100)"
    result = await executor.execute(
        ToolCall(
            id="command",
            name="run_command",
            arguments={"command": [sys.executable, "-c", code]},
        )
    )

    assert result.success
    assert "must-not-leak" not in result.stdout
    assert result.truncated
    assert "truncated" in result.stdout
    assert "VERY_SECRET_API_KEY" not in sanitized_environment(dict(os.environ))


@pytest.mark.asyncio
async def test_shell_timeout_kills_process_group(tmp_path: Path) -> None:
    marker = tmp_path / "should-not-exist"
    child_code = f"import time; time.sleep(0.6); open({str(marker)!r}, 'w').write('bad')"
    parent_code = (
        "import subprocess,sys,time; "
        f"subprocess.Popen([sys.executable, '-c', {child_code!r}]); time.sleep(5)"
    )
    executor = ToolExecutor(builtin_tools(), make_context(tmp_path), approval_handler=allow)
    result = await executor.execute(
        ToolCall(
            id="timeout",
            name="run_command",
            arguments={
                "command": [sys.executable, "-c", parent_code],
                "timeout_seconds": 0.1,
            },
        )
    )
    await __import__("asyncio").sleep(0.8)

    assert result.error_type == "timeout"
    assert not marker.exists()


@pytest.mark.asyncio
async def test_network_command_is_critical_and_requires_approval(tmp_path: Path) -> None:
    seen: list[ApprovalRequest] = []

    async def deny(request: ApprovalRequest) -> ApprovalDecision:
        seen.append(request)
        return ApprovalDecision.DENY

    executor = ToolExecutor(builtin_tools(), make_context(tmp_path), approval_handler=deny)
    with pytest.raises(PolicyDeniedError, match="用户拒绝"):
        await executor.execute(
            ToolCall(
                id="network",
                name="run_command",
                arguments={"command": ["curl", "https://example.com"]},
            )
        )
    assert seen[0].risk_level is ToolRiskLevel.CRITICAL
