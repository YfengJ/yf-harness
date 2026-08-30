"""Explicit, bounded Agent state machine shared by all modes and interfaces."""

from __future__ import annotations

import asyncio
import json
from collections import Counter
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from pydantic import Field

from yfharness.core.agent_events import (
    AgentEvent,
    BudgetUpdated,
    ModelEventObserved,
    StateChanged,
    ToolExecutionFinished,
    ToolExecutionStarted,
)
from yfharness.core.context import ContextBuilder
from yfharness.core.events import ErrorEvent, TextDelta, ToolCallCompleted, UsageEvent
from yfharness.core.exceptions import (
    AgentLimitError,
    HarnessError,
    PolicyDeniedError,
    ProviderError,
    ToolExecutionError,
    ToolProtocolError,
)
from yfharness.core.models import (
    AgentRun,
    AgentRunResult,
    AgentState,
    ChatRequest,
    ContentPart,
    ContentPartType,
    DomainModel,
    Message,
    MessageRole,
    ModelConfig,
    RunStatus,
    ToolCall,
    ToolDefinition,
    ToolResult,
    Usage,
)
from yfharness.core.policies import AgentMode
from yfharness.core.prompts import build_system_prompt
from yfharness.core.skills import SkillInvocation
from yfharness.core.tool_protocol import parse_fallback_tool_calls
from yfharness.providers.base import Provider
from yfharness.tools.registry import ToolExecutor

EventSink = Callable[[AgentEvent], Awaitable[None]]


class AgentLimits(DomainModel):
    max_steps: int = Field(default=20, ge=1)
    max_tool_calls: int = Field(default=50, ge=0)
    max_run_seconds: float = Field(default=900, gt=0)
    max_token_budget: int | None = Field(default=None, gt=0)
    max_cost: float | None = Field(default=None, ge=0)
    max_repeated_tool_calls: int = Field(default=2, ge=1)
    max_tool_repairs: int = Field(default=2, ge=0)
    provider_retries: int = Field(default=2, ge=0, le=10)


_ALLOWED_TRANSITIONS: dict[AgentState, set[AgentState]] = {
    AgentState.CREATED: {AgentState.BUILDING_CONTEXT},
    AgentState.BUILDING_CONTEXT: {
        AgentState.REQUESTING_MODEL,
        AgentState.COMPACTING,
        AgentState.FAILED,
        AgentState.CANCELLED,
    },
    AgentState.COMPACTING: {
        AgentState.REQUESTING_MODEL,
        AgentState.FAILED,
        AgentState.CANCELLED,
    },
    AgentState.REQUESTING_MODEL: {
        AgentState.STREAMING,
        AgentState.FAILED,
        AgentState.CANCELLED,
    },
    AgentState.STREAMING: {
        AgentState.VALIDATING_TOOL,
        AgentState.BUILDING_CONTEXT,
        AgentState.COMPLETED,
        AgentState.FAILED,
        AgentState.CANCELLED,
    },
    AgentState.VALIDATING_TOOL: {
        AgentState.EXECUTING_TOOL,
        AgentState.BUILDING_CONTEXT,
        AgentState.FAILED,
        AgentState.CANCELLED,
    },
    AgentState.AWAITING_APPROVAL: {
        AgentState.EXECUTING_TOOL,
        AgentState.FAILED,
        AgentState.CANCELLED,
    },
    AgentState.EXECUTING_TOOL: {
        AgentState.VALIDATING_TOOL,
        AgentState.BUILDING_CONTEXT,
        AgentState.FAILED,
        AgentState.CANCELLED,
    },
    AgentState.COMPLETED: set(),
    AgentState.CANCELLED: set(),
    AgentState.FAILED: set(),
}


class AgentRunner:
    def __init__(
        self,
        *,
        provider: Provider,
        model: ModelConfig,
        tools: ToolExecutor,
        mode: AgentMode = AgentMode.AGENT,
        limits: AgentLimits | None = None,
        event_sink: EventSink | None = None,
        context_builder: ContextBuilder | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self.tools = tools
        self.mode = mode
        self.tools.mode = mode
        self.limits = limits or AgentLimits()
        self.event_sink = event_sink or _ignore_event
        self.context_builder = context_builder
        self._active_task: asyncio.Task[Any] | None = None

    def cancel(self) -> bool:
        if self._active_task is None or self._active_task.done():
            return False
        self._active_task.cancel()
        return True

    async def run(
        self,
        user_input: str,
        *,
        session_id: str,
        history: list[Message] | None = None,
        existing_run: AgentRun | None = None,
        attachments: list[ContentPart] | None = None,
        skill: SkillInvocation | None = None,
        goal: str | None = None,
    ) -> AgentRunResult:
        if not user_input.strip():
            raise ValueError("user_input must not be empty")
        run = existing_run or AgentRun(session_id=session_id)
        if run.session_id != session_id or run.state is not AgentState.CREATED:
            raise ValueError("existing_run must be a new run for the same session")
        self._active_task = asyncio.current_task()
        definitions = self._available_tools()
        native_tools = self.model.supports_native_tools
        initial_compacted = False
        if self.context_builder is not None:
            snapshot = self.context_builder.build(
                user_input=user_input,
                history=list(history or []),
                mode=self.mode,
                tools=definitions,
                model=self.model,
                native_tools=native_tools,
                skill=skill,
                goal=goal,
            )
            messages = snapshot.messages
            initial_compacted = snapshot.compacted
        else:
            system_prompt = build_system_prompt(self.mode, definitions, native_tools=native_tools)
            if skill is not None:
                system_prompt += "\n\n" + skill.render()
            if goal:
                system_prompt += "\n\n# 当前会话目标\n" + goal
            messages = list(history or [])
            if self.model.supports_system_message:
                messages.insert(0, Message.text(MessageRole.SYSTEM, system_prompt))
                messages.append(Message.text(MessageRole.USER, user_input))
            else:
                messages.append(
                    Message.text(
                        MessageRole.USER,
                        f"[Harness instructions]\n{system_prompt}\n\n[User]\n{user_input}",
                    )
                )
        if attachments:
            if any(part.type is ContentPartType.TEXT for part in attachments):
                raise ValueError("attachments cannot contain text content parts")
            user_message = next(
                (message for message in reversed(messages) if message.role is MessageRole.USER),
                None,
            )
            if user_message is None:
                raise ValueError("attachments require a user message")
            user_message.content.extend(attachments)
        final_text = ""
        signatures: Counter[str] = Counter()
        repairs = 0
        total_cost = 0.0
        try:
            async with asyncio.timeout(self.limits.max_run_seconds):
                await self._transition(run, AgentState.BUILDING_CONTEXT)
                while True:
                    if run.step_count >= self.limits.max_steps:
                        raise AgentLimitError(f"达到最大步骤数 {self.limits.max_steps}")
                    if self.context_builder is not None:
                        if initial_compacted:
                            await self._transition(run, AgentState.COMPACTING)
                            initial_compacted = False
                        elif run.step_count:
                            snapshot = self.context_builder.fit_messages(
                                messages, model=self.model, tools=definitions
                            )
                            messages = snapshot.messages
                            if snapshot.compacted:
                                await self._transition(run, AgentState.COMPACTING)
                    await self._transition(run, AgentState.REQUESTING_MODEL)
                    run.step_count += 1
                    request = ChatRequest(
                        model=self.model,
                        messages=messages,
                        tools=definitions if native_tools else [],
                        stream=True,
                    )
                    await self._transition(run, AgentState.STREAMING)
                    text, calls, request_usage = await self._model_turn(request)
                    run.usage, total_cost = self._add_usage(run.usage, request_usage, total_cost)
                    await self.event_sink(BudgetUpdated(usage=run.usage, cost=total_cost))
                    self._check_budget(run.usage, total_cost)

                    if not native_tools:
                        try:
                            fallback_calls = parse_fallback_tool_calls(text)
                        except ToolProtocolError as exc:
                            repairs += 1
                            if repairs > self.limits.max_tool_repairs:
                                raise
                            messages.extend(
                                [
                                    Message.text(MessageRole.ASSISTANT, text),
                                    Message.text(
                                        MessageRole.USER,
                                        f"[Harness tool protocol error] {exc}. 请严格修复格式。",
                                    ),
                                ]
                            )
                            await self._transition(run, AgentState.BUILDING_CONTEXT)
                            continue
                        if fallback_calls:
                            calls.extend(fallback_calls)

                    if not calls:
                        final_text = text
                        messages.append(Message.text(MessageRole.ASSISTANT, text))
                        await self._transition(run, AgentState.COMPLETED)
                        run.status = RunStatus.COMPLETED
                        break

                    await self._transition(run, AgentState.VALIDATING_TOOL)
                    if native_tools:
                        messages.append(Message.text(MessageRole.ASSISTANT, text, tool_calls=calls))
                    else:
                        messages.append(Message.text(MessageRole.ASSISTANT, text))
                    for index, call in enumerate(calls):
                        if run.tool_call_count >= self.limits.max_tool_calls:
                            raise AgentLimitError(
                                f"达到最大工具调用数 {self.limits.max_tool_calls}"
                            )
                        signature = _call_signature(call)
                        signatures[signature] += 1
                        if signatures[signature] > self.limits.max_repeated_tool_calls:
                            raise AgentLimitError(f"检测到重复工具调用循环: {call.name}")
                        run.tool_call_count += 1
                        if index:
                            await self._transition(run, AgentState.VALIDATING_TOOL)
                        await self._transition(run, AgentState.EXECUTING_TOOL)
                        await self.event_sink(ToolExecutionStarted(call=call))
                        result = await self._execute_tool(call)
                        if not result.success and result.error_type in {
                            "invalid_arguments",
                            "unknown_tool",
                        }:
                            repairs += 1
                            if repairs > self.limits.max_tool_repairs:
                                raise ToolExecutionError("工具参数修复次数已耗尽")
                        await self.event_sink(ToolExecutionFinished(result=result))
                        messages.append(_tool_result_message(result, native=native_tools))
                    await self._transition(run, AgentState.BUILDING_CONTEXT)
        except asyncio.CancelledError:
            await self._terminal_transition(run, AgentState.CANCELLED)
            run.status = RunStatus.CANCELLED
            run.error = "用户取消运行"
        except TimeoutError:
            await self._terminal_transition(run, AgentState.FAILED)
            run.status = RunStatus.FAILED
            run.error = f"运行超过 {self.limits.max_run_seconds}s"
        except (HarnessError, ValueError) as exc:
            await self._terminal_transition(run, AgentState.FAILED)
            run.status = RunStatus.FAILED
            run.error = str(exc)
        finally:
            run.ended_at = datetime.now(UTC)
            self._active_task = None
        return AgentRunResult(run=run, final_text=final_text, messages=messages)

    async def _model_turn(self, request: ChatRequest) -> tuple[str, list[ToolCall], Usage]:
        last_error: ProviderError | None = None
        for attempt in range(self.limits.provider_retries + 1):
            emitted = False
            text_parts: list[str] = []
            calls: list[ToolCall] = []
            usage = Usage()
            try:
                async for event in self.provider.stream_chat(request):
                    emitted = True
                    await self.event_sink(ModelEventObserved(event=event))
                    if isinstance(event, TextDelta):
                        text_parts.append(event.text)
                    elif isinstance(event, ToolCallCompleted):
                        calls.append(event.tool_call)
                    elif isinstance(event, UsageEvent):
                        usage = event.usage
                    elif isinstance(event, ErrorEvent):
                        raise ProviderError(
                            event.message, code=event.code, retryable=event.retryable
                        )
                return "".join(text_parts), calls, usage
            except ProviderError as exc:
                last_error = exc
                if emitted or not exc.retryable or attempt >= self.limits.provider_retries:
                    raise
                await asyncio.sleep(0.25 * (2**attempt))
        assert last_error is not None
        raise last_error

    async def _execute_tool(self, call: ToolCall) -> ToolResult:
        try:
            return await self.tools.execute(call)
        except PolicyDeniedError as exc:
            return ToolResult(
                tool_call_id=call.id,
                success=False,
                summary=str(exc),
                error_type="policy_denied",
            )
        except ToolExecutionError as exc:
            message = str(exc)
            error_type = "unknown_tool" if message.startswith("未知工具") else "invalid_arguments"
            return ToolResult(
                tool_call_id=call.id,
                success=False,
                summary=message,
                error_type=error_type,
            )

    def _available_tools(self) -> list[ToolDefinition]:
        definitions = self.tools.definitions()
        if self.mode in {AgentMode.PLAN, AgentMode.REVIEW, AgentMode.CHAT}:
            return [definition for definition in definitions if definition.read_only]
        return definitions

    def _add_usage(self, total: Usage, current: Usage, cost: float) -> tuple[Usage, float]:
        request_cost = current.cost
        if request_cost is None:
            request_cost = (
                current.input_tokens * (self.model.input_price or 0)
                + current.output_tokens * (self.model.output_price or 0)
            ) / 1_000_000
        updated = Usage(
            input_tokens=total.input_tokens + current.input_tokens,
            output_tokens=total.output_tokens + current.output_tokens,
            total_tokens=total.total_tokens + current.total_tokens,
            estimated=total.estimated or current.estimated,
            cost=(total.cost or 0) + request_cost,
        )
        return updated, cost + request_cost

    def _check_budget(self, usage: Usage, cost: float) -> None:
        if (
            self.limits.max_token_budget is not None
            and usage.total_tokens > self.limits.max_token_budget
        ):
            raise AgentLimitError(f"超过 Token 预算 {self.limits.max_token_budget}")
        if self.limits.max_cost is not None and cost > self.limits.max_cost:
            raise AgentLimitError(f"超过成本预算 {self.limits.max_cost}")

    async def _transition(self, run: AgentRun, target: AgentState) -> None:
        if target not in _ALLOWED_TRANSITIONS[run.state]:
            raise RuntimeError(f"invalid Agent transition: {run.state} -> {target}")
        run.state = target
        await self.event_sink(StateChanged(state=target))

    async def _terminal_transition(self, run: AgentRun, target: AgentState) -> None:
        if run.state in {AgentState.COMPLETED, AgentState.CANCELLED, AgentState.FAILED}:
            return
        await self._transition(run, target)


async def _ignore_event(_: AgentEvent) -> None:
    return None


def _call_signature(call: ToolCall) -> str:
    return f"{call.name}:{json.dumps(call.arguments, sort_keys=True, ensure_ascii=False)}"


def _tool_result_message(result: ToolResult, *, native: bool) -> Message:
    text = result.model_dump_json(exclude_none=True)
    if native:
        return Message.text(MessageRole.TOOL, text, tool_call_id=result.tool_call_id)
    return Message.text(
        MessageRole.USER,
        f"<YFH_TOOL_RESULT>\n{text}\n</YFH_TOOL_RESULT>",
    )
