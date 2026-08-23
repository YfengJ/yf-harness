"""Recoverable in-session file changes used by `/undo`."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from yfharness.core.exceptions import ToolExecutionError
from yfharness.tools.security import WorkspaceGuard


@dataclass(slots=True)
class ChangeEntry:
    kind: str
    path: Path
    before: bytes | None = None
    after: bytes | None = None
    destination: Path | None = None


class ChangeJournal:
    def __init__(self, guard: WorkspaceGuard) -> None:
        self.guard = guard
        self._entries: list[ChangeEntry] = []

    def record(self, entry: ChangeEntry) -> None:
        self.guard.resolve(entry.path)
        if entry.destination is not None:
            self.guard.resolve(entry.destination)
        self._entries.append(entry)

    @property
    def count(self) -> int:
        return len(self._entries)

    def entries_since(self, index: int) -> list[ChangeEntry]:
        return list(self._entries[index:])

    def undo_last(self) -> str:
        if not self._entries:
            raise ToolExecutionError("没有可撤销的文件修改")
        entry = self._entries.pop()
        path = self.guard.resolve(entry.path)
        if entry.kind == "write":
            if entry.before is None:
                if path.exists():
                    path.unlink()
                return f"已撤销新建文件 {self.guard.relative(path)}"
            _atomic_bytes(path, entry.before)
            return f"已恢复文件 {self.guard.relative(path)}"
        if entry.kind == "delete":
            if entry.before is None:
                path.mkdir(parents=False, exist_ok=False)
            else:
                _atomic_bytes(path, entry.before)
            return f"已恢复删除路径 {self.guard.relative(path)}"
        if entry.kind == "mkdir":
            path.rmdir()
            return f"已撤销目录 {self.guard.relative(path)}"
        if entry.kind == "move" and entry.destination is not None:
            destination = self.guard.resolve(entry.destination, must_exist=True)
            if path.exists():
                raise ToolExecutionError("原路径已存在，无法安全撤销移动")
            os.replace(destination, path)
            if entry.before is not None:
                _atomic_bytes(entry.destination, entry.before)
            return f"已撤销移动 {self.guard.relative(destination)}"
        raise ToolExecutionError(f"未知修改记录类型: {entry.kind}")


def _atomic_bytes(path: Path, content: bytes) -> None:
    temporary = path.with_name(f".{path.name}.yfh-undo-{os.getpid()}")
    try:
        temporary.write_bytes(content)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
