"""Strongly typed, provider-neutral domain models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DomainModel(BaseModel):
    """Strict base that still tolerates additive provider metadata explicitly."""

    model_config = ConfigDict(extra="forbid", frozen=False, validate_assignment=True)


class MessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ContentPartType(StrEnum):
    TEXT = "text"
    FILE = "file"


class ContentPart(DomainModel):
    type: ContentPartType = ContentPartType.TEXT
    text: str = ""
    path: str | None = None
    mime_type: str | None = None


class Message(DomainModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    role: MessageRole
    content: list[ContentPart]
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def text(cls, role: MessageRole, text: str, **kwargs: Any) -> Message:
        return cls(role=role, content=[ContentPart(text=text)], **kwargs)

    @property
    def text_content(self) -> str:
        return "".join(part.text for part in self.content if part.type is ContentPartType.TEXT)


class ModelCapabilities(DomainModel):
    supports_streaming: bool = True
    supports_native_tools: bool = False
    supports_reasoning: bool = False
    supports_system_message: bool = True
    context_window: int | None = Field(default=None, gt=0)
    max_output_tokens: int | None = Field(default=None, gt=0)
    tokenizer: str | None = None


class ModelConfig(ModelCapabilities):
    id: str
    provider: str
    model: str
    input_price: float | None = Field(default=None, ge=0)
    output_price: float | None = Field(default=None, ge=0)


class ToolRiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ToolDefinition(DomainModel):
    name: str
    description: str
    parameters: dict[str, Any]
    risk_level: ToolRiskLevel = ToolRiskLevel.LOW
    read_only: bool = True


class ToolCall(DomainModel):
    id: str
    name: str
    arguments: dict[str, Any]


class ToolResult(DomainModel):
    tool_call_id: str
    success: bool
    summary: str
    structured_data: dict[str, Any] = Field(default_factory=dict)
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    duration: float = Field(default=0, ge=0)
    truncated: bool = False
    error_type: str | None = None
    affected_paths: list[str] = Field(default_factory=list)


class Usage(DomainModel):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    estimated: bool = False
    cost: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def fill_total(self) -> Usage:
        expected = self.input_tokens + self.output_tokens
        if self.total_tokens == 0 and expected:
            self.total_tokens = expected
        elif self.total_tokens and self.total_tokens < expected:
            raise ValueError("total_tokens cannot be smaller than input + output")
        return self


class ChatRequest(DomainModel):
    model: ModelConfig
    messages: list[Message]
    tools: list[ToolDefinition] = Field(default_factory=list)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_output_tokens: int | None = Field(default=None, gt=0)
    stream: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentState(StrEnum):
    CREATED = "created"
    BUILDING_CONTEXT = "building_context"
    REQUESTING_MODEL = "requesting_model"
    STREAMING = "streaming"
    VALIDATING_TOOL = "validating_tool"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING_TOOL = "executing_tool"
    COMPACTING = "compacting"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class RunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class AgentRun(DomainModel):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    state: AgentState = AgentState.CREATED
    status: RunStatus = RunStatus.RUNNING
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    ended_at: datetime | None = None
    step_count: int = Field(default=0, ge=0)
    tool_call_count: int = Field(default=0, ge=0)
    usage: Usage = Field(default_factory=Usage)
    error: str | None = None


class AgentRunResult(DomainModel):
    run: AgentRun
    final_text: str = ""
    messages: list[Message] = Field(default_factory=list)


class ApprovalDecision(StrEnum):
    ALLOW_ONCE = "allow_once"
    ALLOW_SESSION = "allow_session"
    DENY = "deny"
    CANCEL_RUN = "cancel_run"


class ApprovalRequest(DomainModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    tool_call: ToolCall
    risk_level: ToolRiskLevel
    paths: list[str] = Field(default_factory=list)
    command: list[str] | str | None = None
    diff_preview: str | None = None
    decision: ApprovalDecision | None = None


class HealthStatus(StrEnum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    SKIPPED = "skipped"


class ProviderHealth(DomainModel):
    status: HealthStatus
    message: str
    latency_ms: float | None = Field(default=None, ge=0)


FinishReason = Literal["stop", "tool_calls", "length", "cancelled", "error", "unknown"]
