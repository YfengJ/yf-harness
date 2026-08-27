"""Storage-facing records kept separate from provider and UI models."""

from __future__ import annotations

from datetime import datetime

from yfharness.core.models import DomainModel


class SessionRecord(DomainModel):
    id: str
    title: str
    provider: str
    model: str
    mode: str
    archived: bool
    created_at: datetime
    updated_at: datetime


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
