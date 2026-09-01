"""Minimal MCP stdio discovery and tool adapter behind existing approval controls."""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from collections.abc import Awaitable, Callable, Mapping
from contextlib import suppress
from pathlib import Path
from typing import Any, ClassVar, TypeVar

from pydantic import ConfigDict

from yfharness import __version__
from yfharness.config.models import AppConfig, MCPServerSettings
from yfharness.core.exceptions import HarnessError
from yfharness.core.models import ToolDefinition, ToolResult, ToolRiskLevel
from yfharness.tools.base import Tool, ToolContext, ToolInput, ToolPreview
from yfharness.tools.registry import ToolRegistry
from yfharness.tools.security import sanitized_environment, truncate_output

_PROTOCOL_VERSION = "2025-06-18"
_SAFE_NAME = re.compile(r"[^A-Za-z0-9_.-]+")
_ResultT = TypeVar("_ResultT")


class MCPError(HarnessError):
    """An MCP process or protocol exchange failed safely."""


class MCPToolInput(ToolInput):
    model_config = ConfigDict(extra="allow")


class MCPClient:
    def __init__(
        self,
        server_name: str,
        settings: MCPServerSettings,
        workspace: Path,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self.server_name = server_name
        self.settings = settings
        self.workspace = workspace
        self.environ = environ if environ is not None else os.environ

    async def list_tools(self) -> list[dict[str, Any]]:
        async def operation(process: asyncio.subprocess.Process) -> list[dict[str, Any]]:
            await self._initialize(process)
            cursor: str | None = None
            tools: list[dict[str, Any]] = []
            while True:
                params = {"cursor": cursor} if cursor else {}
                result = await self._request(
                    process,
                    "tools/list",
                    params,
                    timeout_seconds=self.settings.tool_timeout,
                )
                page = result.get("tools", [])
                if not isinstance(page, list):
                    raise MCPError(f"MCP {self.server_name} tools/list 返回格式无效")
                tools.extend(item for item in page if isinstance(item, dict))
                next_cursor = result.get("nextCursor")
                if not isinstance(next_cursor, str) or not next_cursor:
                    break
                cursor = next_cursor
            return tools

        return await self._run(operation, timeout_seconds=self.settings.startup_timeout)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        async def operation(process: asyncio.subprocess.Process) -> dict[str, Any]:
            await self._initialize(process)
            return await self._request(
                process,
                "tools/call",
                {"name": name, "arguments": arguments},
                timeout_seconds=self.settings.tool_timeout,
            )

        return await self._run(operation, timeout_seconds=self.settings.tool_timeout)

    async def _run(
        self,
        operation: Callable[[asyncio.subprocess.Process], Awaitable[_ResultT]],
        *,
        timeout_seconds: float,
    ) -> _ResultT:
        environment = sanitized_environment(dict(self.environ))
        environment.update(
            {key: self.environ[key] for key in self.settings.env_keys if key in self.environ}
        )
        try:
            process = await asyncio.create_subprocess_exec(
                *self.settings.command,
                cwd=self.workspace,
                env=environment,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                limit=1_000_000,
            )
        except OSError as exc:
            raise MCPError(f"MCP {self.server_name} 无法启动: {exc}") from exc
        try:
            return await asyncio.wait_for(operation(process), timeout=timeout_seconds)
        except TimeoutError as exc:
            raise MCPError(f"MCP {self.server_name} 超时") from exc
        finally:
            if process.returncode is None:
                try:
                    process.terminate()
                except ProcessLookupError:
                    with suppress(ChildProcessError):
                        await process.wait()
                else:
                    try:
                        await asyncio.wait_for(process.wait(), timeout=2)
                    except TimeoutError:
                        with suppress(ProcessLookupError):
                            process.kill()
                        await process.wait()

    async def _initialize(self, process: asyncio.subprocess.Process) -> None:
        await self._request(
            process,
            "initialize",
            {
                "protocolVersion": _PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "YF-Harness", "version": __version__},
            },
            timeout_seconds=self.settings.startup_timeout,
        )
        await self._send(
            process,
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        )

    async def _request(
        self,
        process: asyncio.subprocess.Process,
        method: str,
        params: dict[str, Any],
        *,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        request_id = f"yfh-{time.monotonic_ns()}"
        await self._send(
            process,
            {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params},
        )
        if process.stdout is None:
            raise MCPError(f"MCP {self.server_name} 没有 stdout")
        while True:
            line = await asyncio.wait_for(process.stdout.readline(), timeout=timeout_seconds)
            if not line:
                raise MCPError(f"MCP {self.server_name} 在 {method} 期间退出")
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise MCPError(f"MCP {self.server_name} 返回无效 JSON") from exc
            if not isinstance(payload, dict) or payload.get("id") != request_id:
                continue
            if isinstance(payload.get("error"), dict):
                error = payload["error"]
                raise MCPError(
                    f"MCP {self.server_name} {method} 失败: {error.get('message', error)}"
                )
            result = payload.get("result")
            if not isinstance(result, dict):
                raise MCPError(f"MCP {self.server_name} {method} 缺少 result")
            return result

    async def _send(self, process: asyncio.subprocess.Process, payload: dict[str, Any]) -> None:
        if process.stdin is None:
            raise MCPError(f"MCP {self.server_name} 没有 stdin")
        process.stdin.write(json.dumps(payload, ensure_ascii=False).encode() + b"\n")
        await process.stdin.drain()


class MCPTool(Tool):
    input_model = MCPToolInput
    risk_level = ToolRiskLevel.HIGH
    read_only = False
    always_approval = True
    original_name: ClassVar[str]
    input_schema: ClassVar[dict[str, Any]]

    def __init__(self, client: MCPClient) -> None:
        self.client = client

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self.input_schema,
            risk_level=self.risk_level,
            read_only=False,
        )

    def validate_arguments(self, value: dict[str, object]) -> ToolInput:
        _validate_json_schema(value, self.input_schema, path="arguments")
        return self.input_model.model_validate(value)

    async def preview(self, arguments: ToolInput, context: ToolContext) -> ToolPreview:
        return ToolPreview(paths=["."], command=self.client.settings.command, network=True)

    async def execute(self, arguments: ToolInput, context: ToolContext) -> ToolResult:
        result = await self.client.call_tool(self.original_name, arguments.model_dump())
        content = result.get("content", [])
        text_parts = (
            [
                str(item.get("text", ""))
                for item in content
                if isinstance(item, dict) and item.get("type") == "text"
            ]
            if isinstance(content, list)
            else []
        )
        stdout, truncated = truncate_output("\n".join(text_parts), context.output_limit)
        structured = result.get("structuredContent")
        structured_data = structured if isinstance(structured, dict) else {"content": content}
        is_error = result.get("isError") is True
        return ToolResult(
            tool_call_id=context.tool_call_id or "",
            success=not is_error,
            summary=f"MCP {self.client.server_name}/{self.original_name} "
            + ("失败" if is_error else "完成"),
            structured_data=structured_data,
            stdout=stdout,
            truncated=truncated,
            error_type="mcp_tool_error" if is_error else None,
        )


async def register_mcp_tools(
    registry: ToolRegistry,
    config: AppConfig,
    workspace: Path,
) -> list[str]:
    registered: list[str] = []
    for server_name, settings in sorted(config.mcp_servers.items()):
        if not settings.enabled:
            continue
        client = MCPClient(server_name, settings, workspace)
        for manifest in await client.list_tools():
            original_name = manifest.get("name")
            if not isinstance(original_name, str) or not original_name:
                continue
            if settings.enabled_tools is not None and original_name not in settings.enabled_tools:
                continue
            if original_name in settings.disabled_tools:
                continue
            exposed_name = f"mcp__{_normalize(server_name)}__{_normalize(original_name)}"
            schema = manifest.get("inputSchema")
            input_schema = schema if isinstance(schema, dict) else {"type": "object"}
            description = str(manifest.get("description") or f"MCP tool {original_name}")
            tool_type = type(
                f"MCPTool_{_normalize(server_name)}_{_normalize(original_name)}",
                (MCPTool,),
                {
                    "name": exposed_name,
                    "description": description,
                    "original_name": original_name,
                    "input_schema": input_schema,
                },
            )
            registry.register(tool_type(client))
            registered.append(exposed_name)
    return registered


def _normalize(value: str) -> str:
    normalized = _SAFE_NAME.sub("_", value).strip("_")
    return normalized or "unnamed"


def _validate_json_schema(value: Any, schema: dict[str, Any], *, path: str) -> None:
    expected = schema.get("type")
    if expected == "object":
        if not isinstance(value, dict):
            raise ValueError(f"{path} must be an object")
        properties = schema.get("properties", {})
        properties = properties if isinstance(properties, dict) else {}
        required = schema.get("required", [])
        if isinstance(required, list):
            missing = [name for name in required if name not in value]
            if missing:
                raise ValueError(f"{path} missing required fields: {', '.join(missing)}")
        if schema.get("additionalProperties") is False:
            unknown = sorted(set(value) - set(properties))
            if unknown:
                raise ValueError(f"{path} has unknown fields: {', '.join(unknown)}")
        for name, item in value.items():
            child = properties.get(name)
            if isinstance(child, dict):
                _validate_json_schema(item, child, path=f"{path}.{name}")
    elif expected == "array":
        if not isinstance(value, list):
            raise ValueError(f"{path} must be an array")
        child = schema.get("items")
        if isinstance(child, dict):
            for index, item in enumerate(value):
                _validate_json_schema(item, child, path=f"{path}[{index}]")
    elif expected == "string" and not isinstance(value, str):
        raise ValueError(f"{path} must be a string")
    elif expected == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
        raise ValueError(f"{path} must be an integer")
    elif expected == "number" and (not isinstance(value, int | float) or isinstance(value, bool)):
        raise ValueError(f"{path} must be a number")
    elif expected == "boolean" and not isinstance(value, bool):
        raise ValueError(f"{path} must be a boolean")
    enum = schema.get("enum")
    if isinstance(enum, list) and value not in enum:
        raise ValueError(f"{path} must be one of {enum}")
