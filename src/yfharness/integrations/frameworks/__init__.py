"""Unified, lazily loaded adapters for third-party agent frameworks."""

from yfharness.integrations.frameworks.base import (
    FrameworkAdapter,
    FrameworkInfo,
    FrameworkName,
    FrameworkRequest,
    FrameworkResult,
)
from yfharness.integrations.frameworks.registry import framework_info, framework_infos, get_adapter

__all__ = [
    "FrameworkAdapter",
    "FrameworkInfo",
    "FrameworkName",
    "FrameworkRequest",
    "FrameworkResult",
    "framework_info",
    "framework_infos",
    "get_adapter",
]
