"""Framework discovery without importing optional SDKs."""

from __future__ import annotations

from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from typing import cast

from yfharness.integrations.frameworks.base import (
    FrameworkAdapter,
    FrameworkError,
    FrameworkInfo,
    FrameworkName,
    FrameworkUnavailableError,
)

_PACKAGES: dict[FrameworkName, tuple[str, dict[str, str]]] = {
    FrameworkName.LANGCHAIN: (
        "LangChain",
        {"langchain": "langchain", "langchain-openai": "langchain-openai"},
    ),
    FrameworkName.LLAMAINDEX: (
        "LlamaIndex",
        {
            "llama-index-core": "llama-index-core",
            "llama-index-llms-openai-like": "llama-index-llms-openai-like",
        },
    ),
    FrameworkName.AUTOGEN: (
        "AutoGen",
        {"autogen-agentchat": "autogen-agentchat", "autogen-ext": "autogen-ext"},
    ),
}

_ADAPTERS: dict[FrameworkName, tuple[str, str]] = {
    FrameworkName.LANGCHAIN: (
        "yfharness.integrations.frameworks.langchain",
        "LangChainAdapter",
    ),
    FrameworkName.LLAMAINDEX: (
        "yfharness.integrations.frameworks.llamaindex",
        "LlamaIndexAdapter",
    ),
    FrameworkName.AUTOGEN: ("yfharness.integrations.frameworks.autogen", "AutoGenAdapter"),
}


def framework_info(name: FrameworkName) -> FrameworkInfo:
    display_name, packages = _PACKAGES[name]
    versions: dict[str, str] = {}
    for label, distribution in packages.items():
        try:
            versions[label] = version(distribution)
        except PackageNotFoundError:
            continue
    return FrameworkInfo(
        name=name,
        display_name=display_name,
        installed=len(versions) == len(packages),
        versions=versions,
        install_extra=name.value,
    )


def framework_infos() -> list[FrameworkInfo]:
    return [framework_info(name) for name in FrameworkName]


def get_adapter(name: FrameworkName) -> FrameworkAdapter:
    info = framework_info(name)
    if not info.installed:
        raise FrameworkUnavailableError(
            f"{info.display_name} 未完整安装；请运行 pip install 'yf-harness[{info.install_extra}]'"
        )
    module_name, class_name = _ADAPTERS[name]
    try:
        adapter_class = getattr(import_module(module_name), class_name)
        return cast(FrameworkAdapter, adapter_class())
    except (ImportError, AttributeError) as exc:
        raise FrameworkError(
            f"{info.display_name} 已安装但无法加载，请检查 extra 版本是否一致: {exc}"
        ) from exc
