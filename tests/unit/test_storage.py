from __future__ import annotations

import json
from pathlib import Path

import pytest

from yfharness.core.models import Message, MessageRole, RunStatus
from yfharness.storage.database import Database
from yfharness.storage.migrations import SCHEMA_VERSION
from yfharness.storage.repositories import RunRepository, SessionRepository


@pytest.mark.asyncio
async def test_migration_creates_required_tables(tmp_path: Path) -> None:
    database = Database(tmp_path / "data" / "test.sqlite3")
    await database.initialize()

    async with database.connect() as connection:
        rows = await (
            await connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        ).fetchall()

    tables = {row["name"] for row in rows}
    assert await database.schema_version() == SCHEMA_VERSION
    assert {
        "sessions",
        "messages",
        "runs",
        "model_requests",
        "tool_calls",
        "approvals",
        "usage_records",
        "context_snapshots",
        "file_change_records",
        "application_settings",
        "schema_version",
    } <= tables


@pytest.mark.asyncio
async def test_session_crud_search_and_export(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.sqlite3")
    await database.initialize()
    repository = SessionRepository(database)
    session = await repository.create(title="Alpha_100%", provider="mock", model="mock-default")
    await repository.add_message(session.id, Message.text(MessageRole.USER, "hello"))
    await repository.add_message(session.id, Message.text(MessageRole.ASSISTANT, "world"))

    assert [item.id for item in await repository.list(query="_100%")] == [session.id]
    assert await repository.rename(session.id, "Renamed")
    assert (await repository.get(session.id)).title == "Renamed"  # type: ignore[union-attr]
    markdown = await repository.export(session.id)
    payload = json.loads(await repository.export(session.id, format="json"))
    assert "## user" in markdown and "hello" in markdown
    assert len(payload["messages"]) == 2
    assert await repository.archive(session.id)
    assert await repository.list() == []
    assert len(await repository.list(include_archived=True)) == 1
    assert await repository.delete(session.id)
    assert await repository.get(session.id) is None


@pytest.mark.asyncio
async def test_sessions_are_scoped_to_their_resolved_workspace(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.sqlite3")
    await database.initialize()
    repository = SessionRepository(database)
    first_workspace = tmp_path / "first"
    second_workspace = tmp_path / "second"
    first_workspace.mkdir()
    second_workspace.mkdir()
    first = await repository.create(
        title="First",
        provider="mock",
        model="mock-default",
        workspace=first_workspace,
    )
    second = await repository.create(
        title="Second",
        provider="mock",
        model="mock-default",
        workspace=second_workspace,
    )
    legacy = await repository.create(
        title="Legacy",
        provider="mock",
        model="mock-default",
    )

    assert [item.id for item in await repository.list(workspace=first_workspace)] == [first.id]
    assert [item.id for item in await repository.list(workspace=second_workspace)] == [second.id]
    assert {item.id for item in await repository.list()} == {first.id, second.id, legacy.id}
    assert (await repository.fork(first.id)).workspace == str(first_workspace.resolve())


@pytest.mark.asyncio
async def test_session_fork_copies_history_without_reusing_message_ids(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.sqlite3")
    await database.initialize()
    repository = SessionRepository(database)
    source = await repository.create(title="Original", provider="mock", model="mock-default")
    await repository.add_message(source.id, Message.text(MessageRole.USER, "explore option A"))

    forked = await repository.fork(source.id)

    source_messages = await repository.messages(source.id)
    forked_messages = await repository.messages(forked.id)
    assert forked.id != source.id
    assert forked.title == "Original · 分支"
    assert forked_messages[0].text_content == "explore option A"
    assert forked_messages[0].id != source_messages[0].id


@pytest.mark.asyncio
async def test_export_redacts_likely_credentials(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.sqlite3")
    await database.initialize()
    repository = SessionRepository(database)
    session = await repository.create(title="Secrets", provider="mock", model="mock-default")
    await repository.add_message(
        session.id,
        Message.text(MessageRole.USER, "Authorization: Bearer secret-value"),
    )

    exported = await repository.export(session.id, format="json")

    assert "secret-value" not in exported
    assert "<redacted" in exported


@pytest.mark.asyncio
async def test_running_records_are_marked_interrupted(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.sqlite3")
    await database.initialize()
    sessions = SessionRepository(database)
    runs = RunRepository(database)
    session = await sessions.create(title="Crash", provider="mock", model="mock-default")
    run = await runs.create(session.id)

    assert await runs.mark_interrupted() == 1
    recovered = await runs.get(run.run_id)
    assert recovered is not None
    assert recovered.status is RunStatus.INTERRUPTED
