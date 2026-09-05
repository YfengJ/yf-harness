"""Failure-oriented regressions from the public-release audit."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
from pathlib import Path

import httpx
import pytest

from yfharness.config.models import ProviderSettings
from yfharness.core.agent import AgentRunner
from yfharness.core.context import ContextBuilder, _recent_with_tool_calls
from yfharness.core.events import FinishEvent, StreamEnd, TextDelta, ToolCallCompleted
from yfharness.core.exceptions import ProviderError, ToolExecutionError
from yfharness.core.models import (
    ApprovalDecision,
    ApprovalRequest,
    ChatRequest,
    Message,
    MessageRole,
    ModelConfig,
    RunStatus,
    ToolCall,
)
from yfharness.core.project_index import ProjectIndex
from yfharness.observability.logging import configure_logging
from yfharness.providers.mock import MockProvider
from yfharness.providers.openai_compatible import OpenAICompatibleProvider
from yfharness.storage.database import Database
from yfharness.storage.migrations import MIGRATIONS, SCHEMA_VERSION
from yfharness.tools.base import ToolContext
from yfharness.tools.changes import ChangeEntry, ChangeJournal, _atomic_bytes
from yfharness.tools.patch import _apply
from yfharness.tools.registry import ToolExecutor, builtin_tools
from yfharness.tools.security import WorkspaceGuard
from yfharness.tools.shell import execute_command


@pytest.mark.parametrize("kind", ["write", "delete", "move"])
def test_tui_undo_preserves_subsequent_edits_and_keeps_retry_record(
    tmp_path: Path, kind: str
) -> None:
    path = tmp_path / "target"
    destination = tmp_path / "destination" if kind == "move" else None
    affected = destination or path
    affected.write_bytes(b"human edit")
    journal = ChangeJournal(WorkspaceGuard(tmp_path))
    journal.record(
        ChangeEntry(
            kind=kind, path=path, before=b"before", after=b"agent edit", destination=destination
        )
    )
    with pytest.raises(ToolExecutionError):
        journal.undo_last()
    assert affected.read_bytes() == b"human edit"
    assert journal.count == 1


async def test_existing_directory_is_not_added_to_undo_journal(tmp_path: Path) -> None:
    (tmp_path / "existing").mkdir()
    guard = WorkspaceGuard(tmp_path)
    journal = ChangeJournal(guard)
    context = ToolContext(workspace=tmp_path, guard=guard, changes=journal)

    async def allow(_: ApprovalRequest) -> ApprovalDecision:
        return ApprovalDecision.ALLOW_ONCE

    executor = ToolExecutor(builtin_tools(), context, approval_handler=allow)
    await executor.execute(
        ToolCall(
            id="mkdir", name="create_directory", arguments={"path": "existing", "exist_ok": True}
        )
    )
    assert journal.count == 0
    assert (tmp_path / "existing").is_dir()


async def test_process_liveness_tracks_another_process() -> None:
    from yfharness.storage.processes import process_alive

    process = await asyncio.create_subprocess_exec(
        sys.executable, "-c", "import time; time.sleep(30)"
    )
    try:
        assert process_alive(process.pid)
    finally:
        process.kill()
        await process.wait()
    assert not process_alive(process.pid)


async def test_concurrent_database_initialization_is_serialized(tmp_path: Path) -> None:
    path = tmp_path / "shared.sqlite3"
    await asyncio.gather(*(Database(path).initialize() for _ in range(6)))
    database = Database(path)
    assert await database.schema_version() == SCHEMA_VERSION
    async with database.connect() as connection:
        row = await (await connection.execute("SELECT COUNT(*) FROM schema_version")).fetchone()
    assert row is not None and row[0] == 1


async def test_failed_migration_rolls_back_schema_and_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = Database(tmp_path / "retry.sqlite3")
    original = MIGRATIONS[2]
    monkeypatch.setitem(MIGRATIONS, 2, original + "\nINVALID SQL;\n")
    with pytest.raises(sqlite3.OperationalError):
        await database.initialize()
    monkeypatch.setitem(MIGRATIONS, 2, original)
    await database.initialize()
    assert await database.schema_version() == SCHEMA_VERSION


def test_logs_redact_formatted_arguments_and_exception_text(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    logger = configure_logging(directory=tmp_path, console=True)
    logger.info("Authorization: Bearer %s", "fixture-credential")
    logger.info("ordinary %s %d", "message", 42)
    try:
        raise ValueError("Bearer fixture-traceback")
    except ValueError:
        logger.exception("operation failed")
    for handler in logger.handlers:
        handler.flush()
    outputs = [
        (tmp_path / "debug.jsonl").read_text(),
        (tmp_path / "yfharness.log").read_text(),
        capsys.readouterr().err,
    ]
    for output in outputs:
        assert "fixture-credential" not in output
        assert "fixture-traceback" not in output
        assert "ordinary message 42" in output
        assert "Logging error" not in output


@pytest.mark.parametrize("tool", [False, True])
async def test_abrupt_sse_eof_never_completes_or_executes_partial_tools(tool: bool) -> None:
    delta = (
        {"tool_calls": [{"index": 0, "function": {"name": "write_file", "arguments": "{}"}}]}
        if tool
        else {"content": "partial"}
    )
    body = "data: " + json.dumps({"choices": [{"delta": delta}]}) + "\n\n"
    client = httpx.AsyncClient(
        base_url="https://example.test/v1",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text=body)),
    )
    model = ModelConfig(id="test", provider="remote", model="test")
    provider = OpenAICompatibleProvider(
        "remote",
        ProviderSettings(type="openai_compatible", base_url="https://example.test/v1"),
        {"test": model},
        client=client,
    )
    observed = []
    try:
        with pytest.raises(ProviderError, match="断开"):
            async for event in provider.stream_chat(
                ChatRequest(model=model, messages=[Message.text(MessageRole.USER, "test")])
            ):
                observed.append(event)
    finally:
        await client.aclose()
    assert not any(isinstance(event, ToolCallCompleted | StreamEnd) for event in observed)


async def test_missing_usage_is_estimated_and_nonstreaming_capability_honored(
    tmp_path: Path,
) -> None:
    from collections.abc import AsyncIterator

    from yfharness.core.events import ModelEvent

    class NoUsageProvider(MockProvider):
        async def stream_chat(self, request: ChatRequest) -> AsyncIterator[ModelEvent]:
            assert request.stream is False
            yield TextDelta(text="estimated result")
            yield FinishEvent(reason="stop")
            yield StreamEnd()

    guard = WorkspaceGuard(tmp_path)
    runner = AgentRunner(
        provider=NoUsageProvider(),
        model=ModelConfig(id="test", provider="mock", model="test", supports_streaming=False),
        tools=ToolExecutor(builtin_tools(), ToolContext(workspace=tmp_path, guard=guard)),
    )
    result = await runner.run("estimate", session_id="s")
    assert result.run.status is RunStatus.COMPLETED
    assert result.run.usage.estimated
    assert result.run.usage.input_tokens > 0 and result.run.usage.output_tokens > 0


async def test_command_drains_both_streams_with_bounded_unicode_output(tmp_path: Path) -> None:
    result = await execute_command(
        [
            sys.executable,
            "-c",
            "import os; os.write(1, ('你' * 700000).encode()); os.write(2, b'e' * 2000000)",
        ],
        cwd=tmp_path,
        shell=False,
        timeout_seconds=10,
        output_limit=100,
        tool_call_id="large",
    )
    assert result.success and result.truncated
    assert result.stdout.startswith("你" * 100)
    assert result.stderr.startswith("e" * 100)
    assert len(result.stdout) < 200 and len(result.stderr) < 200


async def test_command_timeout_keeps_already_emitted_output(tmp_path: Path) -> None:
    result = await execute_command(
        [sys.executable, "-u", "-c", "import time; print('before-timeout'); time.sleep(10)"],
        cwd=tmp_path,
        shell=False,
        timeout_seconds=0.5,
        output_limit=100,
        tool_call_id="timeout",
    )
    assert result.error_type == "timeout"
    assert "before-timeout" in result.stdout


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process-group semantics")
async def test_timeout_kills_descendant_after_parent_exits(tmp_path: Path) -> None:
    child = "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(20)"
    parent = f"import subprocess,sys; subprocess.Popen([sys.executable, '-c', {child!r}])"
    result = await asyncio.wait_for(
        execute_command(
            [sys.executable, "-c", parent],
            cwd=tmp_path,
            shell=False,
            timeout_seconds=0.5,
            output_limit=100,
            tool_call_id="descendant",
        ),
        timeout=6,
    )
    assert result.error_type == "timeout"


@pytest.mark.parametrize(
    ("original", "patch", "expected"),
    [
        ("", "@@ -0,0 +1 @@\n+hello\n", "hello\n"),
        ("one\n", "@@ -1,0 +2 @@\n+two\n", "one\ntwo\n"),
        (
            "old",
            "@@ -1 +1 @@\n-old\n\\ No newline at end of file\n+new\n\\ No newline at end of file\n",
            "new",
        ),
    ],
)
def test_unified_diff_zero_length_hunks_and_missing_final_newline(
    original: str, patch: str, expected: str
) -> None:
    assert _apply(original, patch) == expected


@pytest.mark.skipif(os.name == "nt", reason="POSIX executable permission")
def test_restore_preserves_executable_mode(tmp_path: Path) -> None:
    path = tmp_path / "script.sh"
    path.write_text("after")
    path.chmod(0o755)
    _atomic_bytes(path, b"before")
    assert path.read_bytes() == b"before"
    assert path.stat().st_mode & 0o777 == 0o755


def test_automatic_index_excludes_local_secrets_and_prunes_dependencies(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("API_TOKEN=fixture")
    (tmp_path / ".env.local").write_text("API_TOKEN=fixture")
    (tmp_path / "private.pem").write_text("private fixture")
    (tmp_path / "credentials.json").write_text("{}")
    (tmp_path / ".env.example").write_text("API_TOKEN=fill-me")
    (tmp_path / "app.py").write_text("print('hello')")
    (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
    (tmp_path / "node_modules" / "pkg" / "index.js").write_text("example")
    assert set(ProjectIndex(tmp_path).paths()) == {".env.example", "app.py"}


async def test_write_rejects_changes_made_while_user_reviews_diff(tmp_path: Path) -> None:
    path = tmp_path / "shared.txt"
    path.write_text("original")

    async def approve(_: ApprovalRequest) -> ApprovalDecision:
        path.write_text("human edit must survive")
        return ApprovalDecision.ALLOW_ONCE

    executor = ToolExecutor(
        builtin_tools(),
        ToolContext(workspace=tmp_path, guard=WorkspaceGuard(tmp_path)),
        approval_handler=approve,
    )
    with pytest.raises(ToolExecutionError, match="审批期间"):
        await executor.execute(
            ToolCall(
                id="write",
                name="write_file",
                arguments={"path": "shared.txt", "content": "overwrite"},
            )
        )
    assert path.read_text() == "human edit must survive"


def test_context_truncation_keeps_native_call_result_group() -> None:
    call = Message.text(
        MessageRole.ASSISTANT,
        "",
        tool_calls=[
            ToolCall(id="one", name="read_file", arguments={}),
            ToolCall(id="two", name="read_file", arguments={}),
        ],
    )
    first = Message.text(MessageRole.TOOL, "first", tool_call_id="one")
    second = Message.text(MessageRole.TOOL, "second", tool_call_id="two")
    history = [Message.text(MessageRole.USER, "read both"), call, first, second]
    assert _recent_with_tool_calls(history, 1) == [call, first, second]


async def test_context_failure_returns_terminal_run_and_releases_cancel_handle(
    tmp_path: Path,
) -> None:
    guard = WorkspaceGuard(tmp_path)
    runner = AgentRunner(
        provider=MockProvider(),
        model=ModelConfig(
            id="tiny", provider="mock", model="tiny", context_window=2, max_output_tokens=1
        ),
        tools=ToolExecutor(builtin_tools(), ToolContext(workspace=tmp_path, guard=guard)),
        context_builder=ContextBuilder(tmp_path, lambda text: len(text)),
    )
    result = await runner.run("cannot fit", session_id="overflow")
    assert result.run.status is RunStatus.FAILED
    assert result.run.ended_at is not None
    assert not runner.cancel()
