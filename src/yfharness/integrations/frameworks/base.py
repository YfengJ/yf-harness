"""Framework-neutral request, result, and provider resolution contracts."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pydantic import Field

from yfharness.config.models import AppConfig
from yfharness.core.exceptions import HarnessError
from yfharness.core.models import DomainModel, Usage


class FrameworkName(StrEnum):
    LANGCHAIN = "langchain"
    LLAMAINDEX = "llamaindex"
    AUTOGEN = "autogen"


class FrameworkError(HarnessError):
    """A normalized framework integration failure."""


class FrameworkUnavailableError(FrameworkError):
    """The requested optional framework packages are not installed."""


class FrameworkInfo(DomainModel):
    name: FrameworkName
    display_name: str
    installed: bool
    versions: dict[str, str] = Field(default_factory=dict)
    install_extra: str


class FrameworkRequest(DomainModel):
    task: str = Field(min_length=1)
    provider: str
    model: str
    system_prompt: str = "You are a helpful assistant."
    timeout_seconds: float = Field(default=120, gt=0)


class FrameworkResult(DomainModel):
    framework: FrameworkName
    provider: str
    model: str
    text: str
    duration: float = Field(ge=0)
    usage: Usage = Field(default_factory=lambda: Usage(estimated=True))
    metadata: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FrameworkRuntime:
    provider: str
    model_name: str
    model_id: str
    is_mock: bool
    base_url: str | None
    api_key: str
    timeout_seconds: float
    max_retries: int
    verify_ssl: bool
    context_window: int


class FrameworkAdapter(ABC):
    name: FrameworkName

    @abstractmethod
    async def run(self, request: FrameworkRequest, config: AppConfig) -> FrameworkResult:
        """Run one task through the native framework agent API."""


def resolve_runtime(request: FrameworkRequest, config: AppConfig) -> FrameworkRuntime:
    try:
        provider = config.providers[request.provider]
    except KeyError as exc:
        raise FrameworkError(f"unknown provider {request.provider!r}") from exc
    try:
        model = config.models[request.model]
    except KeyError as exc:
        raise FrameworkError(f"unknown model {request.model!r}") from exc
    if model.provider != request.provider:
        raise FrameworkError(f"model {request.model!r} belongs to provider {model.provider!r}")
    api_key = ""
    if provider.api_key_env:
        api_key = os.environ.get(provider.api_key_env, "")
        if not api_key:
            raise FrameworkError(f"环境变量 {provider.api_key_env} 未设置")
    elif provider.type == "openai_compatible":
        # OpenAI-compatible local servers often ignore authentication, while SDKs require a value.
        api_key = "not-required"
    return FrameworkRuntime(
        provider=request.provider,
        model_name=request.model,
        model_id=model.model,
        is_mock=provider.type == "mock",
        base_url=provider.base_url,
        api_key=api_key,
        timeout_seconds=min(request.timeout_seconds, provider.timeout_seconds),
        max_retries=provider.max_retries,
        verify_ssl=provider.verify_ssl,
        context_window=model.context_window or 32_000,
    )


def estimated_usage(task: str, text: str) -> Usage:
    input_tokens = max(1, len(task) // 4)
    output_tokens = max(1, len(text) // 4)
    return Usage(input_tokens=input_tokens, output_tokens=output_tokens, estimated=True)


def safe_error_message(exc: Exception, api_key: str) -> str:
    """Keep SDK failures useful without echoing a runtime credential."""

    message = str(exc)
    if api_key and api_key != "not-required":
        message = message.replace(api_key, "<redacted>")
    return message
