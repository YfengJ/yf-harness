from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Select

from yfharness.config.models import AppConfig
from yfharness.core.policies import AgentMode, ApprovalPolicy


@dataclass(frozen=True, slots=True)
class SettingsSelection:
    provider: str
    model: str
    mode: AgentMode
    policy: ApprovalPolicy


class SettingsScreen(ModalScreen[SettingsSelection | None]):
    BINDINGS: ClassVar[list[BindingType]] = [("escape", "cancel", "取消")]

    def __init__(
        self,
        config: AppConfig,
        *,
        provider: str,
        model: str,
        mode: AgentMode,
        policy: ApprovalPolicy,
    ) -> None:
        super().__init__()
        self.config = config
        self.current = SettingsSelection(provider, model, mode, policy)

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-card"):
            yield Label("Provider")
            yield Select(
                [(name, name) for name in sorted(self.config.providers)],
                value=self.current.provider,
                id="provider-select",
            )
            yield Label("Model")
            yield Select(
                [(name, name) for name in sorted(self.config.models)],
                value=self.current.model,
                id="model-select",
            )
            yield Label("模式")
            yield Select(
                [(value.value, value.value) for value in AgentMode],
                value=self.current.mode.value,
                id="mode-select",
            )
            yield Label("审批策略")
            yield Select(
                [(value.value, value.value) for value in ApprovalPolicy],
                value=self.current.policy.value,
                id="policy-select",
            )
            with Horizontal(classes="modal-actions"):
                yield Button("保存", id="save", variant="success")
                yield Button("取消", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "save":
            self.dismiss(None)
            return
        provider = str(self.query_one("#provider-select", Select).value)
        model = str(self.query_one("#model-select", Select).value)
        configured_model = self.config.models.get(model)
        if configured_model is None or configured_model.provider != provider:
            self.notify("模型不属于所选 Provider", severity="error")
            return
        self.dismiss(
            SettingsSelection(
                provider=provider,
                model=model,
                mode=AgentMode(str(self.query_one("#mode-select", Select).value)),
                policy=ApprovalPolicy(str(self.query_one("#policy-select", Select).value)),
            )
        )

    def action_cancel(self) -> None:
        self.dismiss(None)
