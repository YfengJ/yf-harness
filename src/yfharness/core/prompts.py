"""Small composable prompts; policy enforcement remains in code."""

from __future__ import annotations

import json

from yfharness.core.models import ToolDefinition
from yfharness.core.policies import AgentMode
from yfharness.core.tool_protocol import END_MARKER, START_MARKER

_MODE_INSTRUCTIONS = {
    AgentMode.CHAT: "当前为 Chat 模式：专注对话，不请求写入或执行工具。",
    AgentMode.PLAN: "当前为 Plan 模式：只读取、搜索和检查状态，不修改任何内容。",
    AgentMode.AGENT: "当前为 Agent 模式：可以请求工具，但所有调用受权限和审批约束。",
    AgentMode.REVIEW: "当前为 Review 模式：读取 diff、文件和测试信息，输出结构化审查，不修改内容。",
}


def build_system_prompt(
    mode: AgentMode,
    tools: list[ToolDefinition],
    *,
    native_tools: bool,
) -> str:
    sections = [
        "你是 YF-Harness 中运行的模型。模型输出不拥有任何直接权限。",
        _MODE_INSTRUCTIONS[mode],
    ]
    if tools and not native_tools:
        schemas = [tool.model_dump(mode="json") for tool in tools]
        example = {"tool": "read_file", "arguments": {"path": "README.md"}}
        sections.append(
            "原生工具调用不可用。仅当确实需要工具时，整个回答必须严格为：\n"
            f"{START_MARKER}\n{json.dumps(example, ensure_ascii=False)}\n{END_MARKER}\n"
            "不得添加解释、Markdown 代码块或猜测参数。可用工具 Schema：\n"
            + json.dumps(schemas, ensure_ascii=False)
        )
    return "\n\n".join(sections)
