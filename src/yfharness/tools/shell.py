"""Timeout- and approval-controlled subprocess execution."""

from __future__ import annotations

import asyncio
import codecs
import os
import shlex
import signal
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

from pydantic import Field, model_validator

from yfharness.core.models import ToolResult, ToolRiskLevel
from yfharness.tools.base import Tool, ToolContext, ToolInput, ToolPreview
from yfharness.tools.security import sanitized_environment

_NETWORK_COMMANDS = {"curl", "wget", "nc", "ncat", "ssh", "scp", "ftp", "telnet"}
_DANGEROUS_TOKENS = {"sudo", "shutdown", "reboot", "mkfs", "diskutil", "format", "dd"}


class RunCommandInput(ToolInput):
    command: list[str] | str
    cwd: str = "."
    shell: bool = False
    timeout_seconds: float | None = Field(default=None, gt=0, le=3600)
    network: bool = False

    @model_validator(mode="after")
    def require_explicit_shell(self) -> RunCommandInput:
        if isinstance(self.command, str) and not self.shell:
            raise ValueError("字符串命令必须显式设置 shell=true；默认请使用参数数组")
        if isinstance(self.command, list) and not self.command:
            raise ValueError("命令参数数组不能为空")
        return self


class RunCommandTool(Tool):
    name = "run_command"
    description = "经审批运行有超时、输出限制和环境脱敏的命令。"
    input_model = RunCommandInput
    risk_level = ToolRiskLevel.HIGH
    read_only = False
    always_approval = True

    def effective_risk(self, arguments: ToolInput) -> ToolRiskLevel:
        assert isinstance(arguments, RunCommandInput)
        tokens = _tokens(arguments.command)
        if arguments.shell or arguments.network or _is_network(tokens) or _is_dangerous(tokens):
            return ToolRiskLevel.CRITICAL
        return self.risk_level

    async def preview(self, arguments: ToolInput, context: ToolContext) -> ToolPreview:
        assert isinstance(arguments, RunCommandInput)
        cwd = context.guard.resolve(arguments.cwd, must_exist=True)
        tokens = _tokens(arguments.command)
        network = arguments.network or _is_network(tokens)
        return ToolPreview(
            paths=[context.guard.relative(cwd)],
            command=arguments.command,
            network=network,
        )

    async def execute(self, arguments: ToolInput, context: ToolContext) -> ToolResult:
        assert isinstance(arguments, RunCommandInput)
        cwd = context.guard.resolve(arguments.cwd, must_exist=True)
        timeout = arguments.timeout_seconds or context.command_timeout
        return await execute_command(
            arguments.command,
            cwd=cwd,
            shell=arguments.shell,
            timeout_seconds=timeout,
            output_limit=context.output_limit,
            tool_call_id=context.tool_call_id or "",
        )


class RunTestsInput(ToolInput):
    command: list[str] = Field(default_factory=lambda: [sys.executable, "-m", "pytest"])
    cwd: str = "."
    timeout_seconds: float = Field(default=300, gt=0, le=3600)


class RunTestsTool(Tool):
    name = "run_tests"
    description = "经审批运行测试命令并返回结构化退出状态。"
    input_model = RunTestsInput
    risk_level = ToolRiskLevel.HIGH
    read_only = False
    always_approval = True

    async def preview(self, arguments: ToolInput, context: ToolContext) -> ToolPreview:
        assert isinstance(arguments, RunTestsInput)
        cwd = context.guard.resolve(arguments.cwd, must_exist=True)
        return ToolPreview(paths=[context.guard.relative(cwd)], command=arguments.command)

    async def execute(self, arguments: ToolInput, context: ToolContext) -> ToolResult:
        assert isinstance(arguments, RunTestsInput)
        cwd = context.guard.resolve(arguments.cwd, must_exist=True)
        return await execute_command(
            arguments.command,
            cwd=cwd,
            shell=False,
            timeout_seconds=arguments.timeout_seconds,
            output_limit=context.output_limit,
            tool_call_id=context.tool_call_id or "",
        )


async def execute_command(
    command: list[str] | str,
    *,
    cwd: Path,
    shell: bool,
    timeout_seconds: float,
    output_limit: int,
    tool_call_id: str,
) -> ToolResult:
    started = time.monotonic()
    kwargs: dict[str, Any] = {
        "cwd": cwd,
        "env": sanitized_environment(),
        "stdout": asyncio.subprocess.PIPE,
        "stderr": asyncio.subprocess.PIPE,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        kwargs["start_new_session"] = True
    if shell:
        assert isinstance(command, str)
        process = await asyncio.create_subprocess_shell(command, **kwargs)
    else:
        assert isinstance(command, list)
        process = await asyncio.create_subprocess_exec(*command, **kwargs)
    timed_out = False
    stdout_task = asyncio.create_task(_read_bounded(process.stdout, output_limit))
    stderr_task = asyncio.create_task(_read_bounded(process.stderr, output_limit))
    completion = asyncio.gather(process.wait(), stdout_task, stderr_task)
    try:
        await asyncio.wait_for(asyncio.shield(completion), timeout=timeout_seconds)
    except TimeoutError:
        timed_out = True
        await _terminate(process)
        await completion
    except asyncio.CancelledError:
        await _terminate(process)
        await completion
        raise
    stdout, stdout_truncated = stdout_task.result()
    stderr, stderr_truncated = stderr_task.result()
    duration = time.monotonic() - started
    if timed_out:
        return ToolResult(
            tool_call_id=tool_call_id,
            success=False,
            summary=f"命令在 {timeout_seconds:.1f}s 后超时并已终止",
            stdout=stdout,
            stderr=stderr,
            exit_code=process.returncode,
            duration=duration,
            truncated=stdout_truncated or stderr_truncated,
            error_type="timeout",
        )
    return ToolResult(
        tool_call_id=tool_call_id,
        success=process.returncode == 0,
        summary=f"命令退出码 {process.returncode}",
        stdout=stdout,
        stderr=stderr,
        exit_code=process.returncode,
        duration=duration,
        truncated=stdout_truncated or stderr_truncated,
        error_type=None if process.returncode == 0 else "nonzero_exit",
    )


async def _read_bounded(reader: asyncio.StreamReader | None, limit: int) -> tuple[str, bool]:
    if reader is None:
        return "", False
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    parts: list[str] = []
    retained = 0
    total = 0
    while True:
        chunk = await reader.read(64 * 1024)
        text = decoder.decode(chunk, final=not chunk)
        total += len(text)
        if retained < limit:
            kept = text[: limit - retained]
            parts.append(kept)
            retained += len(kept)
        if not chunk:
            break
    output = "".join(parts)
    if total > limit:
        output += f"\n... <truncated {total - limit} characters>"
    return output, total > limit


async def _terminate(process: asyncio.subprocess.Process) -> None:
    if sys.platform != "win32":
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
    else:
        if process.returncode is not None:
            return
        await _kill_windows_process_tree(process)
    try:
        await asyncio.wait_for(process.wait(), timeout=2)
    except TimeoutError:
        if sys.platform != "win32":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                return
        else:
            process.kill()
        await process.wait()
    finally:
        # Descendants may retain the pipes even after their parent exits on TERM.
        if sys.platform != "win32":
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)


async def _kill_windows_process_tree(process: asyncio.subprocess.Process) -> None:
    """Terminate a Windows process and all descendants, with a direct fallback."""

    try:
        killer = await asyncio.create_subprocess_exec(
            "taskkill",
            "/PID",
            str(process.pid),
            "/T",
            "/F",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await killer.wait()
    except OSError:
        process.kill()


def _tokens(command: list[str] | str) -> list[str]:
    if isinstance(command, list):
        return [token.lower() for token in command]
    try:
        return [token.lower() for token in shlex.split(command)]
    except ValueError:
        return [command.lower()]


def _is_network(tokens: list[str]) -> bool:
    return bool(tokens and Path(tokens[0]).name in _NETWORK_COMMANDS)


def _is_dangerous(tokens: list[str]) -> bool:
    joined = " ".join(tokens)
    return bool(set(tokens) & _DANGEROUS_TOKENS) or "rm -rf" in joined or "> /dev/" in joined
