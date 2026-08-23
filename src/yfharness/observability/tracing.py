"""Async-safe trace/run correlation context."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

current_run_id: ContextVar[str | None] = ContextVar("yfh_run_id", default=None)
current_trace_id: ContextVar[str | None] = ContextVar("yfh_trace_id", default=None)


@dataclass(frozen=True, slots=True)
class TraceContext:
    run_id: str
    trace_id: str


@contextmanager
def trace_scope(context: TraceContext) -> Iterator[None]:
    run_token = current_run_id.set(context.run_id)
    trace_token = current_trace_id.set(context.trace_id)
    try:
        yield
    finally:
        current_run_id.reset(run_token)
        current_trace_id.reset(trace_token)
