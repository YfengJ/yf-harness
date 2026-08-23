from __future__ import annotations

import json

import httpx
import pytest

from yfharness.config.models import ProviderSettings
from yfharness.core.events import (
    FinishEvent,
    ReasoningDelta,
    StreamEnd,
    TextDelta,
    ToolCallCompleted,
    UsageEvent,
)
from yfharness.core.models import ChatRequest, Message, MessageRole, ModelConfig
from yfharness.providers.openai_compatible import OpenAICompatibleProvider


def model() -> ModelConfig:
    return ModelConfig(
        id="test-model",
        provider="remote",
        model="upstream-model",
        supports_streaming=True,
        supports_native_tools=True,
    )


def request(*, stream: bool = True) -> ChatRequest:
    return ChatRequest(
        model=model(), messages=[Message.text(MessageRole.USER, "hello")], stream=stream
    )


def provider(
    handler: httpx.AsyncBaseTransport, *, include_reasoning: bool = False, retries: int = 0
) -> tuple[OpenAICompatibleProvider, httpx.AsyncClient]:
    client = httpx.AsyncClient(base_url="https://example.test/v1", transport=handler)
    instance = OpenAICompatibleProvider(
        "remote",
        ProviderSettings(
            type="openai_compatible",
            base_url="https://example.test/v1",
            include_reasoning=include_reasoning,
            max_retries=retries,
        ),
        {"test-model": model()},
        client=client,
    )
    return instance, client


@pytest.mark.asyncio
async def test_streaming_sse_is_normalized_and_ignores_unknown_fields() -> None:
    lines = [
        {"choices": [{"delta": {"content": "你", "reasoning_content": "hidden"}}]},
        {"choices": [{"delta": {"content": "好"}, "finish_reason": "stop"}], "extra": 1},
        {"choices": [], "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3}},
    ]
    body = "".join(f"data: {json.dumps(item)}\n\n" for item in lines) + "data: [DONE]\n\n"

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    instance, client = provider(httpx.MockTransport(handler))
    try:
        events = [event async for event in instance.stream_chat(request())]
    finally:
        await client.aclose()

    assert "".join(event.text for event in events if isinstance(event, TextDelta)) == "你好"
    assert not any(isinstance(event, ReasoningDelta) for event in events)
    assert any(isinstance(event, UsageEvent) and event.usage.total_tokens == 3 for event in events)
    assert any(isinstance(event, FinishEvent) and event.reason == "stop" for event in events)
    assert isinstance(events[-1], StreamEnd)


@pytest.mark.asyncio
async def test_reasoning_requires_explicit_opt_in() -> None:
    body = (
        'data: {"choices":[{"delta":{"reasoning_content":"why"},"finish_reason":"stop"}]}\n\n'
        "data: [DONE]\n\n"
    )

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body)

    instance, client = provider(httpx.MockTransport(handler), include_reasoning=True)
    try:
        events = [event async for event in instance.stream_chat(request())]
    finally:
        await client.aclose()
    assert any(isinstance(event, ReasoningDelta) and event.text == "why" for event in events)


@pytest.mark.asyncio
async def test_streaming_tool_arguments_are_reassembled() -> None:
    chunks = [
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "c1",
                                "function": {"name": "read_file", "arguments": '{"pa'},
                            }
                        ]
                    }
                }
            ]
        },
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [{"index": 0, "function": {"arguments": 'th":"README.md"}'}}]
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        },
    ]
    body = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks) + "data: [DONE]\n\n"

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body)

    instance, client = provider(httpx.MockTransport(handler))
    try:
        events = [event async for event in instance.stream_chat(request())]
    finally:
        await client.aclose()
    call = next(event.tool_call for event in events if isinstance(event, ToolCallCompleted))
    assert call.name == "read_file"
    assert call.arguments == {"path": "README.md"}


@pytest.mark.asyncio
async def test_non_streaming_completion() -> None:
    async def handler(request_value: httpx.Request) -> httpx.Response:
        payload = json.loads(request_value.content)
        assert payload["stream"] is False
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "done"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )

    instance, client = provider(httpx.MockTransport(handler))
    try:
        events = [event async for event in instance.stream_chat(request(stream=False))]
    finally:
        await client.aclose()
    assert any(isinstance(event, TextDelta) and event.text == "done" for event in events)


@pytest.mark.asyncio
async def test_retryable_http_status_is_retried() -> None:
    attempts = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, json={"error": {"message": "slow down"}})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]},
        )

    instance, client = provider(httpx.MockTransport(handler), retries=1)
    try:
        _ = [event async for event in instance.stream_chat(request(stream=False))]
    finally:
        await client.aclose()
    assert attempts == 2
