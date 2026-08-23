"""Provider abstraction used by the rest of the harness."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from yfharness.core.events import ModelEvent
from yfharness.core.models import ChatRequest, ModelCapabilities, ProviderHealth


class Provider(ABC):
    """Translate a model service into a provider-neutral event stream."""

    name: str

    @abstractmethod
    async def list_models(self) -> list[str]:
        """Return model identifiers discoverable without leaking credentials."""

    @abstractmethod
    def validate_config(self) -> list[str]:
        """Return human-readable validation problems; an empty list means valid."""

    @abstractmethod
    def stream_chat(self, request: ChatRequest) -> AsyncIterator[ModelEvent]:
        """Yield only normalized model events."""

    @abstractmethod
    async def health_check(self) -> ProviderHealth:
        """Check whether the provider can accept a request."""

    @abstractmethod
    def estimate_tokens(self, text: str) -> int:
        """Estimate tokens when the service does not report usage."""

    @abstractmethod
    def get_capabilities(self, model: str) -> ModelCapabilities:
        """Return configured capabilities rather than global provider guesses."""
