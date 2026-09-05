"""Read-only Git inspection tools."""

from __future__ import annotations

from pydantic import Field

from yfharness.core.models import ToolResult
from yfharness.tools.base import Tool, ToolContext, ToolInput
from yfharness.tools.shell import execute_command


class GitStatusInput(ToolInput):
    short: bool = True


class GitStatusTool(Tool):
    name = "git_status"
    description = "读取 workspace Git 状态。"
    input_model = GitStatusInput

    async def execute(self, arguments: ToolInput, context: ToolContext) -> ToolResult:
        assert isinstance(arguments, GitStatusInput)
        command = ["git", "status", "--short", "--branch"] if arguments.short else ["git", "status"]
        return await _git(command, context)


class GitDiffInput(ToolInput):
    staged: bool = False
    path: str | None = None


class GitDiffTool(Tool):
    name = "git_diff"
    description = "读取 Git diff，可限定 workspace 内路径。"
    input_model = GitDiffInput

    async def execute(self, arguments: ToolInput, context: ToolContext) -> ToolResult:
        assert isinstance(arguments, GitDiffInput)
        command = ["git", "diff", "--no-ext-diff", "--no-textconv"]
        if arguments.staged:
            command.append("--cached")
        if arguments.path:
            path = context.guard.resolve(arguments.path)
            command.extend(["--", context.guard.relative(path)])
        return await _git(command, context)


class GitLogInput(ToolInput):
    limit: int = Field(default=20, ge=1, le=200)


class GitLogTool(Tool):
    name = "git_log"
    description = "读取简洁 Git 提交日志。"
    input_model = GitLogInput

    async def execute(self, arguments: ToolInput, context: ToolContext) -> ToolResult:
        assert isinstance(arguments, GitLogInput)
        return await _git(
            ["git", "log", f"-{arguments.limit}", "--date=iso", "--pretty=format:%h%x09%ad%x09%s"],
            context,
        )


async def _git(command: list[str], context: ToolContext) -> ToolResult:
    return await execute_command(
        [command[0], "-c", "core.fsmonitor=false", *command[1:]],
        cwd=context.workspace,
        shell=False,
        timeout_seconds=min(context.command_timeout, 60),
        output_limit=context.output_limit,
        tool_call_id=context.tool_call_id or "",
    )
