"""OpenAI-compatible HTTP/JSON and SSE provider implemented with httpx."""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Any

import httpx

from yfharness.config.models import ProviderSettings
from yfharness.core.attachments import image_data_url
from yfharness.core.events import (
    ErrorEvent,
    FinishEvent,
    ModelEvent,
    ReasoningDelta,
    StreamEnd,
    TextDelta,
    ToolCallCompleted,
    ToolCallDelta,
    ToolCallStarted,
    UsageEvent,
)
from yfharness.core.exceptions import ProviderError
from yfharness.core.models import (
    AttachmentTransfer,
    ChatRequest,
    ContentPartType,
    HealthStatus,
    Message,
    ModelCapabilities,
    ModelConfig,
    ProviderHealth,
    ToolCall,
    Usage,
)
from yfharness.providers.base import Provider

_RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}


class OpenAICompatibleProvider(Provider):
    def __init__(
        self,
        name: str,
        settings: ProviderSettings,
        models: Mapping[str, ModelConfig],
        *,
        client: httpx.AsyncClient | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        if settings.type != "openai_compatible":
            raise ValueError("OpenAICompatibleProvider requires openai_compatible settings")
        self.name = name
        self.settings = settings
        self.models = dict(models)
        self._client = client
        self._environ = environ if environ is not None else os.environ

    async def list_models(self) -> list[str]:
        async with self._client_scope() as client:
            response = await self._request_with_retry(client, "GET", "/models")
            payload = self._decode_json(response)
        items = payload.get("data", [])
        if not isinstance(items, list):
            return []
        return [str(item["id"]) for item in items if isinstance(item, dict) and "id" in item]

    def validate_config(self) -> list[str]:
        problems: list[str] = []
        if not self.settings.base_url:
            problems.append("缺少 base_url")
        if self.settings.api_key_env and not self._environ.get(self.settings.api_key_env):
            problems.append(f"缺少环境变量 {self.settings.api_key_env}")
        if not self.models:
            problems.append("没有配置模型")
        return problems

    async def health_check(self) -> ProviderHealth:
        if problems := self.validate_config():
            return ProviderHealth(status=HealthStatus.ERROR, message="; ".join(problems))
        started = time.monotonic()
        try:
            await self.list_models()
        except ProviderError as exc:
            return ProviderHealth(status=HealthStatus.ERROR, message=str(exc))
        return ProviderHealth(
            status=HealthStatus.OK,
            message="Provider 可访问",
            latency_ms=(time.monotonic() - started) * 1000,
        )

    def estimate_tokens(self, text: str) -> int:
        return max(1, (len(text) + 3) // 4) if text else 0

    def get_capabilities(self, model: str) -> ModelCapabilities:
        try:
            configured = self.models[model]
        except KeyError as exc:
            raise ProviderError(f"模型未配置: {model}", code="model_not_configured") from exc
        fields = set(ModelCapabilities.model_fields)
        return ModelCapabilities.model_validate(configured.model_dump(include=fields))

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[ModelEvent]:
        problems = self.validate_config()
        if problems:
            raise ProviderError("; ".join(problems), code="invalid_config")
        payload = self._build_payload(request)
        async with self._client_scope() as client:
            if request.stream:
                async for event in self._stream_response(client, payload):
                    yield event
            else:
                response = await self._request_with_retry(
                    client, "POST", "/chat/completions", json=payload
                )
                for event in self._parse_completion(self._decode_json(response)):
                    yield event

    def _build_payload(self, request: ChatRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": request.model.model,
            "messages": [
                self._message_payload(message, supports_images=request.model.supports_image_input)
                for message in request.messages
            ],
            "stream": request.stream,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        max_tokens = request.max_output_tokens or request.model.max_output_tokens
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if request.tools and request.model.supports_native_tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
                for tool in request.tools
            ]
        if request.stream:
            payload["stream_options"] = {"include_usage": True}
        return payload

    @staticmethod
    def _message_payload(message: Message, *, supports_images: bool) -> dict[str, Any]:
        remote_images = [
            part
            for part in message.content
            if part.type is ContentPartType.IMAGE
            and part.transfer is AttachmentTransfer.REMOTE_MODEL
        ]
        if remote_images and not supports_images:
            raise ProviderError(
                "当前模型未声明图片输入能力",
                code="image_input_not_supported",
            )
        text = "".join(part.text for part in message.content if part.type is ContentPartType.TEXT)
        content: str | list[dict[str, Any]] = text
        if remote_images:
            content = [{"type": "text", "text": text}]
            content.extend(
                {
                    "type": "image_url",
                    "image_url": {"url": image_data_url(part)},
                }
                for part in remote_images
            )
        value: dict[str, Any] = {
            "role": message.role.value,
            "content": content,
        }
        if message.name:
            value["name"] = message.name
        if message.tool_call_id:
            value["tool_call_id"] = message.tool_call_id
        if message.tool_calls:
            value["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(call.arguments, ensure_ascii=False),
                    },
                }
                for call in message.tool_calls
            ]
        return value

    async def _stream_response(
        self, client: httpx.AsyncClient, payload: dict[str, Any]
    ) -> AsyncIterator[ModelEvent]:
        response = await self._send_stream_with_retry(client, payload)
        builders: dict[int, dict[str, str]] = {}
        finished = False
        try:
            async for line in response.aiter_lines():
                if not line or line.startswith(":"):
                    continue
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError as exc:
                    raise ProviderError(
                        "流式响应包含无效 JSON", code="invalid_json", details={"line": data[:200]}
                    ) from exc
                async for event in self._parse_chunk(chunk, builders):
                    if isinstance(event, FinishEvent):
                        finished = True
                    yield event
        except httpx.HTTPError as exc:
            raise self._network_error(exc, code="stream_interrupted") from exc
        finally:
            await response.aclose()

        for index in sorted(builders):
            item = builders[index]
            arguments = self._parse_tool_arguments(item["arguments"])
            yield ToolCallCompleted(
                tool_call=ToolCall(id=item["id"], name=item["name"], arguments=arguments)
            )
        if not finished:
            yield FinishEvent(reason="unknown")
        yield StreamEnd()

    async def _parse_chunk(
        self, chunk: Any, builders: dict[int, dict[str, str]]
    ) -> AsyncIterator[ModelEvent]:
        if not isinstance(chunk, dict):
            return
        if isinstance(chunk.get("error"), dict):
            error = chunk["error"]
            yield ErrorEvent(
                message=str(error.get("message", "Provider error")),
                code=str(error.get("code", "provider_error")),
            )
        usage = chunk.get("usage")
        if isinstance(usage, dict):
            yield UsageEvent(usage=self._usage(usage))
        choices = chunk.get("choices")
        if not isinstance(choices, list):
            return
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            delta = choice.get("delta")
            if isinstance(delta, dict):
                content = delta.get("content")
                if isinstance(content, str) and content:
                    yield TextDelta(text=content)
                if self.settings.include_reasoning:
                    reasoning = delta.get("reasoning_content", delta.get("reasoning"))
                    if isinstance(reasoning, str) and reasoning:
                        yield ReasoningDelta(text=reasoning)
                tool_calls = delta.get("tool_calls")
                if isinstance(tool_calls, list):
                    for call_delta in tool_calls:
                        async for event in self._tool_delta(call_delta, builders):
                            yield event
            reason = choice.get("finish_reason")
            if reason is not None:
                normalized = reason if reason in {"stop", "tool_calls", "length"} else "unknown"
                yield FinishEvent(reason=normalized)

    async def _tool_delta(
        self, value: Any, builders: dict[int, dict[str, str]]
    ) -> AsyncIterator[ModelEvent]:
        if not isinstance(value, dict):
            return
        index = int(value.get("index", 0))
        function_value = value.get("function")
        function: dict[Any, Any] = function_value if isinstance(function_value, dict) else {}
        call_id = str(value.get("id") or builders.get(index, {}).get("id") or f"call-{index}")
        name_delta = str(function.get("name") or "")
        arguments_delta = str(function.get("arguments") or "")
        if index not in builders:
            builders[index] = {"id": call_id, "name": "", "arguments": ""}
            yield ToolCallStarted(index=index, call_id=call_id, name=name_delta)
        builders[index]["name"] += name_delta
        builders[index]["arguments"] += arguments_delta
        yield ToolCallDelta(
            index=index,
            call_id=call_id,
            name_delta=name_delta,
            arguments_delta=arguments_delta,
        )

    def _parse_completion(self, payload: dict[str, Any]) -> list[ModelEvent]:
        events: list[ModelEvent] = []
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderError("响应缺少 choices", code="invalid_response")
        choice = choices[0]
        if not isinstance(choice, dict):
            raise ProviderError("响应 choice 格式无效", code="invalid_response")
        message = choice.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str) and content:
                events.append(TextDelta(text=content))
            calls = message.get("tool_calls")
            if isinstance(calls, list):
                for item in calls:
                    events.append(ToolCallCompleted(tool_call=self._complete_tool(item)))
        usage = payload.get("usage")
        if isinstance(usage, dict):
            events.append(UsageEvent(usage=self._usage(usage)))
        reason = choice.get("finish_reason")
        normalized = reason if reason in {"stop", "tool_calls", "length"} else "unknown"
        events.extend([FinishEvent(reason=normalized), StreamEnd()])
        return events

    def _complete_tool(self, value: Any) -> ToolCall:
        if not isinstance(value, dict) or not isinstance(value.get("function"), dict):
            raise ProviderError("工具调用格式无效", code="invalid_tool_call")
        function = value["function"]
        return ToolCall(
            id=str(value.get("id", "call-0")),
            name=str(function.get("name", "")),
            arguments=self._parse_tool_arguments(str(function.get("arguments", "{}"))),
        )

    @staticmethod
    def _parse_tool_arguments(value: str) -> dict[str, Any]:
        try:
            parsed = json.loads(value or "{}")
        except json.JSONDecodeError as exc:
            raise ProviderError("工具参数不是有效 JSON", code="invalid_tool_arguments") from exc
        if not isinstance(parsed, dict):
            raise ProviderError("工具参数必须是 JSON 对象", code="invalid_tool_arguments")
        return parsed

    @staticmethod
    def _usage(value: Mapping[str, Any]) -> Usage:
        return Usage(
            input_tokens=int(value.get("prompt_tokens", 0)),
            output_tokens=int(value.get("completion_tokens", 0)),
            total_tokens=int(value.get("total_tokens", 0)),
            estimated=False,
        )

    async def _request_with_retry(
        self, client: httpx.AsyncClient, method: str, path: str, **kwargs: Any
    ) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self.settings.max_retries + 1):
            try:
                response = await client.request(method, path, **kwargs)
                if (
                    response.status_code in _RETRYABLE_STATUS
                    and attempt < self.settings.max_retries
                ):
                    await asyncio.sleep(0.25 * (2**attempt))
                    continue
                self._raise_for_status(response)
                return response
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                if attempt >= self.settings.max_retries:
                    break
                await asyncio.sleep(0.25 * (2**attempt))
        raise self._network_error(last_error or RuntimeError("request failed"))

    async def _send_stream_with_retry(
        self, client: httpx.AsyncClient, payload: dict[str, Any]
    ) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self.settings.max_retries + 1):
            request = client.build_request("POST", "/chat/completions", json=payload)
            try:
                response = await client.send(request, stream=True)
                if (
                    response.status_code in _RETRYABLE_STATUS
                    and attempt < self.settings.max_retries
                ):
                    await response.aclose()
                    await asyncio.sleep(0.25 * (2**attempt))
                    continue
                self._raise_for_status(response)
                return response
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                if attempt >= self.settings.max_retries:
                    break
                await asyncio.sleep(0.25 * (2**attempt))
        raise self._network_error(last_error or RuntimeError("stream request failed"))

    @staticmethod
    def _decode_json(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ProviderError("Provider 返回无效 JSON", code="invalid_json") from exc
        if not isinstance(payload, dict):
            raise ProviderError("Provider JSON 顶层必须是对象", code="invalid_json")
        return payload

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.is_success:
            return
        retryable = response.status_code in _RETRYABLE_STATUS
        message = f"Provider HTTP {response.status_code}"
        try:
            payload = response.json()
            if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
                message = str(payload["error"].get("message", message))
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
        raise ProviderError(
            message,
            code="http_error",
            retryable=retryable,
            status_code=response.status_code,
        )

    @staticmethod
    def _network_error(exc: Exception, *, code: str = "network_error") -> ProviderError:
        return ProviderError(str(exc) or exc.__class__.__name__, code=code, retryable=True)

    @asynccontextmanager
    async def _client_scope(self) -> AsyncIterator[httpx.AsyncClient]:
        if self._client is not None:
            yield self._client
            return
        api_key = (
            self._environ.get(self.settings.api_key_env, "") if self.settings.api_key_env else ""
        )
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        async with httpx.AsyncClient(
            base_url=str(self.settings.base_url).rstrip("/"),
            headers=headers,
            timeout=self.settings.timeout_seconds,
            verify=self.settings.verify_ssl,
        ) as client:
            yield client
