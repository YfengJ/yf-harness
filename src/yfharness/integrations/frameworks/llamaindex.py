"""LlamaIndex Workflow agent adapter."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Generator
from typing import Any

import httpx

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


class LlamaIndexAdapter(FrameworkAdapter):
    name = FrameworkName.LLAMAINDEX

    async def run(self, request: FrameworkRequest, config: AppConfig) -> FrameworkResult:
        from llama_index.core.agent.workflow import ReActAgent

        runtime = resolve_runtime(request, config)
        http_client: httpx.AsyncClient | None = None
        if runtime.is_mock:
            model: Any = _offline_llm(f"[LlamaIndex offline] 已收到任务：{request.task}")
        else:
            from llama_index.llms.openai_like import OpenAILike  # type: ignore[import-untyped]

            http_client = httpx.AsyncClient(verify=runtime.verify_ssl)
            model = OpenAILike(
                model=runtime.model_id,
                api_base=runtime.base_url,
                api_key=runtime.api_key,
                timeout=runtime.timeout_seconds,
                max_retries=runtime.max_retries,
                context_window=runtime.context_window,
                is_chat_model=True,
                is_function_calling_model=False,
                async_http_client=http_client,
            )
        started = time.perf_counter()
        try:
            agent = ReActAgent(
                llm=model,
                tools=[],
                system_prompt=request.system_prompt,
                streaming=False,
                timeout=runtime.timeout_seconds,
            )
            async with asyncio.timeout(runtime.timeout_seconds):
                response = await agent.run(user_msg=request.task)
            message = getattr(response, "response", response)
            text = str(getattr(message, "content", message)).strip()
            if not text:
                raise FrameworkError("LlamaIndex 未返回文本内容")
            return FrameworkResult(
                framework=self.name,
                provider=runtime.provider,
                model=runtime.model_name,
                text=text,
                duration=time.perf_counter() - started,
                usage=_response_usage(response, request.task, text),
                metadata={
                    "native_agent": "llama_index.core.agent.workflow.ReActAgent",
                    "tools": 0,
                },
            )
        except TimeoutError as exc:
            raise FrameworkError(f"LlamaIndex 运行超时 ({runtime.timeout_seconds:g}s)") from exc
        except FrameworkError:
            raise
        except Exception as exc:
            raise FrameworkError(
                f"LlamaIndex 运行失败: {safe_error_message(exc, runtime.api_key)}"
            ) from exc
        finally:
            if http_client is not None:
                await http_client.aclose()


def _offline_llm(answer: str) -> Any:
    from llama_index.core.base.llms.types import CompletionResponse, LLMMetadata
    from llama_index.core.llms import CustomLLM
    from llama_index.core.llms.callbacks import llm_completion_callback

    class OfflineLLM(CustomLLM):
        @property
        def metadata(self) -> Any:
            return LLMMetadata(
                context_window=32_000,
                num_output=512,
                is_chat_model=False,
                model_name="yfh-offline",
            )

        @llm_completion_callback()
        def complete(self, prompt: str, **kwargs: Any) -> Any:
            del prompt, kwargs
            return CompletionResponse(text=f"Thought: I can answer directly.\nAnswer: {answer}")

        @llm_completion_callback()
        def stream_complete(self, prompt: str, **kwargs: Any) -> Generator[Any, None, None]:
            yield self.complete(prompt, **kwargs)

    return OfflineLLM()


def _response_usage(response: Any, task: str, text: str) -> Usage:
    raw = getattr(response, "raw", None)
    if isinstance(raw, dict) and isinstance(raw.get("usage"), dict):
        value = raw["usage"]
        input_tokens = int(value.get("prompt_tokens", 0))
        output_tokens = int(value.get("completion_tokens", 0))
        if input_tokens or output_tokens:
            return Usage(input_tokens=input_tokens, output_tokens=output_tokens)
    return estimated_usage(task, text)
