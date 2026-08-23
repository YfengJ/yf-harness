from __future__ import annotations

import pytest

from yfharness.providers.mock import MockProvider
from yfharness.providers.registry import ProviderRegistry, builtin_registry


def test_builtin_registry_constructs_mock() -> None:
    assert isinstance(builtin_registry().create("mock"), MockProvider)


def test_registry_rejects_duplicate_name() -> None:
    registry = ProviderRegistry()
    registry.register("mock", MockProvider)

    with pytest.raises(ValueError, match="already registered"):
        registry.register("mock", MockProvider)


def test_registry_reports_available_names() -> None:
    with pytest.raises(ValueError, match="available: mock"):
        builtin_registry().create("missing")
