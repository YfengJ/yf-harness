from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Markdown

from yfharness.tui.commands import COMMANDS


class HelpScreen(ModalScreen[None]):
    BINDINGS: ClassVar[list[BindingType]] = [("escape", "dismiss", "关闭")]

    def compose(self) -> ComposeResult:
        shortcuts = """
# YF-Harness 帮助

- `Ctrl+N` 新会话 · `Ctrl+K` 命令提示 · `Ctrl+C` 取消运行
- `Ctrl+L` 聚焦输入 · `Ctrl+P` 切换模式 · `Ctrl+O` 聚焦会话
- `Ctrl+Enter` 发送 · `F1` 帮助 · `Esc` 返回
- `Alt+↑/↓` 输入历史 · `Ctrl+Shift+A` 暂停/恢复自动滚动

## Slash Commands
"""
        command_lines = "\n".join(
            f"- `/{name}` — {description}" for name, description in COMMANDS.items()
        )
        with Vertical(id="modal-card"):
            yield Markdown(shortcuts + command_lines)
            yield Button("关闭", id="close", variant="primary")

    def on_button_pressed(self, _: Button.Pressed) -> None:
        self.dismiss()
