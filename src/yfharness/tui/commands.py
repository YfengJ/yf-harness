"""Client-side Slash Command parsing and discoverability."""

from __future__ import annotations

import difflib
import shlex
from dataclasses import dataclass

COMMANDS: dict[str, str] = {
    "help": "显示帮助",
    "new": "新建会话",
    "sessions": "聚焦会话列表",
    "rename": "重命名当前会话",
    "model": "查看或切换模型",
    "provider": "查看或切换 Provider",
    "mode": "查看或切换模式",
    "tools": "列出可用工具",
    "permissions": "查看或切换审批策略",
    "context": "显示上下文组成",
    "add": "附加文件或目录",
    "remove": "移除附加上下文",
    "compact": "压缩当前对话",
    "retry": "重试上一条任务",
    "stop": "停止当前运行",
    "clear": "清空界面消息",
    "undo": "撤销最近文件修改",
    "export": "导出当前会话",
    "logs": "打开日志与诊断",
    "doctor": "执行诊断",
    "quit": "退出 TUI",
}


@dataclass(frozen=True, slots=True)
class SlashCommand:
    name: str
    arguments: tuple[str, ...]


class SlashCommandError(ValueError):
    pass


def parse_slash_command(value: str) -> SlashCommand | None:
    stripped = value.strip()
    if not stripped.startswith("/"):
        return None
    try:
        parts = shlex.split(stripped[1:])
    except ValueError as exc:
        raise SlashCommandError(f"命令参数无法解析: {exc}") from exc
    if not parts:
        raise SlashCommandError("请输入 Slash Command；使用 /help 查看列表")
    name = parts[0].lower()
    if name not in COMMANDS:
        suggestion = difflib.get_close_matches(name, COMMANDS, n=1, cutoff=0.5)
        suffix = f"，你是否想输入 /{suggestion[0]}？" if suggestion else ""
        raise SlashCommandError(f"未知命令 /{name}{suffix}")
    return SlashCommand(name=name, arguments=tuple(parts[1:]))


def command_suggestions(prefix: str) -> list[str]:
    value = prefix.strip().lstrip("/").lower()
    return [
        f"/{name} — {description}"
        for name, description in COMMANDS.items()
        if name.startswith(value)
    ]
