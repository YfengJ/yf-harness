"""Deterministic offline provider for demos, tests, evals, and failure drills."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from yfharness.core.events import (
    ErrorEvent,
    FinishEvent,
    ModelEvent,
    StreamEnd,
    TextDelta,
    ToolCallCompleted,
    ToolCallDelta,
    ToolCallStarted,
    UsageEvent,
)
from yfharness.core.exceptions import ProviderError
from yfharness.core.models import (
    ChatRequest,
    HealthStatus,
    ModelCapabilities,
    ProviderHealth,
    ToolCall,
    Usage,
)
from yfharness.providers.base import Provider


class MockFailure(StrEnum):
    TIMEOUT = "timeout"
    INVALID_JSON = "invalid_json"
    INTERRUPT = "interrupt"
    RATE_LIMIT = "rate_limit"
    ERROR = "error"


@dataclass(slots=True)
class MockScript:
    text: str | None = None
    chunks: list[str] | None = None
    tool_call: ToolCall | None = None
    failure: MockFailure | None = None
    delay_seconds: float = 0.0

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> MockScript:
        tool = value.get("tool_call")
        return cls(
            text=value.get("text"),
            chunks=value.get("chunks"),
            tool_call=ToolCall.model_validate(tool) if tool else None,
            failure=MockFailure(value["failure"]) if value.get("failure") else None,
            delay_seconds=float(value.get("delay_seconds", 0)),
        )


class MockProvider(Provider):
    name = "mock"

    def __init__(
        self,
        *,
        response: str = "你好！我是 YF-Harness 的离线 MockProvider。",
        scripts: Iterable[MockScript | dict[str, Any]] | None = None,
        chunk_size: int = 4,
    ) -> None:
        self.response = response
        self.chunk_size = max(1, chunk_size)
        self._scripts = [
            script if isinstance(script, MockScript) else MockScript.from_mapping(script)
            for script in (scripts or [])
        ]
        self._request_index = 0

    async def list_models(self) -> list[str]:
        return ["mock-default", "scripted"]

    def validate_config(self) -> list[str]:
        return []

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(status=HealthStatus.OK, message="MockProvider 离线可用")

    def estimate_tokens(self, text: str) -> int:
        # A documented conservative fallback: roughly four Unicode characters per token.
        return max(1, (len(text) + 3) // 4) if text else 0

    def get_capabilities(self, model: str) -> ModelCapabilities:
        return ModelCapabilities(
            supports_streaming=True,
            supports_native_tools=True,
            supports_system_message=True,
            context_window=32_000,
            max_output_tokens=4_096,
            tokenizer="approx_chars_4",
        )

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[ModelEvent]:
        script = self._next_script()
        if script.failure is MockFailure.TIMEOUT:
            await asyncio.sleep(script.delay_seconds or 3600)
        if script.failure is MockFailure.RATE_LIMIT:
            raise ProviderError("模拟限流", code="rate_limit", retryable=True, status_code=429)
        if script.failure is MockFailure.ERROR:
            raise ProviderError("模拟 Provider 错误", code="mock_error")
        if script.failure is MockFailure.INVALID_JSON:
            yield ErrorEvent(message="模拟无效 JSON", code="invalid_json")
            yield FinishEvent(reason="error")
            yield StreamEnd()
            return

        if script.tool_call is not None:
            call = script.tool_call
            arguments = json.dumps(call.arguments, ensure_ascii=False)
            yield ToolCallStarted(index=0, call_id=call.id, name=call.name)
            yield ToolCallDelta(
                index=0,
                call_id=call.id,
                arguments_delta=arguments,
            )
            yield ToolCallCompleted(tool_call=call)
            yield FinishEvent(reason="tool_calls")
            yield StreamEnd()
            return

        chunks = script.chunks or self._chunk(
            script.text if script.text is not None else self.response
        )
        output = ""
        for index, chunk in enumerate(chunks):
            if script.delay_seconds:
                await asyncio.sleep(script.delay_seconds)
            if script.failure is MockFailure.INTERRUPT and index == 1:
                raise ProviderError("模拟流中断", code="stream_interrupted", retryable=True)
            output += chunk
            yield TextDelta(text=chunk)

        input_text = "".join(message.text_content for message in request.messages)
        usage = Usage(
            input_tokens=self.estimate_tokens(input_text),
            output_tokens=self.estimate_tokens(output),
            estimated=True,
        )
        yield UsageEvent(usage=usage)
        yield FinishEvent(reason="stop")
        yield StreamEnd()

    def _next_script(self) -> MockScript:
        if self._request_index < len(self._scripts):
            script = self._scripts[self._request_index]
            self._request_index += 1
            return script
        return MockScript(text=self.response)

    def _chunk(self, text: str) -> list[str]:
        return [
            text[index : index + self.chunk_size] for index in range(0, len(text), self.chunk_size)
        ]
