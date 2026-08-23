"""Microsoft AutoGen AgentChat adapter."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator, Mapping, Sequence
from typing import Any

from yfharness.config.models import AppConfig
from yfharness.core.models import Usage
from yfharness.integrations.frameworks.base import (
    FrameworkAdapter,
    FrameworkError,
    FrameworkName,
    FrameworkRequest,
    FrameworkResult,
    estimated_usage,
    resolve_runtime,
    safe_error_message,
)


class AutoGenAdapter(FrameworkAdapter):
    name = FrameworkName.AUTOGEN

    async def run(self, request: FrameworkRequest, config: AppConfig) -> FrameworkResult:
        from autogen_agentchat.agents import AssistantAgent
        from autogen_ext.models.openai import OpenAIChatCompletionClient

        runtime = resolve_runtime(request, config)
        if runtime.is_mock:
            model_client: Any = _offline_model_client(
                f"[AutoGen offline] 已收到任务：{request.task}"
            )
        else:
            assert runtime.base_url is not None
            model_client = OpenAIChatCompletionClient(
                model=runtime.model_id,
                base_url=runtime.base_url,
                api_key=runtime.api_key,
                timeout=runtime.timeout_seconds,
                max_retries=runtime.max_retries,
                model_info={
                    "vision": False,
                    "function_calling": True,
                    "json_output": False,
                    "family": "unknown",
                    "structured_output": False,
                    "multiple_system_messages": False,
                },
            )
        started = time.perf_counter()
        try:
            agent = AssistantAgent(
                "yfh_assistant",
                model_client=model_client,
                tools=[],
                system_message=request.system_prompt,
            )
            async with asyncio.timeout(runtime.timeout_seconds):
                result = await agent.run(task=request.task)
            text = _last_text(result.messages)
            if not text:
                raise FrameworkError("AutoGen 未返回文本内容")
            return FrameworkResult(
                framework=self.name,
                provider=runtime.provider,
                model=runtime.model_name,
                text=text,
                duration=time.perf_counter() - started,
                usage=_message_usage(result.messages, request.task, text),
                metadata={
                    "native_agent": "autogen_agentchat.agents.AssistantAgent",
                    "tools": 0,
                    "stop_reason": result.stop_reason,
                },
            )
        except TimeoutError as exc:
            raise FrameworkError(f"AutoGen 运行超时 ({runtime.timeout_seconds:g}s)") from exc
        except FrameworkError:
            raise
        except Exception as exc:
            raise FrameworkError(
                f"AutoGen 运行失败: {safe_error_message(exc, runtime.api_key)}"
            ) from exc
        finally:
            await model_client.close()


def _last_text(messages: Sequence[Any]) -> str:
    for message in reversed(messages):
        content = getattr(message, "content", "")
        if isinstance(content, str) and content:
            return content
    return ""


def _message_usage(messages: Sequence[Any], task: str, text: str) -> Usage:
    input_tokens = 0
    output_tokens = 0
    for message in messages:
        value = getattr(message, "models_usage", None)
        if value is not None:
            input_tokens += int(getattr(value, "prompt_tokens", 0))
            output_tokens += int(getattr(value, "completion_tokens", 0))
    if input_tokens or output_tokens:
        return Usage(input_tokens=input_tokens, output_tokens=output_tokens)
    return estimated_usage(task, text)


def _offline_model_client(answer: str) -> Any:
    from autogen_core import CancellationToken
    from autogen_core.models import (
        ChatCompletionClient,
        CreateResult,
        LLMMessage,
        ModelCapabilities,
        ModelInfo,
        RequestUsage,
    )
    from autogen_core.tools import Tool, ToolSchema
    from pydantic import BaseModel

    class OfflineClient(ChatCompletionClient):
        def __init__(self) -> None:
            self._usage = RequestUsage(prompt_tokens=0, completion_tokens=0)

        async def create(
            self,
            messages: Sequence[LLMMessage],
            *,
            tools: Sequence[Tool | ToolSchema] = (),
            tool_choice: Any = "auto",
            json_output: bool | type[BaseModel] | None = None,
            extra_create_args: Mapping[str, Any] = {},
            cancellation_token: CancellationToken | None = None,
        ) -> CreateResult:
            del tools, tool_choice, json_output, extra_create_args, cancellation_token
            prompt_tokens = max(1, sum(len(str(message)) for message in messages) // 4)
            usage = RequestUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=max(1, len(answer) // 4),
            )
            self._usage = usage
            return CreateResult(
                finish_reason="stop",
                content=answer,
                usage=usage,
                cached=False,
            )

        async def create_stream(
            self,
            messages: Sequence[LLMMessage],
            *,
            tools: Sequence[Tool | ToolSchema] = (),
            tool_choice: Any = "auto",
            json_output: bool | type[BaseModel] | None = None,
            extra_create_args: Mapping[str, Any] = {},
            cancellation_token: CancellationToken | None = None,
        ) -> AsyncGenerator[str | CreateResult, None]:
            yield await self.create(
                messages,
                tools=tools,
                tool_choice=tool_choice,
                json_output=json_output,
                extra_create_args=extra_create_args,
                cancellation_token=cancellation_token,
            )

        async def close(self) -> None:
            return None

        def actual_usage(self) -> RequestUsage:
            return self._usage

        def total_usage(self) -> RequestUsage:
            return self._usage

        def count_tokens(
            self, messages: Sequence[LLMMessage], *, tools: Sequence[Tool | ToolSchema] = ()
        ) -> int:
            return max(1, (sum(len(str(message)) for message in messages) + len(str(tools))) // 4)

        def remaining_tokens(
            self, messages: Sequence[LLMMessage], *, tools: Sequence[Tool | ToolSchema] = ()
        ) -> int:
            return max(0, 32_000 - self.count_tokens(messages, tools=tools))

        @property
        def capabilities(self) -> ModelCapabilities:
            return {
                "vision": False,
                "function_calling": True,
                "json_output": False,
            }

        @property
        def model_info(self) -> ModelInfo:
            return {
                "vision": False,
                "function_calling": True,
                "json_output": False,
                "family": "unknown",
                "structured_output": False,
                "multiple_system_messages": False,
            }

    return OfflineClient()
