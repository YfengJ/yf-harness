from __future__ import annotations

from pathlib import Path

import pytest

from yfharness.core.compaction import ConversationCompactor
from yfharness.core.context import ContextBuilder
from yfharness.core.exceptions import PolicyDeniedError
from yfharness.core.models import Message, MessageRole, ModelConfig, ToolDefinition
from yfharness.core.policies import AgentMode


def model(*, context_window: int = 2_000, system: bool = True) -> ModelConfig:
    return ModelConfig(
        id="small",
        provider="mock",
        model="small",
        context_window=context_window,
        max_output_tokens=100,
        supports_system_message=system,
    )


def test_instruction_priority_attachments_and_auto_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "config"
    workspace = tmp_path / "workspace"
    config.mkdir()
    workspace.mkdir()
    (config / "instructions.md").write_text("global-low", encoding="utf-8")
    (workspace / "YF_HARNESS.md").write_text("root-middle", encoding="utf-8")
    (workspace / ".yfh").mkdir()
    (workspace / ".yfh" / "instructions.md").write_text("project-high", encoding="utf-8")
    (workspace / "README.md").write_text("real readme", encoding="utf-8")
    (workspace / "manual.txt").write_text("manual context", encoding="utf-8")
    (workspace / "CLAUDE.md").write_text("claude-memory", encoding="utf-8")
    (workspace / "AGENTS.md").write_text("codex-rules", encoding="utf-8")
    (workspace / ".cursor" / "rules").mkdir(parents=True)
    (workspace / ".cursor" / "rules" / "python.mdc").write_text(
        "---\ndescription: Python conventions\nglobs: '*.py'\nalwaysApply: false\n---\nuse-types",
        encoding="utf-8",
    )
    monkeypatch.setenv("YFH_CONFIG_DIR", str(config))
    builder = ContextBuilder(workspace, lambda text: max(1, len(text) // 4))
    builder.add("manual.txt")

    snapshot = builder.build(
        user_input="请读取 README.md",
        history=[],
        mode=AgentMode.PLAN,
        tools=[],
        model=model(),
        native_tools=True,
    )

    combined = "\n".join(message.text_content for message in snapshot.messages)
    assert (
        combined.index("global-low")
        < combined.index("root-middle")
        < combined.index("project-high")
    )
    assert "manual context" in combined
    assert "real readme" in combined
    assert "claude-memory" in combined
    assert "codex-rules" in combined
    assert "use-types" not in combined
    assert {source.kind for source in snapshot.sources} >= {
        "instruction",
        "attachment",
        "auto_file",
    }


def test_nested_agents_override_and_cursor_glob_are_scoped(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    source = workspace / "src" / "feature"
    cursor = workspace / ".cursor" / "rules"
    source.mkdir(parents=True)
    cursor.mkdir(parents=True)
    (workspace / "AGENTS.md").write_text("root-agent", encoding="utf-8")
    (source / "AGENTS.md").write_text("ignored-agent", encoding="utf-8")
    (source / "AGENTS.override.md").write_text("nested-override", encoding="utf-8")
    (source / "module.py").write_text("VALUE = 1", encoding="utf-8")
    (cursor / "python.mdc").write_text(
        "---\ndescription: Python only\nglobs: src/**/*.py\nalwaysApply: false\n---\npython-rule",
        encoding="utf-8",
    )
    builder = ContextBuilder(workspace, lambda text: max(1, len(text) // 4))

    documents = builder.instruction_documents(["src/feature/module.py"])
    rendered = "\n".join(document.content for document in documents)

    assert "root-agent" in rendered
    assert "nested-override" in rendered
    assert "ignored-agent" not in rendered
    assert "python-rule" in rendered
    assert [document.priority for document in documents] == sorted(
        document.priority for document in documents
    )


def test_attachment_cannot_escape_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (tmp_path / "secret").write_text("secret", encoding="utf-8")
    builder = ContextBuilder(workspace, len)

    with pytest.raises(PolicyDeniedError):
        builder.add("../secret")


def test_structured_compaction_preserves_constraints_files_tests_and_next_step() -> None:
    messages = [
        Message.text(
            MessageRole.USER,
            "目标：完成发布。必须保留 API 兼容性。不得删除历史。",
        ),
        Message.text(
            MessageRole.ASSISTANT,
            "已完成 src/app.py 修改。采用 Repository。pytest: 12 passed。下一步检查 CI。",
        ),
        Message.text(MessageRole.USER, "继续当前目标，不能泄露 API Key。"),
    ]

    summary = ConversationCompactor().summarize(messages)
    rendered = summary.to_markdown()

    assert "不能泄露 API Key" in rendered
    assert "src/app.py" in summary.modified_files
    assert any("12 passed" in item for item in summary.test_status)
    assert "下一步检查 CI" in summary.next_step


def test_automatic_compaction_keeps_recent_messages_and_summary(tmp_path: Path) -> None:
    builder = ContextBuilder(
        tmp_path,
        lambda text: max(1, len(text) // 2),
        recent_messages=3,
        compaction_threshold=0.5,
    )
    history = [
        Message.text(MessageRole.USER, f"old message {index} 必须保留约束 " + "x" * 80)
        for index in range(8)
    ]
    history.append(Message.text(MessageRole.ASSISTANT, "已完成 demo.py；pytest 8 passed"))

    snapshot = builder.build(
        user_input="latest user goal",
        history=history,
        mode=AgentMode.AGENT,
        tools=[ToolDefinition(name="read", description="read", parameters={})],
        model=model(context_window=1_000),
        native_tools=True,
    )

    assert snapshot.compacted
    assert snapshot.summary is not None
    assert snapshot.estimated_tokens <= snapshot.budget_tokens
    rendered = "\n".join(message.text_content for message in snapshot.messages)
    assert "上下文压缩摘要" in rendered
    assert "latest user goal" in rendered
    assert "必须保留约束" in rendered


def test_model_without_system_message_receives_combined_user_instructions(tmp_path: Path) -> None:
    builder = ContextBuilder(tmp_path, lambda text: max(1, len(text) // 4))
    snapshot = builder.build(
        user_input="hello",
        history=[],
        mode=AgentMode.CHAT,
        tools=[],
        model=model(system=False),
        native_tools=False,
    )

    assert all(message.role is not MessageRole.SYSTEM for message in snapshot.messages)
    assert "[Harness instructions]" in snapshot.messages[-1].text_content


def test_context_automatically_selects_semantically_relevant_local_file(tmp_path: Path) -> None:
    (tmp_path / "parser.py").write_text(
        "def validate_parser(value: str) -> bool:\n    return bool(value)\n",
        encoding="utf-8",
    )
    (tmp_path / "unrelated.py").write_text("COLOR = 'blue'\n", encoding="utf-8")
    builder = ContextBuilder(tmp_path, lambda text: max(1, len(text) // 4))

    snapshot = builder.build(
        user_input="improve parser validation",
        history=[],
        mode=AgentMode.PLAN,
        tools=[],
        model=model(),
        native_tools=True,
    )

    rendered = "\n".join(message.text_content for message in snapshot.messages)
    assert "validate_parser" in rendered
    assert any(
        source.kind == "auto_file" and source.path == "parser.py" for source in snapshot.sources
    )
