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
    ToolRiskLevel,
)
from yfharness.core.policies import (
    AgentMode,
    ApprovalPolicy,
    PolicyAction,
    decide_tool_access,
)
from yfharness.core.workflows import (
    HookEngine,
    HookEvaluation,
    WorkflowProfile,
    combine_policy_actions,
)
from yfharness.tools.base import Tool, ToolContext

ApprovalHandler = Callable[[ApprovalRequest], Awaitable[ApprovalDecision]]
HookSink = Callable[[HookEvaluation], Awaitable[None]]


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
        workflow: WorkflowProfile | None = None,
        hook_sink: HookSink | None = None,
    ) -> None:
        self.registry = registry
        self.context = context
        self.mode = mode
        self.policy = policy
        self.approval_handler = approval_handler
        self.full_auto_enabled = full_auto_enabled
        self.workflow = workflow
        self.hooks = HookEngine(workflow) if workflow is not None else None
        self.hook_sink = hook_sink
        self.session_allowed_tools: set[str] = set()

    def definitions(self) -> list[ToolDefinition]:
        definitions = self.registry.definitions()
        return (
            self.workflow.filter_definitions(definitions)
            if self.workflow is not None
            else definitions
        )

    async def execute(self, call: ToolCall) -> ToolResult:
        if self.workflow is not None and not self.workflow.exposes(call.name):
            raise PolicyDeniedError(f"工作流 {self.workflow.id!r} 未向模型开放工具: {call.name}")
        tool = self.registry.get(call.name)
        try:
            arguments = tool.validate_arguments(call.arguments)
        except (ValidationError, ValueError) as exc:
            raise ToolExecutionError(f"工具参数无效: {exc}") from exc
        risk = tool.effective_risk(arguments)
        always_approval = tool.requires_approval(arguments)
        base_action = decide_tool_access(
            mode=self.mode,
            policy=self.policy,
            tool_name=tool.name,
            risk_level=risk,
            read_only=tool.read_only,
            always_approval=always_approval,
            session_allowed_tools=self.session_allowed_tools,
            full_auto_enabled=self.full_auto_enabled,
        )
        evaluation = self.hooks.pre_tool_use(tool.name, risk) if self.hooks is not None else None
        if evaluation is not None:
            await self._emit_hook(evaluation)
        action = combine_policy_actions(
            base_action,
            evaluation.policy_action() if evaluation is not None else None,
        )
        if action is PolicyAction.DENY:
            raise PolicyDeniedError(f"当前模式或权限策略禁止工具: {tool.name}")
        preview = await tool.preview(arguments, self.context)
        snapshots = (
            self._path_snapshots(preview.paths)
            if tool.name in {"write_file", "apply_patch", "move_path", "delete_path"}
            else {}
        )
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
                network=preview.network,
            )
            decision = await self.approval_handler(request)
            if decision is ApprovalDecision.ALLOW_SESSION:
                self.session_allowed_tools.add(tool.name)
            elif decision is ApprovalDecision.DENY:
                raise PolicyDeniedError(f"用户拒绝工具调用: {tool.name}")
            elif decision is ApprovalDecision.CANCEL_RUN:
                raise asyncio.CancelledError
        if snapshots and snapshots != self._path_snapshots(preview.paths):
            raise ToolExecutionError("审批期间文件发生变化，请重新查看 Diff 并确认")
        self.context.tool_call_id = call.id
        change_index = self.context.changes.count if self.context.changes is not None else 0
        try:
            result = await tool.execute(arguments, self.context)
        except BaseException:
            await self._emit_post_hook(tool.name, risk, success=False)
            raise
        await self._emit_post_hook(tool.name, risk, success=result.success)
        if self.context.change_recorder is not None and self.context.changes is not None:
            for entry in self.context.changes.entries_since(change_index):
                await self.context.change_recorder(entry)
        return result

    def _path_snapshots(self, paths: list[str]) -> dict[str, object]:
        snapshots: dict[str, object] = {}
        for name in paths:
            path = self.context.guard.resolve(name)
            if path.exists():
                stat = path.stat()
                snapshots[name] = (
                    str(path),
                    stat.st_dev,
                    stat.st_ino,
                    stat.st_size,
                    stat.st_mtime_ns,
                    stat.st_ctime_ns,
                )
            else:
                snapshots[name] = (str(path), None)
        return snapshots

    async def _emit_post_hook(
        self,
        tool_name: str,
        risk: ToolRiskLevel,
        *,
        success: bool,
    ) -> None:
        if self.hooks is None:
            return
        evaluation = self.hooks.post_tool_use(tool_name, risk, success=success)
        if evaluation is not None:
            await self._emit_hook(evaluation)

    async def _emit_hook(self, evaluation: HookEvaluation) -> None:
        if self.hook_sink is not None:
            await self.hook_sink(evaluation)


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
    from yfharness.tools.github import github_tools
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
        *github_tools(),
    ):
        registry.register(tool)
    return registry
