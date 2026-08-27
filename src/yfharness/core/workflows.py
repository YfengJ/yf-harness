"""Versioned workflow profiles and conservative declarative lifecycle hooks."""

from __future__ import annotations

import re
from enum import StrEnum
from fnmatch import fnmatchcase
from typing import Literal

from pydantic import Field, field_validator, model_validator

from yfharness.core.models import DomainModel, ToolDefinition, ToolRiskLevel
from yfharness.core.policies import AgentMode, ApprovalPolicy, PolicyAction

_PATTERN = re.compile(r"^[A-Za-z0-9_.?*-]+$")


class HookEvent(StrEnum):
    PRE_TOOL_USE = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"
    POST_TOOL_FAILURE = "post_tool_failure"


class HookAction(StrEnum):
    OBSERVE = "observe"
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


class HookRule(DomainModel):
    """A data-only rule; it never launches a shell, network request, or model."""

    id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    event: HookEvent
    tools: list[str] = Field(default_factory=lambda: ["*"])
    risk_levels: list[ToolRiskLevel] = Field(default_factory=list)
    action: HookAction = HookAction.OBSERVE
    message: str = Field(default="", max_length=500)
    enabled: bool = True

    @field_validator("tools")
    @classmethod
    def validate_patterns(cls, value: list[str]) -> list[str]:
        if not value or any(not _PATTERN.fullmatch(item) for item in value):
            raise ValueError("hook tool patterns must be non-empty safe name globs")
        return value

    @model_validator(mode="after")
    def validate_event_action(self) -> HookRule:
        if self.event is not HookEvent.PRE_TOOL_USE and self.action is not HookAction.OBSERVE:
            raise ValueError("post-tool hooks are observational and cannot allow, ask, or deny")
        return self


class HookEvaluation(DomainModel):
    event: HookEvent
    tool_name: str
    action: HookAction
    rule_ids: list[str]
    reasons: list[str] = Field(default_factory=list)

    def policy_action(self) -> PolicyAction | None:
        if self.action is HookAction.DENY:
            return PolicyAction.DENY
        if self.action is HookAction.ASK:
            return PolicyAction.ASK
        if self.action is HookAction.ALLOW:
            return PolicyAction.ALLOW
        return None


class WorkflowProfile(DomainModel):
    """A small, explicit bundle of defaults, tool exposure, and hook rules."""

    version: Literal[1] = 1
    id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    label: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)
    mode: AgentMode = AgentMode.AGENT
    permissions: ApprovalPolicy = ApprovalPolicy.SAFE_AUTO
    allowed_tools: list[str] | None = None
    denied_tools: list[str] = Field(default_factory=list)
    hooks: list[HookRule] = Field(default_factory=list)

    @field_validator("allowed_tools", "denied_tools")
    @classmethod
    def validate_tool_patterns(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and any(not _PATTERN.fullmatch(item) for item in value):
            raise ValueError("workflow tool patterns must be safe name globs")
        return value

    @model_validator(mode="after")
    def unique_hook_ids(self) -> WorkflowProfile:
        ids = [rule.id for rule in self.hooks]
        if len(ids) != len(set(ids)):
            raise ValueError("workflow hook ids must be unique")
        return self

    def exposes(self, tool_name: str) -> bool:
        allowed = self.allowed_tools is None or any(
            fnmatchcase(tool_name, pattern) for pattern in self.allowed_tools
        )
        denied = any(fnmatchcase(tool_name, pattern) for pattern in self.denied_tools)
        return allowed and not denied

    def filter_definitions(self, definitions: list[ToolDefinition]) -> list[ToolDefinition]:
        return [definition for definition in definitions if self.exposes(definition.name)]


class HookEngine:
    """Evaluate all matching rules and make the most restrictive result win."""

    def __init__(self, profile: WorkflowProfile) -> None:
        self.profile = profile

    def pre_tool_use(
        self,
        tool_name: str,
        risk_level: ToolRiskLevel,
    ) -> HookEvaluation | None:
        rules = self._matching(HookEvent.PRE_TOOL_USE, tool_name, risk_level)
        if not rules:
            return None
        precedence = {
            HookAction.OBSERVE: 0,
            HookAction.ALLOW: 1,
            HookAction.ASK: 2,
            HookAction.DENY: 3,
        }
        action = max((rule.action for rule in rules), key=precedence.__getitem__)
        return self._evaluation(HookEvent.PRE_TOOL_USE, tool_name, action, rules)

    def post_tool_use(
        self,
        tool_name: str,
        risk_level: ToolRiskLevel,
        *,
        success: bool,
    ) -> HookEvaluation | None:
        event = HookEvent.POST_TOOL_USE if success else HookEvent.POST_TOOL_FAILURE
        rules = self._matching(event, tool_name, risk_level)
        return self._evaluation(event, tool_name, HookAction.OBSERVE, rules) if rules else None

    def _matching(
        self,
        event: HookEvent,
        tool_name: str,
        risk_level: ToolRiskLevel,
    ) -> list[HookRule]:
        return [
            rule
            for rule in self.profile.hooks
            if rule.enabled
            and rule.event is event
            and any(fnmatchcase(tool_name, pattern) for pattern in rule.tools)
            and (not rule.risk_levels or risk_level in rule.risk_levels)
        ]

    @staticmethod
    def _evaluation(
        event: HookEvent,
        tool_name: str,
        action: HookAction,
        rules: list[HookRule],
    ) -> HookEvaluation:
        return HookEvaluation(
            event=event,
            tool_name=tool_name,
            action=action,
            rule_ids=[rule.id for rule in rules],
            reasons=[rule.message for rule in rules if rule.message],
        )


def combine_policy_actions(base: PolicyAction, hook: PolicyAction | None) -> PolicyAction:
    """Deny and ask remain sticky; a hook allow can never expand base permissions."""

    if base is PolicyAction.DENY or hook is PolicyAction.DENY:
        return PolicyAction.DENY
    if base is PolicyAction.ASK or hook is PolicyAction.ASK:
        return PolicyAction.ASK
    return PolicyAction.ALLOW
