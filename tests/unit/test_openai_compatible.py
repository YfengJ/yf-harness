from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from yfharness.config.models import ProviderSettings
from yfharness.core.attachments import prepare_image
from yfharness.core.events import (
    FinishEvent,
    ReasoningDelta,
    StreamEnd,
    TextDelta,
    ToolCallCompleted,
    UsageEvent,
)
from yfharness.core.exceptions import ProviderError
from yfharness.core.models import ChatRequest, Message, MessageRole, ModelConfig
from yfharness.providers.openai_compatible import OpenAICompatibleProvider
from yfharness.tools.security import WorkspaceGuard


def model(*, supports_images: bool = False) -> ModelConfig:
    return ModelConfig(
        id="test-model",
        provider="remote",
        model="upstream-model",
        supports_streaming=True,
        supports_native_tools=True,
        supports_image_input=supports_images,
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
async def test_multimodal_message_uses_explicit_verified_data_url(tmp_path: Path) -> None:
    image = tmp_path / "sample.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nimage")
    message = Message.text(MessageRole.USER, "describe")
    message.content.append(prepare_image(image, WorkspaceGuard(tmp_path), send_to_model=True))

    async def handler(request_value: httpx.Request) -> httpx.Response:
        content = json.loads(request_value.content)["messages"][0]["content"]
        assert content[0] == {"type": "text", "text": "describe"}
        assert content[1]["type"] == "image_url"
        assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "done"}, "finish_reason": "stop"}]},
        )

    instance, client = provider(httpx.MockTransport(handler))
    multimodal = ChatRequest(model=model(supports_images=True), messages=[message], stream=False)
    try:
        _ = [event async for event in instance.stream_chat(multimodal)]
    finally:
        await client.aclose()


def test_remote_image_requires_declared_model_capability(tmp_path: Path) -> None:
    image = tmp_path / "sample.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nimage")
    message = Message.text(MessageRole.USER, "describe")
    message.content.append(prepare_image(image, WorkspaceGuard(tmp_path), send_to_model=True))

    with pytest.raises(ProviderError, match="未声明图片"):
        OpenAICompatibleProvider._message_payload(message, supports_images=False)


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


@pytest.mark.asyncio
async def test_streaming_http_error_is_read_closed_and_normalized() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "invalid credentials"}})

    instance, client = provider(httpx.MockTransport(handler))
    try:
        with pytest.raises(ProviderError, match="invalid credentials") as raised:
            _ = [event async for event in instance.stream_chat(request())]
    finally:
        await client.aclose()

    assert raised.value.code == "http_error"
    assert raised.value.status_code == 401
    assert not raised.value.retryable


@pytest.mark.asyncio
async def test_streaming_retryable_status_is_retried() -> None:
    attempts = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, json={"error": {"message": "slow down"}})
        return httpx.Response(
            200,
            text='data: {"choices":[{"delta":{"content":"ok"},"finish_reason":"stop"}]}\n\n'
            "data: [DONE]\n\n",
            headers={"content-type": "text/event-stream"},
        )

    instance, client = provider(httpx.MockTransport(handler), retries=1)
    try:
        events = [event async for event in instance.stream_chat(request())]
    finally:
        await client.aclose()

    assert attempts == 2
    assert any(isinstance(event, TextDelta) and event.text == "ok" for event in events)
