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


@pytest.mark.asyncio
async def test_restore_run_rewinds_multiple_changes_in_reverse_order(tmp_path: Path) -> None:
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
    changed = workspace / "changed.txt"
    created = workspace / "created.txt"
    changed.write_bytes(b"second\n")
    created.write_bytes(b"new\n")
    first_id = await changes.record(
        path="changed.txt",
        before=b"original\n",
        after=b"first\n",
        run_id=run.run_id,
        tool_call_id="write-1",
    )
    second_id = await changes.record(
        path="changed.txt",
        before=b"first\n",
        after=b"second\n",
        run_id=run.run_id,
        tool_call_id="write-2",
    )
    created_id = await changes.record(
        path="created.txt",
        before=None,
        after=b"new\n",
        run_id=run.run_id,
        tool_call_id="write-3",
    )

    message = await WorkspaceReview(workspace, changes).restore_run(run.run_id)

    assert message == "已安全撤销本次运行的 3 项文件变更"
    assert changed.read_bytes() == b"original\n"
    assert not created.exists()
    assert all(
        record is not None and record.undone_at is not None
        for record in (
            await changes.get(first_id),
            await changes.get(second_id),
            await changes.get(created_id),
        )
    )


@pytest.mark.asyncio
async def test_restore_run_is_all_or_nothing_when_any_file_conflicts(tmp_path: Path) -> None:
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
    safe = workspace / "safe.txt"
    conflict = workspace / "conflict.txt"
    safe.write_bytes(b"agent safe\n")
    conflict.write_bytes(b"later user edit\n")
    safe_id = await changes.record(
        path="safe.txt",
        before=b"before safe\n",
        after=b"agent safe\n",
        run_id=run.run_id,
        tool_call_id="write-1",
    )
    conflict_id = await changes.record(
        path="conflict.txt",
        before=b"before conflict\n",
        after=b"agent conflict\n",
        run_id=run.run_id,
        tool_call_id="write-2",
    )

    with pytest.raises(ToolExecutionError, match="整组撤销已取消"):
        await WorkspaceReview(workspace, changes).restore_run(run.run_id)

    assert safe.read_bytes() == b"agent safe\n"
    assert conflict.read_bytes() == b"later user edit\n"
    assert (await changes.get(safe_id)).undone_at is None  # type: ignore[union-attr]
    assert (await changes.get(conflict_id)).undone_at is None  # type: ignore[union-attr]
