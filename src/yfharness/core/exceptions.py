"""Normalized failures crossing YF-Harness subsystem boundaries."""

from __future__ import annotations

from typing import Any


class HarnessError(Exception):
    """Base class for errors safe to present at the application boundary."""


class ProviderError(HarnessError):
    """A provider failure independent of the provider's response shape."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "provider_error",
        retryable: bool = False,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.status_code = status_code
        self.details = details or {}


class ToolExecutionError(HarnessError):
    """A validated tool failed during execution."""


class PolicyDeniedError(HarnessError):
    """A policy prevented an operation before it executed."""


class ContextOverflowError(HarnessError):
    """A request cannot fit after allowed context reduction."""


class ToolProtocolError(HarnessError):
    """A fallback tool envelope is malformed or mixed with prose."""


class AgentLimitError(HarnessError):
    """A configured run, tool, token, or cost limit was reached."""
