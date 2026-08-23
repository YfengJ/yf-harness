"""Mode and approval policy decisions enforced before every tool call."""

from __future__ import annotations

from enum import StrEnum

from yfharness.core.models import ToolRiskLevel


class AgentMode(StrEnum):
    CHAT = "chat"
    PLAN = "plan"
    AGENT = "agent"
    REVIEW = "review"


class ApprovalPolicy(StrEnum):
    ALWAYS_ASK = "always_ask"
    SAFE_AUTO = "safe_auto"
    SESSION_ALLOW = "session_allow"
    DENY_WRITES = "deny_writes"
    FULL_AUTO = "full_auto"


class PolicyAction(StrEnum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


def decide_tool_access(
    *,
    mode: AgentMode,
    policy: ApprovalPolicy,
    tool_name: str,
    risk_level: ToolRiskLevel,
    read_only: bool,
    always_approval: bool,
    session_allowed_tools: set[str],
    full_auto_enabled: bool,
) -> PolicyAction:
    if mode in {AgentMode.PLAN, AgentMode.REVIEW} and not read_only:
        return PolicyAction.DENY
    if mode is AgentMode.CHAT and not read_only:
        return PolicyAction.DENY
    if policy is ApprovalPolicy.DENY_WRITES and not read_only:
        return PolicyAction.DENY
    if always_approval:
        return PolicyAction.ASK
    if policy is ApprovalPolicy.ALWAYS_ASK:
        return PolicyAction.ASK
    if policy is ApprovalPolicy.FULL_AUTO:
        return PolicyAction.ALLOW if full_auto_enabled else PolicyAction.DENY
    if policy is ApprovalPolicy.SESSION_ALLOW and tool_name in session_allowed_tools:
        return PolicyAction.ALLOW
    if read_only and risk_level is ToolRiskLevel.LOW:
        return PolicyAction.ALLOW
    return PolicyAction.ASK
