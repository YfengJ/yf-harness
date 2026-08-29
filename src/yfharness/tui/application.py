"""Keyboard-first Textual application backed by the real AgentRunner."""

from __future__ import annotations

import json
import time
from typing import ClassVar

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import (
    Button,
    Collapsible,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Markdown,
    Static,
    TextArea,
)

from yfharness.config.loader import load_config
from yfharness.config.paths import database_file, log_dir
from yfharness.core.agent import AgentLimits, AgentRunner
from yfharness.core.agent_events import (
    AgentEvent,
    BudgetUpdated,
    HookEvaluated,
    ModelEventObserved,
    StateChanged,
    ToolExecutionFinished,
    ToolExecutionStarted,
)
from yfharness.core.context import ContextBuilder
from yfharness.core.events import TextDelta
from yfharness.core.models import (
    AgentRun,
    ApprovalDecision,
    ApprovalRequest,
    MessageRole,
    RunStatus,
)
from yfharness.core.policies import AgentMode, ApprovalPolicy
from yfharness.core.skills import SkillCatalog, SkillInvocation, parse_skill_reference
from yfharness.core.workflows import HookEvaluation
from yfharness.diagnostics import run_doctor
from yfharness.integrations.mcp import register_mcp_tools
from yfharness.providers.registry import provider_from_config
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
from yfharness.tools.registry import ToolExecutor, builtin_tools
from yfharness.tools.security import WorkspaceGuard
from yfharness.tui.commands import (
    COMMANDS,
    SlashCommand,
    SlashCommandError,
    command_suggestions,
    parse_slash_command,
)
from yfharness.tui.screens.approval import ApprovalScreen
from yfharness.tui.screens.help import HelpScreen
from yfharness.tui.screens.settings import SettingsScreen, SettingsSelection


class SessionItem(ListItem):
    def __init__(self, session: SessionRecord) -> None:
        super().__init__(Label(session.title))
        self.session_id = session.id


class YFHarnessApp(App[None]):
    TITLE = "YF-Harness"
    SUB_TITLE = "本地优先 LLM Agent Harness"
    CSS_PATH = "styles.tcss"
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+n", "new_session", "新会话", priority=True),
        Binding("ctrl+k", "show_commands", "命令", priority=True),
        Binding("ctrl+c", "cancel_run", "取消运行", priority=True),
        Binding("ctrl+l", "focus_prompt", "输入", priority=True),
        Binding("ctrl+p", "cycle_mode", "模式", priority=True),
        Binding("ctrl+o", "focus_sessions", "会话", priority=True),
        Binding("ctrl+enter", "submit_prompt", "发送", priority=True),
        Binding("alt+up", "history_previous", "上一条输入", priority=True),
        Binding("alt+down", "history_next", "下一条输入", priority=True),
        Binding("ctrl+shift+a", "toggle_auto_scroll", "自动滚动", priority=True),
        Binding("f1", "help", "帮助", priority=True),
        Binding("escape", "escape", "返回"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.config = load_config()
        self.database = Database(database_file())
        self.sessions = SessionRepository(self.database)
        self.runs = RunRepository(self.database)
        self.file_changes = FileChangeRepository(self.database)
        self.traces = TraceRepository(self.database)
        self.provider_name = self.config.default_provider
        self.model_name = self.config.default_model
        self.workflow_name = self.config.default_workflow
        workflow = self.config.workflow(self.workflow_name)
        self.mode = workflow.mode
        self.policy = workflow.permissions
        self.current_session_id: str | None = None
        self.active_runner: AgentRunner | None = None
        self.input_history: list[str] = []
        self.history_index = 0
        self.last_prompt: str | None = None
        self.attached_paths: set[str] = set()
        self.guard = WorkspaceGuard(self.config.workspace)
        self.change_journal = ChangeJournal(self.guard)
        self.context_builder = ContextBuilder(self.guard.root, lambda text: max(1, len(text) // 4))
        self.skill_catalog = SkillCatalog(self.guard.root)
        self._stream_text = ""
        self._stream_widget: Static | None = None
        self.auto_scroll = True
        self._active_run_record: AgentRun | None = None
        self._observed_events: list[AgentEvent] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("终端尺寸过小；请增大窗口以显示完整界面。", id="size-warning")
        with Horizontal(id="main-grid"):
            with Vertical(id="sidebar"):
                yield Button("+ 新建会话", id="new-session", variant="primary")
                yield Input(placeholder="搜索会话", id="session-search")
                yield ListView(id="sessions")
                yield Static(id="provider-label")
            with Vertical(id="center"):
                yield VerticalScroll(id="conversation")
                yield Static(id="suggestions")
                yield TextArea(id="prompt", language=None, show_line_numbers=False)
                with Horizontal(id="bottom-actions"):
                    yield Button("设置", id="settings")
                    yield Button("诊断", id="doctor")
                    yield Button("发送", id="send", variant="success")
            with Vertical(id="right-panel"):
                yield Static("运行状态", classes="panel-title")
                yield Static("空闲", id="run-state")
                yield Static("统计", classes="panel-title")
                yield Static("Token: 0 · Cost: 0", id="usage")
                yield Static("上下文", classes="panel-title")
                yield Static("附件: 0", id="context-status")
                yield Static("工具时间线", classes="panel-title")
                yield Static("尚无工具调用", id="timeline")
                yield Static(id="workspace-status")
        yield Footer()

    async def on_mount(self) -> None:
        await self.database.initialize()
        await self.runs.mark_interrupted()
        await self.reload_sessions()
        self._update_status_labels()
        self.query_one("#prompt", TextArea).focus()

    async def reload_sessions(self, query: str | None = None) -> None:
        list_view = self.query_one("#sessions", ListView)
        await list_view.clear()
        for session in await self.sessions.list(query=query, workspace=self.guard.root):
            await list_view.append(SessionItem(session))

    async def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "session-search":
            await self.reload_sessions(event.value or None)

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id != "prompt":
            return
        value = event.text_area.text
        if value.lstrip().startswith("/"):
            suggestions = command_suggestions(value.split(maxsplit=1)[0])[:5]
            self.query_one("#suggestions", Static).update("\n".join(suggestions))
        elif value.lstrip().startswith("$"):
            prefix = value.strip()[1:].split(maxsplit=1)[0].lower()
            suggestions = [
                f"${item.id} — {item.description}"
                for item in self.skill_catalog.discover()
                if item.id.lower().startswith(prefix) or item.name.lower().startswith(prefix)
            ][:5]
            self.query_one("#suggestions", Static).update("\n".join(suggestions))
        else:
            self.query_one("#suggestions", Static).update("")

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, SessionItem):
            await self.open_session(event.item.session_id)

    async def open_session(self, session_id: str) -> None:
        self.current_session_id = session_id
        conversation = self.query_one("#conversation", VerticalScroll)
        await conversation.remove_children()
        for message in await self.sessions.messages(session_id):
            if message.role in {MessageRole.USER, MessageRole.ASSISTANT}:
                await self._mount_message(message.role, message.text_content)
            elif message.role is MessageRole.TOOL:
                await conversation.mount(
                    Collapsible(Static(message.text_content), title="历史工具结果", collapsed=True)
                )
        conversation.scroll_end(animate=False)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        actions = {
            "new-session": self.action_new_session,
            "send": self.action_submit_prompt,
            "settings": self.action_settings,
            "doctor": self.action_doctor,
        }
        action = actions.get(event.button.id or "")
        if action is not None:
            action()

    def action_submit_prompt(self) -> None:
        prompt_widget = self.query_one("#prompt", TextArea)
        value = prompt_widget.text.strip()
        if not value:
            return
        prompt_widget.clear()
        self.query_one("#suggestions", Static).update("")
        try:
            command = parse_slash_command(value)
        except SlashCommandError as exc:
            self.notify(str(exc), severity="error")
            return
        if command is not None:
            self.handle_command(command)
            return
        if self.active_runner is not None:
            self.notify("当前运行尚未结束；可按 Ctrl+C 取消。", severity="warning")
            return
        self.input_history.append(value)
        self.history_index = len(self.input_history)
        self.last_prompt = value
        try:
            skill_reference = parse_skill_reference(value)
        except ValueError as exc:
            self.notify(str(exc), severity="error")
            return
        if skill_reference is None:
            self.run_prompt(value)
            return
        skill_name, skill_arguments = skill_reference
        try:
            self.skill_catalog.resolve(skill_name)
        except ValueError as exc:
            self.notify(str(exc), severity="error")
            return
        self.run_prompt(value, skill_name, skill_arguments)

    @work(exclusive=True, group="agent")
    async def run_prompt(
        self,
        prompt: str,
        skill_name: str | None = None,
        skill_arguments: str = "",
    ) -> None:
        try:
            skill: SkillInvocation | None = None
            if skill_name is not None:
                skill = self.skill_catalog.invoke(skill_name, skill_arguments)
            if self.current_session_id is None:
                session = await self.sessions.create(
                    title=prompt.splitlines()[0][:80],
                    provider=self.provider_name,
                    model=self.model_name,
                    mode=self.mode.value,
                    workspace=self.guard.root,
                )
                self.current_session_id = session.id
            session_id = self.current_session_id
            history = await self.sessions.messages(session_id)
            await self._mount_message(MessageRole.USER, prompt)
            self._stream_text = ""
            self._stream_widget = Static("", classes="message-assistant")
            await self.query_one("#conversation", VerticalScroll).mount(self._stream_widget)
            provider = provider_from_config(self.config, self.provider_name)
            self.context_builder.estimator = provider.estimate_tokens
            model = self.config.models[self.model_name]
            run_record = await self.runs.create(session_id)
            self._active_run_record = run_record
            self._observed_events = []
            started = time.monotonic()
            tool_context = ToolContext(
                workspace=self.guard.root,
                guard=self.guard,
                run_id=run_record.run_id,
                changes=self.change_journal,
            )

            async def record_change(entry: ChangeEntry) -> None:
                path = self.guard.relative(entry.path)
                if entry.destination is not None:
                    path = f"{path} -> {self.guard.relative(entry.destination)}"
                await self.file_changes.record(
                    path=path,
                    before=entry.before,
                    after=entry.after,
                    run_id=run_record.run_id,
                    tool_call_id=tool_context.tool_call_id,
                )

            tool_context.change_recorder = record_change
            registry = builtin_tools()
            await register_mcp_tools(registry, self.config, self.guard.root)
            executor = ToolExecutor(
                registry,
                tool_context,
                mode=self.mode,
                policy=self.policy,
                approval_handler=self._approve,
                workflow=self.config.workflow(self.workflow_name),
                hook_sink=self._observe_hook,
            )
            limits = AgentLimits(
                max_steps=self.config.agent.max_steps,
                max_tool_calls=self.config.agent.max_tool_calls,
                max_run_seconds=self.config.agent.max_run_seconds,
                max_token_budget=self.config.agent.max_token_budget,
                max_cost=self.config.agent.max_cost,
            )
            runner = AgentRunner(
                provider=provider,
                model=model,
                tools=executor,
                mode=self.mode,
                limits=limits,
                event_sink=self._observe_agent,
                context_builder=self.context_builder,
            )
            self.active_runner = runner
            result = await runner.run(
                prompt,
                session_id=session_id,
                history=history,
                existing_run=run_record,
                skill=skill,
            )
            if not model.supports_native_tools and self._stream_widget is not None:
                self._stream_widget.update(result.final_text)
            existing_ids = {message.id for message in history}
            for message in result.messages:
                if message.role is not MessageRole.SYSTEM and message.id not in existing_ids:
                    await self.sessions.add_message(session_id, message)
            await self.runs.finish(
                run_record,
                status=result.run.status,
                state=result.run.state,
                usage=result.run.usage,
                error=result.run.error,
            )
            duration = time.monotonic() - started
            await self.traces.record_model_events(
                run_id=run_record.run_id,
                provider=self.provider_name,
                model=self.model_name,
                request={
                    "task": prompt,
                    "mode": self.mode.value,
                    "workflow": self.workflow_name,
                    "skill": skill.summary.model_dump(mode="json") if skill is not None else None,
                },
                events=[event.model_dump(mode="json") for event in self._observed_events],
                duration=duration,
                error_type=(
                    None if result.run.status is RunStatus.COMPLETED else result.run.status.value
                ),
            )
            await self.traces.record_usage(
                run_id=run_record.run_id,
                provider=self.provider_name,
                model=self.model_name,
                usage=result.run.usage,
                duration=duration,
            )
            if self.context_builder.last_snapshot is not None:
                snapshot = self.context_builder.last_snapshot
                await self.traces.record_context(
                    run_id=run_record.run_id,
                    snapshot=snapshot.trace_payload(),
                    estimated_tokens=snapshot.estimated_tokens,
                )
            calls = {
                event.call.id: event.call
                for event in self._observed_events
                if isinstance(event, ToolExecutionStarted)
            }
            results = {
                event.result.tool_call_id: event.result
                for event in self._observed_events
                if isinstance(event, ToolExecutionFinished)
            }
            definitions = {item.name: item for item in registry.definitions()}
            for call_id, call in calls.items():
                tool_result = results.get(call_id)
                await self.traces.record_tool_call(
                    run_id=run_record.run_id,
                    call_id=call_id,
                    name=call.name,
                    arguments=call.arguments,
                    result=(
                        tool_result.model_dump(mode="json") if tool_result is not None else None
                    ),
                    risk_level=(
                        definitions[call.name].risk_level.value
                        if call.name in definitions
                        else "unknown"
                    ),
                    status="completed" if tool_result is not None else "interrupted",
                )
            if result.run.status is not RunStatus.COMPLETED:
                await self.query_one("#conversation", VerticalScroll).mount(
                    Static(result.run.error or "运行失败", classes="message-error")
                )
            await self.reload_sessions()
        except Exception as exc:
            self.notify(f"运行错误: {exc}", severity="error")
        finally:
            self.active_runner = None
            self._active_run_record = None
            self.query_one("#run-state", Static).update("空闲")

    async def _observe_agent(self, event: AgentEvent) -> None:
        self._observed_events.append(event)
        if isinstance(event, StateChanged):
            self.query_one("#run-state", Static).update(event.state.value)
        elif isinstance(event, ModelEventObserved) and isinstance(event.event, TextDelta):
            if self.config.models[self.model_name].supports_native_tools:
                self._stream_text += event.event.text
                if self._stream_widget is not None:
                    self._stream_widget.update(self._stream_text)
                    if self.auto_scroll:
                        self.query_one("#conversation", VerticalScroll).scroll_end(animate=False)
        elif isinstance(event, ToolExecutionStarted):
            timeline = self.query_one("#timeline", Static)
            timeline.update(f"▶ {event.call.name}\n" + str(timeline.render()))
            await self.query_one("#conversation", VerticalScroll).mount(
                Collapsible(
                    Static(json.dumps(event.call.arguments, ensure_ascii=False, indent=2)),
                    title=f"工具：{event.call.name}",
                    collapsed=True,
                )
            )
        elif isinstance(event, ToolExecutionFinished):
            symbol = "✓" if event.result.success else "✗"
            self.query_one("#timeline", Static).update(f"{symbol} {event.result.summary}")
        elif isinstance(event, BudgetUpdated):
            marker = "估算" if event.usage.estimated else "精确"
            self.query_one("#usage", Static).update(
                f"Token: {event.usage.total_tokens} ({marker}) · Cost: {event.cost:.6f}"
            )

    async def _observe_hook(self, evaluation: HookEvaluation) -> None:
        await self._observe_agent(HookEvaluated(evaluation=evaluation))

    async def _approve(self, request: ApprovalRequest) -> ApprovalDecision:
        decision = await self.push_screen_wait(ApprovalScreen(request))
        if self._active_run_record is not None:
            await self.traces.record_approval(
                request_id=request.id,
                run_id=self._active_run_record.run_id,
                tool_call_id=request.tool_call.id,
                request=request.model_dump(mode="json"),
                decision=decision.value,
            )
        return decision

    async def _mount_message(self, role: MessageRole, content: str) -> None:
        css_class = "message-user" if role is MessageRole.USER else "message-assistant"
        prefix = "**你**\n\n" if role is MessageRole.USER else "**YF-Harness**\n\n"
        await self.query_one("#conversation", VerticalScroll).mount(
            Markdown(prefix + content, classes=css_class)
        )

    def handle_command(self, command: SlashCommand) -> None:
        handler = getattr(self, f"command_{command.name}")
        handler(command.arguments)

    def command_help(self, _: tuple[str, ...]) -> None:
        self.action_help()

    def command_new(self, _: tuple[str, ...]) -> None:
        self.action_new_session()

    def command_sessions(self, _: tuple[str, ...]) -> None:
        self.action_focus_sessions()

    def command_rename(self, arguments: tuple[str, ...]) -> None:
        if self.current_session_id is None or not arguments:
            self.notify("用法: /rename 新标题", severity="warning")
            return
        self.rename_session(" ".join(arguments))

    @work
    async def rename_session(self, title: str) -> None:
        assert self.current_session_id is not None
        await self.sessions.rename(self.current_session_id, title)
        await self.reload_sessions()

    def command_model(self, arguments: tuple[str, ...]) -> None:
        if not arguments:
            self.notify(f"当前模型: {self.model_name}")
        elif arguments[0] not in self.config.models:
            self.notify("未知模型", severity="error")
        elif self.config.models[arguments[0]].provider != self.provider_name:
            self.notify("模型不属于当前 Provider", severity="error")
        else:
            self.model_name = arguments[0]
            self._update_status_labels()

    def command_provider(self, arguments: tuple[str, ...]) -> None:
        if not arguments:
            self.notify(f"当前 Provider: {self.provider_name}")
        elif arguments[0] not in self.config.providers:
            self.notify("未知 Provider", severity="error")
        else:
            self.provider_name = arguments[0]
            candidates = [
                name for name, model in self.config.models.items() if model.provider == arguments[0]
            ]
            if candidates:
                self.model_name = candidates[0]
            self._update_status_labels()

    def command_mode(self, arguments: tuple[str, ...]) -> None:
        if not arguments:
            self.notify(f"当前模式: {self.mode.value}")
            return
        try:
            self.mode = AgentMode(arguments[0])
        except ValueError:
            self.notify("模式必须是 chat/plan/agent/review", severity="error")
        self._update_status_labels()

    def command_workflow(self, arguments: tuple[str, ...]) -> None:
        if not arguments:
            self.notify(f"当前工作流: {self.workflow_name}")
            return
        if arguments[0] not in self.config.workflows:
            self.notify("未知工作流", severity="error")
            return
        self.workflow_name = arguments[0]
        workflow = self.config.workflow(self.workflow_name)
        self.mode = workflow.mode
        self.policy = workflow.permissions
        self._update_status_labels()

    def command_tools(self, _: tuple[str, ...]) -> None:
        lines = [
            f"- `{item.name}` ({item.risk_level.value}, "
            f"{'只读' if item.read_only else '写入/执行'})"
            for item in self.config.workflow(self.workflow_name).filter_definitions(
                builtin_tools().definitions()
            )
        ]
        self.mount_markdown("## 可用工具\n" + "\n".join(lines))

    def command_skills(self, _: tuple[str, ...]) -> None:
        items = self.skill_catalog.discover()
        if not items:
            self.mount_markdown("## 项目技能\n当前工作区没有发现项目技能。")
            return
        lines = [
            f"- `${item.id}` — {item.description}  \n  `{item.path}`"
            for item in items
            if item.user_invocable
        ]
        self.mount_markdown("## 项目技能\n" + "\n".join(lines))

    def command_skill(self, arguments: tuple[str, ...]) -> None:
        if not arguments:
            self.notify("用法: /skill <source:name> [任务参数]", severity="warning")
            return
        name = arguments[0].lstrip("$")
        task = " ".join(arguments[1:])
        try:
            summary = self.skill_catalog.resolve(name)
        except ValueError as exc:
            self.notify(str(exc), severity="error")
            return
        prompt = task or f"执行项目技能 {summary.id}"
        self.run_prompt(prompt, summary.id, task)

    def command_permissions(self, arguments: tuple[str, ...]) -> None:
        if not arguments:
            self.notify(f"当前审批策略: {self.policy.value}")
            return
        try:
            selected = ApprovalPolicy(arguments[0])
        except ValueError:
            self.notify("审批策略名称无效", severity="error")
            return
        if selected is ApprovalPolicy.FULL_AUTO:
            self.notify("full_auto 默认禁用；请在受控环境中通过配置显式启用。", severity="error")
            return
        self.policy = selected
        self._update_status_labels()

    def command_context(self, _: tuple[str, ...]) -> None:
        self.mount_markdown("## 当前上下文\n```text\n" + self.context_builder.describe() + "\n```")

    def command_add(self, arguments: tuple[str, ...]) -> None:
        if not arguments:
            self.notify("用法: /add <path>", severity="warning")
            return
        try:
            path = self.guard.resolve(arguments[0], must_exist=True)
        except Exception as exc:
            self.notify(str(exc), severity="error")
            return
        relative = self.context_builder.add(self.guard.relative(path))
        self.attached_paths.add(relative)
        self._update_status_labels()
        self.notify(f"已附加 {self.guard.relative(path)}")

    def command_remove(self, arguments: tuple[str, ...]) -> None:
        if not arguments:
            self.notify("用法: /remove <path>", severity="warning")
            return
        self.attached_paths.discard(arguments[0])
        self.context_builder.remove(arguments[0])
        self._update_status_labels()

    def command_compact(self, _: tuple[str, ...]) -> None:
        self.compact_session()

    @work
    async def compact_session(self) -> None:
        if self.current_session_id is None:
            self.notify("当前没有会话", severity="warning")
            return
        messages = await self.sessions.messages(self.current_session_id)
        summary = self.context_builder.manual_compact(messages)
        await self.query_one("#conversation", VerticalScroll).mount(
            Collapsible(
                Markdown(summary.to_markdown()),
                title="上下文压缩摘要",
                collapsed=False,
            )
        )
        self.notify("已生成结构化压缩摘要，后续请求将保留摘要和最近消息。")

    def command_retry(self, _: tuple[str, ...]) -> None:
        if self.last_prompt is None:
            self.notify("没有可重试的输入", severity="warning")
        elif self.active_runner is None:
            self.run_prompt(self.last_prompt)

    def command_stop(self, _: tuple[str, ...]) -> None:
        self.action_cancel_run()

    def command_clear(self, _: tuple[str, ...]) -> None:
        self.clear_conversation()

    @work
    async def clear_conversation(self) -> None:
        await self.query_one("#conversation", VerticalScroll).remove_children()

    def command_undo(self, _: tuple[str, ...]) -> None:
        try:
            self.notify(self.change_journal.undo_last())
        except Exception as exc:
            self.notify(str(exc), severity="warning")

    def command_export(self, arguments: tuple[str, ...]) -> None:
        self.export_session(arguments[0] if arguments else "markdown")

    @work
    async def export_session(self, format: str) -> None:
        if self.current_session_id is None:
            self.notify("当前没有会话", severity="warning")
            return
        content = await self.sessions.export(self.current_session_id, format=format)
        export_dir = database_file().parent / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        suffix = "json" if format == "json" else "md"
        path = export_dir / f"{self.current_session_id}.{suffix}"
        path.write_text(content, encoding="utf-8")
        self.notify(f"已导出 {path}")

    def command_logs(self, _: tuple[str, ...]) -> None:
        self.mount_markdown(f"## 日志与诊断\n日志目录：`{log_dir()}`\n使用 `/doctor` 运行诊断。")

    def command_doctor(self, _: tuple[str, ...]) -> None:
        self.action_doctor()

    def command_quit(self, _: tuple[str, ...]) -> None:
        self.exit()

    def mount_markdown(self, content: str) -> None:
        self.mount_content(Markdown(content, classes="message-assistant"))

    @work
    async def mount_content(self, widget: Widget) -> None:
        await self.query_one("#conversation", VerticalScroll).mount(widget)

    def action_new_session(self) -> None:
        if self.active_runner is not None:
            self.notify("请先停止当前运行", severity="warning")
            return
        self.create_session()

    @work
    async def create_session(self) -> None:
        session = await self.sessions.create(
            title="新会话",
            provider=self.provider_name,
            model=self.model_name,
            mode=self.mode.value,
            workspace=self.guard.root,
        )
        self.current_session_id = session.id
        await self.query_one("#conversation", VerticalScroll).remove_children()
        await self.reload_sessions()
        self.query_one("#prompt", TextArea).focus()

    def action_cancel_run(self) -> None:
        if self.active_runner is None or not self.active_runner.cancel():
            self.notify("当前没有运行中的任务")

    def action_focus_prompt(self) -> None:
        self.query_one("#prompt", TextArea).focus()

    def action_focus_sessions(self) -> None:
        self.query_one("#sessions", ListView).focus()

    def action_cycle_mode(self) -> None:
        modes = list(AgentMode)
        self.mode = modes[(modes.index(self.mode) + 1) % len(modes)]
        self._update_status_labels()
        self.notify(f"模式: {self.mode.value}")

    def action_show_commands(self) -> None:
        self.query_one("#suggestions", Static).update(
            "\n".join(f"/{name} — {description}" for name, description in COMMANDS.items())
        )
        self.action_focus_prompt()

    def action_history_previous(self) -> None:
        if not self.input_history:
            return
        self.history_index = max(0, self.history_index - 1)
        self.query_one("#prompt", TextArea).load_text(self.input_history[self.history_index])

    def action_history_next(self) -> None:
        if not self.input_history:
            return
        self.history_index = min(len(self.input_history), self.history_index + 1)
        value = (
            ""
            if self.history_index == len(self.input_history)
            else self.input_history[self.history_index]
        )
        self.query_one("#prompt", TextArea).load_text(value)

    def action_toggle_auto_scroll(self) -> None:
        self.auto_scroll = not self.auto_scroll
        self.notify(f"自动滚动: {'开启' if self.auto_scroll else '暂停'}")

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_settings(self) -> None:
        self.open_settings()

    @work
    async def open_settings(self) -> None:
        selection = await self.push_screen_wait(
            SettingsScreen(
                self.config,
                provider=self.provider_name,
                model=self.model_name,
                workflow=self.workflow_name,
                mode=self.mode,
                policy=self.policy,
            )
        )
        if isinstance(selection, SettingsSelection):
            self.provider_name = selection.provider
            self.model_name = selection.model
            self.workflow_name = selection.workflow
            self.mode = selection.mode
            self.policy = selection.policy
            self._update_status_labels()

    def action_doctor(self) -> None:
        self.show_doctor()

    @work
    async def show_doctor(self) -> None:
        checks = await run_doctor(self.config, check_network=False)
        lines = [f"- **{check.status.value}** `{check.name}` — {check.message}" for check in checks]
        await self.query_one("#conversation", VerticalScroll).mount(
            Markdown("## Doctor\n" + "\n".join(lines), classes="message-assistant")
        )

    def action_escape(self) -> None:
        self.action_focus_prompt()

    def _update_status_labels(self) -> None:
        self.query_one("#provider-label", Static).update(
            f"Provider: {self.provider_name}\nModel: {self.model_name}\n"
            f"Workflow: {self.workflow_name}\nMode: {self.mode.value}\nPolicy: {self.policy.value}"
        )
        self.query_one("#workspace-status", Static).update(f"Workspace\n{self.guard.root}")
        self.query_one("#context-status", Static).update(f"附件: {len(self.attached_paths)}")

    def on_resize(self) -> None:
        warning = self.query_one("#size-warning", Static)
        warning.display = self.size.width < 55 or self.size.height < 18
        self.query_one("#right-panel", Vertical).display = self.size.width >= 95
        self.query_one("#sidebar", Vertical).display = self.size.width >= 65
