"""Deterministic structured summaries that preserve operational state."""

from __future__ import annotations

import re
from collections.abc import Iterable

from pydantic import Field

from yfharness.core.models import DomainModel, Message, MessageRole

_PATH_PATTERN = re.compile(r"(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.[A-Za-z0-9]+")


class CompactionSummary(DomainModel):
    current_goal: str
    completed: list[str] = Field(default_factory=list)
    user_constraints: list[str] = Field(default_factory=list)
    important_decisions: list[str] = Field(default_factory=list)
    modified_files: list[str] = Field(default_factory=list)
    test_status: list[str] = Field(default_factory=list)
    unresolved_issues: list[str] = Field(default_factory=list)
    next_step: str = "继续当前目标"

    def to_markdown(self) -> str:
        sections = [
            "# 上下文压缩摘要",
            f"## 当前目标\n{self.current_goal}",
            _section("已完成事项", self.completed),
            _section("用户约束", self.user_constraints),
            _section("重要决定", self.important_decisions),
            _section("已修改文件", self.modified_files),
            _section("测试状态", self.test_status),
            _section("未解决问题", self.unresolved_issues),
            f"## 下一步\n{self.next_step}",
        ]
        return "\n\n".join(sections)


class ConversationCompactor:
    def summarize(
        self,
        messages: list[Message],
        *,
        previous: CompactionSummary | None = None,
    ) -> CompactionSummary:
        user_texts = [
            message.text_content for message in messages if message.role is MessageRole.USER
        ]
        assistant_texts = [
            message.text_content for message in messages if message.role is MessageRole.ASSISTANT
        ]
        all_lines = [
            line.strip()
            for message in messages
            for line in message.text_content.splitlines()
            if line.strip()
        ]
        constraints = _matching(
            [line for text in user_texts for line in text.splitlines()],
            ("必须", "不得", "不能", "不要", "只允许", "must", "never", "do not", "only"),
        )
        completed = _matching(
            [line for text in assistant_texts for line in text.splitlines()],
            ("已完成", "完成了", "通过", "implemented", "completed", "created", "fixed"),
        )
        decisions = _matching(all_lines, ("决定", "采用", "选择", "decision", "use "))
        tests = _matching(all_lines, ("pytest", "ruff", "mypy", "测试", "passed", "failed"))
        unresolved = _matching(
            all_lines, ("待处理", "未解决", "下一步", "todo", "unresolved", "next step")
        )
        files = sorted({match for line in all_lines for match in _PATH_PATTERN.findall(line)})
        goal = _first_nonempty(reversed(user_texts))
        if goal is None:
            goal = previous.current_goal if previous is not None else "继续当前任务"
        next_step = (
            unresolved[-1]
            if unresolved
            else (previous.next_step if previous is not None else "继续当前目标并验证结果")
        )
        fresh = CompactionSummary(
            current_goal=_clip(goal, 1_500),
            completed=_unique_clipped(completed, 20),
            user_constraints=_unique_clipped(constraints, 30),
            important_decisions=_unique_clipped(decisions, 20),
            modified_files=files[:50],
            test_status=_unique_clipped(tests, 20),
            unresolved_issues=_unique_clipped(unresolved, 20),
            next_step=_clip(next_step, 500),
        )
        if previous is None:
            return fresh
        return CompactionSummary(
            current_goal=fresh.current_goal,
            completed=_merge(previous.completed, fresh.completed, 20),
            user_constraints=_merge(previous.user_constraints, fresh.user_constraints, 30),
            important_decisions=_merge(
                previous.important_decisions,
                fresh.important_decisions,
                20,
            ),
            modified_files=_merge(previous.modified_files, fresh.modified_files, 50),
            test_status=_merge(previous.test_status, fresh.test_status, 20),
            unresolved_issues=_merge(
                previous.unresolved_issues,
                fresh.unresolved_issues,
                20,
            ),
            next_step=fresh.next_step,
        )


def _matching(lines: list[str], markers: tuple[str, ...]) -> list[str]:
    lowered_markers = tuple(marker.lower() for marker in markers)
    return [
        line.strip() for line in lines if any(marker in line.lower() for marker in lowered_markers)
    ]


def _first_nonempty(values: Iterable[str]) -> str | None:
    for value in values:
        if value.strip():
            return value.strip()
    return None


def _unique_clipped(values: list[str], limit: int) -> list[str]:
    return list(dict.fromkeys(_clip(value.strip(), 500) for value in values if value.strip()))[
        :limit
    ]


def _merge(previous: list[str], fresh: list[str], limit: int) -> list[str]:
    return _unique_clipped([*previous, *fresh], limit)


def _clip(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[:limit] + "…"


def _section(title: str, values: list[str]) -> str:
    content = "\n".join(f"- {value}" for value in values) if values else "- 无"
    return f"## {title}\n{content}"
