from __future__ import annotations

from importlib.metadata import PackageNotFoundError

import pytest

from yfharness.config.models import AppConfig, ProviderSettings
from yfharness.core.models import ModelConfig
from yfharness.integrations.frameworks import FrameworkName, FrameworkRequest, registry
from yfharness.integrations.frameworks.base import (
    FrameworkError,
    resolve_runtime,
    safe_error_message,
)


def test_framework_discovery_reports_optional_packages_without_importing_sdks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(_: str) -> str:
        raise PackageNotFoundError

    monkeypatch.setattr(registry, "version", missing)

    infos = registry.framework_infos()

    assert [info.name for info in infos] == list(FrameworkName)
    assert all(not info.installed and not info.versions for info in infos)
    assert {info.install_extra for info in infos} == {"langchain", "llamaindex", "autogen"}


def test_get_adapter_explains_how_to_install_missing_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        registry,
        "framework_info",
        lambda name: registry.FrameworkInfo(
            name=name,
            display_name="LangChain",
            installed=False,
            install_extra="langchain",
        ),
    )

    with pytest.raises(registry.FrameworkUnavailableError, match=r"yf-harness\[langchain\]"):
        registry.get_adapter(FrameworkName.LANGCHAIN)


def test_get_adapter_normalizes_an_incompatible_installed_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        registry,
        "framework_info",
        lambda name: registry.FrameworkInfo(
            name=name,
            display_name="LangChain",
            installed=True,
            versions={"langchain": "1.3.16", "langchain-openai": "1.6.0"},
            install_extra="langchain",
        ),
    )

    def broken_import(_: str) -> object:
        raise ImportError("broken dependency")

    monkeypatch.setattr(registry, "import_module", broken_import)

    with pytest.raises(FrameworkError, match="已安装但无法加载"):
        registry.get_adapter(FrameworkName.LANGCHAIN)


def test_sdk_error_message_redacts_runtime_api_key() -> None:
    assert safe_error_message(ValueError("request key=secret-value failed"), "secret-value") == (
        "request key=<redacted> failed"
    )


def test_resolve_runtime_never_reads_a_literal_api_key_from_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_FRAMEWORK_KEY", "secret-from-env")
    config = _remote_config()
    request = FrameworkRequest(task="hello", provider="remote", model="remote-model")

    runtime = resolve_runtime(request, config)

    assert runtime.api_key == "secret-from-env"
    assert runtime.model_id == "test-model"
    assert runtime.base_url == "https://example.test/v1"


def test_resolve_runtime_rejects_missing_key_and_model_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TEST_FRAMEWORK_KEY", raising=False)
    config = _remote_config()

    with pytest.raises(FrameworkError, match="TEST_FRAMEWORK_KEY"):
        resolve_runtime(
            FrameworkRequest(task="hello", provider="remote", model="remote-model"), config
        )
    with pytest.raises(FrameworkError, match="belongs to provider"):
        resolve_runtime(
            FrameworkRequest(task="hello", provider="mock", model="remote-model"), config
        )


def _remote_config() -> AppConfig:
    return AppConfig(
        default_provider="remote",
        default_model="remote-model",
        providers={
            "mock": ProviderSettings(type="mock"),
            "remote": ProviderSettings(
                type="openai_compatible",
                base_url="https://example.test/v1",
                api_key_env="TEST_FRAMEWORK_KEY",
                timeout_seconds=5,
                max_retries=0,
            ),
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
