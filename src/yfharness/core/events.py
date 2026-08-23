"""Normalized streaming events emitted by every provider."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field

from yfharness.core.models import DomainModel, FinishReason, ToolCall, Usage


class TextDelta(DomainModel):
    type: Literal["text_delta"] = "text_delta"
    text: str


class ReasoningDelta(DomainModel):
    type: Literal["reasoning_delta"] = "reasoning_delta"
    text: str


class ToolCallStarted(DomainModel):
    type: Literal["tool_call_started"] = "tool_call_started"
    index: int
    call_id: str
    name: str = ""


class ToolCallDelta(DomainModel):
    type: Literal["tool_call_delta"] = "tool_call_delta"
    index: int
    call_id: str
    name_delta: str = ""
    arguments_delta: str = ""


class ToolCallCompleted(DomainModel):
    type: Literal["tool_call_completed"] = "tool_call_completed"
    tool_call: ToolCall


class UsageEvent(DomainModel):
    type: Literal["usage"] = "usage"
    usage: Usage


class FinishEvent(DomainModel):
    type: Literal["finish"] = "finish"
    reason: FinishReason


class ErrorEvent(DomainModel):
    type: Literal["error"] = "error"
    message: str
    code: str = "provider_error"
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class StreamEnd(DomainModel):
    type: Literal["stream_end"] = "stream_end"


type ModelEvent = Annotated[
    TextDelta
    | ReasoningDelta
    | ToolCallStarted
    | ToolCallDelta
    | ToolCallCompleted
    | UsageEvent
    | FinishEvent
    | ErrorEvent
    | StreamEnd,
    Field(discriminator="type"),
]
