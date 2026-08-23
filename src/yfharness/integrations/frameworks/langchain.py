"""LangChain 1.x agent adapter."""

from __future__ import annotations

import asyncio
import time
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


class LangChainAdapter(FrameworkAdapter):
    name = FrameworkName.LANGCHAIN

    async def run(self, request: FrameworkRequest, config: AppConfig) -> FrameworkResult:
        from langchain.agents import create_agent

        runtime = resolve_runtime(request, config)
        http_client: httpx.AsyncClient | None = None
        if runtime.is_mock:
            from langchain_core.language_models.fake_chat_models import FakeListChatModel

            model: Any = FakeListChatModel(
                responses=[f"[LangChain offline] 已收到任务：{request.task}"]
            )
        else:
            from langchain_openai import ChatOpenAI

            http_client = httpx.AsyncClient(verify=runtime.verify_ssl)
            model = ChatOpenAI(
                model=runtime.model_id,
                base_url=runtime.base_url,
                api_key=runtime.api_key,
                timeout=runtime.timeout_seconds,
                max_retries=runtime.max_retries,
                http_async_client=http_client,
            )
        started = time.perf_counter()
        try:
            agent = create_agent(model, tools=[], system_prompt=request.system_prompt)
            async with asyncio.timeout(runtime.timeout_seconds):
                response = await agent.ainvoke(
                    {"messages": [{"role": "user", "content": request.task}]}
                )
            messages = response.get("messages", [])
            text = _message_text(messages[-1]) if messages else ""
            if not text:
                raise FrameworkError("LangChain 未返回文本内容")
            return FrameworkResult(
                framework=self.name,
                provider=runtime.provider,
                model=runtime.model_name,
                text=text,
                duration=time.perf_counter() - started,
                usage=_message_usage(messages[-1], request.task, text),
                metadata={"native_agent": "langchain.agents.create_agent", "tools": 0},
            )
        except TimeoutError as exc:
            raise FrameworkError(f"LangChain 运行超时 ({runtime.timeout_seconds:g}s)") from exc
        except FrameworkError:
            raise
        except Exception as exc:
            raise FrameworkError(
                f"LangChain 运行失败: {safe_error_message(exc, runtime.api_key)}"
            ) from exc
        finally:
            if http_client is not None:
                await http_client.aclose()


def _message_text(message: Any) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [item.get("text", "") for item in content if isinstance(item, dict)]
        return "".join(str(part) for part in parts)
    return str(content) if content else ""


def _message_usage(message: Any, task: str, text: str) -> Usage:
    value = getattr(message, "usage_metadata", None)
    if isinstance(value, dict):
        input_tokens = int(value.get("input_tokens", 0))
        output_tokens = int(value.get("output_tokens", 0))
        if input_tokens or output_tokens:
            return Usage(input_tokens=input_tokens, output_tokens=output_tokens)
    return estimated_usage(task, text)
