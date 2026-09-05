"""Workspace-confined file and directory tools with atomic writes."""

from __future__ import annotations

import difflib
import hashlib
import os
import time
from pathlib import Path

from pydantic import Field

from yfharness.core.models import ToolResult, ToolRiskLevel
from yfharness.tools.base import Tool, ToolContext, ToolInput, ToolPreview, result_error
from yfharness.tools.changes import ChangeEntry, ChangeJournal, _atomic_bytes
from yfharness.tools.security import truncate_output


class PathInput(ToolInput):
    path: str


class ListDirectoryInput(PathInput):
    max_entries: int = Field(default=500, ge=1, le=5_000)


class ListDirectoryTool(Tool):
    name = "list_directory"
    description = "列出 workspace 内目录内容。"
    input_model = ListDirectoryInput

    async def execute(self, arguments: ToolInput, context: ToolContext) -> ToolResult:
        assert isinstance(arguments, ListDirectoryInput)
        started = time.monotonic()
        path = context.guard.resolve(arguments.path, must_exist=True)
        if not path.is_dir():
            return result_error(
                tool_call_id=context.tool_call_id or "",
                summary="目标不是目录",
                error_type="not_directory",
            )
        entries = []
        truncated = False
        for index, item in enumerate(sorted(path.iterdir(), key=lambda value: value.name.lower())):
            if index >= arguments.max_entries:
                truncated = True
                break
            kind = "directory" if item.is_dir() else "file"
            if item.is_symlink():
                kind = "symlink"
            entries.append({"name": item.name, "type": kind})
        return ToolResult(
            tool_call_id=context.tool_call_id or "",
            success=True,
            summary=f"列出 {len(entries)} 个条目",
            structured_data={"path": context.guard.relative(path), "entries": entries},
            duration=time.monotonic() - started,
            truncated=truncated,
        )


class ReadFileInput(PathInput):
    max_chars: int | None = Field(default=None, ge=1)


class ReadFileTool(Tool):
    name = "read_file"
    description = "以 UTF-8 读取 workspace 内文本文件。"
    input_model = ReadFileInput

    async def execute(self, arguments: ToolInput, context: ToolContext) -> ToolResult:
        assert isinstance(arguments, ReadFileInput)
        started = time.monotonic()
        path = context.guard.resolve(arguments.path, must_exist=True)
        if not path.is_file():
            return result_error(
                tool_call_id=context.tool_call_id or "",
                summary="目标不是普通文件",
                error_type="not_file",
            )
        if path.stat().st_size > context.read_limit:
            return result_error(
                tool_call_id=context.tool_call_id or "",
                summary=f"文件超过读取上限 {context.read_limit} bytes",
                error_type="file_too_large",
            )
        raw = path.read_bytes()
        if b"\x00" in raw[:8192]:
            return result_error(
                tool_call_id=context.tool_call_id or "",
                summary="拒绝读取疑似二进制文件",
                error_type="binary_file",
            )
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return result_error(
                tool_call_id=context.tool_call_id or "",
                summary="文件不是有效 UTF-8，请先转换编码",
                error_type="unknown_encoding",
            )
        limit = min(arguments.max_chars or context.output_limit, context.output_limit)
        output, truncated = truncate_output(text, limit)
        return ToolResult(
            tool_call_id=context.tool_call_id or "",
            success=True,
            summary=f"读取 {context.guard.relative(path)}",
            structured_data={"path": context.guard.relative(path), "size": len(raw)},
            stdout=output,
            duration=time.monotonic() - started,
            truncated=truncated,
            affected_paths=[context.guard.relative(path)],
        )


class GetFileInfoTool(Tool):
    name = "get_file_info"
    description = "读取文件或目录元数据。"
    input_model = PathInput

    async def execute(self, arguments: ToolInput, context: ToolContext) -> ToolResult:
        assert isinstance(arguments, PathInput)
        started = time.monotonic()
        path = context.guard.resolve(arguments.path, must_exist=True)
        stat = path.stat()
        data = {
            "path": context.guard.relative(path),
            "size": stat.st_size,
            "is_file": path.is_file(),
            "is_directory": path.is_dir(),
            "is_symlink": path.is_symlink(),
            "modified_ns": stat.st_mtime_ns,
        }
        return ToolResult(
            tool_call_id=context.tool_call_id or "",
            success=True,
            summary=f"获取 {data['path']} 元数据",
            structured_data=data,
            duration=time.monotonic() - started,
        )


class CreateDirectoryInput(PathInput):
    parents: bool = True
    exist_ok: bool = False


class CreateDirectoryTool(Tool):
    name = "create_directory"
    description = "在 workspace 内创建目录。"
    input_model = CreateDirectoryInput
    risk_level = ToolRiskLevel.MEDIUM
    read_only = False

    async def preview(self, arguments: ToolInput, context: ToolContext) -> ToolPreview:
        assert isinstance(arguments, CreateDirectoryInput)
        path = context.guard.resolve(arguments.path)
        return ToolPreview(paths=[context.guard.relative(path)])

    async def execute(self, arguments: ToolInput, context: ToolContext) -> ToolResult:
        assert isinstance(arguments, CreateDirectoryInput)
        started = time.monotonic()
        path = context.guard.resolve(arguments.path)
        existed = path.exists()
        path.mkdir(parents=arguments.parents, exist_ok=arguments.exist_ok)
        if not existed:
            _journal(context).record(ChangeEntry(kind="mkdir", path=path))
        relative = context.guard.relative(path)
        return ToolResult(
            tool_call_id=context.tool_call_id or "",
            success=True,
            summary=f"已创建目录 {relative}",
            duration=time.monotonic() - started,
            affected_paths=[relative],
        )


class WriteFileInput(PathInput):
    content: str
    overwrite: bool = True


class WriteFileTool(Tool):
    name = "write_file"
    description = "原子写入 UTF-8 文本，并记录可撤销快照。"
    input_model = WriteFileInput
    risk_level = ToolRiskLevel.MEDIUM
    read_only = False

    async def preview(self, arguments: ToolInput, context: ToolContext) -> ToolPreview:
        assert isinstance(arguments, WriteFileInput)
        path = context.guard.resolve(arguments.path)
        old = _read_existing_text(path)
        diff = _diff(path, old, arguments.content)
        return ToolPreview(paths=[context.guard.relative(path)], diff=diff)

    async def execute(self, arguments: ToolInput, context: ToolContext) -> ToolResult:
        assert isinstance(arguments, WriteFileInput)
        started = time.monotonic()
        path = context.guard.resolve(arguments.path)
        if path.exists() and not arguments.overwrite:
            return result_error(
                tool_call_id=context.tool_call_id or "",
                summary="文件已存在且 overwrite=false",
                error_type="already_exists",
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        before = path.read_bytes() if path.exists() else None
        _atomic_write(path, arguments.content)
        after = path.read_bytes()
        _journal(context).record(ChangeEntry(kind="write", path=path, before=before, after=after))
        relative = context.guard.relative(path)
        return ToolResult(
            tool_call_id=context.tool_call_id or "",
            success=True,
            summary=f"已原子写入 {relative}",
            structured_data={
                "before_sha256": _hash(before),
                "after_sha256": _hash(after),
            },
            duration=time.monotonic() - started,
            affected_paths=[relative],
        )


class MovePathInput(ToolInput):
    source: str
    destination: str
    overwrite: bool = False


class MovePathTool(Tool):
    name = "move_path"
    description = "在 workspace 内移动文件或目录。"
    input_model = MovePathInput
    risk_level = ToolRiskLevel.MEDIUM
    read_only = False

    async def preview(self, arguments: ToolInput, context: ToolContext) -> ToolPreview:
        assert isinstance(arguments, MovePathInput)
        source = context.guard.resolve(arguments.source, must_exist=True)
        destination = context.guard.resolve(arguments.destination)
        return ToolPreview(
            paths=[context.guard.relative(source), context.guard.relative(destination)]
        )

    async def execute(self, arguments: ToolInput, context: ToolContext) -> ToolResult:
        assert isinstance(arguments, MovePathInput)
        started = time.monotonic()
        source = context.guard.resolve(arguments.source, must_exist=True)
        destination = context.guard.resolve(arguments.destination)
        if destination.exists() and not arguments.overwrite:
            return result_error(
                tool_call_id=context.tool_call_id or "",
                summary="目标已存在且 overwrite=false",
                error_type="already_exists",
            )
        if destination.is_dir() and arguments.overwrite:
            return result_error(
                tool_call_id=context.tool_call_id or "",
                summary="为保证可撤销性，不支持覆盖已有目录",
                error_type="directory_overwrite_denied",
            )
        destination_before = destination.read_bytes() if destination.exists() else None
        source_content = source.read_bytes() if source.is_file() else None
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, destination)
        _journal(context).record(
            ChangeEntry(
                kind="move",
                path=source,
                destination=destination,
                before=destination_before,
                after=source_content,
            )
        )
        return ToolResult(
            tool_call_id=context.tool_call_id or "",
            success=True,
            summary=f"已移动到 {context.guard.relative(destination)}",
            duration=time.monotonic() - started,
            affected_paths=[context.guard.relative(source), context.guard.relative(destination)],
        )


class DeletePathTool(Tool):
    name = "delete_path"
    description = "删除 workspace 内单个文件或空目录；始终需要审批。"
    input_model = PathInput
    risk_level = ToolRiskLevel.HIGH
    read_only = False
    always_approval = True

    async def preview(self, arguments: ToolInput, context: ToolContext) -> ToolPreview:
        assert isinstance(arguments, PathInput)
        path = context.guard.resolve(arguments.path, must_exist=True)
        return ToolPreview(paths=[context.guard.relative(path)])

    async def execute(self, arguments: ToolInput, context: ToolContext) -> ToolResult:
        assert isinstance(arguments, PathInput)
        started = time.monotonic()
        path = context.guard.resolve(arguments.path, must_exist=True)
        before = path.read_bytes() if path.is_file() else None
        if path.is_dir():
            path.rmdir()
        else:
            path.unlink()
        _journal(context).record(ChangeEntry(kind="delete", path=path, before=before))
        relative = path.relative_to(context.guard.root).as_posix()
        return ToolResult(
            tool_call_id=context.tool_call_id or "",
            success=True,
            summary=f"已删除 {relative}",
            duration=time.monotonic() - started,
            affected_paths=[relative],
        )


def _journal(context: ToolContext) -> ChangeJournal:
    if context.changes is None:
        context.changes = ChangeJournal(context.guard)
    return context.changes


def _read_existing_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return "<binary or non-UTF-8 content>"


def _diff(path: Path, old: str, new: str) -> str:
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{path.name}",
            tofile=f"b/{path.name}",
        )
    )


def _atomic_write(path: Path, content: str) -> None:
    _atomic_bytes(path, content.encode("utf-8"))


def _hash(content: bytes | None) -> str | None:
    return hashlib.sha256(content).hexdigest() if content is not None else None
