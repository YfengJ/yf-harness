"""Provider construction without conditionals leaking into CLI or AgentRunner."""

from __future__ import annotations

from collections.abc import Callable

import httpx

from yfharness.config.models import AppConfig
from yfharness.providers.base import Provider

ProviderFactory = Callable[..., Provider]


class ProviderRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, ProviderFactory] = {}

    def register(self, name: str, factory: ProviderFactory) -> None:
        if not name.strip():
            raise ValueError("provider name must not be empty")
        if name in self._factories:
            raise ValueError(f"provider already registered: {name}")
        self._factories[name] = factory

    def create(self, name: str, **kwargs: object) -> Provider:
        try:
            factory = self._factories[name]
        except KeyError as exc:
            choices = ", ".join(sorted(self._factories)) or "none"
            raise ValueError(f"unknown provider {name!r}; available: {choices}") from exc
        return factory(**kwargs)

    def names(self) -> list[str]:
        return sorted(self._factories)


def builtin_registry() -> ProviderRegistry:
    from yfharness.providers.mock import MockProvider

    registry = ProviderRegistry()
    registry.register("mock", MockProvider)
    return registry


def provider_from_config(
    config: AppConfig,
    name: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> Provider:
    """Build a configured provider while keeping secrets in the environment."""

    try:
        settings = config.providers[name]
    except KeyError as exc:
        choices = ", ".join(sorted(config.providers)) or "none"
        raise ValueError(f"unknown provider {name!r}; available: {choices}") from exc
    if settings.type == "mock":
        from yfharness.providers.mock import MockProvider

        return MockProvider()

    from yfharness.providers.openai_compatible import OpenAICompatibleProvider

    models = {key: value for key, value in config.models.items() if value.provider == name}
    return OpenAICompatibleProvider(name, settings, models, client=client)
