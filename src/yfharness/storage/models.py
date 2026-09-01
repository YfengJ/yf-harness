"""Storage-facing records kept separate from provider and UI models."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from yfharness.core.compaction import CompactionSummary
from yfharness.core.models import DomainModel


class SessionRecord(DomainModel):
    id: str
    title: str
    provider: str
    model: str
    mode: str
    workspace: str | None = None
    goal: str | None = None
    goal_status: str = "inactive"
    goal_updated_at: datetime | None = None
    context_summary: CompactionSummary | None = None
    context_compacted_at: datetime | None = None
    archived: bool
    created_at: datetime
    updated_at: datetime


class UsageTotals(DomainModel):
    run_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_tokens: int = 0
    estimated_runs: int = 0
    known_cost: float = 0.0
    unknown_cost_runs: int = 0
    duration: float = 0.0


class UsageOverview(DomainModel):
    session: UsageTotals = Field(default_factory=UsageTotals)
    today: UsageTotals = Field(default_factory=UsageTotals)
    month: UsageTotals = Field(default_factory=UsageTotals)
    generated_at: datetime


class FileChangeRecord(DomainModel):
    id: str
    run_id: str | None = None
    tool_call_id: str | None = None
    path: str
    before_hash: str | None = None
    after_hash: str | None = None
    before_content: bytes | None = None
    after_content: bytes | None = None
    created_at: datetime
    undone_at: datetime | None = None
