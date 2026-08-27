"""Headless and interactive command-line entry points."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Annotated

import typer

from yfharness import __version__
from yfharness.config.loader import load_config
from yfharness.config.paths import config_file, database_file
from yfharness.core.agent import AgentLimits, AgentRunner
from yfharness.core.agent_events import (
    AgentEvent,
    HookEvaluated,
    ModelEventObserved,
    ToolExecutionFinished,
    ToolExecutionStarted,
)
from yfharness.core.attachments import prepare_image
from yfharness.core.context import ContextBuilder
from yfharness.core.events import TextDelta
from yfharness.core.exceptions import HarnessError
from yfharness.core.models import (
    ApprovalDecision,
    ApprovalRequest,
    ContentPart,
    HealthStatus,
    MessageRole,
    RunStatus,
)
from yfharness.core.plugins import discover_plugins
from yfharness.core.policies import AgentMode, ApprovalPolicy
from yfharness.core.workflows import HookEvaluation
from yfharness.diagnostics import run_doctor
from yfharness.integrations.mcp import register_mcp_tools
from yfharness.observability import TraceContext, get_logger, trace_scope
from yfharness.providers.registry import builtin_registry, provider_from_config
from yfharness.storage.database import Database
from yfharness.storage.models import SessionRecord
from yfharness.storage.repositories import (
    FileChangeRepository,
    RunRepository,
    SessionRepository,
    TraceRepository,
)
from yfharness.tools.base import ToolContext
from yfharness.tools.changes import ChangeEntry, ChangeJournal
from yfharness.tools.registry import ToolExecutor, ToolRegistry, builtin_tools
from yfharness.tools.security import WorkspaceGuard

app = typer.Typer(
    name="yfh",
    help="YF-Harness：本地优先、终端优先的 LLM Agent Harness。",
    no_args_is_help=True,
)
providers_app = typer.Typer(help="查看和诊断 Provider。")
config_app = typer.Typer(help="查看配置。")
sessions_app = typer.Typer(help="管理已保存会话。")
models_app = typer.Typer(help="查看模型配置。")
tools_app = typer.Typer(help="查看可用工具。")
workflows_app = typer.Typer(help="查看可用工作流配置。")
mcp_app = typer.Typer(help="发现显式启用的 MCP stdio 工具。")
plugins_app = typer.Typer(help="静态发现项目插件声明，不自动激活。")
frameworks_app = typer.Typer(help="发现、诊断和运行可选 Agent 框架。")
app.add_typer(providers_app, name="providers")
app.add_typer(config_app, name="config")
app.add_typer(sessions_app, name="sessions")
app.add_typer(models_app, name="models")
app.add_typer(tools_app, name="tools")
app.add_typer(workflows_app, name="workflows")
app.add_typer(mcp_app, name="mcp")
app.add_typer(plugins_app, name="plugins")
app.add_typer(frameworks_app, name="frameworks")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit


@app.callback()
def root(
    version: Annotated[
        bool,
        typer.Option("--version", callback=_version_callback, is_eager=True, help="显示版本。"),
    ] = False,
) -> None:
    """YF-Harness command group."""


@app.command()
def run(
    task: Annotated[str | None, typer.Argument(help="任务内容；省略时从 stdin 读取。")] = None,
    task_file: Annotated[
        Path | None,
        typer.Option("--file", exists=True, dir_okay=False, help="从 UTF-8 文件读取任务。"),
    ] = None,
    provider: Annotated[str | None, typer.Option("--provider", help="Provider 名称。")] = None,
    model: Annotated[str | None, typer.Option("--model", help="模型配置名称。")] = None,
    output: Annotated[str, typer.Option("--output", help="输出格式：text 或 json。")] = "text",
    timeout: Annotated[float, typer.Option("--timeout", min=0.1, help="运行超时秒数。")] = 120.0,
    session: Annotated[str | None, typer.Option("--session", help="继续已有会话 ID。")] = None,
    save: Annotated[bool, typer.Option("--save/--no-save", help="是否保存会话和运行记录。")] = True,
    workflow: Annotated[str | None, typer.Option("--workflow", help="工作流配置名称。")] = None,
    image: Annotated[
        list[Path] | None,
        typer.Option("--image", exists=True, dir_okay=False, help="附加图片(可重复)。"),
    ] = None,
    send_images: Annotated[
        bool,
        typer.Option(
            "--send-images/--local-images",
            help="明确授权将图片内容发送给所选模型。",
        ),
    ] = False,
    mode: Annotated[AgentMode | None, typer.Option("--mode", help="覆盖工作流的运行模式。")] = None,
    permissions: Annotated[
        ApprovalPolicy | None, typer.Option("--permissions", help="覆盖工作流的工具审批策略。")
    ] = None,
) -> None:
    """运行一个无界面、可自动化的模型请求。"""

    if task is not None and task_file is not None:
        typer.echo("错误：任务参数与 --file 不能同时使用。", err=True)
        raise typer.Exit(code=2)
    try:
        prompt = task_file.read_text(encoding="utf-8") if task_file is not None else task
    except UnicodeDecodeError as exc:
        typer.echo("错误：任务文件必须是 UTF-8。", err=True)
        raise typer.Exit(code=2) from exc
    prompt = prompt if prompt is not None else sys.stdin.read()
    if not prompt.strip():
        typer.echo("错误：任务内容不能为空。", err=True)
        raise typer.Exit(code=2)
    if output not in {"text", "json"}:
        typer.echo("错误：--output 只能是 text 或 json。", err=True)
        raise typer.Exit(code=2)

    try:
        config = load_config()
        provider_name = provider or config.default_provider
        model_name = model or config.default_model
        result = asyncio.run(
            _run_once(
                prompt,
                provider_name,
                model_name,
                timeout,
                stream=output == "text",
                session_id=session,
                save=save,
                mode=mode,
                permissions=permissions,
                workflow_name=workflow,
                image_paths=image,
                send_images=send_images,
            )
        )
    except (HarnessError, TimeoutError, ValueError, KeyError, OSError, sqlite3.Error) as exc:
        typer.echo(f"错误：{exc}", err=True)
        raise typer.Exit(code=1) from exc

    if output == "json":
        typer.echo(json.dumps(result, ensure_ascii=False))


@app.command()
def tui() -> None:
    """启动键盘优先的 Textual 界面。"""

    from yfharness.tui.application import YFHarnessApp

    YFHarnessApp().run()


@app.command()
def desktop() -> None:
    """启动独立的 YF-Harness 桌面应用。"""

    try:
        from yfharness.desktop.app import main as desktop_main
    except ImportError as exc:
        typer.echo("错误：桌面组件未安装；请运行 pip install 'yf-harness[desktop]'。", err=True)
        raise typer.Exit(code=1) from exc
    desktop_main()


@app.command()
def chat(
    provider: Annotated[str | None, typer.Option("--provider")] = None,
    model: Annotated[str | None, typer.Option("--model")] = None,
) -> None:
    """启动可恢复的无 TUI 交互对话。"""

    config = load_config()
    provider_name = provider or config.default_provider
    model_name = model or config.default_model
    session_id: str | None = None
    typer.echo("YF-Harness Chat；输入 /quit 退出，Ctrl+C 取消。")
    while True:
        try:
            prompt = typer.prompt("你")
        except (EOFError, KeyboardInterrupt):
            typer.echo("\n再见。")
            return
        if prompt.strip() == "/quit":
            return
        try:
            result = asyncio.run(
                _run_once(
                    prompt,
                    provider_name,
                    model_name,
                    config.agent.max_run_seconds,
                    stream=True,
                    session_id=session_id,
                    save=True,
                    mode=AgentMode.CHAT,
                )
            )
            session_id = str(result["session_id"])
        except HarnessError as exc:
            typer.echo(f"错误：{exc}", err=True)


@app.command()
def replay(
    run_id: Annotated[str, typer.Argument(help="运行 ID。")],
    execute: Annotated[
        bool, typer.Option("--execute", help="确认后重新发起模型请求；默认只读。")
    ] = False,
    yes: Annotated[bool, typer.Option("--yes", help="确认重新执行。")] = False,
) -> None:
    """查看运行事件；默认绝不重新执行工具。"""

    async def load() -> dict[str, object]:
        database = Database(database_file())
        await database.initialize()
        return await TraceRepository(database).replay(run_id)

    try:
        payload = asyncio.run(load())
    except (KeyError, sqlite3.Error) as exc:
        typer.echo(f"错误：{exc}", err=True)
        raise typer.Exit(code=1) from exc
    if not execute:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        return
    if not yes and not typer.confirm("重新执行可能再次请求模型和工具，是否继续？"):
        raise typer.Abort
    requests = payload.get("model_requests")
    if not isinstance(requests, list) or not requests:
        typer.echo("错误：该运行没有可重新执行的模型请求。", err=True)
        raise typer.Exit(code=1)
    first = requests[0]
    if not isinstance(first, dict) or not isinstance(first.get("request_json"), dict):
        typer.echo("错误：回放请求格式无效。", err=True)
        raise typer.Exit(code=1)
    request_data = first["request_json"]
    task = request_data.get("task")
    if not isinstance(task, str):
        typer.echo("错误：回放中没有原始任务。", err=True)
        raise typer.Exit(code=1)
    result = asyncio.run(
        _run_once(
            task,
            str(first["provider"]),
            str(first["model"]),
            120,
            stream=True,
            save=True,
        )
    )
    typer.echo(json.dumps(result, ensure_ascii=False))


@app.command("eval")
def eval_command(
    output: Annotated[Path | None, typer.Option("--output", help="报告目录。")] = None,
) -> None:
    """运行 20 类不需要 API Key 的离线 Harness Eval。"""

    from yfharness.evals.runner import EvalRunner

    report = asyncio.run(EvalRunner().run(report_directory=output))
    typer.echo(f"用例总数: {report.total}")
    typer.echo(f"通过数: {report.passed}")
    typer.echo(f"失败数: {report.failed}")
    typer.echo(f"通过率: {report.pass_rate:.1%}")
    typer.echo(f"总耗时: {report.duration:.3f}s")
    typer.echo(f"平均步骤数: {report.average_steps:.2f}")
    typer.echo(f"工具错误数: {report.tool_errors}")
    for case in report.cases:
        if not case.passed:
            typer.echo(f"失败: {case.name}: {case.reason}")
    typer.echo(f"JSON 报告: {report.report_path}")
    if report.failed:
        raise typer.Exit(code=1)


async def _run_once(
    prompt: str,
    provider_name: str,
    model_name: str,
    timeout_seconds: float,
    *,
    stream: bool,
    session_id: str | None = None,
    save: bool = True,
    mode: AgentMode | None = None,
    permissions: ApprovalPolicy | None = None,
    workflow_name: str | None = None,
    image_paths: list[Path] | None = None,
    send_images: bool = False,
    attachment_parts: list[ContentPart] | None = None,
    event_sink: Callable[[AgentEvent], Awaitable[None]] | None = None,
    approval_handler: Callable[[ApprovalRequest], Awaitable[ApprovalDecision]] | None = None,
    runner_sink: Callable[[AgentRunner], None] | None = None,
) -> dict[str, object]:
    config = load_config()
    workflow = config.workflow(workflow_name)
    mode = mode or workflow.mode
    permissions = permissions or workflow.permissions
    provider = provider_from_config(config, provider_name)
    try:
        model_config = config.models[model_name]
    except KeyError as exc:
        raise ValueError(f"unknown model {model_name!r}") from exc
    if model_config.provider != provider_name:
        raise ValueError(f"model {model_name!r} belongs to provider {model_config.provider!r}")
    session_repo: SessionRepository | None = None
    run_repo: RunRepository | None = None
    change_repo: FileChangeRepository | None = None
    trace_repo: TraceRepository | None = None
    run_record = None
    history = []
    if session_id is not None and not save:
        raise ValueError("--session requires --save")
    if save:
        database = Database(database_file())
        await database.initialize()
        session_repo = SessionRepository(database)
        run_repo = RunRepository(database)
        change_repo = FileChangeRepository(database)
        trace_repo = TraceRepository(database)
        await run_repo.mark_interrupted()
        if session_id is None:
            session_record = await session_repo.create(
                title=prompt.strip().splitlines()[0][:80],
                provider=provider_name,
                model=model_name,
                mode=mode.value,
            )
            session_id = session_record.id
        else:
            existing_session = await session_repo.get(session_id)
            if existing_session is None:
                raise KeyError(f"session not found: {session_id}")
            if (existing_session.provider, existing_session.model) != (provider_name, model_name):
                raise ValueError("existing session provider/model does not match requested values")
            history = await session_repo.messages(session_id)
        run_record = await run_repo.create(session_id)
    else:
        session_id = "ephemeral"

    guard = WorkspaceGuard(config.workspace)
    changes = ChangeJournal(guard)
    tool_registry = builtin_tools()
    mcp_tools = await register_mcp_tools(tool_registry, config, guard.root)
    attachments = list(attachment_parts or [])
    attachments.extend(
        prepare_image(path, guard, send_to_model=send_images) for path in image_paths or []
    )

    async def record_change(entry: ChangeEntry) -> None:
        if change_repo is None or run_record is None:
            return
        path = guard.relative(entry.path)
        if entry.destination is not None:
            path = f"{path} -> {guard.relative(entry.destination)}"
        await change_repo.record(
            path=path,
            before=entry.before,
            after=entry.after,
            run_id=run_record.run_id,
            tool_call_id=tool_context.tool_call_id,
        )

    async def approve(request: ApprovalRequest) -> ApprovalDecision:
        if approval_handler is not None:
            decision = await approval_handler(request)
        elif not sys.stdin.isatty():
            decision = ApprovalDecision.DENY
        else:
            typer.echo(f"\n工具审批: {request.tool_call.name} [{request.risk_level.value}]")
            typer.echo(f"参数: {json.dumps(request.tool_call.arguments, ensure_ascii=False)}")
            if request.paths:
                typer.echo(f"路径: {', '.join(request.paths)}")
            if request.command:
                typer.echo(f"命令: {request.command}")
            if request.diff_preview:
                typer.echo(request.diff_preview)
            allowed = await asyncio.to_thread(typer.confirm, "允许本次工具调用？")
            decision = ApprovalDecision.ALLOW_ONCE if allowed else ApprovalDecision.DENY
        if trace_repo is not None and run_record is not None:
            await trace_repo.record_approval(
                request_id=request.id,
                run_id=run_record.run_id,
                tool_call_id=request.tool_call.id,
                request=request.model_dump(mode="json"),
                decision=decision.value,
            )
        return decision

    observed_events: list[AgentEvent] = []

    async def observe(event: AgentEvent) -> None:
        observed_events.append(event)
        if event_sink is not None:
            await event_sink(event)
        if not stream or not isinstance(event, ModelEventObserved):
            return
        if model_config.supports_native_tools and isinstance(event.event, TextDelta):
            typer.echo(event.event.text, nl=False)

    async def observe_hook(evaluation: HookEvaluation) -> None:
        await observe(HookEvaluated(evaluation=evaluation))

    tool_context = ToolContext(
        workspace=guard.root,
        guard=guard,
        run_id=run_record.run_id if run_record is not None else None,
        changes=changes,
        change_recorder=record_change,
    )
    tool_executor = ToolExecutor(
        tool_registry,
        tool_context,
        mode=mode,
        policy=permissions,
        approval_handler=approve,
        workflow=workflow,
        hook_sink=observe_hook,
    )
    agent_limits = AgentLimits(
        max_steps=config.agent.max_steps,
        max_tool_calls=config.agent.max_tool_calls,
        max_run_seconds=min(timeout_seconds, config.agent.max_run_seconds),
        max_token_budget=config.agent.max_token_budget,
        max_cost=config.agent.max_cost,
    )
    runner = AgentRunner(
        provider=provider,
        model=model_config,
        tools=tool_executor,
        mode=mode,
        limits=agent_limits,
        event_sink=observe,
        context_builder=ContextBuilder(config.workspace, provider.estimate_tokens),
    )
    if runner_sink is not None:
        runner_sink(runner)
    started = time.monotonic()
    context = TraceContext(
        run_id=run_record.run_id if run_record is not None else "ephemeral",
        trace_id=run_record.trace_id if run_record is not None else "ephemeral",
    )
    logger = get_logger()
    with trace_scope(context):
        logger.info("agent run started", extra={"provider": provider_name, "model": model_name})
        result = await runner.run(
            prompt,
            session_id=session_id,
            history=history,
            existing_run=run_record,
            attachments=attachments,
        )
        logger.info(
            "agent run finished",
            extra={
                "provider": provider_name,
                "model": model_name,
                "duration": time.monotonic() - started,
                "error_type": None
                if result.run.status is RunStatus.COMPLETED
                else result.run.status.value,
            },
        )
    if stream and not model_config.supports_native_tools:
        typer.echo(result.final_text, nl=False)
    if stream:
        typer.echo()
    if session_repo is not None:
        existing_ids = {message.id for message in history}
        for message in result.messages:
            if message.role is not MessageRole.SYSTEM and message.id not in existing_ids:
                await session_repo.add_message(session_id, message)
    if run_record is not None and run_repo is not None:
        await run_repo.finish(
            run_record,
            status=result.run.status,
            state=result.run.state,
            usage=result.run.usage,
            error=result.run.error,
        )
    if trace_repo is not None and run_record is not None:
        duration = time.monotonic() - started
        await trace_repo.record_model_events(
            run_id=run_record.run_id,
            provider=provider_name,
            model=model_name,
            request={
                "task": prompt,
                "mode": mode.value,
                "workflow": workflow.id,
                "attachments": [
                    {
                        "name": Path(part.path or "").name,
                        "mime_type": part.mime_type,
                        "size_bytes": part.size_bytes,
                        "transfer": part.transfer.value,
                    }
                    for part in attachments
                ],
            },
            events=[event.model_dump(mode="json") for event in observed_events],
            duration=duration,
            error_type=None
            if result.run.status is RunStatus.COMPLETED
            else result.run.status.value,
        )
        started_calls = {
            event.call.id: event.call
            for event in observed_events
            if isinstance(event, ToolExecutionStarted)
        }
        finished_calls = {
            event.result.tool_call_id: event.result
            for event in observed_events
            if isinstance(event, ToolExecutionFinished)
        }
        definitions = {item.name: item for item in tool_registry.definitions()}
        for call_id, call in started_calls.items():
            tool_result = finished_calls.get(call_id)
            await trace_repo.record_tool_call(
                run_id=run_record.run_id,
                call_id=call_id,
                name=call.name,
                arguments=call.arguments,
                result=tool_result.model_dump(mode="json") if tool_result is not None else None,
                risk_level=definitions[call.name].risk_level.value
                if call.name in definitions
                else "unknown",
                status="completed" if tool_result is not None else "interrupted",
            )
        await trace_repo.record_usage(
            run_id=run_record.run_id,
            provider=provider_name,
            model=model_name,
            usage=result.run.usage,
            duration=duration,
        )
        if runner.context_builder is not None and runner.context_builder.last_snapshot is not None:
            snapshot = runner.context_builder.last_snapshot
            await trace_repo.record_context(
                run_id=run_record.run_id,
                snapshot=snapshot.model_dump(mode="json"),
                estimated_tokens=snapshot.estimated_tokens,
            )
    if result.run.status is not RunStatus.COMPLETED:
        raise HarnessError(result.run.error or f"run ended with {result.run.status.value}")
    context_payload: dict[str, object] | None = None
    if runner.context_builder is not None and runner.context_builder.last_snapshot is not None:
        snapshot = runner.context_builder.last_snapshot
        context_payload = {
            "estimated_tokens": snapshot.estimated_tokens,
            "budget_tokens": snapshot.budget_tokens,
            "usage_ratio": snapshot.usage_ratio,
            "compacted": snapshot.compacted,
            "sources": [source.model_dump(mode="json") for source in snapshot.sources],
        }
    return {
        "session_id": session_id,
        "run_id": result.run.run_id,
        "provider": provider_name,
        "model": model_name,
        "workflow": {
            "id": workflow.id,
            "label": workflow.label,
            "mode": mode.value,
            "permissions": permissions.value,
            "visible_tools": [item.name for item in tool_executor.definitions()],
            "hook_count": len(workflow.hooks),
        },
        "text": result.final_text,
        "usage": result.run.usage.model_dump(mode="json"),
        "steps": result.run.step_count,
        "tool_calls": result.run.tool_call_count,
        "context": context_payload,
        "attachments": [
            {
                "name": Path(part.path or "").name,
                "mime_type": part.mime_type,
                "size_bytes": part.size_bytes,
                "transfer": part.transfer.value,
            }
            for part in attachments
        ],
        "mcp_tools": mcp_tools,
    }


@providers_app.command("list")
def providers_list() -> None:
    """列出已注册 Provider。"""

    names = set(builtin_registry().names()) | set(load_config().providers)
    for name in sorted(names):
        typer.echo(name)


@models_app.command("list")
def models_list() -> None:
    """列出模型配置及所属 Provider。"""

    for name, model_config in sorted(load_config().models.items()):
        typer.echo(f"{name}\t{model_config.provider}\t{model_config.model}")


@tools_app.command("list")
def tools_list() -> None:
    """列出工具、风险和只读属性。"""

    from yfharness.tools.registry import builtin_tools

    for definition in builtin_tools().definitions():
        typer.echo(
            f"{definition.name}\t{definition.risk_level.value}\t"
            f"{'read-only' if definition.read_only else 'write/execute'}"
        )


@workflows_app.command("list")
def workflows_list() -> None:
    """列出版本化工作流、默认策略和可见工具数。"""

    config = load_config()
    definitions = builtin_tools().definitions()
    for name, workflow in sorted(config.workflows.items()):
        marker = "*" if name == config.default_workflow else " "
        typer.echo(
            f"{marker} {name}\t{workflow.mode.value}\t{workflow.permissions.value}\t"
            f"{len(workflow.filter_definitions(definitions))} tools\t"
            f"{len(workflow.hooks)} hooks\t{workflow.label}"
        )


@mcp_app.command("list")
def mcp_list() -> None:
    """启动已显式启用的 stdio 服务，列出经本地命名隔离后的工具。"""

    async def discover() -> list[str]:
        config = load_config()
        registry = ToolRegistry()
        return await register_mcp_tools(registry, config, config.workspace)

    try:
        names = asyncio.run(discover())
    except (HarnessError, OSError, ValueError) as exc:
        typer.echo(f"错误：{exc}", err=True)
        raise typer.Exit(code=1) from exc
    if not names:
        typer.echo("没有已启用的 MCP 工具。")
        return
    for name in names:
        typer.echo(name)


@plugins_app.command("list")
def plugins_list() -> None:
    """列出 workspace `.yfh/plugins/*/plugin.json` 及其待审查权限。"""

    plugins = discover_plugins(load_config().workspace)
    if not plugins:
        typer.echo("没有发现项目插件。")
        return
    for item in plugins:
        permissions = ",".join(item.manifest.requested_permissions) or "none"
        typer.echo(
            f"{item.manifest.id}\t{item.manifest.version}\t{item.status}\t"
            f"permissions={permissions}\t{item.manifest_path}"
        )


@frameworks_app.command("list")
def frameworks_list() -> None:
    """列出框架、安装状态和已发现版本。"""

    from yfharness.integrations.frameworks import framework_infos

    for info in framework_infos():
        versions = ", ".join(f"{name}={value}" for name, value in info.versions.items())
        typer.echo(
            f"{info.name.value}\t{'installed' if info.installed else 'missing'}\t"
            f"{versions or f'pip install yf-harness[{info.install_extra}]'}"
        )


@frameworks_app.command("doctor")
def frameworks_doctor() -> None:
    """诊断全部可选框架，不把未安装的可选项视为全局错误。"""

    from yfharness.integrations.frameworks import framework_infos

    for info in framework_infos():
        if info.installed:
            versions = ", ".join(f"{name} {value}" for name, value in info.versions.items())
            typer.echo(f"[OK] framework:{info.name.value}: {versions}")
        else:
            typer.echo(
                f"[Skipped] framework:{info.name.value}: 可选依赖未完整安装；"
                f"pip install 'yf-harness[{info.install_extra}]'"
            )


@frameworks_app.command("run")
def frameworks_run(
    framework: Annotated[str, typer.Argument(help="框架：langchain、llamaindex 或 autogen。")],
    task: Annotated[str, typer.Argument(help="任务内容。")],
    provider: Annotated[str | None, typer.Option("--provider", help="Provider 名称。")] = None,
    model: Annotated[str | None, typer.Option("--model", help="模型配置名称。")] = None,
    system_prompt: Annotated[
        str, typer.Option("--system", help="传给框架 Agent 的系统提示词。")
    ] = "You are a helpful assistant.",
    output: Annotated[str, typer.Option("--output", help="输出格式：text 或 json。")] = "text",
    timeout: Annotated[float, typer.Option("--timeout", min=0.1, help="运行超时秒数。")] = 120,
) -> None:
    """通过框架原生 Agent API 运行一个无工具任务。"""

    from yfharness.integrations.frameworks import (
        FrameworkName,
        FrameworkRequest,
        get_adapter,
    )

    if output not in {"text", "json"}:
        typer.echo("错误：--output 只能是 text 或 json。", err=True)
        raise typer.Exit(code=2)
    try:
        framework_name = FrameworkName(framework.lower())
    except ValueError as exc:
        typer.echo(f"错误：未知框架 {framework!r}。", err=True)
        raise typer.Exit(code=2) from exc
    try:
        config = load_config()
        request = FrameworkRequest(
            task=task,
            provider=provider or config.default_provider,
            model=model or config.default_model,
            system_prompt=system_prompt,
            timeout_seconds=timeout,
        )
        result = asyncio.run(get_adapter(framework_name).run(request, config))
    except (HarnessError, TimeoutError, ValueError, KeyError, OSError) as exc:
        typer.echo(f"错误：{exc}", err=True)
        raise typer.Exit(code=1) from exc
    if output == "json":
        typer.echo(json.dumps(result.model_dump(mode="json"), ensure_ascii=False))
    else:
        typer.echo(result.text)


@sessions_app.command("list")
def sessions_list(
    query: Annotated[str | None, typer.Option("--query", help="按标题搜索。")] = None,
    archived: Annotated[bool, typer.Option("--archived", help="包含已归档会话。")] = False,
) -> None:
    """列出已保存会话。"""

    async def operation() -> list[SessionRecord]:
        database = Database(database_file())
        await database.initialize()
        return await SessionRepository(database).list(query=query, include_archived=archived)

    for record in asyncio.run(operation()):
        typer.echo(f"{record.id}\t{record.title}\t{record.provider}/{record.model}")


@sessions_app.command("rename")
def sessions_rename(session_id: str, title: str) -> None:
    """重命名会话。"""

    changed = asyncio.run(_session_update("rename", session_id, title))
    if not changed:
        typer.echo("错误：会话不存在。", err=True)
        raise typer.Exit(code=1)


@sessions_app.command("archive")
def sessions_archive(session_id: str) -> None:
    """归档会话。"""

    changed = asyncio.run(_session_update("archive", session_id))
    if not changed:
        typer.echo("错误：会话不存在。", err=True)
        raise typer.Exit(code=1)


@sessions_app.command("delete")
def sessions_delete(
    session_id: str,
    yes: Annotated[bool, typer.Option("--yes", help="确认永久删除会话。")] = False,
) -> None:
    """确认后永久删除会话。"""

    if not yes and not typer.confirm(f"确定删除会话 {session_id}？"):
        raise typer.Abort
    changed = asyncio.run(_session_update("delete", session_id))
    if not changed:
        typer.echo("错误：会话不存在。", err=True)
        raise typer.Exit(code=1)


@sessions_app.command("export")
def sessions_export(
    session_id: str,
    format: Annotated[str, typer.Option("--format", help="markdown 或 json。")] = "markdown",
    output: Annotated[Path | None, typer.Option("--output", help="写入文件；默认 stdout。")] = None,
) -> None:
    """脱敏导出会话。"""

    async def operation() -> str:
        database = Database(database_file())
        await database.initialize()
        return await SessionRepository(database).export(session_id, format=format)

    try:
        content = asyncio.run(operation())
    except (KeyError, ValueError, sqlite3.Error) as exc:
        typer.echo(f"错误：{exc}", err=True)
        raise typer.Exit(code=1) from exc
    if output is None:
        typer.echo(content)
    else:
        output.write_text(content, encoding="utf-8")
        typer.echo(output)


async def _session_update(operation: str, session_id: str, value: str | None = None) -> bool:
    database = Database(database_file())
    await database.initialize()
    repository = SessionRepository(database)
    if operation == "rename" and value is not None:
        return await repository.rename(session_id, value)
    if operation == "archive":
        return await repository.archive(session_id)
    if operation == "delete":
        return await repository.delete(session_id)
    raise ValueError(f"unknown session operation: {operation}")


@config_app.command("path")
def config_path() -> None:
    """显示用户配置文件路径。"""

    typer.echo(config_file())


@config_app.command("show")
def config_show() -> None:
    """显示合并后的脱敏配置。"""

    typer.echo(json.dumps(load_config().redacted_dict(), ensure_ascii=False, indent=2))


@app.command()
def doctor(
    network: Annotated[
        bool,
        typer.Option("--network/--no-network", help="是否执行 Provider 健康检查。"),
    ] = True,
) -> None:
    """检查 Python、目录、工作区与 Provider 配置。"""

    try:
        checks = asyncio.run(run_doctor(load_config(), check_network=network))
    except HarnessError as exc:
        typer.echo(f"错误：{exc}", err=True)
        raise typer.Exit(code=1) from exc
    labels = {
        HealthStatus.OK: "OK",
        HealthStatus.WARNING: "Warning",
        HealthStatus.ERROR: "Error",
        HealthStatus.SKIPPED: "Skipped",
    }
    for check in checks:
        typer.echo(f"[{labels[check.status]}] {check.name}: {check.message}")
    if any(check.status is HealthStatus.ERROR for check in checks):
        raise typer.Exit(code=1)


def _configure_utf8_stdio() -> None:
    """Keep redirected Windows CLI input and output Unicode-safe."""

    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            # Embedded hosts may expose immutable or already-closed streams.
            continue


def main() -> None:
    _configure_utf8_stdio()
    app()


if __name__ == "__main__":
    main()
