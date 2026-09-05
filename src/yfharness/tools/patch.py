"""Strict unified-diff application; context must match exactly."""

from __future__ import annotations

import difflib
import re
import time
from dataclasses import dataclass

from yfharness.core.exceptions import ToolExecutionError
from yfharness.core.models import ToolResult, ToolRiskLevel
from yfharness.tools.base import Tool, ToolContext, ToolInput, ToolPreview
from yfharness.tools.changes import ChangeEntry
from yfharness.tools.filesystem import _atomic_write, _hash, _journal

_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: .*)?$")


class ApplyPatchInput(ToolInput):
    path: str
    patch: str


@dataclass(slots=True)
class Hunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[str]


class ApplyPatchTool(Tool):
    name = "apply_patch"
    description = "对单个 UTF-8 文件应用严格 unified diff。"
    input_model = ApplyPatchInput
    risk_level = ToolRiskLevel.MEDIUM
    read_only = False

    async def preview(self, arguments: ToolInput, context: ToolContext) -> ToolPreview:
        assert isinstance(arguments, ApplyPatchInput)
        path = context.guard.resolve(arguments.path, must_exist=True)
        # Parse and dry-run before asking, so approval never presents an invalid patch.
        original = _decode_utf8(path.read_bytes())
        _apply(_normalize_newlines(original), _normalize_newlines(arguments.patch))
        return ToolPreview(paths=[context.guard.relative(path)], diff=arguments.patch)

    async def execute(self, arguments: ToolInput, context: ToolContext) -> ToolResult:
        assert isinstance(arguments, ApplyPatchInput)
        started = time.monotonic()
        path = context.guard.resolve(arguments.path, must_exist=True)
        before = path.read_bytes()
        old_text = _decode_utf8(before)
        newline = _preferred_newline(old_text)
        new_text = _apply(
            _normalize_newlines(old_text),
            _normalize_newlines(arguments.patch),
        )
        _atomic_write(path, _restore_newlines(new_text, newline))
        after = path.read_bytes()
        _journal(context).record(ChangeEntry(kind="write", path=path, before=before, after=after))
        relative = context.guard.relative(path)
        return ToolResult(
            tool_call_id=context.tool_call_id or "",
            success=True,
            summary=f"已应用补丁 {relative}",
            structured_data={"before_sha256": _hash(before), "after_sha256": _hash(after)},
            duration=time.monotonic() - started,
            affected_paths=[relative],
        )


def _apply(original: str, patch: str) -> str:
    hunks = _parse_hunks(patch)
    source = original.splitlines(keepends=True)
    output: list[str] = []
    cursor = 0
    for hunk in hunks:
        start = hunk.old_start if hunk.old_count == 0 else hunk.old_start - 1
        if start < cursor or start > len(source):
            raise ToolExecutionError("补丁 hunk 行号超出范围或重叠")
        output.extend(source[cursor:start])
        source_index = start
        old_seen = 0
        new_seen = 0
        for patch_line in hunk.lines:
            marker, content = patch_line[0], patch_line[1:]
            if marker in {" ", "-"}:
                if source_index >= len(source) or source[source_index] != content:
                    raise ToolExecutionError(
                        f"补丁上下文不匹配，源文件第 {source_index + 1} 行已变化"
                    )
                if marker == " ":
                    output.append(content)
                    new_seen += 1
                source_index += 1
                old_seen += 1
            elif marker == "+":
                output.append(content)
                new_seen += 1
            elif marker == "\\" and patch_line.startswith("\\ No newline"):
                continue
            else:
                raise ToolExecutionError(f"无效补丁行标记: {marker!r}")
        if (old_seen, new_seen) != (hunk.old_count, hunk.new_count):
            raise ToolExecutionError("补丁 hunk 行数与头部不一致")
        cursor = source_index
    output.extend(source[cursor:])
    return "".join(output)


def _parse_hunks(patch: str) -> list[Hunk]:
    lines = patch.splitlines(keepends=True)
    hunks: list[Hunk] = []
    index = 0
    while index < len(lines):
        line = lines[index].rstrip("\r\n")
        if line.startswith(("--- ", "+++ ", "diff ", "index ")) or not line:
            index += 1
            continue
        match = _HUNK.match(line)
        if match is None:
            raise ToolExecutionError(f"补丁包含 hunk 外内容: {line[:80]}")
        index += 1
        body: list[str] = []
        while index < len(lines) and not lines[index].startswith("@@ "):
            if lines[index].startswith("\\ No newline at end of file"):
                if not body:
                    raise ToolExecutionError("无效的补丁换行标记")
                body[-1] = body[-1].removesuffix("\n")
            else:
                body.append(lines[index])
            index += 1
        hunks.append(
            Hunk(
                old_start=int(match.group(1)),
                old_count=int(match.group(2) or 1),
                new_start=int(match.group(3)),
                new_count=int(match.group(4) or 1),
                lines=body,
            )
        )
    if not hunks:
        raise ToolExecutionError("补丁不包含 unified diff hunk")
    return hunks


def create_patch(path: str, old: str, new: str) -> str:
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )


def _decode_utf8(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ToolExecutionError("补丁目标必须是 UTF-8 文本") from exc


def _preferred_newline(content: str) -> str:
    if "\r\n" in content:
        return "\r\n"
    if "\r" in content:
        return "\r"
    return "\n"


def _normalize_newlines(content: str) -> str:
    return content.replace("\r\n", "\n").replace("\r", "\n")


def _restore_newlines(content: str, newline: str) -> str:
    return content if newline == "\n" else content.replace("\n", newline)
