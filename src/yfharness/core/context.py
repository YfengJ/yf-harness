"""Context composition, instruction priority, attachments, budgeting, and compaction."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

from pydantic import Field

from yfharness.core.compaction import CompactionSummary, ConversationCompactor
from yfharness.core.exceptions import ContextOverflowError
from yfharness.core.instructions import InstructionDocument, InstructionResolver
from yfharness.core.models import (
    DomainModel,
    Message,
    MessageRole,
    ModelConfig,
    ToolDefinition,
)
from yfharness.core.policies import AgentMode
from yfharness.core.project_index import ProjectIndex
from yfharness.core.prompts import build_system_prompt
from yfharness.core.skills import SkillInvocation
from yfharness.tools.security import WorkspaceGuard, truncate_output

TokenEstimator = Callable[[str], int]


class ContextSource(DomainModel):
    kind: str
    label: str
    estimated_tokens: int = 0
    path: str | None = None
    scope: str | None = None


class ContextSnapshot(DomainModel):
    messages: list[Message]
    sources: list[ContextSource] = Field(default_factory=list)
    estimated_tokens: int
    budget_tokens: int
    usage_ratio: float
    compacted: bool = False
    summary: CompactionSummary | None = None

    def trace_payload(self) -> dict[str, object]:
        """Return diagnostics without persisting prompts, attachments, or skill bodies."""

        return {
            "sources": [source.model_dump(mode="json") for source in self.sources],
            "estimated_tokens": self.estimated_tokens,
            "budget_tokens": self.budget_tokens,
            "usage_ratio": self.usage_ratio,
            "compacted": self.compacted,
            "summary_present": self.summary is not None,
        }


class ContextBuilder:
    """Build context in documented low-to-high instruction priority order."""

    def __init__(
        self,
        workspace: Path,
        estimator: TokenEstimator,
        *,
        read_limit: int = 200_000,
        recent_messages: int = 8,
        compaction_threshold: float = 0.8,
    ) -> None:
        self.guard = WorkspaceGuard(workspace)
        self.estimator = estimator
        self.read_limit = read_limit
        self.recent_messages = recent_messages
        self.compaction_threshold = compaction_threshold
        self.attachments: dict[str, str] = {}
        self.previous_summary: CompactionSummary | None = None
        self.compactor = ConversationCompactor()
        self.last_snapshot: ContextSnapshot | None = None
        self._active_sources: list[ContextSource] = []
        self.instructions = InstructionResolver(
            self.guard.root,
            read_limit=read_limit,
        )
        self.project_index = ProjectIndex(self.guard.root)

    def add(self, path: str) -> str:
        resolved = self.guard.resolve(path, must_exist=True)
        relative = self.guard.relative(resolved)
        self.attachments[relative] = self._attachment_text(resolved)
        return relative

    def remove(self, path: str) -> bool:
        return self.attachments.pop(path, None) is not None

    def manual_compact(self, messages: list[Message]) -> CompactionSummary:
        self.previous_summary = self.compactor.summarize(messages)
        return self.previous_summary

    def build(
        self,
        *,
        user_input: str,
        history: list[Message],
        mode: AgentMode,
        tools: list[ToolDefinition],
        model: ModelConfig,
        native_tools: bool,
        skill: SkillInvocation | None = None,
    ) -> ContextSnapshot:
        sources: list[ContextSource] = []
        system = build_system_prompt(mode, tools, native_tools=native_tools)
        request_budget = max(
            1,
            (model.context_window or 32_000) - (model.max_output_tokens or 4_096),
        )
        auto_paths = self._auto_relevant_paths(user_input)
        relevant_paths = [*self.attachments, *auto_paths]
        instruction_text = self._instruction_text(sources, relevant_paths)
        attachment_text = self._attachments_text(
            sources,
            auto_paths,
            auto_token_budget=min(8_000, max(256, request_budget // 4)),
        )
        combined_system = system
        if instruction_text:
            combined_system += "\n\n# 项目与用户指令\n" + instruction_text
        if skill is not None:
            combined_system += "\n\n" + skill.render()
            sources.append(
                ContextSource(
                    kind="skill",
                    label=skill.summary.id,
                    path=skill.summary.path,
                    scope=skill.summary.source,
                    estimated_tokens=self.estimator(skill.instructions),
                )
            )
        messages = list(history)
        if self.previous_summary is not None:
            summary_message = Message.text(
                MessageRole.SYSTEM if model.supports_system_message else MessageRole.USER,
                self.previous_summary.to_markdown(),
            )
            messages = [summary_message, *messages[-self.recent_messages :]]
            sources.append(ContextSource(kind="summary", label="previous compaction"))
        user_text = user_input
        if attachment_text:
            user_text += "\n\n# 附加文件上下文\n" + attachment_text
        if model.supports_system_message:
            messages = [Message.text(MessageRole.SYSTEM, combined_system), *messages]
            messages.append(Message.text(MessageRole.USER, user_text))
        else:
            messages.append(
                Message.text(
                    MessageRole.USER,
                    f"[Harness instructions]\n{combined_system}\n\n[User]\n{user_text}",
                )
            )
        sources.extend(
            [
                ContextSource(kind="harness", label="fixed system instructions"),
                ContextSource(kind="mode", label=mode.value),
                ContextSource(kind="history", label=f"{len(history)} messages"),
                ContextSource(kind="user", label="current input"),
                ContextSource(kind="tools", label=f"{len(tools)} definitions"),
            ]
        )
        return self.fit_messages(messages, model=model, tools=tools, sources=sources)

    def fit_messages(
        self,
        messages: list[Message],
        *,
        model: ModelConfig,
        tools: list[ToolDefinition],
        sources: list[ContextSource] | None = None,
    ) -> ContextSnapshot:
        budget = max(1, (model.context_window or 32_000) - (model.max_output_tokens or 4_096))
        estimated = self._estimate(messages, tools)
        compacted = False
        summary = self.previous_summary
        fitted = messages
        if estimated > int(budget * self.compaction_threshold):
            compacted = True
            summary = self.compactor.summarize(messages)
            self.previous_summary = summary
            system_messages = [
                message for message in messages if message.role is MessageRole.SYSTEM
            ][:1]
            recent = [message for message in messages if message.role is not MessageRole.SYSTEM][
                -self.recent_messages :
            ]
            summary_role = MessageRole.SYSTEM if model.supports_system_message else MessageRole.USER
            fitted = [
                *system_messages,
                Message.text(summary_role, summary.to_markdown()),
                *recent,
            ]
            estimated = self._estimate(fitted, tools)
            while estimated > budget and len(recent) > 2:
                recent.pop(0)
                fitted = [
                    *system_messages,
                    Message.text(summary_role, summary.to_markdown()),
                    *recent,
                ]
                estimated = self._estimate(fitted, tools)
            if estimated > budget:
                raise ContextOverflowError(
                    f"结构化压缩后仍需约 {estimated} Token，超过预算 {budget}"
                )
        snapshot_sources = list(sources or [])
        if sources is not None:
            self._active_sources = list(sources)
        elif self._active_sources:
            snapshot_sources = list(self._active_sources)
        if compacted:
            snapshot_sources.append(ContextSource(kind="summary", label="automatic compaction"))
        for source in snapshot_sources:
            if source.estimated_tokens == 0:
                source.estimated_tokens = self.estimator(source.label)
        snapshot = ContextSnapshot(
            messages=fitted,
            sources=snapshot_sources,
            estimated_tokens=estimated,
            budget_tokens=budget,
            usage_ratio=min(estimated / budget, 1.0),
            compacted=compacted,
            summary=summary,
        )
        self.last_snapshot = snapshot
        return snapshot

    def describe(self) -> str:
        if self.last_snapshot is None:
            return (
                f"Workspace: {self.guard.root}\n附件: "
                + (", ".join(self.attachments) or "无")
                + "\n尚未构建请求上下文"
            )
        snapshot = self.last_snapshot
        lines = [
            f"Token: {snapshot.estimated_tokens}/{snapshot.budget_tokens} "
            f"({snapshot.usage_ratio:.1%})",
            f"已压缩: {'是' if snapshot.compacted else '否'}",
            "组成:",
            *(f"- {source.kind}: {source.label}" for source in snapshot.sources),
            "附件: " + (", ".join(self.attachments) or "无"),
        ]
        return "\n".join(lines)

    def instruction_documents(
        self,
        relevant_paths: list[str] | None = None,
    ) -> list[InstructionDocument]:
        """Return the effective instruction chain for diagnostics and desktop UI."""

        return self.instructions.discover(relevant_paths or self.attachments)

    def _instruction_text(
        self,
        sources: list[ContextSource],
        relevant_paths: list[str],
    ) -> str:
        sections: list[str] = []
        for document in self.instruction_documents(relevant_paths):
            sections.append(f"## {document.label}\n{document.content}")
            sources.append(
                ContextSource(
                    kind="instruction",
                    label=document.label,
                    path=document.path,
                    scope=document.scope,
                    estimated_tokens=self.estimator(document.content),
                )
            )
        return "\n\n".join(sections)

    def _attachments_text(
        self,
        sources: list[ContextSource],
        auto_paths: list[str],
        *,
        auto_token_budget: int,
    ) -> str:
        sections = [f"## {path}\n{text}" for path, text in self.attachments.items()]
        for relative, text in self.attachments.items():
            sources.append(
                ContextSource(
                    kind="attachment",
                    label=relative,
                    path=relative,
                    estimated_tokens=self.estimator(text),
                )
            )
        remaining = auto_token_budget
        for relative in auto_paths:
            if relative in self.attachments or remaining <= 0:
                continue
            path = self.guard.resolve(relative, must_exist=True)
            text = self._fit_text_to_tokens(self._attachment_text(path), remaining)
            if not text:
                continue
            tokens = self.estimator(text)
            remaining -= tokens
            sections.append(f"## {relative}\n{text}")
            sources.append(
                ContextSource(
                    kind="auto_file",
                    label=relative,
                    path=relative,
                    estimated_tokens=tokens,
                )
            )
        return "\n\n".join(sections)

    def _fit_text_to_tokens(self, text: str, budget: int) -> str:
        if budget <= 0:
            return ""
        if self.estimator(text) <= budget:
            return text
        low, high = 0, len(text)
        while low < high:
            middle = (low + high + 1) // 2
            candidate = text[:middle] + "\n... <auto context truncated>"
            if self.estimator(candidate) <= budget:
                low = middle
            else:
                high = middle - 1
        return text[:low] + "\n... <auto context truncated>" if low else ""

    def _auto_relevant_paths(self, user_input: str) -> list[str]:
        candidates = re.findall(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*", user_input)
        selected: list[str] = []
        for candidate in candidates:
            try:
                path = self.guard.resolve(candidate, must_exist=True)
            except Exception:
                continue
            if path.is_file():
                selected.append(self.guard.relative(path))
            if len(selected) == 3:
                break
        for indexed in self.project_index.select(user_input, limit=5):
            if indexed.path not in selected:
                selected.append(indexed.path)
            if len(selected) == 5:
                break
        return selected

    def _attachment_text(self, path: Path) -> str:
        if path.is_dir():
            entries = sorted(item.name + ("/" if item.is_dir() else "") for item in path.iterdir())
            text = "目录摘要:\n" + "\n".join(entries[:200])
            if len(entries) > 200:
                text += f"\n... 省略 {len(entries) - 200} 项"
            return text
        return self._read_text(path)

    def _read_text(self, path: Path) -> str:
        raw = path.read_bytes()
        if len(raw) > self.read_limit:
            raw = raw[: self.read_limit]
        if b"\x00" in raw[:8192]:
            return "<疑似二进制文件，未读取>"
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return "<非 UTF-8 文件，未读取>"
        return truncate_output(text, self.read_limit)[0]

    def _estimate(self, messages: list[Message], tools: list[ToolDefinition]) -> int:
        message_text = "\n".join(message.text_content for message in messages)
        tool_text = json.dumps([tool.model_dump(mode="json") for tool in tools], ensure_ascii=False)
        return self.estimator(message_text) + self.estimator(tool_text)
