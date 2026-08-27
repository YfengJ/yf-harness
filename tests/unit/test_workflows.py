from __future__ import annotations

import pytest
from pydantic import ValidationError

from yfharness.core.models import ToolDefinition, ToolRiskLevel
from yfharness.core.policies import PolicyAction
from yfharness.core.workflows import (
    HookAction,
    HookEngine,
    HookEvent,
    HookRule,
    WorkflowProfile,
    combine_policy_actions,
)


def definition(name: str) -> ToolDefinition:
    return ToolDefinition(name=name, description=name, parameters={})


def test_workflow_allow_then_deny_filters_deterministically() -> None:
    profile = WorkflowProfile(
        id="review",
        label="Review",
        allowed_tools=["git_*", "read_*"],
        denied_tools=["git_log"],
    )

    visible = profile.filter_definitions(
        [definition("read_file"), definition("git_status"), definition("git_log")]
    )

    assert [item.name for item in visible] == ["read_file", "git_status"]
    assert not profile.exposes("write_file")


def test_pre_hooks_merge_with_most_restrictive_result() -> None:
    profile = WorkflowProfile(
        id="guarded",
        label="Guarded",
        hooks=[
            HookRule(
                id="allow-read",
                event=HookEvent.PRE_TOOL_USE,
                tools=["read_*"],
                action=HookAction.ALLOW,
            ),
            HookRule(
                id="ask-sensitive-read",
                event=HookEvent.PRE_TOOL_USE,
                tools=["read_file"],
                risk_levels=[ToolRiskLevel.HIGH],
                action=HookAction.ASK,
                message="sensitive path",
            ),
            HookRule(
                id="deny-read",
                event=HookEvent.PRE_TOOL_USE,
                tools=["read_file"],
                risk_levels=[ToolRiskLevel.CRITICAL],
                action=HookAction.DENY,
            ),
        ],
    )
    engine = HookEngine(profile)

    high = engine.pre_tool_use("read_file", ToolRiskLevel.HIGH)
    critical = engine.pre_tool_use("read_file", ToolRiskLevel.CRITICAL)

    assert high is not None and high.action is HookAction.ASK
    assert high.rule_ids == ["allow-read", "ask-sensitive-read"]
    assert critical is not None and critical.action is HookAction.DENY
    assert combine_policy_actions(PolicyAction.ASK, PolicyAction.ALLOW) is PolicyAction.ASK
    assert combine_policy_actions(PolicyAction.DENY, PolicyAction.ALLOW) is PolicyAction.DENY


def test_post_hooks_are_observational_only() -> None:
    with pytest.raises(ValidationError, match="observational"):
        HookRule(
            id="unsafe-post",
            event=HookEvent.POST_TOOL_USE,
            action=HookAction.DENY,
        )

    profile = WorkflowProfile(
        id="audit",
        label="Audit",
        hooks=[
            HookRule(
                id="failed-shell",
                event=HookEvent.POST_TOOL_FAILURE,
                tools=["run_*"],
                message="command failed",
            )
        ],
    )
    evaluation = HookEngine(profile).post_tool_use(
        "run_tests",
        ToolRiskLevel.HIGH,
        success=False,
    )

    assert evaluation is not None
    assert evaluation.action is HookAction.OBSERVE
    assert evaluation.reasons == ["command failed"]


def test_profile_rejects_unknown_versions_and_unsafe_patterns() -> None:
    with pytest.raises(ValidationError):
        WorkflowProfile.model_validate({"version": 2, "id": "future", "label": "Future"})
    with pytest.raises(ValidationError, match="safe name globs"):
        WorkflowProfile(id="bad", label="Bad", denied_tools=["../../*"])
