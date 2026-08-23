"""Strict fallback tool protocol for models without native tool calling."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from yfharness.core.exceptions import ToolProtocolError
from yfharness.core.models import ToolCall

START_MARKER = "<YFH_TOOL_CALL>"
END_MARKER = "</YFH_TOOL_CALL>"


def parse_fallback_tool_calls(text: str) -> list[ToolCall] | None:
    stripped = text.strip()
    contains_marker = START_MARKER in stripped or END_MARKER in stripped
    if not contains_marker:
        return None
    if not (stripped.startswith(START_MARKER) and stripped.endswith(END_MARKER)):
        raise ToolProtocolError("工具调用边界前后不能包含解释文字或 Markdown")
    if stripped.count(START_MARKER) != 1 or stripped.count(END_MARKER) != 1:
        raise ToolProtocolError("工具调用必须包含且只包含一对边界标记")
    payload_text = stripped[len(START_MARKER) : -len(END_MARKER)].strip()
    if payload_text.startswith("```") or payload_text.endswith("```"):
        raise ToolProtocolError("工具调用 JSON 不能包裹 Markdown 代码块")
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise ToolProtocolError(f"工具调用 JSON 无效: {exc.msg}") from exc
    items = payload if isinstance(payload, list) else [payload]
    if not items:
        raise ToolProtocolError("工具调用列表不能为空")
    return [_parse_item(item) for item in items]


def _parse_item(value: Any) -> ToolCall:
    if not isinstance(value, dict):
        raise ToolProtocolError("每个工具调用必须是 JSON 对象")
    allowed = {"id", "tool", "arguments"}
    if extra := set(value) - allowed:
        raise ToolProtocolError(f"工具调用包含未知字段: {', '.join(sorted(extra))}")
    name = value.get("tool")
    arguments = value.get("arguments")
    if not isinstance(name, str) or not name.strip():
        raise ToolProtocolError("tool 必须是非空字符串")
    if not isinstance(arguments, dict):
        raise ToolProtocolError("arguments 必须是 JSON 对象")
    call_id = value.get("id")
    if call_id is not None and not isinstance(call_id, str):
        raise ToolProtocolError("id 必须是字符串")
    return ToolCall(id=call_id or f"fallback-{uuid4()}", name=name, arguments=arguments)
