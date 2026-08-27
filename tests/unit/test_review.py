from __future__ import annotations

from pathlib import Path

import pytest

from yfharness.core.exceptions import ToolExecutionError
from yfharness.core.review import WorkspaceReview
from yfharness.storage.database import Database
from yfharness.storage.repositories import FileChangeRepository, RunRepository, SessionRepository


@pytest.mark.asyncio
async def test_review_lists_diff_and_restores_when_file_is_unchanged(tmp_path: Path) -> None:
    database = Database(tmp_path / "review.sqlite3")
    await database.initialize()
    sessions = SessionRepository(database)
    session = await sessions.create(title="review", provider="mock", model="mock-default")
    run = await RunRepository(database).create(session.id)
    changes = FileChangeRepository(database)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    path = workspace / "example.txt"
    path.write_bytes(b"after\n")
    record_id = await changes.record(
        path="example.txt",
        before=b"before\n",
        after=b"after\n",
        run_id=run.run_id,
        tool_call_id="write-1",
    )
    review = WorkspaceReview(workspace, changes)

    items = await review.list_for_session(session.id)
    message = await review.restore(record_id)

    assert len(items) == 1
    assert items[0].summary == "修改文件"
    assert "-before" in items[0].diff
    assert "+after" in items[0].diff
    assert message == "已恢复文件 example.txt"
    assert path.read_bytes() == b"before\n"
    stored = await changes.get(record_id)
    assert stored is not None
    assert stored.undone_at is not None


@pytest.mark.asyncio
async def test_restore_refuses_to_overwrite_later_user_edit(tmp_path: Path) -> None:
    database = Database(tmp_path / "review.sqlite3")
    await database.initialize()
    session = await SessionRepository(database).create(
        title="review",
        provider="mock",
        model="mock-default",
    )
    run = await RunRepository(database).create(session.id)
    changes = FileChangeRepository(database)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    path = workspace / "example.txt"
    path.write_bytes(b"user edit\n")
    record_id = await changes.record(
        path="example.txt",
        before=b"before\n",
        after=b"agent edit\n",
        run_id=run.run_id,
        tool_call_id="write-1",
    )
    review = WorkspaceReview(workspace, changes)

    with pytest.raises(ToolExecutionError, match="拒绝覆盖"):
        await review.restore(record_id)

    assert path.read_bytes() == b"user edit\n"
