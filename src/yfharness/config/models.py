"""Validated application configuration without resolved secret values."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator

from yfharness.core.models import DomainModel, ModelConfig


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
        return self

    def redacted_dict(self) -> dict[str, object]:
        value = self.model_dump(mode="json")
        providers = value.get("providers")
        if isinstance(providers, dict):
            for settings in providers.values():
                if isinstance(settings, dict) and settings.get("api_key_env"):
                    settings["api_key_env"] = str(settings["api_key_env"])
                    settings["api_key_present"] = "<checked at runtime>"
        return value
