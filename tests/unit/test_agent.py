from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from yfharness.core.agent import AgentLimits, AgentRunner
from yfharness.core.agent_events import AgentEvent, StateChanged
from yfharness.core.models import (
    AgentState,
    ModelConfig,
    RunStatus,
    ToolCall,
)
from yfharness.core.policies import AgentMode
from yfharness.providers.mock import MockFailure, MockProvider, MockScript
from yfharness.tools.base import ToolContext
from yfharness.tools.registry import ToolExecutor, builtin_tools
from yfharness.tools.security import WorkspaceGuard


def configured_model(*, native_tools: bool = True) -> ModelConfig:
    return ModelConfig(
        id="scripted",
        provider="mock",
        model="scripted",
        supports_native_tools=native_tools,
        input_price=1.0,
        output_price=2.0,
    )


def executor(workspace: Path) -> ToolExecutor:
    guard = WorkspaceGuard(workspace)
    return ToolExecutor(builtin_tools(), ToolContext(workspace=guard.root, guard=guard))


@pytest.mark.asyncio
async def test_final_answer_transitions_and_usage(tmp_path: Path) -> None:
    events: list[AgentEvent] = []

    async def observe(event: AgentEvent) -> None:
        events.append(event)

    runner = AgentRunner(
        provider=MockProvider(response="final"),
        model=configured_model(),
        tools=executor(tmp_path),
        event_sink=observe,
    )
    result = await runner.run("hello", session_id="s1")

    assert result.run.status is RunStatus.COMPLETED
    assert result.final_text == "final"
    assert result.run.step_count == 1
    assert result.run.usage.total_tokens > 0
    states = [event.state for event in events if isinstance(event, StateChanged)]
    assert states == [
        AgentState.BUILDING_CONTEXT,
        AgentState.REQUESTING_MODEL,
        AgentState.STREAMING,
        AgentState.COMPLETED,
    ]


@pytest.mark.asyncio
async def test_unpriced_model_keeps_cost_unknown_and_rejects_cost_limit(tmp_path: Path) -> None:
    model = configured_model().model_copy(update={"input_price": None, "output_price": None})
    runner = AgentRunner(
        provider=MockProvider(response="final"),
        model=model,
        tools=executor(tmp_path),
    )

    result = await runner.run("hello", session_id="s1")

    assert result.run.status is RunStatus.COMPLETED
    assert result.run.usage.cost is None

    limited = AgentRunner(
        provider=MockProvider(response="final"),
        model=model,
        tools=executor(tmp_path),
        limits=AgentLimits(max_cost=1.0),
    )
    failed = await limited.run("hello", session_id="s2")

    assert failed.run.status is RunStatus.FAILED
    assert "无法执行成本预算" in (failed.run.error or "")


@pytest.mark.asyncio
async def test_native_tool_round_trip_reads_real_file(tmp_path: Path) -> None:
    (tmp_path / "note.txt").write_text("real content", encoding="utf-8")
    provider = MockProvider(
        scripts=[
            MockScript(
                tool_call=ToolCall(id="read-1", name="read_file", arguments={"path": "note.txt"})
            ),
            MockScript(text="I used the real file"),
        ]
    )
    runner = AgentRunner(provider=provider, model=configured_model(), tools=executor(tmp_path))

    result = await runner.run("read it", session_id="s1")

    assert result.run.status is RunStatus.COMPLETED
    assert result.run.tool_call_count == 1
    assert any("real content" in message.text_content for message in result.messages)


@pytest.mark.asyncio
async def test_fallback_protocol_uses_same_tool_path(tmp_path: Path) -> None:
    (tmp_path / "note.txt").write_text("fallback content", encoding="utf-8")
    call_text = (
        '<YFH_TOOL_CALL>\n{"tool":"read_file","arguments":{"path":"note.txt"}}\n</YFH_TOOL_CALL>'
    )
    provider = MockProvider(scripts=[MockScript(text=call_text), MockScript(text="done")])
    runner = AgentRunner(
        provider=provider,
        model=configured_model(native_tools=False),
        tools=executor(tmp_path),
    )

    result = await runner.run("read", session_id="s1")

    assert result.run.status is RunStatus.COMPLETED
    assert result.run.tool_call_count == 1
    assert any("fallback content" in message.text_content for message in result.messages)


@pytest.mark.asyncio
async def test_invalid_tool_arguments_are_returned_for_repair(tmp_path: Path) -> None:
    provider = MockProvider(
        scripts=[
            MockScript(
                tool_call=ToolCall(
                    id="bad", name="read_file", arguments={"path": "x", "extra": True}
                )
            ),
            MockScript(text="repaired response"),
        ]
    )
    runner = AgentRunner(provider=provider, model=configured_model(), tools=executor(tmp_path))

    result = await runner.run("test repair", session_id="s1")

    assert result.run.status is RunStatus.COMPLETED
    assert any("工具参数无效" in message.text_content for message in result.messages)


@pytest.mark.asyncio
async def test_repeated_tool_call_loop_is_stopped(tmp_path: Path) -> None:
    call = ToolCall(id="same", name="read_file", arguments={"path": "missing.txt"})
    provider = MockProvider(scripts=[MockScript(tool_call=call) for _ in range(3)])
    runner = AgentRunner(
        provider=provider,
        model=configured_model(),
        tools=executor(tmp_path),
        limits=AgentLimits(max_repeated_tool_calls=2),
    )

    result = await runner.run("loop", session_id="s1")

    assert result.run.status is RunStatus.FAILED
    assert "重复工具调用循环" in (result.run.error or "")


@pytest.mark.asyncio
async def test_max_steps_is_enforced(tmp_path: Path) -> None:
    call = ToolCall(id="call", name="read_file", arguments={"path": "missing"})
    runner = AgentRunner(
        provider=MockProvider(scripts=[MockScript(tool_call=call)]),
        model=configured_model(),
        tools=executor(tmp_path),
        limits=AgentLimits(max_steps=1),
    )

    result = await runner.run("bounded", session_id="s1")

    assert result.run.status is RunStatus.FAILED
    assert "最大步骤数" in (result.run.error or "")


@pytest.mark.asyncio
async def test_token_budget_is_enforced(tmp_path: Path) -> None:
    runner = AgentRunner(
        provider=MockProvider(response="long enough answer"),
        model=configured_model(),
        tools=executor(tmp_path),
        limits=AgentLimits(max_token_budget=1),
    )

    result = await runner.run("input", session_id="s1")

    assert result.run.status is RunStatus.FAILED
    assert "Token 预算" in (result.run.error or "")


@pytest.mark.asyncio
async def test_retry_only_before_first_event(tmp_path: Path) -> None:
    provider = MockProvider(
        scripts=[
            MockScript(failure=MockFailure.RATE_LIMIT),
            MockScript(text="retried"),
        ]
    )
    runner = AgentRunner(
        provider=provider,
        model=configured_model(),
        tools=executor(tmp_path),
        limits=AgentLimits(provider_retries=1),
    )

    result = await runner.run("retry", session_id="s1")
    assert result.run.status is RunStatus.COMPLETED
    assert result.final_text == "retried"

    interrupted = AgentRunner(
        provider=MockProvider(
            scripts=[
                MockScript(chunks=["partial", "later"], failure=MockFailure.INTERRUPT),
                MockScript(text="must not retry"),
            ]
        ),
        model=configured_model(),
        tools=executor(tmp_path),
        limits=AgentLimits(provider_retries=1),
    )
    failed = await interrupted.run("no duplicate", session_id="s2")
    assert failed.run.status is RunStatus.FAILED
    assert failed.run.step_count == 1


@pytest.mark.asyncio
async def test_cancel_interrupts_active_provider(tmp_path: Path) -> None:
    runner = AgentRunner(
        provider=MockProvider(scripts=[MockScript(failure=MockFailure.TIMEOUT, delay_seconds=60)]),
        model=configured_model(),
        tools=executor(tmp_path),
    )
    task = asyncio.create_task(runner.run("wait", session_id="s1"))
    await asyncio.sleep(0.01)

    assert runner.cancel()
    result = await task
    assert result.run.status is RunStatus.CANCELLED


@pytest.mark.asyncio
async def test_plan_mode_denies_unadvertised_write_call(tmp_path: Path) -> None:
    provider = MockProvider(
        scripts=[
            MockScript(
                tool_call=ToolCall(
                    id="write", name="write_file", arguments={"path": "bad", "content": "bad"}
                )
            ),
            MockScript(text="denied safely"),
        ]
    )
    runner = AgentRunner(
        provider=provider,
        model=configured_model(),
        tools=executor(tmp_path),
        mode=AgentMode.PLAN,
    )

    result = await runner.run("do not write", session_id="s1")
    assert result.run.status is RunStatus.COMPLETED
    assert not (tmp_path / "bad").exists()
    assert any("权限策略禁止" in message.text_content for message in result.messages)
