from __future__ import annotations

from pathlib import Path

import pytest

from yfharness.core.models import Usage
from yfharness.storage.database import Database
from yfharness.storage.repositories import RunRepository, SessionRepository, TraceRepository


@pytest.mark.asyncio
async def test_trace_repository_builds_redacted_read_only_replay(tmp_path: Path) -> None:
    database = Database(tmp_path / "trace.sqlite3")
    await database.initialize()
    sessions = SessionRepository(database)
    runs = RunRepository(database)
    traces = TraceRepository(database)
    session = await sessions.create(title="trace", provider="mock", model="scripted")
    run = await runs.create(session.id)
    await traces.record_model_events(
        run_id=run.run_id,
        provider="mock",
        model="scripted",
        request={"task": "hello", "api_key": "must-not-store"},
        events=[{"type": "text_delta", "text": "ok"}],
        duration=0.1,
    )
    await traces.record_tool_call(
        run_id=run.run_id,
        call_id="call-1",
        name="read_file",
        arguments={"path": "README.md"},
        result={"success": True},
        risk_level="low",
        status="completed",
    )
    await traces.record_approval(
        request_id="approval-1",
        run_id=run.run_id,
        tool_call_id="call-1",
        request={"authorization": "Bearer nope"},
        decision="allow_once",
    )
    await traces.record_usage(
        run_id=run.run_id,
        provider="mock",
        model="scripted",
        usage=Usage(input_tokens=1, output_tokens=2, estimated=True),
        duration=0.1,
    )
    await traces.record_context(
        run_id=run.run_id,
        snapshot={"sources": ["user"]},
        estimated_tokens=3,
    )

    replay = await traces.replay(run.run_id)

    assert replay["mode"] == "read_only_replay"
    assert replay["tool_calls"][0]["tool_name"] == "read_file"  # type: ignore[index]
    serialized = str(replay)
    assert "must-not-store" not in serialized
    assert "Bearer nope" not in serialized
