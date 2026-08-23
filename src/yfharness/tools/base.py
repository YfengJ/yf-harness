"""Tool contracts and execution context."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from yfharness.core.models import ToolDefinition, ToolResult, ToolRiskLevel
from yfharness.tools.changes import ChangeEntry, ChangeJournal
from yfharness.tools.security import WorkspaceGuard


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


@dataclass(slots=True)
class ToolContext:
    workspace: Path
    guard: WorkspaceGuard
    output_limit: int = 100_000
    read_limit: int = 1_000_000
    command_timeout: float = 120.0
    run_id: str | None = None
    tool_call_id: str | None = None
    changes: ChangeJournal | None = None
    change_recorder: Callable[[ChangeEntry], Awaitable[None]] | None = None


@dataclass(slots=True)
class ToolPreview:
    paths: list[str]
    command: list[str] | str | None = None
    diff: str | None = None
    network: bool = False


class Tool(ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    input_model: ClassVar[type[ToolInput]]
    risk_level: ClassVar[ToolRiskLevel] = ToolRiskLevel.LOW
    read_only: ClassVar[bool] = True
    always_approval: ClassVar[bool] = False

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self.input_model.model_json_schema(),
            risk_level=self.risk_level,
            read_only=self.read_only,
        )

    def effective_risk(self, arguments: ToolInput) -> ToolRiskLevel:
        return self.risk_level

    def requires_approval(self, arguments: ToolInput) -> bool:
        return self.always_approval

    async def preview(self, arguments: ToolInput, context: ToolContext) -> ToolPreview:
        return ToolPreview(paths=[])

    @abstractmethod
    async def execute(self, arguments: ToolInput, context: ToolContext) -> ToolResult:
        """Execute already validated and authorized arguments."""


def result_error(
    *,
    tool_call_id: str,
    summary: str,
    error_type: str,
    stderr: str = "",
) -> ToolResult:
    return ToolResult(
        tool_call_id=tool_call_id,
        success=False,
        summary=summary,
        error_type=error_type,
        stderr=stderr,
    )
