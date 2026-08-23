from __future__ import annotations

from pathlib import Path

import pytest

from yfharness.core.models import ApprovalDecision, ApprovalRequest, ToolCall
from yfharness.storage.database import Database
from yfharness.storage.repositories import FileChangeRepository
from yfharness.tools.base import ToolContext
from yfharness.tools.changes import ChangeEntry, ChangeJournal
from yfharness.tools.registry import ToolExecutor, builtin_tools
from yfharness.tools.security import WorkspaceGuard


@pytest.mark.asyncio
async def test_executor_can_persist_file_change_snapshot(tmp_path: Path) -> None:
    database = Database(tmp_path / "records.sqlite3")
    await database.initialize()
    repository = FileChangeRepository(database)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    guard = WorkspaceGuard(workspace)

    async def record(entry: ChangeEntry) -> None:
        await repository.record(
            path=guard.relative(entry.path),
            before=entry.before,
            after=entry.after,
            run_id=None,
            tool_call_id="write-1",
        )

    async def allow(_: ApprovalRequest) -> ApprovalDecision:
        return ApprovalDecision.ALLOW_ONCE

    context = ToolContext(
        workspace=guard.root,
        guard=guard,
        changes=ChangeJournal(guard),
        change_recorder=record,
    )
    executor = ToolExecutor(builtin_tools(), context, approval_handler=allow)
    await executor.execute(
        ToolCall(
            id="write-1",
            name="write_file",
            arguments={"path": "created.txt", "content": "content"},
        )
    )

    async with database.connect() as connection:
        row = await (
            await connection.execute(
                "SELECT path, before_hash, after_hash FROM file_change_records"
            )
        ).fetchone()
    assert row is not None
    assert row["path"] == "created.txt"
    assert row["before_hash"] is None
    assert row["after_hash"]
