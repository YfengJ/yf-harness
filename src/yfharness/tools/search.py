"""Bounded text and filename search without shell interpolation."""

from __future__ import annotations

import fnmatch
import os
import re
import time
from pathlib import Path

from pydantic import Field

from yfharness.core.models import ToolResult
from yfharness.tools.base import Tool, ToolContext, ToolInput


class SearchTextInput(ToolInput):
    query: str = Field(min_length=1)
    path: str = "."
    glob: str = "*"
    regex: bool = False
    case_sensitive: bool = False
    max_results: int = Field(default=200, ge=1, le=2_000)


class SearchTextTool(Tool):
    name = "search_text"
    description = "在 workspace 文本文件中进行有界搜索。"
    input_model = SearchTextInput

    async def execute(self, arguments: ToolInput, context: ToolContext) -> ToolResult:
        assert isinstance(arguments, SearchTextInput)
        started = time.monotonic()
        root = context.guard.resolve(arguments.path, must_exist=True)
        flags = 0 if arguments.case_sensitive else re.IGNORECASE
        pattern = re.compile(
            arguments.query if arguments.regex else re.escape(arguments.query), flags
        )
        matches: list[dict[str, object]] = []
        truncated = False
        for file_path in _files(root):
            if not fnmatch.fnmatch(file_path.name, arguments.glob):
                continue
            try:
                if file_path.stat().st_size > context.read_limit:
                    continue
                raw = file_path.read_bytes()
                if b"\x00" in raw[:8192]:
                    continue
                text = raw.decode("utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for line_number, line in enumerate(text.splitlines(), 1):
                if pattern.search(line):
                    matches.append(
                        {
                            "path": context.guard.relative(file_path),
                            "line": line_number,
                            "text": line[:500],
                        }
                    )
                    if len(matches) >= arguments.max_results:
                        truncated = True
                        break
            if truncated:
                break
        return ToolResult(
            tool_call_id=context.tool_call_id or "",
            success=True,
            summary=f"找到 {len(matches)} 处匹配",
            structured_data={"matches": matches},
            duration=time.monotonic() - started,
            truncated=truncated,
        )


class FindFilesInput(ToolInput):
    pattern: str = Field(min_length=1)
    path: str = "."
    max_results: int = Field(default=500, ge=1, le=5_000)


class FindFilesTool(Tool):
    name = "find_files"
    description = "按 glob 查找 workspace 文件。"
    input_model = FindFilesInput

    async def execute(self, arguments: ToolInput, context: ToolContext) -> ToolResult:
        assert isinstance(arguments, FindFilesInput)
        started = time.monotonic()
        root = context.guard.resolve(arguments.path, must_exist=True)
        matches: list[str] = []
        truncated = False
        for file_path in _files(root):
            relative_to_search = file_path.relative_to(root).as_posix()
            if fnmatch.fnmatch(relative_to_search, arguments.pattern) or fnmatch.fnmatch(
                file_path.name, arguments.pattern
            ):
                matches.append(context.guard.relative(file_path))
                if len(matches) >= arguments.max_results:
                    truncated = True
                    break
        return ToolResult(
            tool_call_id=context.tool_call_id or "",
            success=True,
            summary=f"找到 {len(matches)} 个文件",
            structured_data={"paths": matches},
            duration=time.monotonic() - started,
            truncated=truncated,
        )


def _files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    files: list[Path] = []
    for directory, names, filenames in os.walk(root, followlinks=False):
        names[:] = [name for name in names if not (Path(directory) / name).is_symlink()]
        files.extend(
            Path(directory) / name
            for name in filenames
            if not (Path(directory) / name).is_symlink()
        )
    return files
