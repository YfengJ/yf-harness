from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx
from typer.testing import CliRunner

from yfharness.cli import app
from yfharness.config.models import AppConfig, ProviderSettings
from yfharness.core.models import ModelConfig
from yfharness.integrations.frameworks import (
    FrameworkName,
    FrameworkRequest,
    get_adapter,
)

pytestmark = [
    pytest.mark.frameworks,
    pytest.mark.filterwarnings(
        "ignore:The `__fields__` attribute is deprecated.*:DeprecationWarning"
    ),
    pytest.mark.filterwarnings(
        "ignore:The `__fields_set__` attribute is deprecated.*:DeprecationWarning"
    ),
    pytest.mark.filterwarnings(
        "ignore:Accessing the 'model_computed_fields' attribute.*:DeprecationWarning"
    ),
    pytest.mark.filterwarnings(
        "ignore:Accessing the 'model_fields' attribute.*:DeprecationWarning"
    ),
    pytest.mark.filterwarnings("ignore:is_running called from within a step.*:DeprecationWarning"),
]

runner = CliRunner()


@pytest.mark.asyncio
@pytest.mark.parametrize("framework", list(FrameworkName))
async def test_every_framework_runs_a_native_offline_agent(framework: FrameworkName) -> None:
    result = await get_adapter(framework).run(
        FrameworkRequest(task="offline contract", provider="mock", model="mock-default"),
        AppConfig(),
    )

    assert result.framework is framework
    assert "offline" in result.text.lower()
    assert result.metadata["tools"] == 0
    assert result.metadata["native_agent"]
    assert result.usage.total_tokens > 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("framework", "native_content", "expected"),
    [
        (FrameworkName.LANGCHAIN, "LangChain remote response", "LangChain remote response"),
        (
            FrameworkName.LLAMAINDEX,
            "Thought: I can answer directly.\nAnswer: LlamaIndex remote response",
            "LlamaIndex remote response",
        ),
        (FrameworkName.AUTOGEN, "AutoGen remote response", "AutoGen remote response"),
    ],
)
@respx.mock
async def test_every_framework_uses_its_real_openai_compatible_client(
    framework: FrameworkName,
    native_content: str,
    expected: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    route = respx.post("https://example.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=_chat_completion(native_content))
    )
    monkeypatch.setenv("TEST_FRAMEWORK_KEY", "test-secret")

    result = await get_adapter(framework).run(
        FrameworkRequest(task="remote contract", provider="remote", model="remote-model"),
        _remote_config(),
    )

    assert expected in result.text
    assert route.called
    request = route.calls.last.request
    assert request.headers["authorization"] == "Bearer test-secret"
    body = json.loads(request.content)
    assert body["model"] == "test-model"
    assert result.usage.input_tokens == 11
    assert result.usage.output_tokens == 7


def test_framework_cli_lists_diagnoses_and_runs_all_offline() -> None:
    listed = runner.invoke(app, ["frameworks", "list"])
    diagnosed = runner.invoke(app, ["frameworks", "doctor"])

    assert listed.exit_code == 0, listed.output
    assert diagnosed.exit_code == 0, diagnosed.output
    for framework in FrameworkName:
        assert f"{framework.value}\tinstalled" in listed.output
        assert f"[OK] framework:{framework.value}" in diagnosed.output
        run = runner.invoke(
            app,
            ["frameworks", "run", framework.value, "cli contract", "--output", "json"],
        )
        assert run.exit_code == 0, run.output
        payload = json.loads(run.output)
        assert payload["framework"] == framework.value
        assert payload["metadata"]["tools"] == 0


def test_framework_cli_rejects_unknown_name_and_output() -> None:
    unknown = runner.invoke(app, ["frameworks", "run", "unknown", "task"])
    bad_output = runner.invoke(app, ["frameworks", "run", "langchain", "task", "--output", "yaml"])

    assert unknown.exit_code == 2 and "未知框架" in unknown.output
    assert bad_output.exit_code == 2 and "text 或 json" in bad_output.output


def _remote_config() -> AppConfig:
    return AppConfig(
        default_provider="remote",
        default_model="remote-model",
        providers={
            "remote": ProviderSettings(
                type="openai_compatible",
                base_url="https://example.test/v1",
                api_key_env="TEST_FRAMEWORK_KEY",
                timeout_seconds=5,
                max_retries=0,
            )
        },
        models={
            "remote-model": ModelConfig(
                id="remote-model",
                provider="remote",
                model="test-model",
                context_window=8_000,
            )
        },
    )


def _chat_completion(content: str) -> dict[str, Any]:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1_700_000_000,
        "model": "test-model",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
    }
