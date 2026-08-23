"""Tool lookup, schema validation, policy, approval, and execution."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from pydantic import ValidationError

from yfharness.core.exceptions import PolicyDeniedError, ToolExecutionError
from yfharness.core.models import (
    ApprovalDecision,
    ApprovalRequest,
    ToolCall,
    ToolDefinition,
    ToolResult,
)
from yfharness.core.policies import (
    AgentMode,
    ApprovalPolicy,
    PolicyAction,
    decide_tool_access,
)
from yfharness.tools.base import Tool, ToolContext

ApprovalHandler = Callable[[ApprovalRequest], Awaitable[ApprovalDecision]]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError as exc:
            choices = ", ".join(sorted(self._tools))
            raise ToolExecutionError(f"未知工具 {name!r}; 可用工具: {choices}") from exc

    def definitions(self) -> list[ToolDefinition]:
        return [self._tools[name].definition() for name in sorted(self._tools)]

    def names(self) -> list[str]:
        return sorted(self._tools)


class ToolExecutor:
    def __init__(
        self,
        registry: ToolRegistry,
        context: ToolContext,
        *,
        mode: AgentMode = AgentMode.AGENT,
        policy: ApprovalPolicy = ApprovalPolicy.SAFE_AUTO,
        approval_handler: ApprovalHandler | None = None,
        full_auto_enabled: bool = False,
    ) -> None:
        self.registry = registry
        self.context = context
        self.mode = mode
        self.policy = policy
        self.approval_handler = approval_handler
        self.full_auto_enabled = full_auto_enabled
        self.session_allowed_tools: set[str] = set()

    async def execute(self, call: ToolCall) -> ToolResult:
        tool = self.registry.get(call.name)
        try:
            arguments = tool.input_model.model_validate(call.arguments)
        except ValidationError as exc:
            raise ToolExecutionError(f"工具参数无效: {exc}") from exc
        risk = tool.effective_risk(arguments)
        always_approval = tool.requires_approval(arguments)
        action = decide_tool_access(
            mode=self.mode,
            policy=self.policy,
            tool_name=tool.name,
            risk_level=risk,
            read_only=tool.read_only,
            always_approval=always_approval,
            session_allowed_tools=self.session_allowed_tools,
            full_auto_enabled=self.full_auto_enabled,
        )
        if action is PolicyAction.DENY:
            raise PolicyDeniedError(f"当前模式或权限策略禁止工具: {tool.name}")
        preview = await tool.preview(arguments, self.context)
        if action is PolicyAction.ASK:
            if self.approval_handler is None:
                raise PolicyDeniedError(f"工具需要审批但没有审批处理器: {tool.name}")
            request = ApprovalRequest(
                run_id=self.context.run_id or "untracked",
                tool_call=call,
                risk_level=risk,
                paths=preview.paths,
                command=preview.command,
                diff_preview=preview.diff,
            )
            decision = await self.approval_handler(request)
            if decision is ApprovalDecision.ALLOW_SESSION:
                self.session_allowed_tools.add(tool.name)
            elif decision is ApprovalDecision.DENY:
                raise PolicyDeniedError(f"用户拒绝工具调用: {tool.name}")
            elif decision is ApprovalDecision.CANCEL_RUN:
                raise asyncio.CancelledError
        self.context.tool_call_id = call.id
        change_index = self.context.changes.count if self.context.changes is not None else 0
        result = await tool.execute(arguments, self.context)
        if self.context.change_recorder is not None and self.context.changes is not None:
            for entry in self.context.changes.entries_since(change_index):
                await self.context.change_recorder(entry)
        return result


def builtin_tools() -> ToolRegistry:
    from yfharness.tools.filesystem import (
        CreateDirectoryTool,
        DeletePathTool,
        GetFileInfoTool,
        ListDirectoryTool,
        MovePathTool,
        ReadFileTool,
        WriteFileTool,
    )
    from yfharness.tools.git import GitDiffTool, GitLogTool, GitStatusTool
    from yfharness.tools.patch import ApplyPatchTool
    from yfharness.tools.search import FindFilesTool, SearchTextTool
    from yfharness.tools.shell import RunCommandTool, RunTestsTool

    registry = ToolRegistry()
    for tool in (
        ListDirectoryTool(),
        ReadFileTool(),
        SearchTextTool(),
        FindFilesTool(),
        GetFileInfoTool(),
        GitStatusTool(),
        GitDiffTool(),
        GitLogTool(),
        CreateDirectoryTool(),
        WriteFileTool(),
        ApplyPatchTool(),
        MovePathTool(),
        DeletePathTool(),
        RunCommandTool(),
        RunTestsTool(),
    ):
        registry.register(tool)
    return registry
