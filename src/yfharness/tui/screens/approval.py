from __future__ import annotations

import json
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Markdown, Static

from yfharness.core.models import ApprovalDecision, ApprovalRequest


class ApprovalScreen(ModalScreen[ApprovalDecision]):
    BINDINGS: ClassVar[list[BindingType]] = [("escape", "deny", "拒绝")]

    def __init__(self, request: ApprovalRequest) -> None:
        super().__init__()
        self.request = request

    def compose(self) -> ComposeResult:
        request = self.request
        details = [
            f"# 工具审批：`{request.tool_call.name}`",
            f"风险等级：**{request.risk_level.value}**",
            "## 参数",
            "```json\n"
            + json.dumps(request.tool_call.arguments, ensure_ascii=False, indent=2)
            + "\n```",
        ]
        if request.paths:
            details.extend(["## 路径", "\n".join(f"- `{path}`" for path in request.paths)])
        if request.command:
            details.extend(["## 命令", f"```text\n{request.command}\n```"])
        if request.diff_preview:
            details.extend(["## Diff 预览", f"```diff\n{request.diff_preview}\n```"])
        with Vertical(id="modal-card"):
            with VerticalScroll():
                yield Markdown("\n\n".join(details))
                yield Static("模型输出不可信；请只批准你理解的操作。", classes="warning")
            with Horizontal(classes="modal-actions"):
                yield Button("允许一次", id="once", variant="success")
                yield Button("会话允许", id="session", variant="primary")
                yield Button("拒绝", id="deny", variant="warning")
                yield Button("取消运行", id="cancel", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        decisions = {
            "once": ApprovalDecision.ALLOW_ONCE,
            "session": ApprovalDecision.ALLOW_SESSION,
            "deny": ApprovalDecision.DENY,
            "cancel": ApprovalDecision.CANCEL_RUN,
        }
        self.dismiss(decisions[event.button.id or "deny"])

    def action_deny(self) -> None:
        self.dismiss(ApprovalDecision.DENY)
