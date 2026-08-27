"""Validated application configuration without resolved secret values."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator

from yfharness.core.models import DomainModel, ModelConfig
from yfharness.core.policies import AgentMode, ApprovalPolicy
from yfharness.core.workflows import WorkflowProfile


class ProviderSettings(DomainModel):
    type: Literal["mock", "openai_compatible"]
    base_url: str | None = None
    api_key_env: str = ""
    timeout_seconds: float = Field(default=120, gt=0)
    max_retries: int = Field(default=2, ge=0, le=10)
    include_reasoning: bool = False
    verify_ssl: bool = True

    @model_validator(mode="after")
    def require_http_base_url(self) -> ProviderSettings:
        if self.type == "openai_compatible":
            if not self.base_url:
                raise ValueError("openai_compatible provider requires base_url")
            if not self.base_url.startswith(("http://", "https://")):
                raise ValueError("base_url must use http:// or https://")
        return self


class AgentSettings(DomainModel):
    max_steps: int = Field(default=20, ge=1)
    max_tool_calls: int = Field(default=50, ge=0)
    max_run_seconds: float = Field(default=900, gt=0)
    max_token_budget: int | None = Field(default=None, gt=0)
    max_cost: float | None = Field(default=None, ge=0)


class MCPServerSettings(DomainModel):
    command: list[str] = Field(min_length=1)
    enabled: bool = False
    enabled_tools: list[str] | None = None
    disabled_tools: list[str] = Field(default_factory=list)
    env_keys: list[str] = Field(default_factory=list)
    startup_timeout: float = Field(default=10, gt=0, le=120)
    tool_timeout: float = Field(default=60, gt=0, le=900)

    @field_validator("env_keys")
    @classmethod
    def validate_env_keys(cls, value: list[str]) -> list[str]:
        pattern = r"^[A-Za-z_][A-Za-z0-9_]*$"
        if len(value) != len(set(value)) or any(not re.fullmatch(pattern, item) for item in value):
            raise ValueError("MCP env_keys must contain unique environment variable names")
        return value


def _default_workflows() -> dict[str, WorkflowProfile]:
    return {
        "balanced": WorkflowProfile(
            id="balanced",
            label="平衡",
            description="低风险只读自动执行，写入和命令继续遵守审批策略。",
        ),
        "plan": WorkflowProfile(
            id="plan",
            label="只读规划",
            description="只向模型暴露只读工具，并拒绝写入。",
            mode=AgentMode.PLAN,
            permissions=ApprovalPolicy.DENY_WRITES,
            denied_tools=[
                "create_directory",
                "write_file",
                "apply_patch",
                "move_path",
                "delete_path",
                "run_command",
                "run_tests",
            ],
        ),
        "guarded": WorkflowProfile(
            id="guarded",
            label="逐项确认",
            description="每个工具调用都需要明确审批。",
            permissions=ApprovalPolicy.ALWAYS_ASK,
        ),
    }


class AppConfig(DomainModel):
    default_provider: str = "mock"
    default_model: str = "mock-default"
    language: str = "zh-CN"
    providers: dict[str, ProviderSettings] = Field(
        default_factory=lambda: {"mock": ProviderSettings(type="mock")}
    )
    models: dict[str, ModelConfig] = Field(
        default_factory=lambda: {
            "mock-default": ModelConfig(
                id="mock-default",
                provider="mock",
                model="mock-default",
                supports_streaming=True,
                supports_native_tools=True,
                context_window=32_000,
                max_output_tokens=4_096,
                tokenizer="approx_chars_4",
            )
        }
    )
    agent: AgentSettings = Field(default_factory=AgentSettings)
    default_workflow: str = "balanced"
    workflows: dict[str, WorkflowProfile] = Field(default_factory=_default_workflows)
    mcp_servers: dict[str, MCPServerSettings] = Field(default_factory=dict)
    workspace: Path = Field(default_factory=Path.cwd)

    @field_validator("workspace", mode="before")
    @classmethod
    def expand_workspace(cls, value: object) -> object:
        return Path(str(value)).expanduser() if value is not None else value

    @model_validator(mode="after")
    def validate_references(self) -> AppConfig:
        if self.default_provider not in self.providers:
            raise ValueError(f"default_provider is not configured: {self.default_provider}")
        if self.default_model not in self.models:
            raise ValueError(f"default_model is not configured: {self.default_model}")
        for name, model in self.models.items():
            if model.provider not in self.providers:
                raise ValueError(f"model {name!r} references unknown provider {model.provider!r}")
        if self.default_workflow not in self.workflows:
            raise ValueError(f"default_workflow is not configured: {self.default_workflow}")
        for name, workflow in self.workflows.items():
            if workflow.id != name:
                raise ValueError(f"workflow key {name!r} does not match profile id {workflow.id!r}")
        for name in self.mcp_servers:
            if not name or any(
                character not in "abcdefghijklmnopqrstuvwxyz0123456789_.-"
                for character in name.lower()
            ):
                raise ValueError(f"invalid MCP server name: {name!r}")
        return self

    def workflow(self, name: str | None = None) -> WorkflowProfile:
        selected = name or self.default_workflow
        try:
            return self.workflows[selected]
        except KeyError as exc:
            raise ValueError(f"unknown workflow {selected!r}") from exc

    def redacted_dict(self) -> dict[str, object]:
        value = self.model_dump(mode="json")
        providers = value.get("providers")
        if isinstance(providers, dict):
            for settings in providers.values():
                if isinstance(settings, dict) and settings.get("api_key_env"):
                    settings["api_key_env"] = str(settings["api_key_env"])
                    settings["api_key_present"] = "<checked at runtime>"
        return value
