"""Review and conflict-safe restoration of persisted agent file changes."""

from __future__ import annotations

import difflib
import hashlib
from pathlib import Path

from yfharness.core.exceptions import ToolExecutionError
from yfharness.core.models import DomainModel
from yfharness.storage.models import FileChangeRecord
from yfharness.storage.repositories import FileChangeRepository
from yfharness.tools.changes import _atomic_bytes
from yfharness.tools.security import WorkspaceGuard, truncate_output


class ChangeReviewItem(DomainModel):
    id: str
    run_id: str | None = None
    path: str
    summary: str
    diff: str
    created_at: str
    status: str
    can_restore: bool


class WorkspaceReview:
    """Turn stored snapshots into reviewable diffs and safe restore actions."""

    def __init__(
        self,
        workspace: Path,
        repository: FileChangeRepository,
        *,
        diff_limit: int = 60_000,
    ) -> None:
        self.guard = WorkspaceGuard(workspace)
        self.repository = repository
        self.diff_limit = diff_limit

    async def list_for_session(self, session_id: str) -> list[ChangeReviewItem]:
        records = await self.repository.list_for_session(session_id)
        return [self._review_item(record) for record in records]

    async def restore(self, record_id: str) -> str:
        record = await self.repository.get(record_id)
        if record is None:
            raise ToolExecutionError("变更记录不存在")
        if record.undone_at is not None:
            raise ToolExecutionError("该变更已经撤销")
        if " -> " in record.path or (record.before_hash is None and record.after_hash is None):
            raise ToolExecutionError("该变更类型暂不支持单独撤销")
        path = self.guard.resolve(record.path)
        current = path.read_bytes() if path.is_file() else None
        if _hash(current) != record.after_hash:
            raise ToolExecutionError("文件在 Agent 修改后又发生变化，已拒绝覆盖")
        if record.before_content is None:
            if path.exists():
                path.unlink()
            message = f"已撤销新建文件 {record.path}"
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            _atomic_bytes(path, record.before_content)
            message = f"已恢复文件 {record.path}"
        if not await self.repository.mark_undone(record.id):
            raise ToolExecutionError("变更状态已被其他操作更新")
        return message

    async def restore_run(self, run_id: str) -> str:
        records = await self.repository.list_for_run(run_id)
        active = [record for record in records if record.undone_at is None]
        if not active:
            raise ToolExecutionError("该运行没有可撤销的文件变更")
        virtual: dict[Path, bytes | None] = {}
        original: dict[Path, bytes | None] = {}
        for record in active:
            if " -> " in record.path or (record.before_hash is None and record.after_hash is None):
                raise ToolExecutionError("该运行包含暂不支持整体撤销的变更类型")
            path = self.guard.resolve(record.path)
            if path.exists() and not path.is_file():
                raise ToolExecutionError(f"目标不是普通文件，已拒绝覆盖：{record.path}")
            if path not in virtual:
                current = path.read_bytes() if path.is_file() else None
                virtual[path] = current
                original[path] = current
            if _hash(virtual[path]) != record.after_hash:
                raise ToolExecutionError(f"{record.path} 在 Agent 修改后又发生变化，整组撤销已取消")
            virtual[path] = record.before_content

        written: dict[Path, bytes | None] = {}
        try:
            for record in active:
                path = self.guard.resolve(record.path)
                current = path.read_bytes() if path.is_file() else None
                if _hash(current) != record.after_hash:
                    raise ToolExecutionError(
                        f"{record.path} 在撤销写入前又发生变化，整组撤销已取消"
                    )
                _restore_content(path, record.before_content)
                written[path] = record.before_content
            if not await self.repository.mark_undone_many([record.id for record in active]):
                raise ToolExecutionError("变更状态已被其他操作更新，整组撤销已回滚")
        except Exception as exc:
            rollback_conflicts: list[str] = []
            for path, restored_content in written.items():
                current = path.read_bytes() if path.is_file() else None
                if _hash(current) != _hash(restored_content):
                    rollback_conflicts.append(self.guard.relative(path))
                    continue
                _restore_content(path, original[path])
            if rollback_conflicts:
                joined = "、".join(rollback_conflicts)
                raise ToolExecutionError(
                    f"整组撤销遇到并发编辑，以下文件未覆盖，请人工检查：{joined}"
                ) from exc
            raise
        return f"已安全撤销本次运行的 {len(active)} 项文件变更"

    def _review_item(self, record: FileChangeRecord) -> ChangeReviewItem:
        status = "undone" if record.undone_at is not None else "active"
        can_restore = (
            status == "active"
            and " -> " not in record.path
            and not (record.before_hash is None and record.after_hash is None)
        )
        return ChangeReviewItem(
            id=record.id,
            run_id=record.run_id,
            path=record.path,
            summary=_change_summary(record),
            diff=_unified_diff(record, self.diff_limit),
            created_at=record.created_at.isoformat(),
            status=status,
            can_restore=can_restore,
        )


def _change_summary(record: FileChangeRecord) -> str:
    if record.undone_at is not None:
        return "已撤销"
    if record.before_hash is None and record.after_hash is not None:
        return "新增文件"
    if record.before_hash is not None and record.after_hash is None:
        return "删除文件"
    if record.before_hash != record.after_hash:
        return "修改文件"
    return "文件操作"


def _unified_diff(record: FileChangeRecord, limit: int) -> str:
    before = _decode(record.before_content)
    after = _decode(record.after_content)
    if before is None or after is None:
        return "二进制内容不提供文本 Diff"
    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)
    rendered = "".join(
        difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile=f"a/{record.path}",
            tofile=f"b/{record.path}",
        )
    )
    return truncate_output(rendered or "内容未变化", limit)[0]


def _decode(content: bytes | None) -> str | None:
    if content is None:
        return ""
    if b"\x00" in content[:8192]:
        return None
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _hash(content: bytes | None) -> str | None:
    return hashlib.sha256(content).hexdigest() if content is not None else None


def _restore_content(path: Path, content: bytes | None) -> None:
    if content is None:
        if path.exists():
            path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_bytes(path, content)
