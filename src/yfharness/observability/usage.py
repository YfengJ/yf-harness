"""Explicit configured-price cost calculation."""

from __future__ import annotations

from yfharness.core.models import ModelConfig, Usage


def calculate_cost(usage: Usage, model: ModelConfig) -> float | None:
    if model.input_price is None and model.output_price is None:
        return None
    return (
        usage.input_tokens * (model.input_price or 0)
        + usage.output_tokens * (model.output_price or 0)
    ) / 1_000_000
