"""Twenty offline cases spanning the first-release acceptance risks."""

from __future__ import annotations

import asyncio
import sys
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path

from yfharness.core.agent import AgentLimits, AgentRunner
from yfharness.core.context import ContextBuilder
from yfharness.core.exceptions import PolicyDeniedError
from yfharness.core.models import (
    ApprovalDecision,
    ApprovalRequest,
    Message,
    MessageRole,
    ModelConfig,
    RunStatus,
    ToolCall,
)
from yfharness.core.policies import AgentMode
from yfharness.providers.mock import MockFailure, MockProvider, MockScript
from yfharness.storage.database import Database
from yfharness.storage.repositories import RunRepository, SessionRepository
from yfharness.tools.base import ToolContext
from yfharness.tools.patch import create_patch
from yfharness.tools.registry import ToolExecutor, builtin_tools
from yfharness.tools.security import WorkspaceGuard


async def allow(_: ApprovalRequest) -> ApprovalDecision:
    return ApprovalDecision.ALLOW_ONCE


async def deny(_: ApprovalRequest) -> ApprovalDecision:
    return ApprovalDecision.DENY


def model(*, native: bool = True, context_window: int = 32_000) -> ModelConfig:
    return ModelConfig(
        id="scripted",
        provider="mock",
        model="scripted",
        supports_native_tools=native,
        context_window=context_window,
        max_output_tokens=100,
    )


def tools(
    workspace: Path, approval: Callable[[ApprovalRequest], Awaitable[ApprovalDecision]] = allow
) -> ToolExecutor:
    guard = WorkspaceGuard(workspace)
    return ToolExecutor(
        builtin_tools(), ToolContext(workspace=guard.root, guard=guard), approval_handler=approval
    )


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


async def conversation(workspace: Path) -> tuple[bool, int, int, str]:
    result = await AgentRunner(
        provider=MockProvider(response="hello"), model=model(), tools=tools(workspace)
    ).run("hello", session_id="eval")
    return result.final_text == "hello", result.run.step_count, 0, result.run.error or ""


async def streaming_text(workspace: Path) -> tuple[bool, int, int, str]:
    result = await AgentRunner(
        provider=MockProvider(scripts=[MockScript(chunks=["a", "b", "c"])]),
        model=model(),
        tools=tools(workspace),
    ).run("stream", session_id="eval")
    return result.final_text == "abc", result.run.step_count, 0, result.run.error or ""


async def _tool_round_trip(
    workspace: Path, call: ToolCall, *, setup: Callable[[], None] | None = None
) -> tuple[bool, int, int, str]:
    if setup:
        setup()
    result = await AgentRunner(
        provider=MockProvider(scripts=[MockScript(tool_call=call), MockScript(text="done")]),
        model=model(),
        tools=tools(workspace),
    ).run("tool", session_id="eval")
    success = result.run.status is RunStatus.COMPLETED and any(
        message.role is MessageRole.TOOL and '"success":true' in message.text_content
        for message in result.messages
    )
    return success, result.run.step_count, 0 if success else 1, result.run.error or ""


async def read_file(workspace: Path) -> tuple[bool, int, int, str]:
    return await _tool_round_trip(
        workspace,
        ToolCall(id="read", name="read_file", arguments={"path": "a.txt"}),
        setup=lambda: _write(workspace / "a.txt", "real"),
    )


async def search_text(workspace: Path) -> tuple[bool, int, int, str]:
    return await _tool_round_trip(
        workspace,
        ToolCall(id="search", name="search_text", arguments={"query": "needle"}),
        setup=lambda: _write(workspace / "a.txt", "needle"),
    )


async def create_file(workspace: Path) -> tuple[bool, int, int, str]:
    outcome = await _tool_round_trip(
        workspace,
        ToolCall(id="write", name="write_file", arguments={"path": "created.txt", "content": "ok"}),
    )
    return (workspace / "created.txt").read_text(encoding="utf-8") == "ok", *outcome[1:]


async def apply_patch(workspace: Path) -> tuple[bool, int, int, str]:
    old, new = "old\n", "new\n"
    (workspace / "a.txt").write_text(old, encoding="utf-8")
    outcome = await _tool_round_trip(
        workspace,
        ToolCall(
            id="patch",
            name="apply_patch",
            arguments={"path": "a.txt", "patch": create_patch("a.txt", old, new)},
        ),
    )
    return (workspace / "a.txt").read_text(encoding="utf-8") == new, *outcome[1:]


async def shell_approval(workspace: Path) -> tuple[bool, int, int, str]:
    seen = 0

    async def approve(_: ApprovalRequest) -> ApprovalDecision:
        nonlocal seen
        seen += 1
        return ApprovalDecision.ALLOW_ONCE

    executor = tools(workspace, approve)
    result = await executor.execute(
        ToolCall(id="shell", name="run_command", arguments={"command": ["echo", "ok"]})
    )
    return result.success and seen == 1, 0, 0 if result.success else 1, result.summary


async def rejected_approval(workspace: Path) -> tuple[bool, int, int, str]:
    executor = tools(workspace, deny)
    try:
        await executor.execute(
            ToolCall(id="write", name="write_file", arguments={"path": "bad", "content": "bad"})
        )
    except PolicyDeniedError:
        return not (workspace / "bad").exists(), 0, 0, "denied"
    return False, 0, 1, "unexpected execution"


async def invalid_arguments_repair(workspace: Path) -> tuple[bool, int, int, str]:
    bad = ToolCall(id="bad", name="read_file", arguments={"path": "x", "extra": 1})
    result = await AgentRunner(
        provider=MockProvider(scripts=[MockScript(tool_call=bad), MockScript(text="fixed")]),
        model=model(),
        tools=tools(workspace),
    ).run("repair", session_id="eval")
    ok = result.run.status is RunStatus.COMPLETED and any(
        "工具参数无效" in message.text_content for message in result.messages
    )
    return ok, result.run.step_count, 1, result.run.error or ""


async def unknown_tool(workspace: Path) -> tuple[bool, int, int, str]:
    call = ToolCall(id="unknown", name="does_not_exist", arguments={})
    result = await AgentRunner(
        provider=MockProvider(scripts=[MockScript(tool_call=call), MockScript(text="recovered")]),
        model=model(),
        tools=tools(workspace),
    ).run("unknown", session_id="eval")
    ok = result.run.status is RunStatus.COMPLETED and any(
        "未知工具" in message.text_content for message in result.messages
    )
    return ok, result.run.step_count, 1, result.run.error or ""


async def max_steps(workspace: Path) -> tuple[bool, int, int, str]:
    call = ToolCall(id="read", name="read_file", arguments={"path": "missing"})
    result = await AgentRunner(
        provider=MockProvider(scripts=[MockScript(tool_call=call)]),
        model=model(),
        tools=tools(workspace),
        limits=AgentLimits(max_steps=1),
    ).run("bounded", session_id="eval")
    return result.run.status is RunStatus.FAILED, result.run.step_count, 1, result.run.error or ""


async def repeated_call(workspace: Path) -> tuple[bool, int, int, str]:
    call = ToolCall(id="repeat", name="read_file", arguments={"path": "missing"})
    result = await AgentRunner(
        provider=MockProvider(scripts=[MockScript(tool_call=call) for _ in range(3)]),
        model=model(),
        tools=tools(workspace),
        limits=AgentLimits(max_repeated_tool_calls=2),
    ).run("repeat", session_id="eval")
    return (
        "重复工具调用" in (result.run.error or ""),
        result.run.step_count,
        2,
        result.run.error or "",
    )


async def provider_timeout(workspace: Path) -> tuple[bool, int, int, str]:
    result = await AgentRunner(
        provider=MockProvider(scripts=[MockScript(failure=MockFailure.TIMEOUT, delay_seconds=60)]),
        model=model(),
        tools=tools(workspace),
        limits=AgentLimits(max_run_seconds=0.02),
    ).run("timeout", session_id="eval")
    return result.run.status is RunStatus.FAILED, result.run.step_count, 0, result.run.error or ""


async def stream_interruption(workspace: Path) -> tuple[bool, int, int, str]:
    result = await AgentRunner(
        provider=MockProvider(
            scripts=[MockScript(chunks=["partial", "later"], failure=MockFailure.INTERRUPT)]
        ),
        model=model(),
        tools=tools(workspace),
    ).run("interrupt", session_id="eval")
    return result.run.status is RunStatus.FAILED, result.run.step_count, 0, result.run.error or ""


async def context_compaction(workspace: Path) -> tuple[bool, int, int, str]:
    builder = ContextBuilder(
        workspace,
        lambda text: max(1, len(text) // 2),
        recent_messages=2,
        compaction_threshold=0.5,
    )
    history = [Message.text(MessageRole.USER, "必须保留 " + "x" * 100) for _ in range(8)]
    snapshot = builder.build(
        user_input="latest",
        history=history,
        mode=AgentMode.AGENT,
        tools=[],
        model=model(context_window=800),
        native_tools=True,
    )
    return snapshot.compacted and snapshot.summary is not None, 0, 0, ""


async def path_traversal(workspace: Path) -> tuple[bool, int, int, str]:
    try:
        WorkspaceGuard(workspace).resolve("../secret")
    except PolicyDeniedError:
        return True, 0, 0, "blocked"
    return False, 0, 1, "escape allowed"


async def symlink_escape(workspace: Path) -> tuple[bool, int, int, str]:
    with tempfile.TemporaryDirectory(prefix="yfh-eval-outside-") as outside_directory:
        outside = Path(outside_directory)
        (workspace / "link").symlink_to(outside, target_is_directory=True)
        try:
            WorkspaceGuard(workspace).resolve("link/new")
        except PolicyDeniedError:
            return True, 0, 0, "blocked"
        return False, 0, 1, "symlink escape allowed"


async def shell_timeout(workspace: Path) -> tuple[bool, int, int, str]:
    result = await tools(workspace).execute(
        ToolCall(
            id="timeout",
            name="run_command",
            arguments={
                "command": [sys.executable, "-c", "import time; time.sleep(2)"],
                "timeout_seconds": 0.02,
            },
        )
    )
    return result.error_type == "timeout", 0, 1, result.summary


async def user_cancel(workspace: Path) -> tuple[bool, int, int, str]:
    runner = AgentRunner(
        provider=MockProvider(scripts=[MockScript(failure=MockFailure.TIMEOUT, delay_seconds=60)]),
        model=model(),
        tools=tools(workspace),
    )
    task = asyncio.create_task(runner.run("cancel", session_id="eval"))
    await asyncio.sleep(0.01)
    runner.cancel()
    result = await task
    return (
        result.run.status is RunStatus.CANCELLED,
        result.run.step_count,
        0,
        result.run.error or "",
    )


async def session_recovery(workspace: Path) -> tuple[bool, int, int, str]:
    database = Database(workspace / "sessions.sqlite3")
    await database.initialize()
    sessions = SessionRepository(database)
    runs = RunRepository(database)
    session = await sessions.create(title="recover", provider="mock", model="scripted")
    run = await runs.create(session.id)
    # Simulate a legacy/orphaned run, not a run owned by this live process.
    async with database.connect() as connection:
        await connection.execute("UPDATE runs SET owner_pid=NULL WHERE run_id=?", (run.run_id,))
        await connection.commit()
    await runs.mark_interrupted()
    recovered = await runs.get(run.run_id)
    return recovered is not None and recovered.status is RunStatus.INTERRUPTED, 0, 0, ""


CaseFunction = Callable[[Path], Awaitable[tuple[bool, int, int, str]]]

CASES: list[tuple[str, CaseFunction]] = [
    ("普通对话", conversation),
    ("流式文本", streaming_text),
    ("读取文件", read_file),
    ("搜索文本", search_text),
    ("创建文件", create_file),
    ("应用补丁", apply_patch),
    ("Shell 审批", shell_approval),
    ("用户拒绝审批", rejected_approval),
    ("工具参数修复", invalid_arguments_repair),
    ("未知工具", unknown_tool),
    ("最大步骤", max_steps),
    ("重复工具调用", repeated_call),
    ("Provider 超时", provider_timeout),
    ("Provider 流中断", stream_interruption),
    ("上下文压缩", context_compaction),
    ("路径穿越", path_traversal),
    ("符号链接逃逸", symlink_escape),
    ("Shell 超时", shell_timeout),
    ("用户取消", user_cancel),
    ("会话恢复", session_recovery),
]


def temporary_workspace() -> tempfile.TemporaryDirectory[str]:
    return tempfile.TemporaryDirectory(prefix="yfh-eval-")
