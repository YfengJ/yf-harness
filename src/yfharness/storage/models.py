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
