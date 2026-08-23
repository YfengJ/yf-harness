from __future__ import annotations

import pytest

from yfharness.core.events import (
    FinishEvent,
    StreamEnd,
    TextDelta,
    ToolCallCompleted,
    UsageEvent,
)
from yfharness.core.exceptions import ProviderError
from yfharness.core.models import ChatRequest, Message, MessageRole, ModelConfig, ToolCall
from yfharness.providers.mock import MockFailure, MockProvider, MockScript


def request() -> ChatRequest:
    return ChatRequest(
        model=ModelConfig(id="scripted", provider="mock", model="scripted"),
        messages=[Message.text(MessageRole.USER, "test")],
    )


@pytest.mark.asyncio
async def test_mock_stream_emits_text_usage_finish_and_end() -> None:
    provider = MockProvider(response="abcdef", chunk_size=2)

    events = [event async for event in provider.stream_chat(request())]

    assert "".join(event.text for event in events if isinstance(event, TextDelta)) == "abcdef"
    assert any(isinstance(event, UsageEvent) and event.usage.estimated for event in events)
    assert any(isinstance(event, FinishEvent) and event.reason == "stop" for event in events)
    assert isinstance(events[-1], StreamEnd)


@pytest.mark.asyncio
async def test_mock_script_emits_tool_call() -> None:
    call = ToolCall(id="call-1", name="read_file", arguments={"path": "README.md"})
    provider = MockProvider(scripts=[MockScript(tool_call=call)])

    events = [event async for event in provider.stream_chat(request())]

    completed = next(event for event in events if isinstance(event, ToolCallCompleted))
    assert completed.tool_call == call


@pytest.mark.asyncio
async def test_mock_rate_limit_is_normalized() -> None:
    provider = MockProvider(scripts=[MockScript(failure=MockFailure.RATE_LIMIT)])

    with pytest.raises(ProviderError) as caught:
        _ = [event async for event in provider.stream_chat(request())]

    assert caught.value.code == "rate_limit"
    assert caught.value.retryable is True


@pytest.mark.asyncio
async def test_mock_stream_interruption() -> None:
    provider = MockProvider(
        scripts=[MockScript(chunks=["one", "two"], failure=MockFailure.INTERRUPT)]
    )

    with pytest.raises(ProviderError, match="模拟流中断"):
        _ = [event async for event in provider.stream_chat(request())]
