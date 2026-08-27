"""Observable events emitted by the Agent state machine."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import Field

from yfharness.core.events import ModelEvent
from yfharness.core.models import AgentState, DomainModel, ToolCall, ToolResult, Usage
from yfharness.core.workflows import HookEvaluation


class StateChanged(DomainModel):
    type: Literal["state_changed"] = "state_changed"
    state: AgentState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ModelEventObserved(DomainModel):
    type: Literal["model_event"] = "model_event"
    event: ModelEvent


class ToolExecutionStarted(DomainModel):
    type: Literal["tool_execution_started"] = "tool_execution_started"
    call: ToolCall


class ToolExecutionFinished(DomainModel):
    type: Literal["tool_execution_finished"] = "tool_execution_finished"
    result: ToolResult


class BudgetUpdated(DomainModel):
    type: Literal["budget_updated"] = "budget_updated"
    usage: Usage
    cost: float = 0


class HookEvaluated(DomainModel):
    type: Literal["hook_evaluated"] = "hook_evaluated"
    evaluation: HookEvaluation


type AgentEvent = Annotated[
    StateChanged
    | ModelEventObserved
    | ToolExecutionStarted
    | ToolExecutionFinished
    | BudgetUpdated
    | HookEvaluated,
    Field(discriminator="type"),
]
